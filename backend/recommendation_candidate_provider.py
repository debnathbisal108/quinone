"""Deterministic USDA-backed recommendation candidate discovery for Quinone.

Recommendation discovery deliberately does NOT call any LLM.
Quinone maintains a broad internal base of ordinary single-food identities and
search metadata. For each request, this module selects a relevant, diverse
subset, resolves those foods against USDA FoodData Central, hydrates authoritative
nutrient values, and returns only verified candidates. The recommendation engine
then applies all diet/allergy/medical/personalization gates and full meal-score
simulation before anything is shown.

The small legacy curated catalogue remains only as an outage fallback when USDA
verification cannot provide a usable pool.
"""

from __future__ import annotations

import asyncio
import copy
import inspect
import logging
import os
import re
from typing import Any, Iterable

from nutrient_profile import attach_nutrients
from recommendation_food_base import RECOMMENDATION_FOOD_BASE
from usda_recipe_service import search_usda_foods

logger = logging.getLogger("quinone.recommendation_candidates")

DYNAMIC_CANDIDATE_PROVIDER_VERSION = "2.0.0"

_PREPARATION_TOKENS = {
    "raw", "cooked", "boiled", "steamed", "roasted", "baked", "fried",
    "fresh", "frozen", "dried", "dry", "plain", "unsalted", "salted",
    "without", "with", "prepared", "ready", "eat", "whole", "chopped",
}

_ALLERGEN_TERMS: dict[str, tuple[str, ...]] = {
    "milk": ("milk", "yogurt", "yoghurt", "cheese", "paneer", "whey", "casein"),
    "dairy": ("milk", "yogurt", "yoghurt", "cheese", "paneer", "whey", "casein"),
    "egg": ("egg",),
    "fish": (
        "fish", "salmon", "tuna", "sardine", "mackerel", "cod", "trout",
        "herring", "anchovy", "tilapia",
    ),
    "shellfish": ("shrimp", "prawn", "crab", "lobster", "oyster", "mussel", "clam"),
    "tree_nuts": (
        "almond", "walnut", "cashew", "pistachio", "pecan", "hazelnut",
        "macadamia", "brazil nut",
    ),
    "peanut": ("peanut",),
    "soy": ("soy", "soya", "tofu", "tempeh", "edamame"),
    "wheat": ("wheat", "bulgur", "couscous", "semolina", "farina"),
    "gluten": ("wheat", "barley", "rye", "bulgur", "couscous", "semolina"),
    "sesame": ("sesame", "tahini"),
}

# Health-domain hints are ONLY a cheap pre-search prioritization device. They do
# not decide whether a food helps a module; the normal evidence/scoring
# simulation makes that decision after USDA hydration.
_DOMAIN_NUTRIENT_HINTS: dict[str, tuple[str, ...]] = {
    "glycemic": ("fiber_g", "magnesium_mg", "protein_g"),
    "blood_sugar": ("fiber_g", "magnesium_mg", "protein_g"),
    "metabolic": ("fiber_g", "magnesium_mg", "potassium_mg", "protein_g"),
    "cardiovascular": ("fiber_g", "potassium_mg", "magnesium_mg", "omega3_g"),
    "heart": ("fiber_g", "potassium_mg", "magnesium_mg", "omega3_g"),
    "blood_pressure": ("potassium_mg", "magnesium_mg", "fiber_g"),
    "bone": ("calcium_mg", "vitamin_d_ug", "protein_g", "magnesium_mg"),
    "musculoskeletal": ("protein_g", "calcium_mg", "vitamin_d_ug", "magnesium_mg"),
    "healthy_aging": ("protein_g", "calcium_mg", "vitamin_d_ug", "magnesium_mg"),
    "joint": ("omega3_g", "vitamin_c_mg", "protein_g"),
    "arthritis": ("omega3_g", "vitamin_c_mg"),
    "immune": ("vitamin_c_mg", "zinc_mg", "selenium_ug", "vitamin_d_ug"),
    "hepatic": ("fiber_g", "omega3_g", "magnesium_mg"),
    "liver": ("fiber_g", "omega3_g", "magnesium_mg"),
    "renal": ("fiber_g", "vitamin_c_mg"),
    "kidney": ("fiber_g", "vitamin_c_mg"),
    "brain": ("omega3_g", "folate_ug", "vitamin_b12_ug", "magnesium_mg"),
    "cognitive": ("omega3_g", "folate_ug", "vitamin_b12_ug"),
    "gut": ("fiber_g",),
    "digestive": ("fiber_g",),
}

_NUTRIENT_ALIASES: dict[str, str] = {
    "carbohydrates_g": "carbohydrate_g",
    "carbs_g": "carbohydrate_g",
    "total_fat_g": "fat_g",
    "sat_fat_g": "saturated_fat_g",
    "saturated_fat": "saturated_fat_g",
    "added_sugar_g": "added_sugars_g",
    "vitamin_b12_mcg": "vitamin_b12_ug",
    "b12_ug": "vitamin_b12_ug",
    "folate_ug_dfe": "folate_ug",
    "vitamin_a_ug_rae": "vitamin_a_ug",
    "vitamin_d_mcg": "vitamin_d_ug",
    "selenium_mcg": "selenium_ug",
}



def _usda_discovery_available() -> bool:
    key = os.environ.get("USDA_API_KEY", "").strip().lower()
    return bool(key) and key not in {"test", "mock", "dummy", "replace_with_your_usda_api_key"}

def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and parsed not in {float("inf"), float("-inf")} else None


def _canonical_nutrient(value: Any) -> str:
    key = re.sub(r"\s+", "_", str(value or "").strip().lower())
    return _NUTRIENT_ALIASES.get(key, key)


def _normalized_tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if len(token) >= 3 and token not in _PREPARATION_TOKENS
    }


def _already_present(description: str, current_foods: Iterable[dict[str, Any]]) -> bool:
    candidate = _normalized_tokens(description)
    if not candidate:
        return False
    for food in current_foods:
        text = " ".join(
            str(food.get(key) or "")
            for key in ("canonical_name", "display_name", "name")
        )
        existing = _normalized_tokens(text)
        if not existing:
            continue
        # Exact/subset identity catches "Blueberries" vs "Blueberries, raw";
        # for multi-token names require a strong overlap to avoid treating e.g.
        # green beans and kidney beans as the same food merely because both say beans.
        overlap = candidate & existing
        smaller = min(len(candidate), len(existing))
        if smaller == 1 and overlap:
            if candidate == existing:
                return True
            # A single distinctive token is safe only if either normalized name
            # is literally contained in the other string.
            ctext = " ".join(sorted(candidate))
            etext = " ".join(sorted(existing))
            if ctext in etext or etext in ctext:
                return True
        elif smaller > 1 and len(overlap) / smaller >= 0.75:
            return True
    return False


def _diet_tags(food_group: str) -> list[str]:
    group = str(food_group or "").strip().lower()
    if group in {"plant", "fruit", "vegetable", "legume", "soy", "grain", "nuts_seeds"}:
        return ["vegan", "vegetarian"]
    if group == "dairy":
        return ["vegetarian"]
    if group == "egg":
        return ["ovo_vegetarian"]
    if group in {"fish", "shellfish"}:
        return ["pescatarian"]
    return []


def _inferred_allergens(description: str) -> set[str]:
    text = str(description or "").lower()
    found: set[str] = set()
    for allergen, terms in _ALLERGEN_TERMS.items():
        if any(term in text for term in terms):
            found.add(allergen)
    return found


def _infer_food_group(description: str) -> str:
    text = str(description or "").lower()
    if any(term in text for term in _ALLERGEN_TERMS["shellfish"]):
        return "shellfish"
    if any(term in text for term in _ALLERGEN_TERMS["fish"]):
        return "fish"
    if re.search(r"\begg(s)?\b", text):
        return "egg"
    if any(term in text for term in ("beef", "pork", "chicken", "turkey", "lamb", "mutton", "goat", "venison", "meat")):
        return "meat"
    if any(term in text for term in _ALLERGEN_TERMS["milk"]):
        return "dairy"
    if any(term in text for term in _ALLERGEN_TERMS["soy"]):
        return "soy"
    return "plant"


def _target_hint_set(
    target_domains: list[dict[str, Any]],
    target_nutrients: list[str],
) -> set[str]:
    hints = {_canonical_nutrient(value) for value in target_nutrients if str(value or "").strip()}
    for item in target_domains:
        if not isinstance(item, dict):
            continue
        text = " ".join(
            str(item.get(key) or "")
            for key in ("key", "label", "name", "domain")
        ).lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
        for token, nutrients in _DOMAIN_NUTRIENT_HINTS.items():
            if token in normalized:
                hints.update(nutrients)
    return hints


def _seed_score(seed: dict[str, Any], hints: set[str]) -> float:
    focus = {_canonical_nutrient(key) for key in seed.get("focus_nutrients", [])}
    direct = len(focus & hints)
    # Exact target overlap dominates. A tiny constant means every food remains
    # eligible for diversity/fallback even if a novel domain has no hint map.
    return direct * 10.0 + min(len(focus), 5) * 0.05


def _selected_seed_ideas(
    *,
    current_foods: list[dict[str, Any]],
    target_domains: list[dict[str, Any]],
    target_nutrients: list[str],
    maximum_candidates: int,
) -> list[dict[str, Any]]:
    hints = _target_hint_set(target_domains, target_nutrients)
    ranked = []
    for index, seed in enumerate(RECOMMENDATION_FOOD_BASE):
        text = f"{seed.get('name', '')} {seed.get('search_query', '')}"
        if _already_present(text, current_foods):
            continue
        ranked.append((_seed_score(seed, hints), -index, seed))
    ranked.sort(reverse=True, key=lambda row: (row[0], row[1]))

    # Search a moderate pool, not all 100+ foods per button tap. Round-robin by
    # food group keeps the shortlist varied and prevents repetitive berry/nut
    # suggestions even when many foods share the same target nutrient.
    search_budget = max(maximum_candidates + 8, min(maximum_candidates * 2, 32))
    buckets: dict[str, list[dict[str, Any]]] = {}
    group_order: list[str] = []
    for _, _, seed in ranked:
        group = str(seed.get("food_group") or "other")
        if group not in buckets:
            buckets[group] = []
            group_order.append(group)
        buckets[group].append(seed)

    selected: list[dict[str, Any]] = []
    cursor = 0
    while len(selected) < search_budget and any(buckets.values()):
        group = group_order[cursor % len(group_order)]
        cursor += 1
        rows = buckets.get(group) or []
        if not rows:
            if cursor > len(group_order) * (search_budget + 2):
                break
            continue
        seed = rows.pop(0)
        selected.append({
            "seed_id": seed["id"],
            "name": seed["name"],
            "usda_search_query": seed["search_query"],
            "serving_g": seed["serving_g"],
            "meal_roles": list(seed.get("meal_roles", [])),
            "food_group": seed.get("food_group"),
            "diet_tags": list(seed.get("diet_tags", [])),
            "allergens": list(seed.get("allergens", [])),
            "focus_nutrients": list(seed.get("focus_nutrients", [])),
        })
    return selected


async def _search_usda_recommendation_candidate(query: str) -> list[dict[str, Any]]:
    """Search USDA across both current and older service signatures."""
    kwargs: dict[str, Any] = {"limit": 1}
    try:
        signature = inspect.signature(search_usda_foods)
        parameters = signature.parameters
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        if accepts_kwargs or "include_branded" in parameters:
            kwargs["include_branded"] = False
        if accepts_kwargs or "validation_pool_size" in parameters:
            kwargs["validation_pool_size"] = 3
        if "include_branded" not in kwargs:
            kwargs["limit"] = 3
    except (TypeError, ValueError):
        kwargs = {"limit": 3}

    try:
        return await search_usda_foods(query, **kwargs)
    except TypeError as error:
        if "unexpected keyword argument" not in str(error):
            raise
        logger.warning(
            "USDA search contract mismatch; retrying recommendation verification "
            "with legacy arguments only: %s",
            error,
        )
        return await search_usda_foods(query, limit=3)


async def _resolve_idea_searches(
    ideas: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if not ideas:
        return []
    searches = await asyncio.gather(
        *[_search_usda_recommendation_candidate(str(idea["usda_search_query"])) for idea in ideas],
        return_exceptions=True,
    )
    resolved: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen_fdc: set[int] = set()
    for idea, result in zip(ideas, searches):
        if isinstance(result, Exception) or not result:
            continue
        candidate = next(
            (
                item for item in result
                if isinstance(item, dict)
                and isinstance(item.get("fdc_id"), int)
                and str(item.get("data_type") or "") != "Branded"
            ),
            None,
        )
        if candidate is None:
            continue
        fdc_id = int(candidate["fdc_id"])
        if fdc_id in seen_fdc:
            continue
        seen_fdc.add(fdc_id)
        resolved.append((idea, candidate))
    return resolved


async def _attach_usda_per100(
    resolved: list[tuple[dict[str, Any], dict[str, Any]]]
) -> dict[int, dict[str, Any]]:
    if not resolved:
        return {}
    foods: list[dict[str, Any]] = []
    for index, (_, match) in enumerate(resolved, start=1):
        fdc_id = int(match["fdc_id"])
        foods.append({
            "id": f"recommendation_candidate_{index:03d}",
            "name": match.get("display_name") or match.get("description"),
            "display_name": match.get("display_name") or match.get("description"),
            "canonical_name": match.get("description"),
            "food_source": "USDA FoodData Central",
            "analysis_route": "DIRECT_USDA",
            "quantity": 100.0,
            "estimated_weight_g": 100.0,
            "unit": "g",
            "preparation": "as listed by USDA",
            "ingredients": [],
            "spices": [],
            "resolver": {
                "status": "resolved",
                "fdc_id": fdc_id,
                "matched_description": match.get("description"),
                "matched_name": match.get("description"),
                "data_type": match.get("data_type"),
                "match_query": match.get("description"),
                "confidence": 1.0,
                "source": "recommendation_food_base_usda",
            },
        })
    attached = await attach_nutrients({
        "status": "completed",
        "meal": {"meal_type": "Recommendation candidate verification", "foods": foods},
    })
    output: dict[int, dict[str, Any]] = {}
    for food in attached.get("meal", {}).get("foods", []):
        if not isinstance(food, dict):
            continue
        resolver = food.get("resolver") if isinstance(food.get("resolver"), dict) else {}
        fdc_id = resolver.get("fdc_id")
        nutrients = food.get("nutrients")
        if isinstance(fdc_id, int) and isinstance(nutrients, dict):
            output[fdc_id] = food
    return output


def _fallback_result(
    fallback_candidates: Iterable[dict[str, Any]],
    reason: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return (
        [copy.deepcopy(item) for item in fallback_candidates],
        {
            "provider_version": DYNAMIC_CANDIDATE_PROVIDER_VERSION,
            "mode": "legacy_curated_fallback",
            "reason": reason,
            "llm_used": False,
            "internal_food_base_size": len(RECOMMENDATION_FOOD_BASE),
            "internal_candidates_searched": 0,
            "usda_verified_candidates": 0,
        },
    )


async def rehydrate_usda_candidate(
    fdc_id: int,
    *,
    serving_g: float = 100.0,
) -> dict[str, Any] | None:
    """Rebuild a recommendation candidate from its exact FDC id."""
    from usda_recipe_service import get_usda_food_detail

    try:
        numeric_id = int(fdc_id)
    except (TypeError, ValueError):
        return None
    detail = await get_usda_food_detail(numeric_id)
    if not isinstance(detail, dict):
        return None
    description = str(detail.get("description") or "").strip()
    if not description:
        return None
    data_type = str(detail.get("dataType") or "Unknown")
    if data_type == "Branded":
        return None

    group = _infer_food_group(description)
    stub = {
        "id": f"rehydrate_fdc_{numeric_id}",
        "name": description,
        "display_name": description,
        "canonical_name": description,
        "food_source": "USDA FoodData Central",
        "analysis_route": "DIRECT_USDA",
        "quantity": 100.0,
        "estimated_weight_g": 100.0,
        "unit": "g",
        "preparation": "as listed by USDA",
        "ingredients": [],
        "spices": [],
        "resolver": {
            "status": "resolved",
            "fdc_id": numeric_id,
            "matched_description": description,
            "matched_name": description,
            "data_type": data_type,
            "match_query": description,
            "confidence": 1.0,
            "source": "recommendation_food_base_usda",
        },
    }
    attached = await attach_nutrients({
        "status": "completed",
        "meal": {"meal_type": "Recommendation revalidation", "foods": [stub]},
    })
    foods = attached.get("meal", {}).get("foods", [])
    food = foods[0] if isinstance(foods, list) and foods and isinstance(foods[0], dict) else None
    if food is None or not isinstance(food.get("nutrients"), dict):
        return None
    nutrients = {
        str(key): float(value)
        for key, value in food["nutrients"].items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    return {
        "id": f"internal_fdc_{numeric_id}",
        "fdc_id": numeric_id,
        "name": description,
        "search_query": description,
        "serving_g": round(max(5.0, min(float(serving_g), 500.0)), 1),
        "meal_roles": [],
        "diet_tags": _diet_tags(group),
        "allergens": sorted(_inferred_allergens(description)),
        "nutrients": nutrients,
        "candidate_source": "internal_usda_verified",
        "food_group": group,
        "data_type": data_type,
        "food_category": str(detail.get("foodCategory") or "").strip() or None,
        "nutrient_source": "USDA FoodData Central",
    }


async def discover_recommendation_candidates(
    *,
    current_result: dict[str, Any],
    current_foods: list[dict[str, Any]],
    profile: dict[str, Any],
    target_domains: list[dict[str, Any]] | None = None,
    target_nutrients: list[str] | None = None,
    local_hour: int = 12,
    maximum_candidates: int = 16,
    fallback_candidates: Iterable[dict[str, Any]] = (),
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return a diverse context-relevant pool verified against USDA.

    ``current_result``, ``profile`` and ``local_hour`` are accepted to preserve
    the stable provider contract. Candidate *safety* is intentionally not
    decided here; the recommendation engine/guidance safety layer handles it.
    """
    del current_result, profile, local_hour
    if not _usda_discovery_available():
        return _fallback_result(fallback_candidates, "usda_api_key_unavailable")
    maximum_candidates = max(4, min(int(maximum_candidates), 24))
    ideas = _selected_seed_ideas(
        current_foods=current_foods,
        target_domains=list(target_domains or []),
        target_nutrients=list(target_nutrients or []),
        maximum_candidates=maximum_candidates,
    )
    if not ideas:
        return _fallback_result(fallback_candidates, "all_internal_candidates_already_present")

    try:
        resolved = await _resolve_idea_searches(ideas)
        attached = await _attach_usda_per100(resolved)
    except Exception as error:
        logger.warning("USDA recommendation candidate verification failed: %s", error)
        return _fallback_result(fallback_candidates, "usda_verification_failed")

    candidates: list[dict[str, Any]] = []
    for idea, match in resolved:
        fdc_id = int(match["fdc_id"])
        food = attached.get(fdc_id)
        if food is None:
            continue
        nutrients = {
            str(key): float(value)
            for key, value in (food.get("nutrients") or {}).items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        if not any(
            (nutrients.get(key) or 0.0) > 0
            for key in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g")
        ):
            continue
        description = str(match.get("description") or idea.get("name") or "Food").strip()
        if _already_present(f"{idea.get('name', '')} {description}", current_foods):
            continue

        inferred_group = _infer_food_group(description)
        seed_group = str(idea.get("food_group") or inferred_group)
        group = inferred_group if inferred_group not in {"plant"} else seed_group
        allergens = {
            str(value).strip().lower()
            for value in idea.get("allergens", [])
            if str(value).strip()
        }
        allergens.update(_inferred_allergens(description))
        candidate = {
            "id": f"internal_fdc_{fdc_id}",
            "seed_id": idea.get("seed_id"),
            "fdc_id": fdc_id,
            "name": str(idea.get("name") or match.get("display_name") or description).strip(),
            "search_query": description,
            "serving_g": round(max(5.0, min(_number(idea.get("serving_g")) or 100.0, 500.0)), 1),
            "meal_roles": [
                str(role).strip().lower()
                for role in idea.get("meal_roles", [])
                if str(role).strip()
            ],
            "diet_tags": list(idea.get("diet_tags") or _diet_tags(group)),
            "allergens": sorted(allergens),
            "nutrients": nutrients,
            "candidate_source": "internal_usda_verified",
            "food_group": group,
            "data_type": match.get("data_type"),
            "food_category": match.get("food_category"),
            "focus_nutrients": list(idea.get("focus_nutrients", [])),
            "nutrient_source": "USDA FoodData Central",
        }
        candidates.append(candidate)
        if len(candidates) >= maximum_candidates:
            break

    if not candidates:
        return _fallback_result(fallback_candidates, "no_usda_verified_internal_candidates")

    return candidates, {
        "provider_version": DYNAMIC_CANDIDATE_PROVIDER_VERSION,
        "mode": "internal_food_base_usda_verified",
        "reason": None,
        "llm_used": False,
        "internal_food_base_size": len(RECOMMENDATION_FOOD_BASE),
        "internal_candidates_searched": len(ideas),
        "usda_verified_candidates": len(candidates),
        "candidate_universe": "Quinone internal food base; nutrients verified by USDA FoodData Central",
    }
