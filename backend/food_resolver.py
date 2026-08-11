from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import httpx
from rapidfuzz import fuzz

# =========================================================================
# LOGGING
# =========================================================================

logger = logging.getLogger("nutrica.food_resolver")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
logger.setLevel(os.environ.get("NUTRICA_LOG_LEVEL", "INFO"))
logger.propagate = False

# =========================================================================
# CONFIG
# =========================================================================

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
USDA_FOOD_URL = "https://api.nal.usda.gov/fdc/v1/food/{fdc_id}"

USDA_API_KEY = os.environ.get(
    "USDA_API_KEY"
)

if not USDA_API_KEY:
    raise RuntimeError(
        "USDA_API_KEY is not configured."
    )

PAGE_SIZE = 10
REQUEST_TIMEOUT_S = 8.0
MAX_RETRIES = 2
RETRY_BACKOFF_BASE_S = 1.5
MAX_CONCURRENT_REQUESTS = 5
MIN_REQUEST_INTERVAL_S = 0.15  # spacing between outbound calls, be polite to USDA

RESOLVED_THRESHOLD = 70.0        # final_score (0-100) at/above this -> "resolved"
LOW_CONFIDENCE_THRESHOLD = 40.0  # below RESOLVED but at/above this -> "resolved_low_confidence"

CACHE_FILE_PATH = os.environ.get("NUTRICA_USDA_CACHE_PATH", "")  # optional disk persistence

# Cache candidate accessibility so the same FDC ID is not validated repeatedly.
_fdc_accessibility_cache: Dict[int, bool] = {}

FUZZY_WEIGHT = 0.75
DB_PRIORITY_WEIGHT = 0.25

# Higher number = higher priority. Applied per the ROUTES/DATABASE PRIORITY spec.
DB_PRIORITY_GENERIC = {
    "Foundation": 100.0,
    "SR Legacy": 80.0,
    "Survey (FNDDS)": 60.0,
    "Experimental": 40.0,
    "Branded": 20.0,
}

DB_PRIORITY_BRANDED = {
    "Branded": 100.0,
    "Foundation": 80.0,
    "SR Legacy": 60.0,
    "Survey (FNDDS)": 40.0,
    "Experimental": 20.0,
}

# Ordinal priority order, derived from the score tables above (both tables
# were already defined in priority order, so this just reads that order
# out explicitly for use as a hard sort key - see rank_candidates()).
# Lower index = higher priority.
_DB_PRIORITY_ORDER_GENERIC = list(DB_PRIORITY_GENERIC.keys())
_DB_PRIORITY_ORDER_BRANDED = list(DB_PRIORITY_BRANDED.keys())

# Candidates whose description contains one of these terms are rejected
# outright - before scoring - unless the search query itself contains that
# term too. This stops a plain ingredient query like "Onion" from ever
# being satisfied by a compound/prepared dish that merely contains onion
# as a sub-ingredient (e.g. "Bread, onion", "Onion soup", "Onion dip").
# Fuzzy matching alone cannot make this distinction: a bare single-word
# query is, by definition, a subset of every one of these candidates too,
# so it can and does score deceptively high on token_set_ratio.
CANDIDATE_REJECT_TERMS = [
    "bread", "burger", "pizza", "soup", "dip", "sandwich", "cracker",
    "frozen meal", "prepared meal", "salad", "casserole", "lasagna",
    "pasta dish", "mixed dish", "meal kit", "snack",
]
_CANDIDATE_REJECT_PATTERNS = [
    (term, re.compile(rf"\b{re.escape(term)}\b")) for term in CANDIDATE_REJECT_TERMS
]


class ResolverStatus:
    RESOLVED = "resolved"
    LOW_CONFIDENCE = "resolved_low_confidence"
    NOT_FOUND = "not_found"
    SKIPPED_NUTRITION_LABEL = "skipped_nutrition_label"
    ERROR = "error"


# =========================================================================
# CACHE
# =========================================================================

class SearchCache:
    """
    Async-safe cache for raw USDA search results, keyed by normalized query
    string. Every call to search_food() is cached, so repeated queries
    (e.g. "Garlic powder" showing up across ten different dishes) never hit
    the network twice. Optionally persists to disk so the cache survives
    process restarts, which matters on Render's free tier where instances
    spin down and cold-start frequently.
    """

    def __init__(self, disk_path: str = ""):
        self._store: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
        self._disk_path = disk_path
        if self._disk_path and os.path.exists(self._disk_path):
            try:
                with open(self._disk_path, "r", encoding="utf-8") as f:
                    self._store = json.load(f)
                logger.info(
                    "Loaded %d cached USDA queries from %s",
                    len(self._store),
                    self._disk_path,
                )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Could not load USDA cache file %s: %s", self._disk_path, exc
                )
                self._store = {}

    @staticmethod
    def _normalize(query: str) -> str:
        return re.sub(r"\s+", " ", (query or "").strip().lower())

    async def get(self, query: str) -> Optional[List[Dict[str, Any]]]:
        key = self._normalize(query)
        async with self._lock:
            return self._store.get(key)

    async def set(self, query: str, results: List[Dict[str, Any]]) -> None:
        key = self._normalize(query)
        async with self._lock:
            self._store[key] = results
            if self._disk_path:
                try:
                    with open(self._disk_path, "w", encoding="utf-8") as f:
                        json.dump(self._store, f)
                except OSError as exc:
                    logger.warning(
                        "Could not persist USDA cache to %s: %s", self._disk_path, exc
                    )

    def stats(self) -> Dict[str, int]:
        return {"cached_queries": len(self._store)}


_cache = SearchCache(CACHE_FILE_PATH)
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
_throttle_lock = asyncio.Lock()
_last_request_time = 0.0


async def _throttle() -> None:
    """Keep a minimum spacing between outbound USDA requests."""
    global _last_request_time
    async with _throttle_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < MIN_REQUEST_INTERVAL_S:
            await asyncio.sleep(MIN_REQUEST_INTERVAL_S - elapsed)
        _last_request_time = time.monotonic()


# =========================================================================
# SEARCH
# =========================================================================

async def search_food(
    query: str,
    client: httpx.AsyncClient,
    page_size: int = PAGE_SIZE,
) -> List[Dict[str, Any]]:
    """
    Search USDA FoodData Central.

    Returns an empty list when the query is rejected, no food is
    found, or all temporary retries fail. A single failed lookup
    must not terminate the complete meal analysis.
    """

    original_query = str(
        query or ""
    ).strip()

    query = sanitize_usda_query(
        original_query
    )

    if not query:
        return []

    cached = await _cache.get(query)

    if cached is not None:
        logger.debug(
            "Cache hit for query %r",
            query,
        )
        return cached

    params = {
        "api_key": USDA_API_KEY,
        "query": query,
        "pageSize": page_size,
    }

    last_exc: Optional[Exception] = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            async with _semaphore:
                await _throttle()

                response = await client.get(
                    USDA_SEARCH_URL,
                    params=params,
                    timeout=REQUEST_TIMEOUT_S,
                )

            if response.status_code == 400:
                logger.warning(
                    "USDA rejected search query %r "
                    "(original query: %r).",
                    query,
                    original_query,
                )

                # Do not retry the same rejected request.
                return []

            if response.status_code in {
                401,
                403,
            }:
                logger.error(
                    "USDA rejected the API credentials "
                    "with status %s.",
                    response.status_code,
                )

                # Retrying cannot fix an invalid or disabled key.
                return []

            if response.status_code == 404:
                logger.warning(
                    "USDA search endpoint returned 404 "
                    "for query %r.",
                    query,
                )
                return []

            if response.status_code == 429:
                wait = (
                    RETRY_BACKOFF_BASE_S
                    * attempt
                    * 2
                )

                logger.warning(
                    "USDA rate limit hit for %r. "
                    "Backing off %.1f seconds.",
                    query,
                    wait,
                )

                if attempt < MAX_RETRIES:
                    await asyncio.sleep(wait)

                continue

            if response.status_code >= 500:
                logger.warning(
                    "USDA server error %s "
                    "(attempt %d/%d) for %r.",
                    response.status_code,
                    attempt,
                    MAX_RETRIES,
                    query,
                )

                if attempt < MAX_RETRIES:
                    await asyncio.sleep(
                        RETRY_BACKOFF_BASE_S
                        * attempt
                    )

                continue

            response.raise_for_status()

            data = response.json()

            foods = (
                data.get("foods", [])
                if isinstance(data, dict)
                else []
            )

            if not isinstance(foods, list):
                foods = []

            logger.debug(
                "USDA search %r returned %d candidates.",
                query,
                len(foods),
            )

            await _cache.set(
                query,
                foods,
            )

            return foods

        except httpx.TimeoutException as exc:
            last_exc = exc

            logger.warning(
                "USDA search timeout "
                "(attempt %d/%d) for %r.",
                attempt,
                MAX_RETRIES,
                query,
            )

        except httpx.HTTPStatusError as exc:
            last_exc = exc

            status_code = (
                exc.response.status_code
            )

            logger.warning(
                "USDA search HTTP error %s "
                "(attempt %d/%d) for %r.",
                status_code,
                attempt,
                MAX_RETRIES,
                query,
            )

            # Any client-side rejection except 429 should
            # not be retried unchanged.
            if (
                400 <= status_code < 500
                and status_code != 429
            ):
                return []

        except (
            httpx.RequestError,
            json.JSONDecodeError,
        ) as exc:
            last_exc = exc

            logger.warning(
                "USDA search failed "
                "(attempt %d/%d) for %r: %s",
                attempt,
                MAX_RETRIES,
                query,
                exc,
            )

        if attempt < MAX_RETRIES:
            await asyncio.sleep(
                RETRY_BACKOFF_BASE_S
                * attempt
            )

    logger.error(
        "USDA search exhausted retries "
        "for %r: %s",
        query,
        last_exc,
    )

    return []
def sanitize_usda_query(
    query: str,
) -> str:
    """
    Simplify AI-generated USDA search text.

    Removes punctuation and bracketed alternative names that
    occasionally produce rejected or unnecessarily specific
    FoodData Central searches.
    """

    cleaned = str(
        query or ""
    ).strip()

    if not cleaned:
        return ""

    # Example:
    # "Coriander (cilantro) leaves, raw"
    # becomes:
    # "Coriander leaves raw"
    cleaned = re.sub(
        r"\([^)]*\)",
        " ",
        cleaned,
    )

    cleaned = re.sub(
        r"[,;/\\|]+",
        " ",
        cleaned,
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    )

    return cleaned.strip()

# =========================================================================
# RANKING / MATCHING
# =========================================================================

def _normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fuzzy_score(query: str, candidate_description: str) -> float:
    """
    Combine three RapidFuzz metrics into a single 0-100 fuzzy score.

    - token_set_ratio: most forgiving of extra/missing words. USDA
      descriptions are often longer and more detailed than the query
      (e.g. "Pizza, cheese, regular crust, frozen, cooked" vs "Cheese
      pizza"), so this carries the most weight.
    - token_sort_ratio: rewards matching word content regardless of order.
    - partial_ratio: catches cases where the query is effectively a clean
      substring of a longer USDA description.
    """
    q = _normalize_text(query)
    c = _normalize_text(candidate_description)
    if not q or not c:
        return 0.0

    tser = fuzz.token_set_ratio(q, c)
    tsr = fuzz.token_sort_ratio(q, c)
    pr = fuzz.partial_ratio(q, c)

    combined = (0.45 * tser) + (0.35 * tsr) + (0.20 * pr)
    return round(combined, 2)


def _db_priority_score(data_type: str, food_source: str) -> float:
    table = DB_PRIORITY_BRANDED if food_source == "Branded" else DB_PRIORITY_GENERIC
    return table.get(data_type, 10.0)  # unrecognized data types get low nonzero priority


_GENERIC_QUERY_WORDS = {
    "raw",
    "cooked",
    "boiled",
    "fried",
    "baked",
    "roasted",
    "fresh",
    "prepared",
    "food",
    "dish",
    "with",
    "without",
    "and",
    "or",
    "the",
}


def _meaningful_tokens(
    text: str,
) -> set[str]:
    """
    Extract words that identify the actual food.

    Preparation words are excluded because missing "raw" or
    "cooked" should not be treated the same as missing "mint",
    "paneer", "chicken", etc.
    """

    normalized = _normalize_text(text)

    return {
        token
        for token in normalized.split()
        if (
            len(token) > 2
            and token not in _GENERIC_QUERY_WORDS
        )
    }


def _query_token_coverage(
    query: str,
    candidate_description: str,
) -> float:
    """
    Return the fraction of meaningful query words present
    in the USDA candidate.
    """

    query_tokens = _meaningful_tokens(query)
    candidate_tokens = _meaningful_tokens(
        candidate_description
    )

    if not query_tokens:
        return 1.0

    matched = (
        query_tokens
        & candidate_tokens
    )

    return len(matched) / len(query_tokens)


def rank_candidates(
    query: str,
    candidates: List[Dict[str, Any]],
    food_source: str = "Generic",
) -> List[Dict[str, Any]]:
    """
    Rank USDA candidates while preserving food specificity.

    A broad candidate that omits a distinguishing query word
    must not outrank a more specific candidate merely because
    it shares one generic food term.
    """

    ranked: List[Dict[str, Any]] = []

    normalized_query = _normalize_text(query)
    query_tokens = _meaningful_tokens(query)

    for candidate in candidates:
        description = (
            candidate.get("description")
            or ""
        )

        data_type = (
            candidate.get("dataType")
            or "Unknown"
        )

        fdc_id = candidate.get("fdcId")

        if fdc_id is None or not description:
            continue

        normalized_description = (
            _normalize_text(description)
        )

        description_tokens = (
            _meaningful_tokens(description)
        )

        fuzzy = _fuzzy_score(
            query,
            description,
        )

        db_priority = _db_priority_score(
            data_type,
            food_source,
        )

        token_coverage = (
            _query_token_coverage(
                query,
                description,
            )
        )

        missing_tokens = sorted(
            query_tokens
            - description_tokens
        )

        # Strongly penalize candidates that discard
        # distinctive food-identifying terms.
        specificity_penalty = (
            1.0 - token_coverage
        ) * 45.0

        # Reward an exact normalized phrase match.
        exact_match_bonus = (
            10.0
            if normalized_query
            == normalized_description
            else 0.0
        )

        final_score = (
            FUZZY_WEIGHT * fuzzy
            + DB_PRIORITY_WEIGHT * db_priority
            + exact_match_bonus
            - specificity_penalty
        )

        # If a multi-word food loses half or more of its
        # identifying terms, it cannot be called resolved.
        if (
            len(query_tokens) >= 2
            and token_coverage < 0.67
        ):
            final_score = min(
                final_score,
                LOW_CONFIDENCE_THRESHOLD - 0.01,
            )

        final_score = round(
            max(0.0, min(100.0, final_score)),
            2,
        )

        brand_owner = (
            candidate.get("brandOwner")
            or candidate.get("brandName")
        )

        matched_name = (
            description
            if not brand_owner
            else (
                f"{description} "
                f"({brand_owner})"
            )
        )

        ranked.append(
            {
                "fdc_id": fdc_id,
                "matched_name": matched_name,
                "data_type": data_type,
                "fuzzy_score": fuzzy,
                "db_priority_score": (
                    db_priority
                ),
                "query_token_coverage": round(
                    token_coverage,
                    4,
                ),
                "missing_query_tokens": (
                    missing_tokens
                ),
                "final_score": final_score,
            }
        )

    ranked.sort(
        key=lambda candidate: (
            candidate[
                "query_token_coverage"
            ],
            candidate["final_score"],
        ),
        reverse=True,
    )

    return ranked


# =========================================================================
# RESOLUTION
# =========================================================================


async def _candidate_is_accessible(
    client: httpx.AsyncClient,
    fdc_id: Any,
) -> bool:
    """Verify that a USDA search candidate can actually be fetched by the
    Food Details endpoint.

    FoodData Central can retain a browser-facing page for an older FDC ID
    while the API detail endpoint no longer serves that exact record. Search
    candidates that cannot be fetched must never be accepted as resolved,
    otherwise nutrient_profile receives an FDC ID that produces a 404 and the
    food silently loses its nutrient profile.
    """
    try:
        numeric_id = int(fdc_id)
    except (TypeError, ValueError):
        return False

    cached = _fdc_accessibility_cache.get(numeric_id)
    if cached is not None:
        return cached

    url = USDA_FOOD_URL.format(fdc_id=numeric_id)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with _fetch_semaphore:
                await _throttle_fetch()
                response = await client.get(
                    url,
                    params={"api_key": USDA_API_KEY},
                    timeout=REQUEST_TIMEOUT_S,
                )

            if response.status_code == 200:
                _fdc_accessibility_cache[numeric_id] = True
                return True

            if response.status_code == 404:
                logger.warning(
                    "Rejecting stale/unavailable USDA candidate fdcId=%s "
                    "because Food Details returned 404.",
                    numeric_id,
                )
                _fdc_accessibility_cache[numeric_id] = False
                return False

            if response.status_code == 429:
                wait = RETRY_BACKOFF_BASE_S * attempt * 2
                logger.warning(
                    "USDA rate limit while validating fdcId=%s; "
                    "retrying in %.1fs.",
                    numeric_id,
                    wait,
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(wait)
                continue

            if response.status_code >= 500:
                logger.warning(
                    "USDA server error %s while validating fdcId=%s "
                    "(attempt %d/%d).",
                    response.status_code,
                    numeric_id,
                    attempt,
                    MAX_RETRIES,
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_BACKOFF_BASE_S * attempt)
                continue

            # Authentication/configuration errors are not evidence that the
            # food itself is invalid. Surface the problem rather than caching
            # the candidate as permanently unavailable.
            response.raise_for_status()

        except httpx.TimeoutException:
            logger.warning(
                "Timeout validating USDA fdcId=%s (attempt %d/%d).",
                numeric_id,
                attempt,
                MAX_RETRIES,
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "USDA validation HTTP %s for fdcId=%s.",
                exc.response.status_code,
                numeric_id,
            )
            return False
        except httpx.RequestError as exc:
            logger.warning(
                "USDA validation request failed for fdcId=%s "
                "(attempt %d/%d): %s",
                numeric_id,
                attempt,
                MAX_RETRIES,
                exc,
            )

        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_BACKOFF_BASE_S * attempt)

    # A transient outage must not be cached as a permanent invalid ID.
    return False


async def _first_accessible_candidate(
    client: httpx.AsyncClient,
    ranked: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return the highest-ranked candidate whose Food Details record is
    retrievable. If a search result points to a stale 404 ID, continue to the
    next ranked candidate instead of poisoning the nutrient stage."""
    for candidate in ranked:
        fdc_id = candidate.get("fdc_id")
        if fdc_id is None:
            continue
        if await _candidate_is_accessible(client, fdc_id):
            return candidate
    return None


async def _resolve_single(
    client: httpx.AsyncClient,
    primary_query: Optional[str],
    fallback_queries: List[str],
    food_source: str = "Generic",
) -> Dict[str, Any]:
    """
    Shared resolution routine used by every route.

    Tries primary_query first (usda_food_description, or an ingredient/spice
    name), then each fallback query in order (possible_usda_queries). Keeps
    the best candidate seen across all attempts, and stops early the moment
    a high-confidence match is found so we don't burn extra API calls.
    """

    # print("=" * 80)
    # print("PRIMARY :", primary_query)
    # print("FALLBACKS :", fallback_queries)

    queries_to_try: List[str] = []
    seen_queries: set[str] = set()
    
    raw_queries = [
        primary_query,
        *fallback_queries,
    ]
    
    for raw_query in raw_queries:
        cleaned_query = sanitize_usda_query(
            raw_query or ""
        )
    
        if not cleaned_query:
            continue
    
        normalized_query = (
            cleaned_query.lower()
        )
    
        if normalized_query in seen_queries:
            continue
    
        seen_queries.add(
            normalized_query
        )
    
        queries_to_try.append(
            cleaned_query
        )

    MAX_QUERIES_PER_ENTRY = 3

    queries_to_try = (
        queries_to_try[
            :MAX_QUERIES_PER_ENTRY
        ]
    )
    
    if not queries_to_try:
        return {
            "status": ResolverStatus.ERROR,
            "fdc_id": None,
            "matched_name": None,
            "data_type": None,
            "match_query": None,
            "match_score": 0.0,
            "error": "no searchable query available",
        }

    best: Optional[Dict[str, Any]] = None
    best_query: Optional[str] = None

    for q in queries_to_try:
        try:
            raw_candidates = await search_food(q, client)
        except Exception as exc:  # never let one bad query take down the whole meal
            logger.error("Unexpected error searching %r: %s", q, exc)
            raw_candidates = []

        ranked = rank_candidates(q, raw_candidates, food_source)
        if ranked:
            top = await _first_accessible_candidate(client, ranked)
            if top is None:
                logger.warning(
                    "USDA search %r returned ranked candidates, but none "
                    "could be retrieved from Food Details.",
                    q,
                )
                continue

            if best is None or top["final_score"] > best["final_score"]:
                best = top
                best_query = q
            if (
                top["final_score"]
                >= RESOLVED_THRESHOLD
                and top.get(
                    "query_token_coverage",
                    0.0,
                )
                >= 0.67
            ):
                break
    if best is None:
        return {
            "status": ResolverStatus.NOT_FOUND,
            "fdc_id": None,
            "matched_name": None,
            "data_type": None,
            "match_query": queries_to_try[0],
            "match_score": 0.0,
        }

    coverage = best.get(
        "query_token_coverage",
        0.0,
    )
    
    if (
        best["final_score"]
        >= RESOLVED_THRESHOLD
        and coverage >= 0.67
    ):
        status = ResolverStatus.RESOLVED
    
    elif (
        best["final_score"]
        >= LOW_CONFIDENCE_THRESHOLD
        and coverage >= 0.67
    ):
        status = ResolverStatus.LOW_CONFIDENCE
    
    else:
        status = ResolverStatus.NOT_FOUND

    found = status != ResolverStatus.NOT_FOUND
    return {
        "status": status,
        "fdc_id": best["fdc_id"] if found else None,
        "matched_name": best["matched_name"] if found else None,
        "data_type": best["data_type"] if found else None,
        "match_query": best_query,
        "match_score": round(best["final_score"] / 100.0, 4),
    }


async def resolve_food(client: httpx.AsyncClient, food: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the FDC ID for a top-level food (DIRECT_USDA route, or the
    parent dish itself under DECOMPOSE)."""
    primary = food.get("usda_food_description")
    fallbacks = list(food.get("possible_usda_queries") or [])
    if not primary and not fallbacks:
        fallbacks = [food.get("name", "")]
    food_source = food.get("food_source") or "Generic"
    return await _resolve_single(client, primary, fallbacks, food_source)


async def resolve_ingredient(
    client: httpx.AsyncClient,
    ingredient: Dict[str, Any]
) -> Dict[str, Any]:
    """Resolve the FDC ID for a single ingredient of a DECOMPOSE dish."""

    primary = ingredient.get("usda_food_description")
    fallbacks = list(ingredient.get("possible_usda_queries") or [])

    if not primary and not fallbacks:
        fallbacks = [
            ingredient.get("canonical_name")
            or ingredient.get("name", "")
        ]

    return await _resolve_single(
        client,
        primary,
        fallbacks,
        food_source="Generic"
    )


async def resolve_spice(
    client: httpx.AsyncClient,
    spice: Dict[str, Any]
) -> Dict[str, Any]:
    """Resolve the FDC ID for a single spice of a DECOMPOSE dish."""

    primary = spice.get("usda_food_description")
    fallbacks = list(spice.get("possible_usda_queries") or [])

    if not primary and not fallbacks:
        fallbacks = [spice.get("name", "")]

    return await _resolve_single(
        client,
        primary,
        fallbacks,
        food_source="Generic"
    )


async def _empty_list() -> List[Any]:
    return []


async def _resolve_one_food(client: httpx.AsyncClient, food: Dict[str, Any]) -> None:
    """Mutates `food` in place, attaching a 'resolver' block per its analysis_route."""
    route = food.get("analysis_route", "DIRECT_USDA")
    name = food.get("name", "<unnamed food>")

    if route == "NUTRITION_LABEL":
        food["resolver"] = {
            "status": ResolverStatus.SKIPPED_NUTRITION_LABEL,
            "fdc_id": None,
            "matched_name": None,
            "data_type": None,
            "match_query": None,
            "match_score": None,
            "note": "Nutrition sourced directly from product label OCR; USDA lookup skipped.",
        }
        return

    if route == "DIRECT_USDA":
        food["resolver"] = await resolve_food(client, food)
        return

    if route == "DECOMPOSE":
        ingredients = (
            food.get("ingredients")
            or []
        )
    
        spices = (
            food.get("spices")
            or []
        )
    
        # A DECOMPOSE parent is an aggregation object.
        # Its nutrients are calculated from its ingredients
        # and spices, not from a complete-dish USDA match.
        food["resolver"] = {
            "status": "resolved_from_components",
            "fdc_id": None,
            "matched_name": None,
            "data_type": None,
            "match_query": None,
            "match_score": None,
            "note": (
                "Parent nutrition is calculated from "
                "resolved ingredients and spices."
            ),
        }
    
        ingredients_task = (
            asyncio.gather(
                *[
                    resolve_ingredient(
                        client,
                        ingredient,
                    )
                    for ingredient in ingredients
                ]
            )
            if ingredients
            else _empty_list()
        )
    
        spices_task = (
            asyncio.gather(
                *[
                    resolve_spice(
                        client,
                        spice,
                    )
                    for spice in spices
                ]
            )
            if spices
            else _empty_list()
        )
    
        (
            ingredient_results,
            spice_results,
        ) = await asyncio.gather(
            ingredients_task,
            spices_task,
        )
    
        for ingredient, resolver in zip(
            ingredients,
            ingredient_results,
        ):
            ingredient["resolver"] = resolver
    
        for spice, resolver in zip(
            spices,
            spice_results,
        ):
            spice["resolver"] = resolver
    
        return
        
    logger.warning(
        "Unknown analysis_route %r for food %r; defaulting to DIRECT_USDA", route, name
    )
    food["resolver"] = await resolve_food(client, food)


async def resolve_meal(
    analysis_result: Dict[str, Any],
) -> Dict[str, Any]:
    """    
    Main entry point.

    Takes the full Gemini meal-analysis JSON and returns a deep copy
    annotated with a "resolver" block on every food, ingredient, and spice
    that requires a USDA lookup. The input dict is never mutated.

    All foods in the meal are resolved concurrently (bounded by
    MAX_CONCURRENT_REQUESTS at the HTTP layer), so a meal with a dozen
    detected foods and ingredients doesn't resolve serially.

    This is an async function. In a plain script, FastAPI endpoint, or
    Celery task, call it with `asyncio.run(resolve_meal(...))` or
    `resolve_meal_sync(...)`. In a Colab/Jupyter cell, use top-level
    `await resolve_meal(...)` directly - see the module docstring.
    """
    if not isinstance(analysis_result, dict):
        raise ValueError(
            "Analysis result must be a dictionary."
        )

    status = analysis_result.get(
        "status",
        "completed",
    )

    if status == "waiting_for_back_label":
        raise ValueError(
            "Food resolution cannot begin until all "
            "required nutrition labels are uploaded."
        )

    if status == "no_food_detected":
        return copy.deepcopy(
            analysis_result
        )

    if status != "completed":
        raise ValueError(
            f"Unsupported analysis status: {status}"
        )

    if "meal" not in analysis_result:
        raise ValueError(
            "Analysis result must contain a "
            "top-level 'meal' key."
        )

    result = copy.deepcopy(
        analysis_result
    )

    foods = result.get("meal", {}).get("foods", []) or []

    if not USDA_API_KEY or USDA_API_KEY == "DEMO_KEY":
        logger.warning(
            "USDA_API_KEY is not set (using public DEMO_KEY, ~30 req/hr limit). "
            "Set the USDA_API_KEY environment variable for production use."
        )

    async with httpx.AsyncClient(headers={"User-Agent": "Nutrica-FoodResolver/1.0"}) as client:
        await asyncio.gather(*[_resolve_one_food(client, food) for food in foods])

    return result


def resolve_meal_sync(
    analysis_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Synchronous convenience wrapper around resolve_meal().

    Use this function only from synchronous Python code.

    In FastAPI async endpoints, call:

        await resolve_meal(analysis_result)

    instead.
    """

    try:
        asyncio.get_running_loop()

    except RuntimeError:
        return asyncio.run(
            resolve_meal(
                analysis_result
            )
        )

    raise RuntimeError(
        "resolve_meal_sync() cannot be called from "
        "inside a running event loop. Use "
        "`await resolve_meal(analysis_result)` instead."
    )
