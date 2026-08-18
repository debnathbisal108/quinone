"""Dynamic recommendation-candidate discovery for Quinone.

Gemini is used only as a *query planner*: it proposes diverse single-food ideas
that fit the meal context. Every proposed food must then resolve to a real USDA
FoodData Central record, and all nutrient/scoring/safety decisions are made by
Quinone's deterministic pipeline. The small curated catalogue is retained only
as a resilient fallback when Gemini or USDA discovery is unavailable.
"""

from __future__ import annotations

import asyncio
import copy
import inspect
import json
import logging
import os
import re
from typing import Any, Iterable

from nutrient_profile import attach_nutrients
from usda_recipe_service import search_usda_foods

logger = logging.getLogger("quinone.recommendation_candidates")

DYNAMIC_CANDIDATE_PROVIDER_VERSION = "1.2.0"

_ENABLE_DYNAMIC = os.environ.get(
    "ENABLE_DYNAMIC_RECOMMENDATION_DISCOVERY", "true"
).strip().lower() in {"1", "true", "yes", "on"}
_GEMINI_MODEL = (
    os.environ.get("GEMINI_RECOMMENDATION_MODEL", "").strip()
    or os.environ.get("GEMINI_MEAL_MODEL", "").strip()
    or "gemini-3.5-flash"
)
_MAX_IDEAS = max(6, min(int(os.environ.get("RECOMMENDATION_IDEA_COUNT", "16")), 24))

_IDEA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "foods": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "usda_search_query": {"type": "string"},
                    "serving_g": {"type": "number"},
                    "meal_roles": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "breakfast", "lunch", "dinner", "snack",
                                "dessert", "side", "topping",
                            ],
                        },
                    },
                    "food_group": {
                        "type": "string",
                        "enum": ["plant", "dairy", "egg", "fish", "meat"],
                    },
                    "allergens": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "milk", "dairy", "egg", "fish", "shellfish",
                                "tree_nuts", "peanut", "soy", "wheat",
                                "gluten", "sesame",
                            ],
                        },
                    },
                    "why_candidate": {"type": "string"},
                },
                "required": [
                    "name", "usda_search_query", "serving_g", "meal_roles",
                    "food_group", "allergens", "why_candidate",
                ],
            },
        }
    },
    "required": ["foods"],
}

_PREPARATION_TOKENS = {
    "raw", "cooked", "boiled", "steamed", "roasted", "baked", "fried",
    "fresh", "frozen", "dried", "dry", "plain", "unsalted", "salted",
    "without", "with", "prepared", "ready", "eat", "whole", "chopped",
}

# Conservative identity-based allergen enrichment. This is not the sole safety
# gate; the recommendation engine still applies profile restrictions and full
# nutrient/domain simulation. It prevents an LLM omission from being the only
# thing standing between a clearly allergenic whole food and an allergy profile.

_COMMON_ENGLISH_ALIASES: dict[str, str] = {
    "rajma": "Kidney beans",
    "rajmah": "Kidney beans",
    "chana": "Chickpeas",
    "kabuli chana": "Chickpeas",
    "moong": "Mung beans",
    "moong dal": "Mung beans",
    "mung dal": "Mung beans",
    "bhindi": "Okra",
    "brinjal": "Eggplant",
    "aubergine": "Eggplant",
    "capsicum": "Bell pepper",
    "groundnut": "Peanuts",
}


def _common_english_display_name(value: Any) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").strip())
    key = re.sub(r"[^a-z0-9 ]+", "", cleaned.lower()).strip()
    return _COMMON_ENGLISH_ALIASES.get(key, cleaned)

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


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed and parsed not in {float("inf"), float("-inf")} else None


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
        # Requiring a meaningful overlap is intentionally conservative for
        # single-ingredient recommendations: recommending another form of an
        # already logged food is usually less useful than offering variety.
        if candidate & existing:
            return True
    return False


def _diet_tags(food_group: str) -> list[str]:
    group = str(food_group or "").strip().lower()
    if group == "plant":
        return ["vegan", "vegetarian"]
    if group == "dairy":
        return ["vegetarian"]
    if group == "egg":
        return ["ovo_vegetarian"]
    if group == "fish":
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
        return "fish"
    if any(term in text for term in _ALLERGEN_TERMS["fish"]):
        return "fish"
    if re.search(r"\begg(s)?\b", text):
        return "egg"
    if any(term in text for term in ("beef", "pork", "chicken", "turkey", "lamb", "mutton", "goat", "venison", "meat")):
        return "meat"
    if any(term in text for term in _ALLERGEN_TERMS["milk"]):
        return "dairy"
    return "plant"


def _minimal_profile_context(profile: dict[str, Any]) -> dict[str, Any]:
    """Only send fields that help candidate ideation; medical scoring stays local."""
    return {
        key: copy.deepcopy(profile.get(key))
        for key in (
            "diet_type", "diet_pattern", "allergies", "intolerances",
            "food_intolerances", "excluded_foods", "disliked_foods",
        )
        if profile.get(key) not in (None, "", [], {})
    }


def _meal_context(current_result: dict[str, Any], current_foods: list[dict[str, Any]]) -> dict[str, Any]:
    root = current_result
    for key in ("final_result", "meal_analysis", "data", "result"):
        nested = root.get(key) if isinstance(root, dict) else None
        if isinstance(nested, dict) and isinstance(nested.get("meal"), dict):
            root = nested
            break
    meal = root.get("meal", {}) if isinstance(root, dict) else {}
    return {
        "meal_type": meal.get("meal_type") or meal.get("meal_name") or "Current meal",
        "foods_already_present": [
            str(food.get("display_name") or food.get("name") or food.get("canonical_name") or "")
            for food in current_foods
            if str(food.get("display_name") or food.get("name") or food.get("canonical_name") or "").strip()
        ],
    }


def _planner_prompt(
    *,
    current_result: dict[str, Any],
    current_foods: list[dict[str, Any]],
    profile: dict[str, Any],
    target_domains: list[dict[str, Any]],
    target_nutrients: list[str],
    local_hour: int,
    maximum_ideas: int,
) -> str:
    context = {
        "meal": _meal_context(current_result, current_foods),
        "user_food_constraints": _minimal_profile_context(profile),
        "target_health_domains": target_domains,
        "target_nutrients": target_nutrients,
        "local_hour": max(0, min(int(local_hour), 23)),
    }
    return f"""
You are a food-candidate planner for a nutrition application. Generate up to
{maximum_ideas} DIVERSE single-food candidates that could plausibly complement
the current meal and help one or more target nutrients/health domains.

IMPORTANT:
- You are NOT the nutrition authority and must not provide nutrient numbers.
- Return ordinary single foods/ingredients, not supplements, medicines,
  restaurant dishes, proprietary products, recipes, or multi-ingredient meals.
- Prefer foods that can be resolved in USDA FoodData Central using a short,
  generic English query. Foods from any cuisine are eligible, but do NOT infer
  or personalize by country, region, nationality, ethnicity, IP/location,
  timezone, locale, or cuisine. No geographic context is supplied or allowed.
- The `name` field MUST be a concise, widely understood American-English common
  food name. If a regional/local-language name has a standard English identity,
  use the English identity (for example: kidney beans, chickpeas, mung beans,
  okra, eggplant, bell pepper, peanuts). Do not use regional vernacular merely
  because the food is common in a particular country.
- Do not repeat anything already in foods_already_present, including another
  preparation of substantially the same food.
- Respect the supplied diet/allergy/intolerance/excluded-food constraints.
- Make the list diverse across food groups and food types rather than repeating
  the same few "healthy foods". Diversity must not be based on an assumed user
  location or cultural identity.
- serving_g is only a realistic screening portion; Quinone will verify and
  simulate it later.
- Keep usda_search_query concise and generic, e.g. "guava raw", "lentils cooked
  boiled without salt", "sardines canned in oil drained".

Context JSON:
{json.dumps(context, ensure_ascii=False, separators=(",", ":"))}
""".strip()


def _parse_json_text(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Gemini recommendation planner returned a non-object response.")
    return parsed


def _generate_ideas_sync(prompt: str, maximum_ideas: int) -> list[dict[str, Any]]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return []
    from google import genai
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=_GEMINI_MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": _IDEA_SCHEMA,
            "max_output_tokens": 4096,
        },
    )
    payload = _parse_json_text(response.text or "")
    raw_foods = payload.get("foods")
    if not isinstance(raw_foods, list):
        return []
    output: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    for item in raw_foods:
        if not isinstance(item, dict):
            continue
        query = re.sub(r"\s+", " ", str(item.get("usda_search_query") or "").strip())
        name = re.sub(r"\s+", " ", str(item.get("name") or "").strip())
        serving = _number(item.get("serving_g"))
        if len(query) < 2 or len(name) < 2 or serving is None or serving <= 0:
            continue
        qkey = query.lower()
        if qkey in seen_queries:
            continue
        seen_queries.add(qkey)
        clean = dict(item)
        clean["usda_search_query"] = query
        clean["name"] = name
        clean["serving_g"] = round(max(5.0, min(serving, 500.0)), 1)
        output.append(clean)
        if len(output) >= maximum_ideas:
            break
    return output


async def _search_usda_recommendation_candidate(query: str) -> list[dict[str, Any]]:
    """Search USDA without assuming a particular service-function revision.

    v24 added ``include_branded`` and ``validation_pool_size`` to
    ``search_usda_foods``. Incremental deployments can legitimately contain a
    newer dynamic candidate provider beside the older v23 search service.
    Recommendation discovery must degrade gracefully in that case rather than
    falling back solely because of a Python signature mismatch.

    On the modern service we keep the optimized non-branded, small validation
    pool. On the legacy service we request a few results and filter branded
    records below.
    """
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
            # Legacy searches return generic foods first, followed by branded
            # foods. Ask for a few so a usable generic record is still likely
            # to survive the provider-side branded filter.
            kwargs["limit"] = 3
    except (TypeError, ValueError):
        # Some test doubles / wrapped callables do not expose a reliable
        # signature. The common v23 contract is always safe.
        kwargs = {"limit": 3}

    try:
        return await search_usda_foods(query, **kwargs)
    except TypeError as error:
        message = str(error)
        if "unexpected keyword argument" not in message:
            raise
        # Last-resort compatibility for a runtime whose callable signature was
        # obscured by a wrapper. Never let an optional optimization kwarg break
        # recommendation discovery.
        logger.warning(
            "USDA search contract mismatch; retrying recommendation candidate "
            "verification with legacy arguments only: %s",
            error,
        )
        return await search_usda_foods(query, limit=3)


async def _resolve_idea_searches(ideas: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if not ideas:
        return []
    searches = await asyncio.gather(
        *[
            _search_usda_recommendation_candidate(
                str(idea["usda_search_query"]),
            )
            for idea in ideas
        ],
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
            # Branded candidates are not used for generic recommendation
            # discovery; the user's normal manual search can still find them.
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
            "id": f"dynamic_candidate_{index:03d}",
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
                "source": "dynamic_recommendation_usda",
            },
        })
    attached = await attach_nutrients({
        "status": "completed",
        "meal": {
            "meal_type": "Recommendation candidate verification",
            "foods": foods,
        },
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


def _fallback_result(fallback_candidates: Iterable[dict[str, Any]], reason: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return (
        [copy.deepcopy(item) for item in fallback_candidates],
        {
            "provider_version": DYNAMIC_CANDIDATE_PROVIDER_VERSION,
            "mode": "curated_fallback",
            "reason": reason,
            "gemini_model": None,
            "ideas_generated": 0,
            "usda_verified_candidates": 0,
        },
    )


async def rehydrate_usda_candidate(
    fdc_id: int,
    *,
    serving_g: float = 100.0,
) -> dict[str, Any] | None:
    """Rebuild a dynamic candidate from its exact FDC id for apply/revalidation.

    No client-supplied nutrient values, diet tags, or allergen tags are trusted.
    The USDA record is fetched through the existing shared detail/cache path and
    the simple-food group/allergen metadata is inferred conservatively from the
    authoritative description.
    """
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
            "source": "dynamic_recommendation_usda",
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
        "id": f"dynamic_fdc_{numeric_id}",
        "fdc_id": numeric_id,
        "name": description,
        "search_query": description,
        "serving_g": round(max(5.0, min(float(serving_g), 500.0)), 1),
        "meal_roles": [],
        "diet_tags": _diet_tags(group),
        "allergens": sorted(_inferred_allergens(description)),
        "nutrients": nutrients,
        "candidate_source": "gemini_usda_dynamic",
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
    """Discover a context-specific USDA-backed candidate pool.

    The returned candidate format intentionally matches recommendation_catalog
    so the existing deterministic eligibility, upper-limit, compatibility and
    full evidence/scoring simulation logic can be reused unchanged.
    """
    if not _ENABLE_DYNAMIC:
        return _fallback_result(fallback_candidates, "dynamic_discovery_disabled")
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        return _fallback_result(fallback_candidates, "gemini_api_key_unavailable")

    maximum_candidates = max(4, min(int(maximum_candidates), 24))
    maximum_ideas = max(maximum_candidates, min(_MAX_IDEAS, 24))
    prompt = _planner_prompt(
        current_result=current_result,
        current_foods=current_foods,
        profile=profile,
        target_domains=list(target_domains or []),
        target_nutrients=list(target_nutrients or []),
        local_hour=local_hour,
        maximum_ideas=maximum_ideas,
    )
    try:
        ideas = await asyncio.to_thread(_generate_ideas_sync, prompt, maximum_ideas)
    except Exception as error:  # model/network failure must never break analysis
        logger.warning("Gemini recommendation candidate planning failed: %s", error)
        return _fallback_result(fallback_candidates, "gemini_planning_failed")
    if not ideas:
        return _fallback_result(fallback_candidates, "gemini_returned_no_candidates")

    # Remove obvious repeats before spending USDA requests.
    ideas = [
        idea for idea in ideas
        if not _already_present(
            f"{idea.get('name', '')} {idea.get('usda_search_query', '')}",
            current_foods,
        )
    ]
    if not ideas:
        return _fallback_result(fallback_candidates, "all_planned_candidates_already_present")

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
        # A recommendation candidate with no usable energy/macronutrient data
        # cannot be simulated reliably enough to show to a user.
        if not any(
            (nutrients.get(key) or 0.0) > 0
            for key in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g")
        ):
            continue
        description = str(match.get("description") or idea.get("name") or "Food").strip()
        if _already_present(description, current_foods):
            continue
        allergens = {
            str(value).strip().lower()
            for value in idea.get("allergens", [])
            if str(value).strip()
        }
        allergens.update(_inferred_allergens(description))
        # Dietary source classification is derived from the USDA-matched
        # identity rather than trusting the LLM's proposed food_group. The LLM
        # is a planner, never a safety authority.
        group = _infer_food_group(description)
        candidate = {
            "id": f"dynamic_fdc_{fdc_id}",
            "fdc_id": fdc_id,
            "name": _common_english_display_name(
                idea.get("name") or match.get("display_name") or description
            ),
            "search_query": description,
            "serving_g": round(max(5.0, min(_number(idea.get("serving_g")) or 100.0, 500.0)), 1),
            "meal_roles": [
                str(role).strip().lower()
                for role in idea.get("meal_roles", [])
                if str(role).strip()
            ],
            "diet_tags": _diet_tags(group),
            "allergens": sorted(allergens),
            "nutrients": nutrients,
            "candidate_source": "gemini_usda_dynamic",
            "food_group": group,
            "data_type": match.get("data_type"),
            "food_category": match.get("food_category"),
            "planner_reason": str(idea.get("why_candidate") or "").strip(),
            "nutrient_source": "USDA FoodData Central",
        }
        candidates.append(candidate)
        if len(candidates) >= maximum_candidates:
            break

    if not candidates:
        return _fallback_result(fallback_candidates, "no_usda_verified_dynamic_candidates")

    return candidates, {
        "provider_version": DYNAMIC_CANDIDATE_PROVIDER_VERSION,
        "mode": "gemini_planned_usda_verified",
        "reason": None,
        "gemini_model": _GEMINI_MODEL,
        "ideas_generated": len(ideas),
        "usda_verified_candidates": len(candidates),
        "candidate_universe": "USDA FoodData Central search; curated catalogue used only as fallback",
    }
