from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Set

import httpx

# =========================================================================
# LOGGING
# =========================================================================

logger = logging.getLogger("nutrica.nutrient_profile")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
logger.setLevel(os.environ.get("NUTRICA_LOG_LEVEL", "INFO"))


# =========================================================================
# CONFIG
# =========================================================================

USDA_FOOD_URL = "https://api.nal.usda.gov/fdc/v1/food/{fdc_id}"

USDA_API_KEY = os.environ.get(
    "USDA_API_KEY"
)

if not USDA_API_KEY:
    raise RuntimeError(
        "USDA_API_KEY is not configured."
    )

REQUEST_TIMEOUT_S = 10.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_S = 1.5
MAX_CONCURRENT_REQUESTS = 5
MIN_REQUEST_INTERVAL_S = 0.15

NUTRIENT_CACHE_FILE_PATH = os.environ.get("NUTRICA_NUTRIENT_CACHE_PATH", "")

# Units that are a reliable 1:1 gram-equivalent for scaling purposes.
# "ml" is included as a standard approximation (1 ml ~= 1 g) for typical
# foods lacking ingredient-specific density data - not exact, but far
# better than the alternative of not scaling liquids at all.
# _GRAM_EQUIVALENT_UNITS = {"g", "ml"}

_GRAM_EQUIVALENT_UNITS = {"g", "gram", "grams"}


class NutrientStatus:
    DOWNLOADED = "downloaded"
    DOWNLOAD_FAILED = "download_failed"
    SKIPPED_NO_FDC_ID = "skipped_no_fdc_id"


# =========================================================================
# CANONICAL SCHEMA
# =========================================================================

CANONICAL_NUTRIENT_KEYS: List[str] = [
    "energy_kcal", "protein_g", "fat_g", "carbohydrate_g", "fiber_g", "sugars_g", "added_sugars_g",
    "calcium_mg", "iron_mg", "magnesium_mg", "phosphorus_mg", "potassium_mg",
    "sodium_mg", "zinc_mg", "copper_mg", "manganese_mg", "selenium_ug",
    "vitamin_a_ug", "vitamin_c_mg", "vitamin_d_ug", "vitamin_e_mg", "vitamin_k_ug",
    "thiamin_mg", "riboflavin_mg", "niacin_mg", "pantothenic_acid_mg",
    "vitamin_b6_mg", "folate_ug", "vitamin_b12_ug", "choline_mg",
    "saturated_fat_g", "monounsaturated_fat_g", "polyunsaturated_fat_g", "trans_fat_g",
    "cholesterol_mg", "omega3_g", "omega6_g",
    "caffeine_mg", "water_g", "ash_g",
]


def _empty_canonical() -> Dict[str, None]:
    return {key: None for key in CANONICAL_NUTRIENT_KEYS}


# =========================================================================
# UNIT CONVERSION
# =========================================================================

# Mass units expressed relative to milligrams, used to convert any g/mg/ug
# amount into any other g/mg/ug amount without touching the reported value.
_MASS_TO_MG = {"G": 1000.0, "MG": 1.0, "UG": 0.001}


def _normalize_unit(unit: str) -> str:
    # IMPORTANT: replace the micro sign BEFORE upper-casing. Python's
    # str.upper() maps U+00B5 MICRO SIGN to U+039C GREEK CAPITAL LETTER MU
    # (not to itself), so a replace() for "\u00b5" done AFTER upper() never
    # matches - the unit silently comes out as an unrecognized string and
    # every microgram-unit nutrient (selenium, folate, vitamin K, ...)
    # would fail to convert and end up null. Also handle the Greek mu
    # variants defensively in case they appear directly in source data.
    u = (unit or "").strip()
    u = u.replace("\u00b5", "u").replace("\u03bc", "u").replace("\u039c", "u")
    u = u.upper()
    if u in ("MCG", "UG", "MCG_RAE", "UG RAE"):
        return "UG"
    if u == "MG":
        return "MG"
    if u in ("G", "GM", "GRAM", "GRAMS"):
        return "G"
    if u in ("KCAL", "CAL"):
        return "KCAL"
    if u == "KJ":
        return "KJ"
    if u == "IU":
        return "IU"
    return u


def _convert_mass(amount: float, source_unit: str, target_unit: str) -> Optional[float]:
    """Convert a mass-based nutrient amount between g/mg/ug. Returns None if
    either unit isn't a recognized mass unit (e.g. IU, or an unknown unit)."""
    source_unit = _normalize_unit(source_unit)
    target_unit = _normalize_unit(target_unit)
    if source_unit not in _MASS_TO_MG or target_unit not in _MASS_TO_MG:
        return None
    mg_value = amount * _MASS_TO_MG[source_unit]
    return mg_value / _MASS_TO_MG[target_unit]


# =========================================================================
# NUTRIENT_ID / NAME -> CANONICAL SCHEMA MAP
# =========================================================================
#
# Every canonical key maps to an ordered list of matchers. Matchers are
# tried in order; the first one with a usable value wins. Each matcher
# matches on USDA nutrient `number` (most stable identifier) OR nutrient
# `name` (case-insensitive exact match) - either is sufficient, which keeps
# this working even if USDA renumbers or renames a nutrient in the future.
#
# `iu_conversion_factor` is only used for the rare legacy IU-unit entries
# (Vitamin A, Vitamin D) and applies a standard, published conversion
# factor to re-express the SAME reported value in canonical units - this is
# unit standardization, not an estimate of an unreported value.

NUTRIENT_MAP: Dict[str, List[Dict[str, Any]]] = {
    "energy_kcal": [
        {"numbers": {"208"}, "names": {"energy"}, "target_unit": "KCAL", "require_raw_unit": "KCAL"},
        {"numbers": {"957"}, "names": {"energy (atwater general factors)"}, "target_unit": "KCAL", "require_raw_unit": "KCAL"},
        {"numbers": {"958"}, "names": {"energy (atwater specific factors)"}, "target_unit": "KCAL", "require_raw_unit": "KCAL"},
    ],
    "protein_g": [{"numbers": {"203"}, "names": {"protein"}, "target_unit": "G"}],
    "fat_g": [{"numbers": {"204"}, "names": {"total lipid (fat)", "total fat"}, "target_unit": "G"}],
    "carbohydrate_g": [
        {"numbers": {"205"}, "names": {"carbohydrate, by difference"}, "target_unit": "G"},
        {"names": {"carbohydrate, by summation"}, "target_unit": "G"},
    ],
    "fiber_g": [{"numbers": {"291"}, "names": {"fiber, total dietary"}, "target_unit": "G"}],
    "sugars_g": [
        {"numbers": {"269"}, "names": {"sugars, total including nlea", "sugars, total"}, "target_unit": "G"},
        {"names": {"total sugars"}, "target_unit": "G"},
    ],
    "calcium_mg": [{"numbers": {"301"}, "names": {"calcium, ca"}, "target_unit": "MG"}],
    "iron_mg": [{"numbers": {"303"}, "names": {"iron, fe"}, "target_unit": "MG"}],
    "magnesium_mg": [{"numbers": {"304"}, "names": {"magnesium, mg"}, "target_unit": "MG"}],
    "phosphorus_mg": [{"numbers": {"305"}, "names": {"phosphorus, p"}, "target_unit": "MG"}],
    "potassium_mg": [{"numbers": {"306"}, "names": {"potassium, k"}, "target_unit": "MG"}],
    "sodium_mg": [{"numbers": {"307"}, "names": {"sodium, na"}, "target_unit": "MG"}],
    "zinc_mg": [{"numbers": {"309"}, "names": {"zinc, zn"}, "target_unit": "MG"}],
    "copper_mg": [{"numbers": {"312"}, "names": {"copper, cu"}, "target_unit": "MG"}],
    "manganese_mg": [{"numbers": {"315"}, "names": {"manganese, mn"}, "target_unit": "MG"}],
    "selenium_ug": [{"numbers": {"317"}, "names": {"selenium, se"}, "target_unit": "UG"}],
    "vitamin_a_ug": [
        {"numbers": {"320"}, "names": {"vitamin a, rae"}, "target_unit": "UG"},
        # Legacy IU entries: 1 IU vitamin A ~ 0.3 ug RAE (standard published factor).
        {"numbers": {"318"}, "names": {"vitamin a, iu"}, "target_unit": "UG", "iu_conversion_factor": 0.3},
    ],
    "vitamin_c_mg": [{"numbers": {"401"}, "names": {"vitamin c, total ascorbic acid"}, "target_unit": "MG"}],
    "vitamin_d_ug": [
        {"numbers": {"328"}, "names": {"vitamin d (d2 + d3)"}, "target_unit": "UG"},
        # Legacy IU entry: 1 IU vitamin D = 0.025 ug (standard published factor).
        {"numbers": {"324"}, "names": {"vitamin d"}, "target_unit": "UG", "iu_conversion_factor": 0.025},
    ],
    "vitamin_e_mg": [{"numbers": {"323"}, "names": {"vitamin e (alpha-tocopherol)"}, "target_unit": "MG"}],
    "vitamin_k_ug": [{"numbers": {"430"}, "names": {"vitamin k (phylloquinone)"}, "target_unit": "UG"}],
    "thiamin_mg": [{"numbers": {"404"}, "names": {"thiamin"}, "target_unit": "MG"}],
    "riboflavin_mg": [{"numbers": {"405"}, "names": {"riboflavin"}, "target_unit": "MG"}],
    "niacin_mg": [{"numbers": {"406"}, "names": {"niacin"}, "target_unit": "MG"}],
    "pantothenic_acid_mg": [{"numbers": {"410"}, "names": {"pantothenic acid"}, "target_unit": "MG"}],
    "vitamin_b6_mg": [{"numbers": {"415"}, "names": {"vitamin b-6"}, "target_unit": "MG"}],
    "folate_ug": [
        {"numbers": {"417"}, "names": {"folate, total"}, "target_unit": "UG"},
        {"numbers": {"435"}, "names": {"folate, dfe"}, "target_unit": "UG"},
    ],
    "vitamin_b12_ug": [{"numbers": {"418"}, "names": {"vitamin b-12"}, "target_unit": "UG"}],
    "choline_mg": [{"numbers": {"421"}, "names": {"choline, total"}, "target_unit": "MG"}],
    "saturated_fat_g": [{"numbers": {"606"}, "names": {"fatty acids, total saturated"}, "target_unit": "G"}],
    "monounsaturated_fat_g": [{"numbers": {"645"}, "names": {"fatty acids, total monounsaturated"}, "target_unit": "G"}],
    "polyunsaturated_fat_g": [{"numbers": {"646"}, "names": {"fatty acids, total polyunsaturated"}, "target_unit": "G"}],
    "trans_fat_g": [{"numbers": {"605"}, "names": {"fatty acids, total trans"}, "target_unit": "G"}],
    "cholesterol_mg": [{"numbers": {"601"}, "names": {"cholesterol"}, "target_unit": "MG"}],
    # Aggregate omega-3/omega-6 tags are only reported by USDA for some foods
    # (mostly Branded/Survey). Left null when not directly reported - we
    # never sum individual fatty-acid isomers ourselves, since that would
    # cross from "standardization" into "estimation".
    "omega3_g": [{"numbers": {"851"}, "names": {"fatty acids, total omega-3"}, "target_unit": "G"}],
    "omega6_g": [{"numbers": {"852"}, "names": {"fatty acids, total omega-6"}, "target_unit": "G"}],
    "caffeine_mg": [{"numbers": {"262"}, "names": {"caffeine"}, "target_unit": "MG"}],
    "water_g": [{"numbers": {"255"}, "names": {"water"}, "target_unit": "G"}],
    "ash_g": [{"numbers": {"207"}, "names": {"ash"}, "target_unit": "G"}],
}


def _resolve_matcher_value(
    matcher: Dict[str, Any],
    by_number: Dict[str, Dict[str, Any]],
    by_name: Dict[str, List[Dict[str, Any]]],
) -> Optional[float]:
    candidates: List[Dict[str, Any]] = []
    for num in matcher.get("numbers", ()):
        item = by_number.get(num)
        if item:
            candidates.append(item)
    for name in matcher.get("names", ()):
        candidates.extend(by_name.get(name, []))

    if not candidates:
        return None

    require_unit = matcher.get("require_raw_unit")
    if require_unit:
        filtered = [c for c in candidates if _normalize_unit(c["unit"]) == require_unit]
        if filtered:
            candidates = filtered

    seen_ids: Set[Any] = set()
    unique_candidates = []
    for c in candidates:
        if c["id"] not in seen_ids:
            seen_ids.add(c["id"])
            unique_candidates.append(c)
    chosen = unique_candidates[0]

    amount = chosen["amount"]
    raw_unit = _normalize_unit(chosen["unit"])
    target_unit = matcher["target_unit"]
    iu_factor = matcher.get("iu_conversion_factor")

    if raw_unit == "IU" and iu_factor is not None:
        value = amount * iu_factor
    elif target_unit == "KCAL":
        value = amount if raw_unit == "KCAL" else None
    else:
        value = _convert_mass(amount, raw_unit, target_unit)

    return round(value, 4) if value is not None else None


def _build_nutrient_index(food_nutrients: List[Dict[str, Any]]):
    """One pass over the raw foodNutrients array, indexed for fast lookup
    both by nutrient number and by lowercased nutrient name."""
    by_number: Dict[str, Dict[str, Any]] = {}
    by_name: Dict[str, List[Dict[str, Any]]] = {}

    for item in food_nutrients or []:
        nutrient = item.get("nutrient") or {}
        amount = item.get("amount")
        nid = nutrient.get("id")
        if amount is None or nid is None:
            continue  # incomplete entry, can't use it safely

        number = str(nutrient.get("number") or "").strip()
        name = (nutrient.get("name") or "").strip().lower()
        unit = nutrient.get("unitName") or ""

        entry = {"id": nid, "number": number, "name": name, "amount": amount, "unit": unit}
        if number and number not in by_number:
            by_number[number] = entry
        if name:
            by_name.setdefault(name, []).append(entry)

    return by_number, by_name


def extract_canonical_nutrients(food_nutrients: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """
    Map a raw USDA `foodNutrients` array onto the canonical Nutrica schema.

    Every one of the 38 canonical keys is always present in the output.
    A nutrient USDA didn't report for this food is left as `null` - never
    estimated, never interpolated.
    """
    by_number, by_name = _build_nutrient_index(food_nutrients)

    canonical = _empty_canonical()
    for key, matchers in NUTRIENT_MAP.items():
        for matcher in matchers:
            value = _resolve_matcher_value(matcher, by_number, by_name)
            if value is not None:
                canonical[key] = value
                break
    return canonical


def extract_all_nutrients(food_nutrients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Preserve every nutrient USDA returned, exactly as returned (id, number,
    name, amount, unit) - regardless of whether it was mapped into the
    canonical schema. This guarantees no information is lost even for
    nutrients this module doesn't yet know how to canonicalize, and keeps
    working automatically if USDA adds new nutrients later.
    """
    result = []
    for item in food_nutrients or []:
        nutrient = item.get("nutrient") or {}
        result.append(
            {
                "id": nutrient.get("id"),
                "number": nutrient.get("number"),
                "name": nutrient.get("name"),
                "amount": item.get("amount"),
                "unit": nutrient.get("unitName"),
            }
        )
    return result


# =========================================================================
# CACHE
# =========================================================================

class NutrientCache:
    """
    Async-safe in-memory cache mapping fdc_id -> nutrient profile. Every
    fdc_id is downloaded from USDA at most once per cache lifetime; repeat
    occurrences of the same FDC ID (a common ingredient like "Salt" showing
    up in dozens of dishes) reuse the cached profile. Optionally persists to
    disk so the cache survives process restarts.
    """

    def __init__(self, disk_path: str = ""):
        self._store: Dict[int, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._disk_path = disk_path
        if self._disk_path and os.path.exists(self._disk_path):
            try:
                with open(self._disk_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self._store = {int(k): v for k, v in raw.items()}
                logger.info(
                    "Loaded %d cached nutrient profiles from %s",
                    len(self._store),
                    self._disk_path,
                )
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                logger.warning(
                    "Could not load nutrient cache file %s: %s", self._disk_path, exc
                )
                self._store = {}

    async def get(self, fdc_id: int) -> Optional[Dict[str, Any]]:
        async with self._lock:
            return self._store.get(fdc_id)

    async def set(self, fdc_id: int, profile: Dict[str, Any]) -> None:
        async with self._lock:
            self._store[fdc_id] = profile
            if self._disk_path:
                try:
                    with open(self._disk_path, "w", encoding="utf-8") as f:
                        json.dump(self._store, f)
                except OSError as exc:
                    logger.warning(
                        "Could not persist nutrient cache to %s: %s", self._disk_path, exc
                    )

    def stats(self) -> Dict[str, int]:
        return {"cached_fdc_ids": len(self._store)}


_nutrient_cache = NutrientCache(NUTRIENT_CACHE_FILE_PATH)
_fetch_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
_fetch_throttle_lock = asyncio.Lock()
_last_fetch_time = 0.0


async def _throttle_fetch() -> None:
    global _last_fetch_time
    async with _fetch_throttle_lock:
        now = time.monotonic()
        elapsed = now - _last_fetch_time
        if elapsed < MIN_REQUEST_INTERVAL_S:
            await asyncio.sleep(MIN_REQUEST_INTERVAL_S - elapsed)
        _last_fetch_time = time.monotonic()


# =========================================================================
# DOWNLOAD
# =========================================================================

async def fetch_food_detail(fdc_id: int, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    """
    Fetch the complete USDA food object for one FDC ID.
    Returns the parsed JSON dict, or None if the food couldn't be
    retrieved after retries (network failure, timeout, 5xx, or 404).
    """
    url = USDA_FOOD_URL.format(fdc_id=fdc_id)
    params = {"api_key": USDA_API_KEY}

    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with _fetch_semaphore:
                await _throttle_fetch()
                response = await client.get(url, params=params, timeout=REQUEST_TIMEOUT_S)

            if response.status_code == 429:
                wait = RETRY_BACKOFF_BASE_S * attempt * 2
                logger.warning(
                    "USDA rate limit hit fetching fdcId=%s, backing off %.1fs", fdc_id, wait
                )
                await asyncio.sleep(wait)
                continue

            if response.status_code == 404:
                logger.warning("USDA fdcId=%s not found (404)", fdc_id)
                return None

            if response.status_code >= 500:
                logger.warning(
                    "USDA server error %s fetching fdcId=%s (attempt %d/%d)",
                    response.status_code, fdc_id, attempt, MAX_RETRIES,
                )
                await asyncio.sleep(RETRY_BACKOFF_BASE_S * attempt)
                continue

            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException as exc:
            last_exc = exc
            logger.warning(
                "Timeout fetching fdcId=%s (attempt %d/%d)", fdc_id, attempt, MAX_RETRIES
            )
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            logger.warning(
                "HTTP error %s fetching fdcId=%s (attempt %d/%d)",
                exc.response.status_code, fdc_id, attempt, MAX_RETRIES,
            )
            if 400 <= exc.response.status_code < 500 and exc.response.status_code != 429:
                break
        except (httpx.RequestError, json.JSONDecodeError) as exc:
            last_exc = exc
            logger.warning(
                "Failed fetching fdcId=%s (attempt %d/%d): %s", fdc_id, attempt, MAX_RETRIES, exc
            )

        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_BACKOFF_BASE_S * attempt)

    logger.error("Exhausted retries fetching fdcId=%s: %s", fdc_id, last_exc)
    return None


async def _get_nutrient_profile(fdc_id: int, client: httpx.AsyncClient) -> Dict[str, Any]:
    """Cache-aware wrapper: download + standardize a single FDC ID's nutrient
    profile, or return a failure stub. Successful profiles are cached;
    failures are not, so a transient outage can be retried on a later call."""
    cached = await _nutrient_cache.get(fdc_id)
    if cached is not None:
        logger.debug("Nutrient cache hit for fdcId=%s", fdc_id)
        return cached

    raw = await fetch_food_detail(fdc_id, client)
    if raw is None:
        return {
            "nutrient_status": NutrientStatus.DOWNLOAD_FAILED,
            "nutrients": _empty_canonical(),
            "all_nutrients": [],
        }

    food_nutrients = raw.get("foodNutrients", []) or []
    profile = {
        "nutrient_status": NutrientStatus.DOWNLOADED,
        "nutrients": extract_canonical_nutrients(food_nutrients),
        "all_nutrients": extract_all_nutrients(food_nutrients),
    }
    await _nutrient_cache.set(fdc_id, profile)
    return profile


# =========================================================================
# PER-PORTION SCALING
# =========================================================================
#
# USDA foodNutrients amounts are per 100 g of the food. These scale a
# cached per-100g profile down to the food/ingredient/spice's own detected
# weight. A `None` nutrient value is always left `None` - scaling never
# turns a missing value into a fabricated one.

def _scale_nutrients(
    nutrients: Dict[str, Optional[float]],
    weight_g: Optional[float],
) -> Dict[str, Optional[float]]:
    """USDA nutrients are per 100 g. Convert them to nutrients for the
    actual ingredient/food weight."""
    if weight_g is None:
        return nutrients

    factor = weight_g / 100.0

    scaled = {}
    for key, value in nutrients.items():
        scaled[key] = None if value is None else round(value * factor, 4)
    return scaled


def _scale_all_nutrients(
    nutrients: List[Dict[str, Any]],
    weight_g: Optional[float],
) -> List[Dict[str, Any]]:
    if weight_g is None:
        return nutrients

    factor = weight_g / 100.0

    scaled = []
    for n in nutrients:
        item = dict(n)
        if item["amount"] is not None:
            item["amount"] = round(item["amount"] * factor, 4)
        scaled.append(item)
    return scaled


# =========================================================================
# ATTACH TO MEAL
# =========================================================================

def _collect_resolved_fdc_ids(
    foods: List[Dict[str, Any]],
) -> List[int]:
    """
    Collect USDA IDs only for non-label foods.

    Branded nutrition-label products must never trigger
    USDA requests for either the product or printed ingredients.
    """

    ids: Set[int] = set()

    for food in foods:
        if (
            food.get("analysis_route")
            == "NUTRITION_LABEL"
        ):
            continue

        resolver = food.get("resolver") or {}

        if resolver.get("fdc_id") is not None:
            ids.add(int(resolver["fdc_id"]))

        for ingredient in (
            food.get("ingredients") or []
        ):
            resolver = (
                ingredient.get("resolver") or {}
            )

            if resolver.get("fdc_id") is not None:
                ids.add(
                    int(resolver["fdc_id"])
                )

        for spice in food.get("spices") or []:
            resolver = spice.get("resolver") or {}

            if resolver.get("fdc_id") is not None:
                ids.add(
                    int(resolver["fdc_id"])
                )

    return list(ids)

def _resolve_entry_weight_g(entry: Dict[str, Any]) -> Optional[float]:
    """
    Determine the gram weight to scale this entry's per-100g USDA nutrient
    profile by.

    Ingredients/spices always carry an explicit estimated_weight_g (grams)
    set by the Vision Engine - use that directly when present.

    Top-level foods only carry "quantity" + "unit". quantity is only a
    valid gram-equivalent when unit is "g" (or "ml", treated as an
    approximate 1:1 g/ml equivalence for typical foods). For countable
    units like "piece", "slice", "cup", "tbsp", or "tsp", quantity is a
    COUNT, not a weight, and must never be used directly as grams - doing
    so silently produces wildly wrong scaled nutrients (e.g. "2 pieces of
    naan" scaled as if it weighed 2 grams instead of ~120g).
    """
    explicit_weight = entry.get("estimated_weight_g")
    if explicit_weight is not None:
        return explicit_weight

    quantity = entry.get("quantity")
    unit = (entry.get("unit") or "").strip().lower()

    if quantity is not None and unit in _GRAM_EQUIVALENT_UNITS:
        return quantity

    if quantity is not None and unit:
        logger.debug(
            "Skipping nutrient scaling for %r: quantity is in unit %r, which "
            "isn't a reliable gram-equivalent - returning per-100g values unscaled.",
            entry.get("name"), unit,
        )

    return None


def _attach_profile(entry: Dict[str, Any], profiles_by_id: Dict[int, Dict[str, Any]]) -> None:
    """Mutates `entry` in place, attaching nutrient_status/nutrients/all_nutrients,
    scaled from USDA's per-100g baseline to this entry's own detected weight."""
    resolver = entry.get("resolver") or {}
    fdc_id = resolver.get("fdc_id")

    if fdc_id is None:
        entry["nutrient_status"] = NutrientStatus.SKIPPED_NO_FDC_ID
        entry["nutrients"] = _empty_canonical()
        entry["all_nutrients"] = []
        return

    profile = profiles_by_id.get(int(fdc_id))
    if profile is None:
        # Defensive fallback; shouldn't happen since every resolved id is
        # collected and fetched up front.
        entry["nutrient_status"] = NutrientStatus.DOWNLOAD_FAILED
        entry["nutrients"] = _empty_canonical()
        entry["all_nutrients"] = []
        return

    entry["nutrient_status"] = profile["nutrient_status"]

    weight_g = _resolve_entry_weight_g(entry)
    entry["nutrients"] = _scale_nutrients(profile["nutrients"], weight_g)
    entry["all_nutrients"] = _scale_all_nutrients(profile["all_nutrients"], weight_g)

def _sum_decomposed_components(
    food: Dict[str, Any],
) -> None:
    """
    Build a DECOMPOSE parent's nutrients from its resolved
    ingredients and spices.

    The parent is not independently matched to a USDA dish.
    """

    totals: Dict[str, Optional[float]] = (
        _empty_canonical()
    )

    ingredients = (
        food.get("ingredients")
        or []
    )

    spices = (
        food.get("spices")
        or []
    )

    contributions: List[Dict[str, Any]] = []
    resolved_component_count = 0

    def add_component(
        component: Dict[str, Any],
        component_type: str,
    ) -> None:
        nonlocal resolved_component_count

        nutrients = component.get("nutrients")

        if not isinstance(nutrients, dict):
            return

        component_has_value = False

        for key in CANONICAL_NUTRIENT_KEYS:
            raw_value = nutrients.get(key)

            if (
                raw_value is None
                or isinstance(raw_value, bool)
                or not isinstance(
                    raw_value,
                    (int, float),
                )
            ):
                continue

            value = float(raw_value)

            if totals[key] is None:
                totals[key] = 0.0

            totals[key] = round(
                float(totals[key]) + value,
                4,
            )

            component_has_value = True

        if not component_has_value:
            return

        resolved_component_count += 1

        contributions.append(
            {
                "name": (
                    component.get("name")
                    or component.get(
                        "canonical_name"
                    )
                    or "Component"
                ),
                "component_type": component_type,
                "estimated_weight_g": (
                    component.get(
                        "estimated_weight_g"
                    )
                ),
                "estimated_percentage": (
                    component.get(
                        "estimated_percentage"
                    )
                ),
                "resolver": component.get(
                    "resolver"
                ),
                "nutrient_status": (
                    component.get(
                        "nutrient_status"
                    )
                ),
                "nutrients": dict(nutrients),
            }
        )

    for ingredient in ingredients:
        if isinstance(ingredient, dict):
            add_component(
                ingredient,
                "ingredient",
            )

    for spice in spices:
        if isinstance(spice, dict):
            add_component(
                spice,
                "spice",
            )

    food["nutrients"] = totals

    # Parent raw USDA nutrients do not exist because the
    # parent itself was not downloaded from USDA.
    food["all_nutrients"] = []

    food["nutrient_status"] = (
        "aggregated_from_components"
        if resolved_component_count > 0
        else "components_have_no_nutrients"
    )

    food["nutrient_source"] = (
        "resolved_ingredients_and_spices"
    )

    food["resolved_component_count"] = (
        resolved_component_count
    )

    food["nutrient_contributions"] = (
        contributions
    )

LABEL_NUTRIENT_KEYS = {
    "energy_kcal",
    "protein_g",
    "fat_g",
    "saturated_fat_g",
    "trans_fat_g",
    "carbohydrate_g",
    "fiber_g",
    "sugars_g",
    "added_sugars_g",
    "sodium_mg",
    "cholesterol_mg",
    "potassium_mg",
    "calcium_mg",
    "iron_mg",
    "caffeine_mg",
}


def _read_number(
    value: Any,
) -> Optional[float]:
    """
    Read a numeric label value without estimating it.
    """

    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, dict):
        for key in (
            "value",
            "amount",
            "quantity",
        ):
            parsed = _read_number(
                value.get(key)
            )

            if parsed is not None:
                return parsed

        return None

    text = str(value).strip().lower()

    if not text:
        return None

    replacements = (
        "kcal",
        "calories",
        "calorie",
        "grams",
        "gram",
        "milligrams",
        "milligram",
        "micrograms",
        "microgram",
        "mg",
        "mcg",
        "µg",
        "ug",
        "ml",
        "g",
    )

    cleaned = text.replace(",", "")

    for token in replacements:
        cleaned = cleaned.replace(
            token,
            "",
        )

    cleaned = cleaned.strip()

    try:
        return float(cleaned)

    except ValueError:
        return None


def _normalize_quantity_unit(
    value: Any,
) -> str:
    unit = str(value or "").strip().lower()

    aliases = {
        "gram": "g",
        "grams": "g",
        "g": "g",
        "millilitre": "ml",
        "millilitres": "ml",
        "milliliter": "ml",
        "milliliters": "ml",
        "ml": "ml",
    }

    return aliases.get(unit, unit)


def _has_reported_nutrients(
    nutrient_data: Any,
) -> bool:
    if not isinstance(nutrient_data, dict):
        return False

    return any(
        _read_number(
            nutrient_data.get(key)
        )
        is not None
        for key in LABEL_NUTRIENT_KEYS
    )


def _extract_label_nutrients(
    nutrient_data: Dict[str, Any],
) -> Dict[str, Optional[float]]:
    """
    Convert Gemini's fixed nutrition-label schema into
    the canonical nutrient dictionary.
    """

    canonical = _empty_canonical()

    for key in LABEL_NUTRIENT_KEYS:
        if key not in canonical:
            continue

        canonical[key] = _read_number(
            nutrient_data.get(key)
        )

    return canonical


def _scale_by_factor(
    nutrients: Dict[str, Optional[float]],
    factor: float,
) -> Dict[str, Optional[float]]:
    return {
        key: (
            None
            if value is None
            else round(
                value * factor,
                4,
            )
        )
        for key, value in nutrients.items()
    }


def _canonical_unit(
    nutrient_key: str,
) -> str:
    if nutrient_key == "energy_kcal":
        return "kcal"

    if nutrient_key.endswith("_g"):
        return "g"

    if nutrient_key.endswith("_mg"):
        return "mg"

    if nutrient_key.endswith("_ug"):
        return "ug"

    return ""


def _label_all_nutrients(
    nutrients: Dict[str, Optional[float]],
) -> List[Dict[str, Any]]:
    """
    Preserve the reported label nutrients in a structure
    similar to USDA's all_nutrients output.
    """

    result: List[Dict[str, Any]] = []

    for key, value in nutrients.items():
        if value is None:
            continue

        result.append(
            {
                "id": None,
                "number": None,
                "name": key,
                "amount": value,
                "unit": _canonical_unit(key),
                "source": "nutrition_label",
            }
        )

    return result


def _label_basis(
    label: Dict[str, Any],
) -> tuple[Optional[float], str]:
    raw_basis = label.get(
        "nutrition_basis"
    )

    if not isinstance(raw_basis, dict):
        return None, ""

    basis_value = _read_number(
        raw_basis.get("value")
    )

    basis_unit = _normalize_quantity_unit(
        raw_basis.get("unit")
    )

    return basis_value, basis_unit


def _serving_basis(
    label: Dict[str, Any],
) -> tuple[Optional[float], str]:
    raw_serving = label.get(
        "serving_size"
    )

    if not isinstance(raw_serving, dict):
        return None, ""

    serving_value = _read_number(
        raw_serving.get("value")
    )

    serving_unit = _normalize_quantity_unit(
        raw_serving.get("unit")
    )

    return serving_value, serving_unit


def _attach_label_profile(
    food: Dict[str, Any],
) -> None:
    """
    Attach nutrients from an uploaded package label.

    The printed label is authoritative. USDA is not used
    for NUTRITION_LABEL foods.
    """

    label = food.get(
        "nutrition_label"
    )

    if not isinstance(label, dict):
        food["nutrient_status"] = (
            "missing_nutrition_label"
        )
        food["nutrients"] = (
            _empty_canonical()
        )
        food["all_nutrients"] = []
        return

    food_quantity = _read_number(
        food.get("quantity")
    )

    food_unit = _normalize_quantity_unit(
        food.get("unit")
    )

    per_100 = label.get(
        "nutrition_per_100g"
    )

    per_serving = label.get(
        "nutrition_per_serving"
    )

    # Prefer the printed per-100 block because it scales
    # directly to the detected consumed quantity.
    if _has_reported_nutrients(per_100):
        nutrients = _extract_label_nutrients(
            per_100
        )

        basis_value, basis_unit = (
            _label_basis(label)
        )

        # Gemini may omit nutrition_basis even when the
        # panel clearly says per 100 g or per 100 ml.
        if basis_value is None:
            basis_value = 100.0

        if not basis_unit:
            basis_unit = food_unit

        if (
            food_quantity is not None
            and food_quantity > 0
            and basis_value > 0
            and food_unit in {"g", "ml"}
            and food_unit == basis_unit
        ):
            factor = (
                food_quantity
                / basis_value
            )

            nutrients = _scale_by_factor(
                nutrients,
                factor,
            )

            scaling_status = (
                "scaled_to_consumed_quantity"
            )
        else:
            # Do not pretend the per-100 values are the
            # consumed totals when units do not match.
            food["nutrient_status"] = (
                "label_quantity_unit_mismatch"
            )
            food["nutrients"] = (
                _empty_canonical()
            )
            food["all_nutrients"] = []
            food["nutrition_label_error"] = {
                "food_quantity": food_quantity,
                "food_unit": food_unit,
                "basis_value": basis_value,
                "basis_unit": basis_unit,
            }
            return

        food["nutrients"] = nutrients
        food["all_nutrients"] = (
            _label_all_nutrients(
                nutrients
            )
        )
        food["nutrient_status"] = (
            "nutrition_label_attached"
        )
        food["nutrient_source"] = (
            "uploaded_nutrition_label"
        )
        food["nutrition_label_basis"] = {
            "source": "nutrition_per_100g",
            "value": basis_value,
            "unit": basis_unit,
            "scaling_status": scaling_status,
        }
        return

    if _has_reported_nutrients(
        per_serving
    ):
        nutrients = _extract_label_nutrients(
            per_serving
        )

        serving_value, serving_unit = (
            _serving_basis(label)
        )

        if (
            food_quantity is not None
            and food_quantity > 0
            and serving_value is not None
            and serving_value > 0
            and food_unit in {"g", "ml"}
            and food_unit == serving_unit
        ):
            serving_count = (
                food_quantity
                / serving_value
            )

            nutrients = _scale_by_factor(
                nutrients,
                serving_count,
            )

            scaling_status = (
                "scaled_by_serving_count"
            )
        else:
            # If the food quantity is itself a count of
            # servings, allow direct count scaling.
            if (
                food_quantity is not None
                and food_quantity > 0
                and food_unit in {
                    "piece",
                    "serving",
                }
            ):
                nutrients = _scale_by_factor(
                    nutrients,
                    food_quantity,
                )

                serving_count = (
                    food_quantity
                )

                scaling_status = (
                    "scaled_by_detected_count"
                )
            else:
                food["nutrient_status"] = (
                    "label_serving_unit_mismatch"
                )
                food["nutrients"] = (
                    _empty_canonical()
                )
                food["all_nutrients"] = []
                food[
                    "nutrition_label_error"
                ] = {
                    "food_quantity": (
                        food_quantity
                    ),
                    "food_unit": food_unit,
                    "serving_value": (
                        serving_value
                    ),
                    "serving_unit": (
                        serving_unit
                    ),
                }
                return

        food["nutrients"] = nutrients
        food["all_nutrients"] = (
            _label_all_nutrients(
                nutrients
            )
        )
        food["nutrient_status"] = (
            "nutrition_label_attached"
        )
        food["nutrient_source"] = (
            "uploaded_nutrition_label"
        )
        food["nutrition_label_basis"] = {
            "source": (
                "nutrition_per_serving"
            ),
            "serving_value": serving_value,
            "serving_unit": serving_unit,
            "serving_count": serving_count,
            "scaling_status": scaling_status,
        }
        return

    food["nutrient_status"] = (
        "label_has_no_reported_nutrients"
    )
    food["nutrients"] = (
        _empty_canonical()
    )
    food["all_nutrients"] = []

async def attach_nutrients(
    resolved_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Attach USDA nutrient profiles to the completed output
    produced by food_resolver.resolve_meal().

    The input dictionary is not modified.
    """

    if not isinstance(resolved_result, dict):
        raise ValueError(
            "Resolved result must be a dictionary."
        )

    status = resolved_result.get(
        "status",
        "completed",
    )

    if status != "completed":
        raise ValueError(
            "Nutrient attachment requires a completed "
            f"analysis result, received status: {status}"
        )

    meal = resolved_result.get("meal")

    if not isinstance(meal, dict):
        raise ValueError(
            "Resolved result must contain a valid "
            "top-level 'meal' object."
        )

    foods = meal.get("foods")

    if not isinstance(foods, list):
        raise ValueError(
            "Resolved result must contain a valid "
            "'meal.foods' list."
        )

    result = copy.deepcopy(
        resolved_result
    )

    result_foods = (
        result
        .get("meal", {})
        .get("foods", [])
    )

    unique_ids = _collect_resolved_fdc_ids(
        result_foods
    )

    profiles_by_id: Dict[
        int,
        Dict[str, Any],
    ] = {}

    if unique_ids:
        async with httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Nutrica-NutrientProfile/1.0"
                )
            }
        ) as client:
            fetched = await asyncio.gather(
                *[
                    _get_nutrient_profile(
                        fdc_id,
                        client,
                    )
                    for fdc_id in unique_ids
                ]
            )

        profiles_by_id = dict(
            zip(
                unique_ids,
                fetched,
            )
        )

    for food in result_foods:
        route = food.get(
            "analysis_route",
            "DIRECT_USDA",
        )
    
        if route == "NUTRITION_LABEL":
            _attach_label_profile(
                food
            )
    
            # Package ingredients are descriptive only.
            continue
    
        if route == "DECOMPOSE":
            for ingredient in (
                food.get("ingredients")
                or []
            ):
                _attach_profile(
                    ingredient,
                    profiles_by_id,
                )
    
            for spice in (
                food.get("spices")
                or []
            ):
                _attach_profile(
                    spice,
                    profiles_by_id,
                )
    
            _sum_decomposed_components(
                food
            )
    
            continue
    
        # DIRECT_USDA and any ordinary standalone food.
        _attach_profile(
            food,
            profiles_by_id,
        )
    result["nutrient_profile_status"] = (
        "completed"
    )

    return result


def attach_nutrients_sync(
    resolved_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Synchronous wrapper for ordinary Python scripts.

    Inside FastAPI async endpoints, use:

        await attach_nutrients(resolved_result)
    """

    try:
        asyncio.get_running_loop()

    except RuntimeError:
        return asyncio.run(
            attach_nutrients(
                resolved_result
            )
        )

    raise RuntimeError(
        "attach_nutrients_sync() cannot be called "
        "inside a running event loop. Use "
        "`await attach_nutrients(resolved_result)` "
        "instead."
    )
