"""Immediate, post-analysis food recommendations for the current day."""

from __future__ import annotations

import copy
import math
from typing import Any, Iterable

from evidence_engine import attach_evidence
from feature_engineering import compute_features
from health_domain_scoring import attach_domain_scores
from nutrient_target_engine import calculate_nutrient_targets
from personalization_engine import attach_personalization, normalize_user_profile
from recommendation_catalog import FOOD_RECOMMENDATION_CATALOG


RECOMMENDATION_ENGINE_VERSION = "1.0.0"

_FALLBACK_TARGETS: dict[str, dict[str, Any]] = {
    "energy_kcal": {"type": "range", "low": 1800.0, "high": 2400.0},
    "protein_g": {"type": "minimum", "value": 50.0},
    "fiber_g": {"type": "minimum", "value": 28.0},
    "calcium_mg": {"type": "minimum", "value": 1000.0},
    "iron_mg": {"type": "minimum", "value": 18.0},
    "magnesium_mg": {"type": "minimum", "value": 420.0},
    "potassium_mg": {"type": "minimum", "value": 3400.0},
    "vitamin_c_mg": {"type": "minimum", "value": 90.0},
    "vitamin_d_ug": {"type": "minimum", "value": 20.0},
    "vitamin_b12_ug": {"type": "minimum", "value": 2.4},
    "folate_ug": {"type": "minimum", "value": 400.0},
    "omega3_g": {"type": "minimum", "value": 1.6},
    "sodium_mg": {"type": "maximum", "value": 2300.0},
    "saturated_fat_g": {"type": "maximum", "value": 20.0},
    "added_sugars_g": {"type": "maximum", "value": 50.0},
    "trans_fat_g": {"type": "maximum", "value": 2.0},
}

_NUTRIENT_LABELS = {
    "energy_kcal": "energy", "protein_g": "protein", "fiber_g": "fiber",
    "calcium_mg": "calcium", "iron_mg": "iron", "magnesium_mg": "magnesium",
    "potassium_mg": "potassium", "vitamin_c_mg": "vitamin C",
    "vitamin_d_ug": "vitamin D", "vitamin_b12_ug": "vitamin B12",
    "folate_ug": "folate", "omega3_g": "omega-3", "sodium_mg": "sodium",
    "saturated_fat_g": "saturated fat", "added_sugars_g": "added sugar",
    "trans_fat_g": "trans fat",
}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _unwrap_result(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("final_result", "meal_analysis", "data", "result"):
        nested = payload.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("meal"), dict):
            return nested
    return payload


def _result_identity(payload: dict[str, Any], fallback: str) -> str:
    root = _unwrap_result(payload)
    return str(payload.get("analysis_id") or root.get("analysis_id") or fallback)


def _food_identity(food: dict[str, Any]) -> str:
    return str(
        food.get("canonical_name") or food.get("display_name") or food.get("name") or "food"
    ).strip().lower()


def _collect_day_foods(
    current_result: dict[str, Any],
    today_results: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current_id = _result_identity(current_result, "current")
    ordered = [*today_results, current_result]
    seen_results: set[str] = set()
    day_foods: list[dict[str, Any]] = []
    current_foods: list[dict[str, Any]] = []

    for result_index, payload in enumerate(ordered, start=1):
        if not isinstance(payload, dict):
            continue
        identity = _result_identity(payload, f"result_{result_index}")
        if identity in seen_results:
            continue
        seen_results.add(identity)
        root = _unwrap_result(payload)
        foods = root.get("meal", {}).get("foods", [])
        if not isinstance(foods, list):
            continue
        for food_index, source in enumerate(foods, start=1):
            if not isinstance(source, dict) or not isinstance(source.get("nutrients"), dict):
                continue
            food = copy.deepcopy(source)
            food["id"] = f"day_{result_index:03d}_food_{food_index:03d}"
            food["belongs_to_food_id"] = None
            food.setdefault("ingredients", [])
            food.setdefault("spices", [])
            food.setdefault("quantity", food.get("estimated_weight_g") or 100.0)
            food.setdefault("unit", "g")
            day_foods.append(food)
            # The final payload is always the just-completed analysis. The
            # positional check keeps current-meal actions working for legacy
            # results that do not carry an analysis_id.
            if identity == current_id or result_index == len(ordered):
                current_foods.append(food)

    return day_foods, current_foods


def _sum_nutrients(foods: Iterable[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for food in foods:
        nutrients = food.get("nutrients")
        if not isinstance(nutrients, dict):
            continue
        for key, raw in nutrients.items():
            value = _number(raw)
            if value is None:
                continue
            totals[key] = round(totals.get(key, 0.0) + value, 4)
    return totals


def _resolved_targets(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    targets = copy.deepcopy(_FALLBACK_TARGETS)
    calculated = calculate_nutrient_targets(profile).get("targets", {})
    if not isinstance(calculated, dict):
        return targets
    for key, raw in calculated.items():
        if not isinstance(raw, dict):
            continue
        target_type = str(raw.get("target_type") or "").lower()
        resolved = _number(raw.get("resolved_value"))
        low = _number(raw.get("range_low"))
        high = _number(raw.get("range_high"))
        upper = _number(raw.get("upper_limit"))
        if key == "sodium_mg":
            # Sodium AI is not a goal to actively fill. Keep a ceiling; for
            # sodium-sensitive profiles, a lower resolved value may tighten it.
            conditions = set(profile.get("chronic_conditions", []))
            if conditions & {"hypertension", "high_blood_pressure", "chronic_kidney_disease", "ckd"}:
                if resolved is not None and resolved > 0:
                    targets[key] = {"type": "maximum", "value": min(2300.0, resolved)}
            continue
        if key == "energy_kcal" and resolved is not None and resolved > 0:
            targets[key] = {
                "type": "range",
                "low": round(resolved * 0.9, 2),
                "high": round(resolved * 1.1, 2),
            }
            continue
        if low is not None and high is not None and low > 0 and high > 0:
            targets[key] = {"type": "range", "low": low, "high": high}
        elif upper is not None and upper > 0 and (
            "upper" in target_type or "maximum" in target_type or "limit" in target_type
        ):
            targets[key] = {"type": "maximum", "value": upper}
        elif resolved is not None and resolved > 0:
            targets[key] = {
                "type": "maximum" if "maximum" in target_type or "upper" in target_type else "minimum",
                "value": resolved,
            }
    return targets


def _target_score(totals: dict[str, float], targets: dict[str, dict[str, Any]]) -> float:
    values: list[float] = []
    for key, target in targets.items():
        current = max(0.0, totals.get(key, 0.0))
        kind = target.get("type")
        if kind == "range":
            low, high = float(target["low"]), float(target["high"])
            if current < low:
                score = current / low * 100.0
            elif current <= high:
                score = 100.0
            else:
                score = max(0.0, 100.0 - ((current - high) / high * 120.0))
        elif kind == "maximum":
            ceiling = float(target["value"])
            score = 100.0 if current <= ceiling else max(
                0.0, 100.0 - ((current - ceiling) / ceiling * 160.0)
            )
        else:
            goal = float(target["value"])
            score = min(100.0, current / goal * 100.0)
        values.append(score)
    return round(sum(values) / len(values), 2) if values else 0.0


def _overall_score(result: dict[str, Any]) -> tuple[float, dict[str, float]]:
    meal = result.get("meal", {})
    personalization = meal.get("personalization")
    score_map = (
        personalization.get("personalized_domain_scores")
        if isinstance(personalization, dict)
        else None
    )
    if not isinstance(score_map, dict) or not score_map:
        score_map = meal.get("health_domain_scores", {})
    weighted = 0.0
    total_weight = 0.0
    domains: dict[str, float] = {}
    for key, raw in score_map.items() if isinstance(score_map, dict) else []:
        item = raw if isinstance(raw, dict) else {"score": raw}
        score = _number(item.get("score"))
        if score is None:
            continue
        confidence = max(_number(item.get("confidence")) or 0.25, 0.25)
        domains[str(key)] = round(score, 2)
        weighted += score * confidence
        total_weight += confidence
    return (round(weighted / total_weight, 2) if total_weight else 0.0, domains)


def _history_weighted_day_score(
    results: Iterable[dict[str, Any]],
) -> tuple[float, dict[str, float]]:
    """Mirror the energy-weighted daily score used by Flutter Insights/Home."""
    seen: set[str] = set()
    overall_total = 0.0
    overall_weight = 0.0
    domain_totals: dict[str, float] = {}
    domain_weights: dict[str, float] = {}
    for index, payload in enumerate(results, start=1):
        identity = _result_identity(payload, f"history_{index}")
        if identity in seen:
            continue
        seen.add(identity)
        root = _unwrap_result(payload)
        score, domains = _overall_score(root)
        foods = root.get("meal", {}).get("foods", [])
        calories = _sum_nutrients(foods if isinstance(foods, list) else []).get("energy_kcal", 0.0)
        weight = calories if calories > 0 else 1.0
        if score > 0:
            overall_total += score * weight
            overall_weight += weight
        for key, value in domains.items():
            domain_totals[key] = domain_totals.get(key, 0.0) + value * weight
            domain_weights[key] = domain_weights.get(key, 0.0) + weight
    return (
        round(overall_total / overall_weight, 2) if overall_weight else 0.0,
        {
            key: round(value / domain_weights[key], 2)
            for key, value in domain_totals.items()
            if domain_weights.get(key, 0.0) > 0
        },
    )


async def _score_food_set(
    foods: list[dict[str, Any]],
    profile: dict[str, Any],
) -> tuple[float, dict[str, float]]:
    payload = {
        "status": "completed",
        "meal": {
            "meal_type": "Current day",
            "estimated_visible_food_weight_g": sum(
                _number(food.get("estimated_weight_g"))
                or (_number(food.get("quantity")) if str(food.get("unit")) == "g" else 0.0)
                or 0.0
                for food in foods
            ),
            "foods": copy.deepcopy(foods),
        },
    }
    featured = await compute_features(payload)
    evidenced = await attach_evidence(featured)
    scored = await attach_domain_scores(evidenced)
    personalized = await attach_personalization(scored, profile)
    return _overall_score(personalized)


def _scaled_candidate_food(candidate: dict[str, Any], grams: float, index: int) -> dict[str, Any]:
    factor = grams / 100.0
    nutrients = {
        key: round(float(value) * factor, 4)
        for key, value in candidate["nutrients"].items()
    }
    return {
        "id": f"recommendation_{index:03d}",
        "name": candidate["name"],
        "display_name": candidate["name"],
        "canonical_name": candidate["search_query"],
        "category": "Recommended foundational food",
        "food_source": "Generic",
        "analysis_route": "DIRECT_USDA",
        "quantity": grams,
        "estimated_weight_g": grams,
        "unit": "g",
        "preparation": "ready to eat",
        "edible_fraction": 1.0,
        "ingredients": [],
        "spices": [],
        "nutrients": nutrients,
        "all_nutrients": [],
        "nutrient_status": "recommendation_catalog_estimate",
    }


def _profile_allows(candidate: dict[str, Any], profile: dict[str, Any]) -> bool:
    diet = str(profile.get("diet_type") or profile.get("diet_pattern") or "").lower()
    tags = set(candidate.get("diet_tags") or [])
    if diet == "vegan" and "vegan" not in tags:
        return False
    if diet == "vegetarian" and not ({"vegetarian", "vegan"} & tags):
        return False
    if diet == "pescatarian" and not ({"pescatarian", "vegetarian", "vegan"} & tags):
        return False
    allergies = {str(item).lower().replace(" ", "_") for item in profile.get("allergies", [])}
    candidate_allergens = {
        str(item).lower().replace(" ", "_") for item in candidate.get("allergens", [])
    }
    return not bool(allergies & candidate_allergens)


def _time_context(local_hour: int) -> tuple[str, float, int]:
    if local_hour < 11:
        return "this meal or lunch", 350.0, 3
    if local_hour < 16:
        return "this meal or an afternoon snack", 300.0, 2
    if local_hour < 21:
        return "this meal or dinner", 250.0, 1
    return "this meal or a small late snack", 160.0, 0


def _priority_changes(
    before: dict[str, float],
    after: dict[str, float],
    targets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for key, target in targets.items():
        old = before.get(key, 0.0)
        new = after.get(key, 0.0)
        kind = target.get("type")
        if kind == "range":
            goal = float(target["low"])
            old_gap = max(0.0, goal - old)
            new_gap = max(0.0, goal - new)
        elif kind == "maximum":
            goal = float(target["value"])
            old_gap = max(0.0, old - goal)
            new_gap = max(0.0, new - goal)
        else:
            goal = float(target["value"])
            old_gap = max(0.0, goal - old)
            new_gap = max(0.0, goal - new)
        improvement = old_gap - new_gap
        if improvement <= 0:
            continue
        changes.append({
            "nutrient": key,
            "label": _NUTRIENT_LABELS.get(key, key.replace("_", " ")),
            "before": round(old, 2),
            "after": round(new, 2),
            "target": round(goal, 2),
            "improvement": round(improvement, 2),
            "_priority": improvement / max(goal, 0.0001),
        })
    changes.sort(key=lambda item: item["_priority"], reverse=True)
    return [
        {key: value for key, value in item.items() if key != "_priority"}
        for item in changes[:4]
    ]


def _reason(action: str, changes: list[dict[str, Any]], context: str) -> str:
    labels = [item["label"] for item in changes[:3]]
    if labels:
        joined = ", ".join(labels[:-1]) + (f" and {labels[-1]}" if len(labels) > 1 else labels[0])
        verb = "reduces excess" if action in {"replace", "adjust_portion"} else "closes today’s gaps in"
        return f"This {verb} {joined} and fits {context}."
    return f"This produces a better simulated current-day balance and fits {context}."


async def recommend_after_analysis(
    *,
    current_result: dict[str, Any],
    today_results: list[dict[str, Any]],
    profile: dict[str, Any] | None,
    local_hour: int,
    maximum_results: int = 5,
) -> dict[str, Any]:
    normalized_profile = normalize_user_profile(profile)
    day_foods, current_foods = _collect_day_foods(current_result, today_results)
    if not day_foods:
        raise ValueError("No nutrient-bearing foods were available for recommendations.")

    targets = _resolved_targets(normalized_profile)
    baseline_totals = _sum_nutrients(day_foods)
    simulated_baseline_score, simulated_baseline_domains = await _score_food_set(
        day_foods,
        normalized_profile,
    )
    history_score, history_domains = _history_weighted_day_score(
        [*today_results, current_result]
    )
    baseline_score = history_score if history_score > 0 else simulated_baseline_score
    baseline_domains = history_domains if history_domains else simulated_baseline_domains
    baseline_balance = _target_score(baseline_totals, targets)
    context, max_extra_calories, remaining_occasions = _time_context(max(0, min(local_hour, 23)))
    current_meal_role = (
        "breakfast" if local_hour < 11
        else "lunch" if local_hour < 16
        else "dinner" if local_hour < 21
        else "snack"
    )

    evaluated: list[dict[str, Any]] = []
    candidate_index = 0
    for candidate in FOOD_RECOMMENDATION_CATALOG:
        if not _profile_allows(candidate, normalized_profile):
            continue
        serving = float(candidate["serving_g"])
        per100_energy = float(candidate["nutrients"].get("energy_kcal", 0.0))
        added_energy = per100_energy * serving / 100.0
        if added_energy > max_extra_calories:
            serving = max(10.0, serving * max_extra_calories / added_energy)
        candidate_index += 1
        addition = _scaled_candidate_food(candidate, serving, candidate_index)
        simulated_foods = [*copy.deepcopy(day_foods), addition]
        totals = _sum_nutrients(simulated_foods)
        simulated_score, domains = await _score_food_set(simulated_foods, normalized_profile)
        balance = _target_score(totals, targets)
        score_delta = simulated_score - simulated_baseline_score
        predicted_score = max(0.0, min(100.0, baseline_score + score_delta))
        balance_delta = balance - baseline_balance
        if score_delta <= 0.05 and balance_delta <= 0.25:
            continue
        changes = _priority_changes(baseline_totals, totals, targets)
        utility = score_delta * 1.8 + balance_delta
        candidate_roles = set(candidate.get("meal_roles") or [])
        scope = (
            "current_meal"
            if current_meal_role in candidate_roles or bool(candidate_roles & {"side", "topping"})
            else "next_meal"
        )
        evaluated.append({
            "action": "add",
            "scope": scope,
            "food": {
                "catalog_id": candidate["id"],
                "name": candidate["name"],
                "search_query": candidate["search_query"],
                "quantity": round(serving, 1),
                "unit": "g",
            },
            "baseline_score": baseline_score,
            "predicted_score": predicted_score,
            "score_delta": round(score_delta, 2),
            "predicted_score_low": round(max(0.0, predicted_score - 1.5), 1),
            "predicted_score_high": round(min(100.0, predicted_score + 1.5), 1),
            "domain_deltas": {
                key: round(value - simulated_baseline_domains.get(key, value), 2)
                for key, value in domains.items()
                if abs(value - simulated_baseline_domains.get(key, value)) >= 0.25
            },
            "nutrient_effects": changes,
            "reason": _reason("add", changes, context),
            "warnings": ["Confirm the actual food and portion before counting it as eaten."],
            "confidence": 0.78,
            "_utility": utility,
        })

    # Portion-reduction actions are generated only for an actual current-meal
    # food that is the largest contributor to an exceeded upper-limit nutrient.
    excess_keys = []
    for key, target in targets.items():
        if target.get("type") != "maximum":
            continue
        limit = float(target["value"])
        if baseline_totals.get(key, 0.0) > limit:
            excess_keys.append(key)
    for nutrient_key in excess_keys[:2]:
        offender = max(
            current_foods,
            key=lambda food: _number((food.get("nutrients") or {}).get(nutrient_key)) or 0.0,
            default=None,
        )
        if offender is None:
            continue
        contribution = _number((offender.get("nutrients") or {}).get(nutrient_key)) or 0.0
        quantity = _number(offender.get("estimated_weight_g")) or _number(offender.get("quantity"))
        if contribution <= 0 or quantity is None or quantity <= 10:
            continue
        reduced = copy.deepcopy(offender)
        for key, value in (reduced.get("nutrients") or {}).items():
            numeric = _number(value)
            reduced["nutrients"][key] = None if numeric is None else round(numeric * 0.5, 4)
        reduced["quantity"] = quantity * 0.5
        reduced["estimated_weight_g"] = quantity * 0.5
        simulated = [reduced if food["id"] == offender["id"] else copy.deepcopy(food) for food in day_foods]
        totals = _sum_nutrients(simulated)
        simulated_score, domains = await _score_food_set(simulated, normalized_profile)
        score_delta = simulated_score - simulated_baseline_score
        predicted_score = max(0.0, min(100.0, baseline_score + score_delta))
        balance_delta = _target_score(totals, targets) - baseline_balance
        if score_delta <= 0.05 and balance_delta <= 0.25:
            continue
        changes = _priority_changes(baseline_totals, totals, targets)
        evaluated.append({
            "action": "adjust_portion",
            "scope": "current_meal",
            "food": {
                "name": str(offender.get("display_name") or offender.get("name") or "Food"),
                "quantity": round(quantity * 0.5, 1),
                "original_quantity": round(quantity, 1),
                "unit": "g",
            },
            "baseline_score": baseline_score,
            "predicted_score": predicted_score,
            "score_delta": round(score_delta, 2),
            "predicted_score_low": round(max(0.0, predicted_score - 1.0), 1),
            "predicted_score_high": round(min(100.0, predicted_score + 1.0), 1),
            "domain_deltas": {
                key: round(value - simulated_baseline_domains.get(key, value), 2)
                for key, value in domains.items()
                if abs(value - simulated_baseline_domains.get(key, value)) >= 0.25
            },
            "nutrient_effects": changes,
            "reason": (
                f"Reducing this portion lowers today’s {_NUTRIENT_LABELS.get(nutrient_key, nutrient_key)} "
                "excess while preserving the rest of the meal."
            ),
            "warnings": ["Use the portion you actually consume; the recommendation is not logged automatically."],
            "confidence": 0.84,
            "_utility": score_delta * 1.8 + balance_delta,
        })

        # Also test a true food replacement. The alternative must contribute
        # materially less of the exceeded nutrient than the current offender.
        replacement_options: list[tuple[dict[str, Any], float]] = []
        for candidate in FOOD_RECOMMENDATION_CATALOG:
            if not _profile_allows(candidate, normalized_profile):
                continue
            serving = float(candidate["serving_g"])
            candidate_excess = float(candidate["nutrients"].get(nutrient_key, 0.0)) * serving / 100.0
            if candidate_excess < contribution * 0.45:
                replacement_options.append((candidate, serving))
        replacement_options.sort(
            key=lambda pair: (
                float(pair[0]["nutrients"].get("fiber_g", 0.0))
                + float(pair[0]["nutrients"].get("protein_g", 0.0)) * 0.4
            ),
            reverse=True,
        )
        for candidate, serving in replacement_options[:3]:
            candidate_index += 1
            replacement = _scaled_candidate_food(candidate, serving, candidate_index)
            simulated = [
                replacement if food["id"] == offender["id"] else copy.deepcopy(food)
                for food in day_foods
            ]
            totals = _sum_nutrients(simulated)
            simulated_score, domains = await _score_food_set(simulated, normalized_profile)
            score_delta = simulated_score - simulated_baseline_score
            predicted_score = max(0.0, min(100.0, baseline_score + score_delta))
            balance_delta = _target_score(totals, targets) - baseline_balance
            if score_delta <= 0.05 and balance_delta <= 0.25:
                continue
            changes = _priority_changes(baseline_totals, totals, targets)
            evaluated.append({
                "action": "replace",
                "scope": "current_meal",
                "food": {
                    "catalog_id": candidate["id"],
                    "name": candidate["name"],
                    "search_query": candidate["search_query"],
                    "quantity": round(serving, 1),
                    "unit": "g",
                },
                "replaces": {
                    "name": str(offender.get("display_name") or offender.get("name") or "Food"),
                    "quantity": round(quantity, 1),
                    "unit": "g",
                },
                "baseline_score": baseline_score,
                "predicted_score": predicted_score,
                "score_delta": round(score_delta, 2),
                "predicted_score_low": round(max(0.0, predicted_score - 1.5), 1),
                "predicted_score_high": round(min(100.0, predicted_score + 1.5), 1),
                "domain_deltas": {
                    key: round(value - simulated_baseline_domains.get(key, value), 2)
                    for key, value in domains.items()
                    if abs(value - simulated_baseline_domains.get(key, value)) >= 0.25
                },
                "nutrient_effects": changes,
                "reason": (
                    f"Replacing {_food_identity(offender)} with {candidate['name']} lowers "
                    f"today’s {_NUTRIENT_LABELS.get(nutrient_key, nutrient_key)} load and "
                    "improves the simulated score."
                ),
                "warnings": ["Only make this swap if it fits the meal and your dietary needs."],
                "confidence": 0.76,
                "_utility": score_delta * 1.8 + balance_delta,
            })
            break

    evaluated.sort(key=lambda item: (item["_utility"], item["score_delta"]), reverse=True)
    selected: list[dict[str, Any]] = []
    seen_foods: set[str] = set()
    for item in evaluated:
        identity = f"{item['action']}:{item['food'].get('name', '').lower()}"
        if identity in seen_foods:
            continue
        seen_foods.add(identity)
        item = {key: value for key, value in item.items() if key != "_utility"}
        item["id"] = f"recommendation_{len(selected) + 1:03d}"
        selected.append(item)
        if len(selected) >= max(1, min(maximum_results, 8)):
            break

    return {
        "status": "completed",
        "engine_version": RECOMMENDATION_ENGINE_VERSION,
        "generated_for_analysis_id": _result_identity(current_result, "current"),
        "timing": {
            "local_hour": local_hour,
            "context": context,
            "estimated_eating_occasions_remaining": remaining_occasions,
        },
        "baseline": {
            "current_day_score": baseline_score,
            "nutrition_balance_score": baseline_balance,
            "domain_scores": baseline_domains,
            "meals_included": len({
                _result_identity(item, str(index))
                for index, item in enumerate([*today_results, current_result])
                if isinstance(item, dict)
            }),
        },
        "recommendations": selected,
        "message": (
            "No safe material improvement was found from the current catalogue."
            if not selected
            else "Recommendations were simulated immediately after this analysis."
        ),
        "disclaimer": (
            "Predictions use estimated portions and catalogue nutrient profiles. "
            "Nothing is counted as consumed until the user logs it."
        ),
    }
