from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from usda_detail_cache import get_food_detail, set_food_detail

USDA_API_KEY = os.getenv("USDA_API_KEY", "DEMO_KEY")
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
USDA_FOOD_URL = "https://api.nal.usda.gov/fdc/v1/food/{fdc_id}"
DETAIL_TIMEOUT_SECONDS = 12.0
DETAIL_MAX_RETRIES = 2
DETAIL_CONCURRENCY = 6
CACHE_TTL_SECONDS = 15 * 60
MAX_CACHE_ITEMS = 250

_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_cache_lock = asyncio.Lock()
_detail_cache: dict[int, dict[str, Any] | None] = {}
_detail_cache_lock = asyncio.Lock()
_detail_semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)

_DATA_TYPE_SCORE = {
    "Foundation": 100,
    "SR Legacy": 82,
    "Survey (FNDDS)": 62,
    "Branded": 18,
}

PREFERRED_GENERIC_DATA_TYPES = [
    "Foundation",
    "SR Legacy",
    "Survey (FNDDS)",
]

_PREPARATION_TERMS = {
    "raw", "fresh", "cooked", "boiled", "fried", "baked", "roasted",
    "frozen", "dried", "dry", "sweetened", "unsweetened", "canned",
    "drained", "pasteurized", "powder", "ground", "whole", "sliced",
    "chopped", "prepared",
}

# Strong clues that a result is a compound/product rather than the ingredient
# itself. These are penalties only; they are not hard rejections because a
# user may genuinely search for one of these prepared foods.
_COMPOUND_TERMS = {
    "pudding", "pastry", "granola", "cereal", "babyfood", "bar", "snack",
    "cookie", "cake", "pie", "muffin", "bread", "sauce", "soup", "dip",
    "sandwich", "pizza", "casserole", "meal", "mix", "filling",
}


def _clean_query(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9\s\-']+", " ", value or "")
    return re.sub(r"\s+", " ", value).strip()


def _tokens(value: str) -> list[str]:
    return [token for token in re.split(r"\W+", value.lower()) if token]


def _canonical_token(token: str) -> str:
    token = token.lower().strip()
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _token_matches(query_token: str, candidate_token: str) -> bool:
    q = _canonical_token(query_token)
    c = _canonical_token(candidate_token)
    if q == c:
        return True
    # Supports type-ahead searches such as "blueberr" -> "blueberries".
    if len(q) >= 4 and c.startswith(q):
        return True
    if len(c) >= 4 and q.startswith(c) and len(q) - len(c) <= 2:
        return True
    return False


def _ordered_identity_match(query: str, description: str) -> tuple[int, float]:
    """Return (identity tier, token coverage).

    Tier 5: exact normalized description.
    Tier 4: the description begins with the queried food identity.
    Tier 3: all query identity tokens occur very early in the description.
    Tier 2: all query identity tokens occur, but only later in a compound food.
    Tier 1: partial token coverage.
    """
    q_tokens = [t for t in _tokens(query) if t not in _PREPARATION_TERMS]
    d_tokens = _tokens(description)
    if not q_tokens or not d_tokens:
        return (0, 0.0)

    matched_indices: list[int] = []
    for q in q_tokens:
        idx = next((i for i, d in enumerate(d_tokens) if _token_matches(q, d)), None)
        if idx is not None:
            matched_indices.append(idx)

    coverage = len(matched_indices) / len(q_tokens)
    normalized_q = " ".join(_canonical_token(t) for t in _tokens(query))
    normalized_d = " ".join(_canonical_token(t) for t in d_tokens)
    if normalized_q == normalized_d:
        return (5, coverage)

    if coverage == 1.0:
        # All identity words must occupy the beginning of the USDA description
        # to be considered the food itself. "Egg, yolk, raw" satisfies this;
        # "Pudding ... egg yolk" does not.
        early_limit = max(2, len(q_tokens) + 1)
        if max(matched_indices) < early_limit and min(matched_indices) <= 1:
            return (4, coverage)
        if max(matched_indices) < 5:
            return (3, coverage)
        return (2, coverage)
    if coverage > 0:
        return (1, coverage)
    return (0, 0.0)


def _preparation_score(query: str, description: str) -> float:
    q = {_canonical_token(t) for t in _tokens(query) if t in _PREPARATION_TERMS}
    if not q:
        # For an unqualified whole-food search, the least altered form is the
        # safest nutrition default. Users can still request cooked/frozen/etc.
        d = {_canonical_token(t) for t in _tokens(description)}
        if "sweetened" in d or "syrup" in d:
            return -1.0
        if "raw" in d or "fresh" in d:
            return 0.35
        if "unsweetened" in d:
            return 0.15
        return 0.0
    d = {_canonical_token(t) for t in _tokens(description)}
    matched = len(q & d)
    return matched / len(q)


def _looks_brand_specific(query: str, brand_owner: str) -> bool:
    if not brand_owner:
        return False
    q_tokens = {_canonical_token(t) for t in _tokens(query)}
    brand_tokens = {_canonical_token(t) for t in _tokens(brand_owner) if len(t) > 2}
    return bool(q_tokens & brand_tokens)


def _candidate_score(candidate: dict[str, Any], query: str) -> tuple:
    description = str(candidate.get("description") or "")
    data_type = str(candidate.get("dataType") or "")
    brand_owner = str(candidate.get("brandOwner") or candidate.get("brandName") or "")

    identity_tier, coverage = _ordered_identity_match(query, description)
    prep_score = _preparation_score(query, description)
    source_score = float(_DATA_TYPE_SCORE.get(data_type, 0))

    d_tokens = _tokens(description)
    q_tokens = _tokens(query)
    extra_tokens = max(0, len(d_tokens) - len(q_tokens))
    compound_count = sum(1 for token in d_tokens if token in _COMPOUND_TERMS)

    # Generic ingredient searches should almost never surface branded products
    # above an equivalent Foundation/SR record. A brand-specific query can opt
    # back into branded priority naturally.
    branded_penalty = 0.0
    brand_specific = _looks_brand_specific(query, brand_owner)
    if data_type == "Branded" and not brand_specific:
        branded_penalty = 55.0

    # Source intent is the first sort key. Numeric penalties cannot enforce a
    # policy if identity_tier is compared before them.
    if data_type == "Branded":
        source_policy_tier = 3 if brand_specific else 1
    else:
        source_policy_tier = 2

    compound_penalty = compound_count * 16.0
    verbosity_penalty = min(18.0, extra_tokens * 0.65)

    # Sort tuple intentionally reflects product policy:
    # source intent -> least-altered/requested preparation -> identity
    # relevance -> source quality -> cleanup.
    cleanup_score = -(branded_penalty + compound_penalty + verbosity_penalty)
    return (
        source_policy_tier,
        round(prep_score, 4),
        identity_tier,
        round(coverage, 4),
        source_score,
        cleanup_score,
    )


def _display_name(description: str) -> str:
    # USDA descriptions are useful but can be visually noisy. Preserve meaning,
    # normalize whitespace, and sentence-case only when the source is all caps.
    value = re.sub(r"\s+", " ", description).strip()
    if value.isupper():
        value = value.title()
    return value


def _normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
    fdc_id = candidate.get("fdcId")
    description = str(candidate.get("description") or "").strip()
    if not isinstance(fdc_id, int) or not description:
        return None
    return {
        "fdc_id": fdc_id,
        "description": description,
        "display_name": _display_name(description),
        "data_type": str(candidate.get("dataType") or "Unknown"),
        "food_category": str(candidate.get("foodCategory") or "").strip() or None,
        "brand_owner": str(candidate.get("brandOwner") or candidate.get("brandName") or "").strip() or None,
    }



async def get_usda_food_detail(
    fdc_id: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Return a USDA Food Details record when the API can retrieve it.

    A browser-facing FoodData Central page can remain visible even when the
    Food Details API returns 404 for that historical FDC ID. Quinone must use
    the API record as the source of truth because nutrient_profile consumes
    the same endpoint.
    """
    try:
        numeric_id = int(fdc_id)
    except (TypeError, ValueError):
        return None

    shared = get_food_detail(numeric_id)
    if shared is not None:
        return shared

    async with _detail_cache_lock:
        if numeric_id in _detail_cache:
            return _detail_cache[numeric_id]

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=httpx.Timeout(DETAIL_TIMEOUT_SECONDS))

    try:
        url = USDA_FOOD_URL.format(fdc_id=numeric_id)
        for attempt in range(1, DETAIL_MAX_RETRIES + 1):
            try:
                async with _detail_semaphore:
                    response = await client.get(
                        url,
                        params={"api_key": USDA_API_KEY},
                    )

                if response.status_code == 200:
                    body = response.json()
                    if isinstance(body, dict):
                        set_food_detail(numeric_id, body)
                        async with _detail_cache_lock:
                            _detail_cache[numeric_id] = body
                        return body
                    return None

                if response.status_code == 404:
                    async with _detail_cache_lock:
                        _detail_cache[numeric_id] = None
                    return None

                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < DETAIL_MAX_RETRIES:
                        await asyncio.sleep(0.45 * attempt)
                        continue
                    return None

                response.raise_for_status()
            except (httpx.TimeoutException, httpx.RequestError):
                if attempt < DETAIL_MAX_RETRIES:
                    await asyncio.sleep(0.45 * attempt)
                    continue
                return None
            except (ValueError, httpx.HTTPStatusError):
                return None
        return None
    finally:
        if owns_client:
            await client.aclose()


async def _candidate_is_usable(
    candidate: dict[str, Any],
    *,
    client: httpx.AsyncClient,
) -> bool:
    fdc_id = candidate.get("fdc_id")
    if not isinstance(fdc_id, int):
        return False
    return await get_usda_food_detail(fdc_id, client=client) is not None


async def validate_or_recover_usda_food(
    *,
    fdc_id: int,
    name: str,
    description: str,
    data_type: str | None = None,
    food_category: str | None = None,
) -> dict[str, Any]:
    """Validate an already-selected FDC ID and recover it if it became stale.

    This is intentionally called again at Analyze time. It protects:
    - saved recipes created before this fix,
    - photo-review drafts containing an older FDC ID,
    - stale client state,
    - USDA records that were superseded after selection.
    """
    detail = await get_usda_food_detail(fdc_id)
    if detail is not None:
        normalized = _normalize_candidate(detail)
        if normalized is not None:
            return normalized
        return {
            "fdc_id": int(fdc_id),
            "description": str(detail.get("description") or description or name).strip(),
            "display_name": _display_name(
                str(detail.get("description") or description or name)
            ),
            "data_type": str(detail.get("dataType") or data_type or "Unknown"),
            "food_category": str(
                detail.get("foodCategory") or food_category or ""
            ).strip() or None,
            "brand_owner": str(
                detail.get("brandOwner") or detail.get("brandName") or ""
            ).strip() or None,
        }

    # The chosen ID is stale/unavailable. Re-run a fresh search by the human-
    # readable identity instead of passing the dead ID to nutrient_profile.
    query_candidates: list[str] = []
    for value in (name, description):
        cleaned = _clean_query(value)
        if len(cleaned) >= 2 and cleaned.lower() not in {
            q.lower() for q in query_candidates
        }:
            query_candidates.append(cleaned)

    for query in query_candidates:
        recovered = await search_usda_foods(query, limit=8)
        if recovered:
            return recovered[0]

    raise ValueError(
        f"USDA food '{name or description}' could not be retrieved and "
        f"no valid replacement was found for fdcId={fdc_id}."
    )


async def search_usda_foods(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    cleaned = _clean_query(query)
    if len(cleaned) < 2:
        return []
    cache_key = cleaned.lower()
    now = time.time()

    async with _cache_lock:
        cached = _cache.get(cache_key)
        if cached is not None and now - cached[0] < CACHE_TTL_SECONDS:
            # Cached search results are already detail-validated.
            return cached[1][:limit]

    preferred_payload = {
        "query": cleaned,
        "pageSize": 30,
        "pageNumber": 1,
        "dataType": PREFERRED_GENERIC_DATA_TYPES,
    }
    branded_payload = {
        "query": cleaned,
        "pageSize": 15,
        "pageNumber": 1,
        "dataType": ["Branded"],
    }
    params = {"api_key": USDA_API_KEY}

    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0)) as client:
        # Query core and branded datasets separately so branded products cannot
        # crowd foundational foods out of USDA's first relevance page. The two
        # requests run concurrently, so this does not add a serial round-trip.
        responses = await asyncio.gather(
            client.post(USDA_SEARCH_URL, params=params, json=preferred_payload),
            client.post(USDA_SEARCH_URL, params=params, json=branded_payload),
            return_exceptions=True,
        )
        raw_foods: list[dict[str, Any]] = []
        successful_responses = 0
        response_errors: list[Exception] = []
        for response in responses:
            if isinstance(response, Exception):
                response_errors.append(response)
                continue
            try:
                response.raise_for_status()
                body = response.json()
            except (httpx.HTTPStatusError, ValueError) as error:
                response_errors.append(error)
                continue
            successful_responses += 1
            foods = body.get("foods", []) if isinstance(body, dict) else []
            if isinstance(foods, list):
                raw_foods.extend(item for item in foods if isinstance(item, dict))

        if successful_responses == 0:
            cause = response_errors[0] if response_errors else None
            raise RuntimeError("USDA food search is temporarily unavailable.") from cause

        normalized: list[tuple[tuple, dict[str, Any]]] = []
        seen: set[int] = set()
        for item in raw_foods:
            if not isinstance(item, dict):
                continue
            candidate = _normalize_candidate(item)
            if candidate is None or candidate["fdc_id"] in seen:
                continue
            seen.add(candidate["fdc_id"])
            normalized.append((_candidate_score(item, cleaned), candidate))

        normalized.sort(key=lambda pair: pair[0], reverse=True)

        # Validate the best-scoring candidates concurrently. Search can return
        # historical IDs that the Food Details API no longer serves.
        pool = [
            candidate
            for _, candidate in normalized[: max(16, limit * 2)]
        ]
        usability = await asyncio.gather(
            *[
                _candidate_is_usable(candidate, client=client)
                for candidate in pool
            ]
        )
        results = [
            candidate
            for candidate, usable in zip(pool, usability)
            if usable
        ][: max(limit, 12)]

    async with _cache_lock:
        if len(_cache) >= MAX_CACHE_ITEMS:
            oldest_key = min(_cache, key=lambda key: _cache[key][0])
            _cache.pop(oldest_key, None)
        _cache[cache_key] = (now, results)

    return results[:limit]
