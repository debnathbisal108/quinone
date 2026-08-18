"""Optional pre-analysis nutrient guidance for editable meal drafts.

Alerts are calculated only from nutrient profiles already attached to the
user-selected USDA foods (and authoritative label foods). Suggested foods are
ideas to search/select; their values never alter the draft until selected and
resolved through the normal USDA workflow.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

from nutrient_target_engine import calculate_nutrient_targets
from nutrient_target_data import CANONICAL_KEY_COMPATIBILITY
from personalization_engine import normalize_user_profile
from recommendation_catalog import FOOD_RECOMMENDATION_CATALOG
from recommendation_engine import (
    _analyze_food_set,
    _candidate_already_present,
    _candidate_eligibility,
    _domain_score_items,
    _meal_compatibility,
    _personalized_upper_limit_safe,
    _protected_domain_decline_items,
    _scaled_candidate_food,
)


GUIDANCE_ENGINE_VERSION = "1.7.0"

_LABELS: dict[str, tuple[str, str]] = {
    "energy_kcal": ("Energy", "kcal"),
    "protein_g": ("Protein", "g"),
    "carbohydrate_g": ("Carbohydrate", "g"),
    "fat_g": ("Total fat", "g"),
    "fiber_g": ("Fiber", "g"),
    "saturated_fat_g": ("Saturated fat", "g"),
    "trans_fat_g": ("Trans fat", "g"),
    "added_sugars_g": ("Added sugar", "g"),
    "sugars_g": ("Total sugar", "g"),
    "sodium_mg": ("Sodium", "mg"),
    "calcium_mg": ("Calcium", "mg"),
    "iron_mg": ("Iron", "mg"),
    "magnesium_mg": ("Magnesium", "mg"),
    "phosphorus_mg": ("Phosphorus", "mg"),
    "potassium_mg": ("Potassium", "mg"),
    "zinc_mg": ("Zinc", "mg"),
    "vitamin_a_ug": ("Vitamin A", "µg"),
    "vitamin_c_mg": ("Vitamin C", "mg"),
    "vitamin_d_ug": ("Vitamin D", "µg"),
    "vitamin_e_mg": ("Vitamin E", "mg"),
    "vitamin_k_ug": ("Vitamin K", "µg"),
    "thiamin_mg": ("Thiamin", "mg"),
    "riboflavin_mg": ("Riboflavin", "mg"),
    "niacin_mg": ("Niacin", "mg"),
    "pantothenic_acid_mg": ("Pantothenic acid", "mg"),
    "vitamin_b6_mg": ("Vitamin B6", "mg"),
    "folate_ug": ("Folate", "µg"),
    "vitamin_b12_ug": ("Vitamin B12", "µg"),
    "choline_mg": ("Choline", "mg"),
    "copper_mg": ("Copper", "mg"),
    "manganese_mg": ("Manganese", "mg"),
    "selenium_ug": ("Selenium", "µg"),
    "iodine_ug": ("Iodine", "µg"),
    "chromium_ug": ("Chromium", "µg"),
    "molybdenum_ug": ("Molybdenum", "µg"),
    "biotin_ug": ("Biotin", "µg"),
    "chloride_mg": ("Chloride", "mg"),
    "cholesterol_mg": ("Cholesterol", "mg"),
    "fluoride_mg": ("Fluoride", "mg"),
    "linoleic_acid_g": ("Linoleic acid", "g"),
    "alpha_linolenic_acid_g": ("Alpha-linolenic acid", "g"),
}

_MACRO_ORDER = ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "fiber_g")
_MACROS = set(_MACRO_ORDER)
_NO_SHORTFALL_KEYS = {
    "sodium_mg",
    "saturated_fat_g",
    "trans_fat_g",
    "added_sugars_g",
    "sugars_g",
    "cholesterol_mg",
}
_HARD_DAILY_CAPS = {
    "sodium_mg": 2300.0,
    "saturated_fat_g": 20.0,
    "added_sugars_g": 50.0,
    "trans_fat_g": 2.0,
}

# General adult reference values used only when the user has not supplied
# enough profile data for the nutrient target engine to resolve a target.
# They are guidance references, not personalized prescriptions. A resolved
# personalized target (and especially requires_clinical_input) always wins.
_GENERIC_REFERENCE_TARGETS: dict[str, dict[str, Any]] = {
    "energy_kcal": {"target_type": "reference_range", "range_low": 1800.0, "range_high": 2400.0, "resolved_unit": "kcal/day"},
    "protein_g": {"target_type": "reference", "resolved_value": 50.0, "resolved_unit": "g/day"},
    "carbohydrate_g": {"target_type": "reference_range", "range_low": 220.0, "range_high": 330.0, "resolved_unit": "g/day"},
    "fat_g": {"target_type": "reference_range", "range_low": 62.4, "range_high": 93.6, "resolved_unit": "g/day"},
    "fiber_g": {"target_type": "minimum", "resolved_value": 28.0, "resolved_unit": "g/day"},
    "vitamin_a_ug": {"target_type": "minimum", "resolved_value": 900.0, "resolved_unit": "ug/day"},
    "vitamin_c_mg": {"target_type": "minimum", "resolved_value": 90.0, "resolved_unit": "mg/day"},
    "vitamin_d_ug": {"target_type": "minimum", "resolved_value": 20.0, "resolved_unit": "ug/day"},
    "vitamin_e_mg": {"target_type": "minimum", "resolved_value": 15.0, "resolved_unit": "mg/day"},
    "vitamin_k_ug": {"target_type": "minimum", "resolved_value": 120.0, "resolved_unit": "ug/day"},
    "thiamin_mg": {"target_type": "minimum", "resolved_value": 1.2, "resolved_unit": "mg/day"},
    "riboflavin_mg": {"target_type": "minimum", "resolved_value": 1.3, "resolved_unit": "mg/day"},
    "niacin_mg": {"target_type": "minimum", "resolved_value": 16.0, "resolved_unit": "mg/day"},
    "pantothenic_acid_mg": {"target_type": "minimum", "resolved_value": 5.0, "resolved_unit": "mg/day"},
    "vitamin_b6_mg": {"target_type": "minimum", "resolved_value": 1.7, "resolved_unit": "mg/day"},
    "folate_ug": {"target_type": "minimum", "resolved_value": 400.0, "resolved_unit": "ug/day"},
    "vitamin_b12_ug": {"target_type": "minimum", "resolved_value": 2.4, "resolved_unit": "ug/day"},
    "choline_mg": {"target_type": "minimum", "resolved_value": 550.0, "resolved_unit": "mg/day"},
    "biotin_ug": {"target_type": "minimum", "resolved_value": 30.0, "resolved_unit": "ug/day"},
    "calcium_mg": {"target_type": "minimum", "resolved_value": 1300.0, "resolved_unit": "mg/day"},
    "iron_mg": {"target_type": "minimum", "resolved_value": 18.0, "resolved_unit": "mg/day"},
    "magnesium_mg": {"target_type": "minimum", "resolved_value": 420.0, "resolved_unit": "mg/day"},
    "phosphorus_mg": {"target_type": "minimum", "resolved_value": 1250.0, "resolved_unit": "mg/day"},
    "potassium_mg": {"target_type": "minimum", "resolved_value": 4700.0, "resolved_unit": "mg/day"},
    "zinc_mg": {"target_type": "minimum", "resolved_value": 11.0, "resolved_unit": "mg/day"},
    "copper_mg": {"target_type": "minimum", "resolved_value": 0.9, "resolved_unit": "mg/day"},
    "manganese_mg": {"target_type": "minimum", "resolved_value": 2.3, "resolved_unit": "mg/day"},
    "selenium_ug": {"target_type": "minimum", "resolved_value": 55.0, "resolved_unit": "ug/day"},
    "iodine_ug": {"target_type": "minimum", "resolved_value": 150.0, "resolved_unit": "ug/day"},
    "chromium_ug": {"target_type": "minimum", "resolved_value": 35.0, "resolved_unit": "ug/day"},
    "molybdenum_ug": {"target_type": "minimum", "resolved_value": 45.0, "resolved_unit": "ug/day"},
    "chloride_mg": {"target_type": "minimum", "resolved_value": 2300.0, "resolved_unit": "mg/day"},
}

# Aliases that require an actual scale conversion. The compatibility registry
# supplies all of the 1:1 aliases automatically below.
_ALIAS_SCALES: dict[tuple[str, str], float] = {
    ("vitamin_d_ug", "vitamin_d_iu"): 0.025,
    ("copper_mg", "copper_ug"): 0.001,
    ("copper_mg", "copper_mcg"): 0.001,
}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _unwrap_result(result: dict[str, Any]) -> dict[str, Any]:
    for key in ("final_result", "meal_analysis", "data", "result"):
        nested = result.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("meal"), dict):
            return nested
    return result


def _foods(result: dict[str, Any]) -> list[dict[str, Any]]:
    raw = _unwrap_result(result).get("meal", {}).get("foods", [])
    return [food for food in raw if isinstance(food, dict)] if isinstance(raw, list) else []


def _day_foods(today_results: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    foods: list[dict[str, Any]] = []
    seen_results: set[str] = set()
    for index, result in enumerate(today_results, start=1):
        if not isinstance(result, dict):
            continue
        root = _unwrap_result(result)
        identity = str(
            result.get("analysis_id")
            or root.get("analysis_id")
            or f"history_{index}"
        )
        if identity in seen_results:
            continue
        seen_results.add(identity)
        foods.extend(_foods(root))
    return foods


def _combined_totals(*sources: dict[str, float]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for source in sources:
        for key, value in source.items():
            totals[key] = totals.get(key, 0.0) + value
    return {key: round(value, 4) for key, value in totals.items()}


def _label_and_unit(
    key: str,
    target: dict[str, Any] | None = None,
) -> tuple[str, str]:
    known = _LABELS.get(key)
    if known is not None:
        return known
    target = target if isinstance(target, dict) else {}
    label = str(target.get("nutrient_name") or key.replace("_", " ").title())
    unit = str(target.get("resolved_unit") or "").split("/", 1)[0]
    return label, unit


def _canonical_nutrients(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    numeric: dict[str, float] = {}
    for key, raw_value in raw.items():
        value = _number(raw_value)
        if value is not None:
            numeric[str(key)] = value
    output = dict(numeric)
    for canonical, compatibility in CANONICAL_KEY_COMPATIBILITY.items():
        candidates = [canonical, *[
            str(key) for key in compatibility.get("accepted_input_keys", [])
            if str(key) != canonical
        ]]
        for alias in candidates:
            value = numeric.get(alias)
            if value is None:
                continue
            output[canonical] = value * _ALIAS_SCALES.get((canonical, alias), 1.0)
            break
    return output


def _nutrient_totals(
    foods: Iterable[dict[str, Any]],
) -> tuple[dict[str, float], set[str]]:
    totals: dict[str, float] = {}
    reported: set[str] = set()
    for food in foods:
        nutrients = _canonical_nutrients(food.get("nutrients"))
        for key, value in nutrients.items():
            reported.add(key)
            totals[key] = totals.get(key, 0.0) + value
    return ({key: round(value, 4) for key, value in totals.items()}, reported)


def _target_has_comparison_value(target: Any) -> bool:
    if not isinstance(target, dict):
        return False
    if target.get("status") == "requires_clinical_input":
        return True
    return any(
        (_number(target.get(key)) or 0.0) > 0
        for key in ("resolved_value", "baseline_value", "range_low", "range_high", "upper_limit")
    )


def _effective_targets(raw_targets: Any) -> tuple[dict[str, dict[str, Any]], set[str]]:
    targets = {
        str(key): dict(value)
        for key, value in (raw_targets.items() if isinstance(raw_targets, dict) else [])
        if isinstance(value, dict)
    }
    fallback_keys: set[str] = set()

    # A resolved energy estimate is a central estimate, not a hard cap.  Give
    # it the same +/-10% balance range used by the post-analysis recommender so
    # genuinely excessive energy can be flagged without treating the exact EER
    # as a limit.
    energy = targets.get("energy_kcal")
    if isinstance(energy, dict) and energy.get("status") != "requires_clinical_input":
        has_energy_range = (
            (_number(energy.get("range_low")) or 0.0) > 0
            and (_number(energy.get("range_high")) or 0.0) > 0
        )
        resolved_energy = _number(energy.get("resolved_value"))
        if not has_energy_range and resolved_energy is not None and resolved_energy > 0:
            targets["energy_kcal"] = {
                **energy,
                "target_type": "reference_range",
                "range_low": round(resolved_energy * 0.90, 2),
                "range_high": round(resolved_energy * 1.10, 2),
                "derived_from_energy_estimate": True,
            }

    # A carbohydrate RDA is a minimum reference, not an upper edge.  The target
    # registry currently exposes 130 g/day as the RDA even when the user's
    # energy target is known.  Using that value as a meal "high" threshold
    # would falsely flag ordinary carbohydrate portions.  Prefer an AMDR-style
    # range derived from resolved energy; otherwise use the generic reference
    # range until enough profile data exists.
    carbohydrate = targets.get("carbohydrate_g")
    if isinstance(carbohydrate, dict) and carbohydrate.get("status") != "requires_clinical_input":
        has_range = (
            (_number(carbohydrate.get("range_low")) or 0.0) > 0
            and (_number(carbohydrate.get("range_high")) or 0.0) > 0
        )
        target_type = str(carbohydrate.get("target_type") or "").lower()
        if not has_range and target_type in {"rda", "ai", "minimum", "reference"}:
            energy = targets.get("energy_kcal")
            resolved_energy = (
                _number(energy.get("resolved_value"))
                if isinstance(energy, dict)
                else None
            )
            if resolved_energy is not None and resolved_energy > 0:
                targets["carbohydrate_g"] = {
                    **carbohydrate,
                    "target_type": "AMDR",
                    "range_low": round(resolved_energy * 0.45 / 4.0, 2),
                    "range_high": round(resolved_energy * 0.65 / 4.0, 2),
                    "generic_reference": False,
                    "derived_from_energy_target": True,
                }
            else:
                fallback = _GENERIC_REFERENCE_TARGETS["carbohydrate_g"]
                targets["carbohydrate_g"] = {
                    **carbohydrate,
                    **fallback,
                    "nutrient_name": (_LABELS.get("carbohydrate_g") or ("Carbohydrate", ""))[0],
                    "status": "generic_reference",
                    "generic_reference": True,
                }
                fallback_keys.add("carbohydrate_g")

    for key, fallback in _GENERIC_REFERENCE_TARGETS.items():
        if _target_has_comparison_value(targets.get(key)):
            continue
        targets[key] = {
            **fallback,
            "nutrient_name": (_LABELS.get(key) or (key, ""))[0],
            "status": "generic_reference",
            "generic_reference": True,
        }
        fallback_keys.add(key)
    return targets, fallback_keys


def _target_value(target: dict[str, Any]) -> float | None:
    # For a true range/AMDR the lower edge is the shortfall reference.  Some
    # target-engine records also retain an RDA/AI in resolved_value (notably
    # carbohydrate), and using that first can hide a genuine meal shortfall.
    target_type = str(target.get("target_type") or "").lower()
    range_low = _number(target.get("range_low"))
    range_high = _number(target.get("range_high"))
    if (
        range_low is not None
        and range_low > 0
        and (range_high is not None and range_high > 0)
        and (
            "range" in target_type
            or "amdr" in target_type
            or target_type == ""
        )
    ):
        return range_low
    for key in ("resolved_value", "range_low", "baseline_value"):
        value = _number(target.get(key))
        if value is not None and value > 0:
            return value
    return None


def _target_high(target: dict[str, Any]) -> float | None:
    for key in ("range_high", "resolved_value", "baseline_value"):
        value = _number(target.get(key))
        if value is not None and value > 0:
            return value
    return None


def _actual_upper_target(target: dict[str, Any]) -> float | None:
    """Return a real daily upper edge, never a minimum mislabeled as a cap."""
    range_high = _number(target.get("range_high"))
    if range_high is not None and range_high > 0:
        return range_high
    if str(target.get("target_type") or "").lower() == "maximum":
        for key in ("upper_limit", "resolved_value", "baseline_value"):
            value = _number(target.get(key))
            if value is not None and value > 0:
                return value
    return None


def _meal_fraction(meal_name: str) -> float:
    lowered = meal_name.lower()
    if any(token in lowered for token in ("snack", "dessert", "drink")):
        return 0.15
    return 0.30


def _contributors(
    foods: list[dict[str, Any]],
    nutrient_key: str,
    maximum: int = 12,
) -> list[dict[str, Any]]:
    rows: list[tuple[float, str, str, float, str]] = []
    for food in foods:
        value = _canonical_nutrients(food.get("nutrients")).get(nutrient_key, 0.0)
        if value <= 0:
            continue
        name = str(food.get("display_name") or food.get("name") or "Food")
        quantity = _number(
            food.get("estimated_weight_g") or food.get("quantity")
        ) or 0.0
        rows.append((
            value,
            name,
            str(food.get("id") or ""),
            quantity,
            str(food.get("unit") or "g"),
        ))
    rows.sort(reverse=True)
    return [
        {
            "name": name,
            "food_id": food_id,
            "amount": round(value, 4),
            "quantity": round(quantity, 3),
            "quantity_unit": quantity_unit,
        }
        for value, name, food_id, quantity, quantity_unit in rows[:maximum]
    ]


def _suggestions(
    *,
    nutrient_key: str,
    direction: str,
    profile: dict[str, Any],
    draft_result: dict[str, Any],
    foods: list[dict[str, Any]],
    local_hour: int,
    projected_totals: dict[str, float],
) -> list[dict[str, Any]]:
    # Excess is corrected by changing the contributing food quantity inside
    # Meal Guidance. Never recommend another food for an excess alert.
    if direction == "excess":
        return []

    ranked: list[tuple[float, dict[str, Any]]] = []

    for candidate in FOOD_RECOMMENDATION_CATALOG:
        if _candidate_already_present(candidate, foods):
            continue
        allowed, _, _ = _candidate_eligibility(candidate, profile)
        compatible, _ = _meal_compatibility(candidate, draft_result, foods, local_hour)
        if not allowed or not compatible:
            continue
        serving = float(candidate.get("serving_g") or 100.0)
        upper_safe, _ = _personalized_upper_limit_safe(candidate, profile, projected_totals, serving_g=serving)
        if not upper_safe:
            continue
        per100 = _number((candidate.get("nutrients") or {}).get(nutrient_key)) or 0.0
        amount = per100 * serving / 100.0
        if amount <= 0:
            continue
        energy = _number((candidate.get("nutrients") or {}).get("energy_kcal")) or 1.0
        rank = amount / max(energy * serving / 100.0, 1.0)
        ranked.append((rank, candidate))
    ranked.sort(key=lambda row: row[0], reverse=True)
    return [
        {
            "type": "add",
            "name": candidate["name"],
            "search_query": candidate["search_query"],
            "quantity": round(float(candidate.get("serving_g") or 100.0), 1),
            "unit": "g",
            "reason": f"Add a source of {(_LABELS.get(nutrient_key) or (nutrient_key, ''))[0].lower()}.",
            "nutrient_basis": "idea_only_until_usda_selection",
        }
        for _, candidate in ranked[:2]
    ]


async def apply_personalized_guidance_safety(
    guidance: dict[str, Any],
    nutrient_result: dict[str, Any],
    *,
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = normalize_user_profile(profile)
    conditions = normalized.get("chronic_conditions") or []
    if not conditions:
        return guidance
    foods = _foods(nutrient_result)
    if not foods:
        return guidance
    meal_type = str(nutrient_result.get("meal", {}).get("meal_type") or nutrient_result.get("meal", {}).get("meal_name") or "Draft meal")
    baseline = await _analyze_food_set(foods, normalized, meal_type=meal_type)
    before_domains = _domain_score_items(baseline)
    catalog_by_query = {str(item.get("search_query") or "").strip().lower(): item for item in FOOD_RECOMMENDATION_CATALOG}
    catalog_by_name = {str(item.get("name") or "").strip().lower(): item for item in FOOD_RECOMMENDATION_CATALOG}
    output = dict(guidance); filtered_alerts=[]; candidate_index=0
    for raw_alert in guidance.get("alerts", []):
        if not isinstance(raw_alert, dict):
            continue
        alert = dict(raw_alert); safe_suggestions=[]
        for raw_suggestion in alert.get("suggestions", []):
            if not isinstance(raw_suggestion, dict):
                continue
            suggestion = dict(raw_suggestion)
            query = str(suggestion.get("search_query") or "").strip().lower(); name = str(suggestion.get("name") or "").strip().lower()
            candidate = catalog_by_query.get(query) or catalog_by_name.get(name)
            if candidate is None:
                continue
            allowed,audit,reasons = _candidate_eligibility(candidate, normalized)
            if not allowed:
                continue
            grams = _number(suggestion.get("quantity")) or _number(candidate.get("serving_g")) or 100.0
            candidate_index += 1
            addition = _scaled_candidate_food(candidate, grams, candidate_index)
            simulated = await _analyze_food_set([*foods, addition], normalized, meal_type=meal_type)
            after_domains = _domain_score_items(simulated)
            protected_decline = _protected_domain_decline_items(before_domains, after_domains, normalized)
            if protected_decline > 0.75:
                continue
            suggestion["personalization_safety"] = {**audit, "condition_domains_verified": True, "max_protected_domain_decline": round(protected_decline,3), "profile_applied": True, "rejection_reasons": reasons}
            safe_suggestions.append(suggestion)
        alert["suggestions"] = safe_suggestions
        filtered_alerts.append(alert)
    output["alerts"] = filtered_alerts
    output["personalization_safety_applied"] = True
    return output


def build_draft_meal_guidance(
    nutrient_result: dict[str, Any],
    *,
    profile: dict[str, Any] | None,
    local_hour: int = 12,
    today_results: Iterable[dict[str, Any]] = (),
    include_shortfalls: bool = True,
) -> dict[str, Any]:
    normalized_profile = normalize_user_profile(profile)
    foods = _foods(nutrient_result)
    draft_totals, reported = _nutrient_totals(foods)
    history_foods = _day_foods(today_results)
    history_totals, history_reported = _nutrient_totals(history_foods)
    projected_totals = _combined_totals(history_totals, draft_totals)
    meal_name = str(
        nutrient_result.get("meal", {}).get("meal_name")
        or nutrient_result.get("meal", {}).get("meal_type")
        or "Meal"
    )
    fraction = _meal_fraction(meal_name)
    target_result = calculate_nutrient_targets(normalized_profile)
    targets, fallback_target_keys = _effective_targets(target_result.get("targets", {}))
    alerts: list[dict[str, Any]] = []
    clinical_keys = {
        key
        for key, target in targets.items() if isinstance(targets, dict)
        if isinstance(target, dict)
        and target.get("status") == "requires_clinical_input"
    }

    for key in sorted(clinical_keys & reported):
        if key not in {"protein_g", "sodium_mg", "potassium_mg", "phosphorus_mg"}:
            continue
        label, unit = _label_and_unit(key, targets.get(key))
        alerts.append({
            "direction": "clinical",
            "severity": "notice",
            "nutrient": key,
            "label": label,
            "amount": round(max(0.0, projected_totals.get(key, 0.0)), 2),
            "unit": unit,
            "reference": 0.0,
            "percentage": 0.0,
            "message": (
                f"Your profile requires clinical inputs before Quinone can classify this meal's "
                f"{label.lower()} as high or low. The current amount is shown without a target judgment."
            ),
            "contributors": _contributors(foods, key),
            "suggestions": [],
        })

    # Macro excesses use the projected DAY total, not an arbitrary per-meal
    # allocation.  The old 30% meal-share check could keep an orange
    # "exceeded" card alive even after the adjusted amount was below the
    # displayed daily reference.  A meal-share remains useful for shortfall
    # guidance below, but it is not an upper limit.
    #
    # Range nutrients (energy/carbohydrate/fat) use their real upper range
    # edge. Protein normally has a minimum/reference rather than a medical UL;
    # for optional balance guidance only, allow a 20% buffer above that daily
    # reference, matching the post-analysis recommendation engine.
    for key in _MACRO_ORDER:
        if key not in reported or key in clinical_keys:
            continue
        target = targets.get(key) if isinstance(targets, dict) else None
        if not isinstance(target, dict):
            continue

        daily_high = _actual_upper_target(target)
        protein_reference = False
        if key == "protein_g" and daily_high is None:
            protein_base = _target_value(target)
            if protein_base is not None and protein_base > 0:
                daily_high = protein_base * 1.20
                protein_reference = True

        # Fiber and any other minimum-only macro have no upper edge and must
        # not be called excessive merely for exceeding a meal allocation.
        if daily_high is None or daily_high <= 0:
            continue

        projected_amount = max(0.0, projected_totals.get(key, 0.0))
        ratio = projected_amount / daily_high
        if ratio <= 1.0:
            continue

        label, unit = _label_and_unit(key, target)
        generic_reference = bool(target.get("generic_reference"))
        if protein_reference:
            message = (
                f"With this draft, today's total is above the general daily protein guidance reference; "
                "this is balance guidance, not a medical upper limit."
                if generic_reference
                else f"With this draft, today's total is above your personalized daily protein guidance reference; "
                "this is balance guidance, not a medical upper limit."
            )
        else:
            message = (
                f"With this draft, today's total exceeds the daily upper reference for {label.lower()}."
                if generic_reference
                else f"With this draft, today's total exceeds your personalized daily upper target for {label.lower()}."
            )

        alerts.append({
            "direction": "excess",
            "severity": "critical" if not protein_reference else "warning",
            "nutrient": key,
            "label": label,
            "amount": round(projected_amount, 2),
            "unit": unit,
            "reference": round(daily_high, 2),
            "percentage": round(ratio * 100.0, 1),
            "message": message,
            "contributors": _contributors(foods, key),
            "suggestions": _suggestions(
                nutrient_key=key,
                direction="excess",
                profile=normalized_profile,
                draft_result=nutrient_result,
                foods=foods,
                local_hour=local_hour,
                projected_totals=projected_totals,
            ),
        })

    caps = dict(_HARD_DAILY_CAPS)
    for key, target in targets.items() if isinstance(targets, dict) else []:
        upper = _number(target.get("upper_limit")) if isinstance(target, dict) else None
        upper_scope = str(target.get("upper_limit_scope") or "").lower()
        is_food_applicable = not any(
            token in upper_scope
            for token in ("supplement", "added_folic_acid")
        )
        if upper is not None and upper > 0 and is_food_applicable:
            caps[key] = min(caps.get(key, upper), upper)

    for key, cap in caps.items():
        if key not in reported or key in clinical_keys or cap <= 0:
            continue
        amount = max(0.0, projected_totals.get(key, 0.0))
        ratio = amount / cap
        if ratio <= 1.0:
            continue
        target = targets.get(key) if isinstance(targets, dict) else None
        label, unit = _label_and_unit(key, target)
        severity = "critical"
        alerts.append({
            "direction": "excess",
            "severity": severity,
            "nutrient": key,
            "label": label,
            "amount": round(amount, 2),
            "unit": unit,
            "reference": round(cap, 2),
            "percentage": round(ratio * 100.0, 1),
            "message": f"With this draft, today's total exceeds the daily limit for {label.lower()}.",
            "contributors": _contributors(foods, key),
            "suggestions": _suggestions(
                nutrient_key=key,
                direction="excess",
                profile=normalized_profile,
                draft_result=nutrient_result,
                foods=foods,
                local_hour=local_hour,
                projected_totals=projected_totals,
            ),
        })

    # Defensive invariant: an excess card must never leave the backend with a
    # value already at/below its own displayed reference.  This also protects
    # clients from stale or mixed target-shape edge cases.
    alerts = [
        alert for alert in alerts
        if alert.get("direction") != "excess"
        or (_number(alert.get("percentage")) or 0.0) > 100.0
    ]

    excess_nutrients = {
        str(alert.get("nutrient"))
        for alert in alerts
        if alert.get("direction") == "excess"
    }
    shortfall_keys = list(_MACRO_ORDER) if include_shortfalls else []
    if include_shortfalls and isinstance(targets, dict):
        shortfall_keys.extend(
            key for key in targets
            if key not in _MACROS and key not in _NO_SHORTFALL_KEYS
        )
    shortfalls: list[tuple[int, float, dict[str, Any]]] = []
    for key in dict.fromkeys(shortfall_keys):
        if (
            key not in reported
            or key in clinical_keys
            or key in excess_nutrients
        ):
            continue
        target = targets.get(key) if isinstance(targets, dict) else None
        if not isinstance(target, dict):
            continue
        target_type = str(target.get("target_type") or "").lower()
        if "maximum" in target_type or "upper" in target_type:
            continue
        daily = _target_value(target)
        if daily is None:
            continue
        expected = daily * fraction
        amount = max(0.0, draft_totals.get(key, 0.0))
        ratio = amount / expected if expected > 0 else 1.0
        if ratio >= 0.80:
            continue
        label, unit = _label_and_unit(key, target)
        generic_reference = bool(target.get("generic_reference"))
        alert = {
            "direction": "low",
            "severity": "notice",
            "nutrient": key,
            "label": label,
            "amount": round(amount, 2),
            "unit": unit,
            "reference": round(expected, 2),
            "percentage": round(ratio * 100.0, 1),
            "message": (
                f"{label} is low for this meal's {fraction * 100:.0f}% share of the general daily reference; "
                "this is not a diagnosis of a daily deficiency."
                if generic_reference
                else f"{label} is low for this meal's {fraction * 100:.0f}% share of the personalized daily target; "
                "this is not a diagnosis of a daily deficiency."
            ),
            "contributors": _contributors(foods, key),
            "suggestions": _suggestions(
                nutrient_key=key,
                direction="low",
                profile=normalized_profile,
                draft_result=nutrient_result,
                foods=foods,
                local_hour=local_hour,
                projected_totals=projected_totals,
            ),
        }
        shortfalls.append((0 if key in _MACROS else 1, ratio, alert))
    shortfalls.sort(key=lambda row: (row[0], row[1]))
    alerts.extend(alert for _, _, alert in shortfalls)

    severity_order = {"critical": 0, "warning": 1, "notice": 2}
    alerts.sort(key=lambda item: severity_order.get(str(item.get("severity")), 9))
    return {
        "status": "completed",
        "engine_version": GUIDANCE_ENGINE_VERSION,
        "optional": True,
        "can_continue": True,
        "meal_target_fraction": fraction,
        "alerts": alerts,
        "summary": {
            "critical_count": sum(item["severity"] == "critical" for item in alerts),
            "warning_count": sum(item["severity"] == "warning" for item in alerts),
            "low_count": sum(item["direction"] == "low" for item in alerts),
        },
        "data_quality": {
            "foods_checked": len(foods),
            "reported_nutrients": len(reported),
            "today_history_foods_checked": len(history_foods),
            "today_history_reported_nutrients": len(history_reported),
            "projected_day_totals_used_for_excess": True,
            "shortfalls_included": include_shortfalls,
            "generic_reference_targets_used": sorted(fallback_target_keys),
            "personalized_targets_preferred_when_available": True,
            "uses_selected_usda_or_label_values": True,
            "unreported_nutrients_treated_as_low": False,
        },
        "message": (
            "No material nutrient balance alerts were found for this draft."
            if not alerts
            else "Review these optional alerts or continue without changing the meal."
        ),
        "disclaimer": (
            "Meal shortfalls use an estimated share of daily targets and appear only after Analyze is tapped. "
            "Food suggestions appear only for shortfalls. Excess alerts are adjusted by changing food "
            "quantity in 10% steps."
        ),
    }
