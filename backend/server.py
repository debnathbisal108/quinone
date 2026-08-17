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
from personalization_engine import normalize_user_profile
from recommendation_catalog import FOOD_RECOMMENDATION_CATALOG
from recommendation_engine import (
    _candidate_already_present,
    _candidate_eligibility,
    _meal_compatibility,
)


GUIDANCE_ENGINE_VERSION = "1.4.0"

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


def _nutrient_totals(
    foods: Iterable[dict[str, Any]],
) -> tuple[dict[str, float], set[str]]:
    totals: dict[str, float] = {}
    reported: set[str] = set()
    for food in foods:
        nutrients = food.get("nutrients")
        if not isinstance(nutrients, dict):
            continue
        for key, raw in nutrients.items():
            value = _number(raw)
            if value is None:
                continue
            reported.add(str(key))
            totals[str(key)] = totals.get(str(key), 0.0) + value
    return ({key: round(value, 4) for key, value in totals.items()}, reported)


def _target_value(target: dict[str, Any]) -> float | None:
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
        value = _number((food.get("nutrients") or {}).get(nutrient_key)) or 0.0
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
    targets = target_result.get("targets", {})
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

    # Macronutrients are checked against both the meal allocation and a real
    # personalized daily range edge. The range edge is used only when the
    # target engine actually supplies one; a minimum/RDA is never converted
    # into a fabricated upper limit.
    for key in _MACRO_ORDER:
        if key not in reported or key in clinical_keys:
            continue
        target = targets.get(key) if isinstance(targets, dict) else None
        if not isinstance(target, dict):
            continue
        allocation_high = _target_high(target)
        if allocation_high is None:
            continue
        actual_daily_high = _actual_upper_target(target)
        expected_high = allocation_high * fraction
        draft_amount = max(0.0, draft_totals.get(key, 0.0))
        projected_amount = max(0.0, projected_totals.get(key, 0.0))
        daily_ratio = (
            projected_amount / actual_daily_high
            if actual_daily_high is not None and actual_daily_high > 0
            else 0.0
        )
        daily_reference_ratio = projected_amount / allocation_high
        meal_ratio = draft_amount / expected_high if expected_high > 0 else 0.0
        above_protein_target = (
            key == "protein_g"
            and actual_daily_high is None
            and daily_reference_ratio > 1.0
        )
        if (
            daily_ratio <= 1.0
            and not above_protein_target
            and meal_ratio <= 1.0
        ):
            continue
        label, unit = _label_and_unit(key, target)
        exceeds_daily = daily_ratio > 1.0
        displayed_amount = (
            projected_amount if exceeds_daily or above_protein_target else draft_amount
        )
        alerts.append({
            "direction": "excess",
            "severity": "critical" if exceeds_daily else "warning",
            "nutrient": key,
            "label": label,
            "amount": round(displayed_amount, 2),
            "unit": unit,
            "reference": round(
                actual_daily_high
                if exceeds_daily
                else allocation_high
                if above_protein_target
                else expected_high,
                2,
            ),
            "percentage": round(
                (
                    daily_ratio
                    if exceeds_daily
                    else daily_reference_ratio
                    if above_protein_target
                    else meal_ratio
                ) * 100.0,
                1,
            ),
            "message": (
                f"With this draft, today's total exceeds your personalized daily upper target for {label.lower()}."
                if exceeds_daily
                else f"With this draft, today's total is above your personalized daily protein target; "
                "that target is an intake reference, not a medical safety limit."
                if above_protein_target
                else f"{label} is above this meal's estimated share of the personalized daily range; "
                "the meal share is guidance, not a medical upper limit."
            ),
            "contributors": _contributors(foods, key),
            "suggestions": _suggestions(
                nutrient_key=key,
                direction="excess",
                profile=normalized_profile,
                draft_result=nutrient_result,
                foods=foods,
                local_hour=local_hour,
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
        if ratio < 0.50:
            continue
        target = targets.get(key) if isinstance(targets, dict) else None
        label, unit = _label_and_unit(key, target)
        severity = "critical" if ratio >= 1.0 else "warning"
        alerts.append({
            "direction": "excess",
            "severity": severity,
            "nutrient": key,
            "label": label,
            "amount": round(amount, 2),
            "unit": unit,
            "reference": round(cap, 2),
            "percentage": round(ratio * 100.0, 1),
            "message": (
                f"With this draft, today's total exceeds the personalized daily limit for {label.lower()}."
                if ratio >= 1.0
                else f"With this draft, today reaches {ratio * 100:.0f}% of the daily {label.lower()} limit."
            ),
            "contributors": _contributors(foods, key),
            "suggestions": _suggestions(
                nutrient_key=key,
                direction="excess",
                profile=normalized_profile,
                draft_result=nutrient_result,
                foods=foods,
                local_hour=local_hour,
            ),
        })

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
                f"{label} is low for this meal's {fraction * 100:.0f}% share of the personalized daily target; "
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
