"""Immediate, post-analysis food recommendations for the current day."""

from __future__ import annotations

import copy
import math
import re
from typing import Any, Iterable

from evidence_engine import DOMAIN_HEALTH_LABEL, attach_evidence
from feature_engineering import compute_features
from health_domain_scoring import attach_domain_scores
from nutrient_target_engine import attach_nutrient_targets, calculate_nutrient_targets
from nutrient_target_data import CANONICAL_KEY_COMPATIBILITY
from personalization_engine import attach_personalization, normalize_user_profile
from recommendation_catalog import FOOD_RECOMMENDATION_CATALOG
from recommendation_candidate_provider import (
    discover_recommendation_candidates,
    rehydrate_usda_candidate,
)


RECOMMENDATION_ENGINE_VERSION = "3.0.0"
RECOMMENDATION_APPLY_CONTRACT_VERSION = 2
_GOOD_ADEQUACY_RATIO = 0.80

_FALLBACK_TARGETS: dict[str, dict[str, Any]] = {
    "energy_kcal": {"type": "range", "low": 1800.0, "high": 2400.0},
    "protein_g": {"type": "minimum", "value": 50.0},
    "carbohydrate_g": {"type": "range", "low": 220.0, "high": 330.0},
    "fat_g": {"type": "range", "low": 62.4, "high": 93.6},
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
    "energy_kcal": "energy", "protein_g": "protein",
    "carbohydrate_g": "carbohydrate", "fat_g": "total fat", "fiber_g": "fiber",
    "calcium_mg": "calcium", "iron_mg": "iron", "magnesium_mg": "magnesium",
    "potassium_mg": "potassium", "vitamin_c_mg": "vitamin C",
    "vitamin_d_ug": "vitamin D", "vitamin_b12_ug": "vitamin B12",
    "folate_ug": "folate", "omega3_g": "omega-3", "sodium_mg": "sodium",
    "saturated_fat_g": "saturated fat", "added_sugars_g": "added sugar",
    "trans_fat_g": "trans fat", "phosphorus_mg": "phosphorus",
    "calcium_mg": "calcium", "iron_mg": "iron", "magnesium_mg": "magnesium",
    "zinc_mg": "zinc", "vitamin_a_ug": "vitamin A", "vitamin_c_mg": "vitamin C",
    "vitamin_d_ug": "vitamin D", "vitamin_b6_mg": "vitamin B6",
    "selenium_ug": "selenium", "iodine_ug": "iodine", "copper_mg": "copper",
    "manganese_mg": "manganese",
}

_NUTRIENT_UNITS = {
    "energy_kcal": "kcal",
    "protein_g": "g",
    "carbohydrate_g": "g",
    "fat_g": "g",
    "fiber_g": "g",
    "sodium_mg": "mg",
    "saturated_fat_g": "g",
    "added_sugars_g": "g",
    "trans_fat_g": "g",
    "phosphorus_mg": "mg", "calcium_mg": "mg", "iron_mg": "mg",
    "magnesium_mg": "mg", "zinc_mg": "mg", "vitamin_a_ug": "µg",
    "vitamin_c_mg": "mg", "vitamin_d_ug": "µg", "vitamin_b6_mg": "mg",
    "selenium_ug": "µg", "iodine_ug": "µg", "copper_mg": "mg",
    "manganese_mg": "mg",
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


def _food_identity(value: Any) -> str:
    """Normalize a food identity for repeat detection across candidate actions."""
    if isinstance(value, dict):
        raw = value.get("canonical_name") or value.get("display_name") or value.get("name") or "food"
    else:
        raw = value or "food"
    tokens = [
        token for token in re.findall(r"[a-z0-9]+", str(raw).lower())
        if token not in {"raw", "cooked", "boiled", "roasted", "baked", "plain", "fresh"}
    ]
    return " ".join(tokens).strip() or "food"


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


_ALIAS_SCALES: dict[tuple[str, str], float] = {
    ("vitamin_d_ug", "vitamin_d_iu"): 0.025,
    ("copper_mg", "copper_ug"): 0.001,
    ("copper_mg", "copper_mcg"): 0.001,
}


def _canonical_nutrient_key(key: str) -> str:
    value = str(key or "").strip()
    for canonical, compatibility in CANONICAL_KEY_COMPATIBILITY.items():
        accepted = {
            canonical,
            *[str(item) for item in compatibility.get("accepted_input_keys", [])],
        }
        if value in accepted:
            return canonical
    return value


def _canonical_nutrients(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    numeric: dict[str, float] = {}
    for key, value in raw.items():
        parsed = _number(value)
        if parsed is not None:
            numeric[str(key)] = parsed
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


def _nutrient_amount(food: dict[str, Any], nutrient_key: str) -> float:
    return max(0.0, _canonical_nutrients(food.get("nutrients")).get(nutrient_key, 0.0))


def _sum_nutrients(foods: Iterable[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for food in foods:
        for key, value in _canonical_nutrients(food.get("nutrients")).items():
            totals[key] = round(totals.get(key, 0.0) + value, 4)
    return totals


def _food_applicable_target_upper(raw: dict[str, Any]) -> float | None:
    upper = _number(raw.get("upper_limit"))
    if upper is None or upper <= 0:
        return None
    scope = str(raw.get("upper_limit_scope") or "").strip().lower()
    if not scope:
        return upper
    if any(
        token in scope
        for token in ("added_", "synthetic", "preformed_retinol")
    ):
        return None
    # Some all-source ULs explicitly include both food and supplements. If
    # food is named in the scope, food intake alone can legitimately be
    # compared with that ceiling. Supplement-only ULs remain excluded.
    if scope == "all_intake" or scope == "all_sources" or "food" in scope:
        return upper
    if "supplement" in scope:
        return None
    return None


def _attach_food_upper(
    target: dict[str, Any], raw: dict[str, Any]
) -> dict[str, Any]:
    result = dict(target)
    upper = _food_applicable_target_upper(raw)
    if upper is not None:
        result["upper_limit"] = upper
    return result


def _resolved_targets(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    targets = copy.deepcopy(_FALLBACK_TARGETS)
    calculated = calculate_nutrient_targets(profile).get("targets", {})
    if not isinstance(calculated, dict):
        return targets

    energy_item = calculated.get("energy_kcal")
    resolved_energy = (
        _number(energy_item.get("resolved_value"))
        if isinstance(energy_item, dict)
        else None
    )
    age_months = _number(profile.get("age_months"))

    for key, raw in calculated.items():
        if not isinstance(raw, dict):
            continue
        if raw.get("status") == "requires_clinical_input":
            # Do not replace a clinically unresolved nutrient with a generic
            # automatic target. Candidate eligibility handles the fail-closed
            # medical restrictions separately.
            targets.pop(key, None)
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
            targets[key] = _attach_food_upper({
                "type": "range",
                "low": round(resolved * 0.9, 2),
                "high": round(resolved * 1.1, 2),
            }, raw)
            continue

        # The carbohydrate registry contains both the 130 g RDA and an AMDR.
        # For excess/portion guidance, the RDA must not be misused as an upper
        # limit. When energy is known, use the adult/age>=1 AMDR (45-65% kcal).
        if key == "carbohydrate_g" and (age_months is None or age_months >= 12):
            if resolved_energy is not None and resolved_energy > 0:
                targets[key] = _attach_food_upper({
                    "type": "range",
                    "low": round(resolved_energy * 0.45 / 4.0, 2),
                    "high": round(resolved_energy * 0.65 / 4.0, 2),
                }, raw)
            # If energy is unavailable, retain the generic reference range.
            continue

        if low is not None and high is not None and low > 0 and high > 0:
            targets[key] = _attach_food_upper(
                {"type": "range", "low": low, "high": high}, raw
            )
        elif upper is not None and upper > 0 and (
            "upper" in target_type or "maximum" in target_type or "limit" in target_type
        ):
            targets[key] = _attach_food_upper(
                {"type": "maximum", "value": upper}, raw
            )
        elif resolved is not None and resolved > 0:
            targets[key] = _attach_food_upper({
                "type": "maximum" if "maximum" in target_type or "upper" in target_type else "minimum",
                "value": resolved,
            }, raw)
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
            upper = _number(target.get("upper_limit"))
            if upper is not None and upper > 0 and current > upper:
                score = max(0.0, 100.0 - ((current - upper) / upper * 160.0))
            else:
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
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    fdc_id = candidate.get("fdc_id")
    dynamic_usda = isinstance(fdc_id, int)
    food = {
        "id": f"recommendation_{index:03d}",
        "name": candidate["name"],
        "display_name": candidate["name"],
        "canonical_name": candidate["search_query"],
        "category": candidate.get("food_category") or "Recommended foundational food",
        "food_source": "USDA FoodData Central" if dynamic_usda else "Generic",
        "analysis_route": "DIRECT_USDA",
        "quantity": grams,
        "estimated_weight_g": grams,
        "unit": "g",
        "preparation": "as listed by USDA" if dynamic_usda else "ready to eat",
        "edible_fraction": 1.0,
        "ingredients": [],
        "spices": [],
        "nutrients": nutrients,
        "all_nutrients": [],
        "nutrient_status": (
            "recommendation_usda_verified"
            if dynamic_usda
            else "recommendation_catalog_estimate"
        ),
        "nutrient_source": (
            "USDA FoodData Central"
            if dynamic_usda
            else "recommendation_catalog"
        ),
    }
    if dynamic_usda:
        food["resolver"] = {
            "status": "resolved",
            "fdc_id": fdc_id,
            "matched_description": candidate.get("search_query"),
            "matched_name": candidate.get("search_query"),
            "data_type": candidate.get("data_type"),
            "match_query": candidate.get("search_query"),
            "confidence": 1.0,
            "source": "dynamic_recommendation_usda",
        }
        food["nutrient_basis"] = {
            "source": "USDA FoodData Central",
            "fdc_id": fdc_id,
            "matched_name": candidate.get("search_query"),
            "data_type": candidate.get("data_type"),
            "scaled_weight_g": grams,
            "per_100g_basis": "verified_before_recommendation",
        }
    return food


def _normalized_values(value: Any) -> set[str]:
    if value is None:
        return set()
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return {
        str(item).strip().lower().replace("-", "_").replace(" ", "_")
        for item in values
        if str(item).strip()
    }


def _profile_conditions(profile: dict[str, Any]) -> set[str]:
    return _normalized_values(
        profile.get("chronic_conditions")
        or profile.get("conditions")
        or []
    )


_CONDITION_ALIASES = {
    "diabetes": {"type_2_diabetes", "diabetes", "prediabetes", "insulin_resistance"},
    "hypertension": {"hypertension", "high_blood_pressure"},
    "ckd": {"chronic_kidney_disease", "ckd", "kidney_disease"},
    "heart_failure": {"heart_failure", "chf"},
    "dyslipidemia": {"dyslipidemia", "high_cholesterol", "hyperlipidemia", "coronary_artery_disease", "cardiovascular_disease", "heart_disease"},
    "fatty_liver": {"fatty_liver", "nafld", "masld"},
}
_CONDITION_PROTECTED_DOMAINS = {
    "diabetes": {"glycemic_control", "metabolic_syndrome"},
    "hypertension": {"blood_pressure", "cardiovascular_health"},
    "ckd": {"renal_health"},
    "heart_failure": {"cardiovascular_health", "blood_pressure"},
    "dyslipidemia": {"cardiovascular_health"},
    "fatty_liver": {"hepatic_health", "metabolic_syndrome"},
}

def _active_condition_groups(profile: dict[str, Any]) -> set[str]:
    conditions = _profile_conditions(profile)
    return {group for group, aliases in _CONDITION_ALIASES.items() if conditions & aliases}

def _domain_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_").replace("&", "and")

def _protected_domain_tokens(profile: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for group in _active_condition_groups(profile):
        out.update(_CONDITION_PROTECTED_DOMAINS.get(group, set()))
    return out

def _medical_candidate_burden(candidate: dict[str, Any], profile: dict[str, Any], *, serving_g: float | None = None) -> list[str]:
    groups = _active_condition_groups(profile)
    if not groups:
        return []
    nutrients = candidate.get("nutrients") if isinstance(candidate.get("nutrients"), dict) else {}
    grams = max(0.0, serving_g if serving_g is not None else (_number(candidate.get("serving_g")) or 100.0))
    factor = grams / 100.0
    def amount(key: str) -> float:
        return max(0.0, (_number(nutrients.get(key)) or 0.0) * factor)
    energy, carb, fiber, sugars = amount("energy_kcal"), amount("carbohydrate_g"), amount("fiber_g"), amount("sugars_g")
    added, sodium, sat, trans = amount("added_sugars_g"), amount("sodium_mg"), amount("saturated_fat_g"), amount("trans_fat_g")
    reasons=[]
    if "diabetes" in groups and (added > 8.0 or (carb > 45.0 and fiber < 4.0 and sugars > 12.0)):
        reasons.append("diabetes_glycemic_burden")
    if "hypertension" in groups and sodium > 500.0:
        reasons.append("hypertension_sodium_burden")
    if "heart_failure" in groups and sodium > 400.0:
        reasons.append("heart_failure_sodium_burden")
    if "dyslipidemia" in groups:
        sat_energy_pct = (sat * 9.0 / energy * 100.0) if energy > 0 else 0.0
        if trans > 0.5 or sat > 5.0 or (sat > 3.0 and sat_energy_pct > 15.0):
            reasons.append("cardiovascular_fat_burden")
    if "fatty_liver" in groups and added > 8.0:
        reasons.append("hepatic_added_sugar_burden")
    return reasons

def _personalized_upper_limit_safe(candidate: dict[str, Any], profile: dict[str, Any], current_totals: dict[str, float], *, serving_g: float | None = None) -> tuple[bool, list[str]]:
    targets = _resolved_targets(profile)
    nutrients = candidate.get("nutrients") if isinstance(candidate.get("nutrients"), dict) else {}
    grams = max(0.0, serving_g if serving_g is not None else (_number(candidate.get("serving_g")) or 100.0))
    factor = grams / 100.0
    reasons=[]
    for key,target in targets.items():
        upper = _number(target.get("upper_limit"))
        if target.get("type") == "maximum":
            value = _number(target.get("value"))
            ceiling = min(
                candidate for candidate in (value, upper)
                if candidate is not None and candidate > 0
            ) if any(candidate is not None and candidate > 0 for candidate in (value, upper)) else None
        else:
            ceiling = upper
        contribution=(_number(nutrients.get(key)) or 0.0)*factor
        if ceiling is None or ceiling <= 0 or contribution <= 0: continue
        before=max(0.0,_number(current_totals.get(key)) or 0.0); after=before+contribution
        if before <= ceiling and after > ceiling: reasons.append(f"personalized_{key}_limit")
        elif before > ceiling and contribution > max(ceiling*0.02,0.01): reasons.append(f"personalized_{key}_already_high")
    return not reasons, sorted(set(reasons))

def _protected_domain_decline_numbers(before: dict[str,float], after: dict[str,float], profile: dict[str,Any]) -> float:
    protected=_protected_domain_tokens(profile)
    if not protected: return 0.0
    vals=[float(old)-float(after[k]) for k,old in before.items() if k in after and _domain_token(k) in protected]
    return max(vals, default=0.0)

def _protected_domain_decline_items(before: dict[str,dict[str,Any]], after: dict[str,dict[str,Any]], profile: dict[str,Any]) -> float:
    protected=_protected_domain_tokens(profile)
    if not protected: return 0.0
    vals=[]
    for k,old_item in before.items():
        if k not in after: continue
        tokens={_domain_token(k),_domain_token(old_item.get("health_domain") if isinstance(old_item,dict) else k)}
        if not tokens & protected: continue
        old=_number(old_item.get("score")); new=_number(after[k].get("score"))
        if old is not None and new is not None: vals.append(old-new)
    return max(vals, default=0.0)

def _candidate_source(candidate: dict[str, Any]) -> str:
    tags = _normalized_values(candidate.get("diet_tags") or [])
    if "pescatarian" in tags:
        return "fish"
    if "ovo_vegetarian" in tags and not ({"vegan", "vegetarian"} & tags):
        return "egg"
    if "vegan" in tags:
        return "plant"
    if "vegetarian" in tags:
        return "dairy_or_vegetarian"
    return "meat"


def _diet_allows(candidate: dict[str, Any], profile: dict[str, Any]) -> bool:
    diet = str(
        profile.get("diet_type")
        or profile.get("diet_pattern")
        or ""
    ).strip().lower().replace("-", "_").replace(" ", "_")
    tags = _normalized_values(candidate.get("diet_tags") or [])
    if not diet or diet in {"omnivore", "non_vegetarian", "mixed"}:
        return True
    if diet == "vegan":
        return "vegan" in tags
    if diet in {"vegetarian", "lacto_vegetarian", "jain", "jain_vegetarian"}:
        return bool({"vegetarian", "vegan"} & tags)
    if diet in {"ovo_vegetarian", "lacto_ovo_vegetarian"}:
        return bool({"ovo_vegetarian", "vegetarian", "vegan"} & tags)
    if diet == "pescatarian":
        return bool({"pescatarian", "ovo_vegetarian", "vegetarian", "vegan"} & tags)
    # Unknown explicit diet classifications fail closed rather than allowing
    # an animal food the user may have prohibited.
    return False


def _candidate_eligibility(
    candidate: dict[str, Any],
    profile: dict[str, Any],
) -> tuple[bool, dict[str, bool], list[str]]:
    reasons: list[str] = []
    diet_verified = _diet_allows(candidate, profile)
    if not diet_verified:
        reasons.append("diet_restriction")

    allergies = _normalized_values(profile.get("allergies") or [])
    intolerances = _normalized_values(
        profile.get("intolerances")
        or profile.get("food_intolerances")
        or []
    )
    candidate_allergens = _normalized_values(candidate.get("allergens") or [])
    allergen_verified = not bool(allergies & candidate_allergens)
    if not allergen_verified:
        reasons.append("allergen")
    if (
        {"lactose", "dairy", "milk"} & intolerances
        and {"dairy", "milk"} & candidate_allergens
    ):
        allergen_verified = False
        reasons.append("intolerance")

    identity = str(candidate.get("id") or candidate.get("name") or "").lower()
    excluded = (
        _normalized_values(profile.get("excluded_foods"))
        | _normalized_values(profile.get("disliked_foods"))
    )
    preference_verified = not any(
        token and token.replace("_", " ") in identity.replace("_", " ")
        for token in excluded
    )
    if not preference_verified:
        reasons.append("excluded_food")

    diet = str(profile.get("diet_type") or profile.get("diet_pattern") or "").lower()
    if "jain" in diet and any(
        term in identity
        for term in ("potato", "onion", "garlic", "carrot", "beet", "radish")
    ):
        preference_verified = False
        reasons.append("jain_root_vegetable")

    conditions = _profile_conditions(profile)
    nutrients = candidate.get("nutrients") if isinstance(candidate.get("nutrients"), dict) else {}
    serving_factor = max(_number(candidate.get("serving_g")) or 0.0, 0.0) / 100.0
    ckd = bool(conditions & {"chronic_kidney_disease", "ckd", "kidney_disease"})
    dialysis = bool(
        profile.get("dialysis_modality")
        or conditions & {"dialysis", "hemodialysis", "peritoneal_dialysis"}
    )
    medical_verified = True
    if ckd:
        potassium = (_number(nutrients.get("potassium_mg")) or 0.0) * serving_factor
        phosphorus = (_number(nutrients.get("phosphorus_mg")) or 0.0) * serving_factor
        protein = (_number(nutrients.get("protein_g")) or 0.0) * serving_factor
        if potassium > 300.0 or phosphorus > 200.0 or (not dialysis and protein > 20.0):
            medical_verified = False
            reasons.append("ckd_nutrient_uncertainty")

    medications = _normalized_values(profile.get("medications") or [])
    vitamin_k = (_number(nutrients.get("vitamin_k_ug")) or 0.0) * serving_factor
    if medications & {"warfarin", "coumadin"} and vitamin_k > 200.0:
        medical_verified = False
        reasons.append("medication_food_interaction")
    potassium = (_number(nutrients.get("potassium_mg")) or 0.0) * serving_factor
    if medications & {
        "potassium_sparing_diuretic",
        "raas_inhibitor",
        "ace_inhibitor",
        "arb",
    } and potassium > 300.0:
        medical_verified = False
        reasons.append("potassium_medication_uncertainty")

    burden_reasons = _medical_candidate_burden(candidate, profile)
    if burden_reasons:
        medical_verified = False
        reasons.extend(burden_reasons)

    audit = {
        "diet_verified": diet_verified,
        "allergen_verified": allergen_verified,
        "medical_constraints_verified": medical_verified,
        "preference_verified": preference_verified,
    }
    return all(audit.values()), audit, sorted(set(reasons))


def _profile_allows(candidate: dict[str, Any], profile: dict[str, Any]) -> bool:
    allowed, _, _ = _candidate_eligibility(candidate, profile)
    return allowed


def _time_context(local_hour: int) -> tuple[str, float, int]:
    if local_hour < 11:
        return "this meal or lunch", 350.0, 3
    if local_hour < 16:
        return "this meal or an afternoon snack", 300.0, 2
    if local_hour < 21:
        return "this meal or dinner", 250.0, 1
    return "this meal or a small late snack", 160.0, 0


def _meal_role(current_result: dict[str, Any], local_hour: int) -> str:
    root = _unwrap_result(current_result)
    meal_type = str(root.get("meal", {}).get("meal_type") or "").lower()
    for role in ("breakfast", "lunch", "dinner", "snack", "dessert"):
        if role in meal_type:
            return role
    if local_hour < 11:
        return "breakfast"
    if local_hour < 16:
        return "lunch"
    if local_hour < 21:
        return "dinner"
    return "snack"


def _meal_compatibility(
    candidate: dict[str, Any],
    current_result: dict[str, Any],
    current_foods: list[dict[str, Any]],
    local_hour: int,
) -> tuple[bool, str]:
    role = _meal_role(current_result, local_hour)
    roles = _normalized_values(candidate.get("meal_roles") or [])
    if roles and role not in roles and not ({"side", "topping"} & roles):
        return False, "meal_role"

    meal_text = " ".join(
        [
            str(_unwrap_result(current_result).get("meal", {}).get("meal_type") or ""),
            *[
                str(food.get("canonical_name") or food.get("name") or "")
                for food in current_foods
            ],
        ]
    ).lower()
    source = _candidate_source(candidate)
    current_has_animal_main = any(
        term in meal_text
        for term in (
            "chicken", "turkey", "mutton", "lamb", "beef", "pork",
            "fish", "salmon", "tuna", "prawn", "shrimp", "egg",
        )
    )
    # Preserve a vegetarian current meal even for an omnivore profile. This is
    # meal coherence, separate from the user's permanent dietary restriction.
    if not current_has_animal_main and source in {"meat", "fish", "egg"}:
        return False, "preserve_vegetarian_meal"

    # Do not classify every recipe containing oats as a breakfast/milk bowl.
    # That old heuristic made a paneer + oats + fruit recipe reject otherwise
    # reasonable side foods and could empty both shortfall and module
    # recommendations. Require an explicit bowl-style meal description, or an
    # actual milk/yogurt + oat/cereal combination.
    meal_type_text = str(
        _unwrap_result(current_result).get("meal", {}).get("meal_type") or ""
    ).lower()
    explicit_bowl = any(
        term in meal_type_text
        for term in ("porridge", "cereal", "smoothie", "oatmeal", "breakfast bowl")
    )
    dairy_bowl = (
        any(term in meal_text for term in ("milk", "yogurt"))
        and any(term in meal_text for term in ("oat", "cereal", "granola"))
    )
    milk_bowl = explicit_bowl or dairy_bowl
    if milk_bowl and source in {"meat", "fish"}:
        return False, "incompatible_with_milk_or_breakfast_bowl"
    if milk_bowl:
        candidate_text = str(
            candidate.get("id") or candidate.get("name") or ""
        ).lower()
        bowl_compatible = any(
            token in candidate_text
            for token in (
                "yogurt", "oat", "chia", "flax", "almond", "walnut",
                "blueberr", "strawberr", "banana", "orange", "apple",
                "fruit", "seed", "nut",
            )
        )
        if not bowl_compatible:
            return False, "incompatible_with_breakfast_bowl"
    return True, "compatible"


def _candidate_already_present(
    candidate: dict[str, Any],
    current_foods: list[dict[str, Any]],
) -> bool:
    """Return True when the catalogue food is already part of the meal.

    Recommendation names and USDA descriptions frequently differ only by
    punctuation, preparation words or singular/plural spelling (for example
    ``blueberry`` vs ``Blueberries, raw``).  A duplicate suggestion is more
    harmful than a conservative match here, so compare lightly stemmed
    identity tokens in addition to exact normalized names.
    """
    ignored = {
        "raw", "cooked", "boiled", "steamed", "roasted", "baked",
        "plain", "low", "fat", "firm", "unsalted", "without", "salt",
        "fresh", "frozen", "prepared", "ready", "eat",
    }

    def stem(token: str) -> str:
        if token.endswith("ies") and len(token) > 5:
            return token[:-3] + "y"
        if token.endswith("es") and len(token) > 5:
            return token[:-2]
        if token.endswith("s") and len(token) > 4 and not token.endswith("ss"):
            return token[:-1]
        return token

    def identity_tokens(value: Any) -> set[str]:
        return {
            stem(token)
            for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
            if len(token) >= 4 and token not in ignored
        }

    candidate_tokens = identity_tokens(
        " ".join(
            str(value or "")
            for value in (candidate.get("name"), candidate.get("search_query"))
        )
    )
    if not candidate_tokens:
        return False
    for food in current_foods:
        food_tokens = identity_tokens(
            " ".join(
                str(value or "")
                for value in (
                    food.get("canonical_name"),
                    food.get("display_name"),
                    food.get("name"),
                )
            )
        )
        if candidate_tokens & food_tokens:
            return True
    return False


def _domain_score_items(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    root = _unwrap_result(result)
    meal = root.get("meal", {}) if isinstance(root.get("meal"), dict) else {}
    personalization = meal.get("personalization")
    score_map = (
        personalization.get("personalized_domain_scores")
        if isinstance(personalization, dict)
        else None
    )
    if not isinstance(score_map, dict) or not score_map:
        score_map = meal.get("health_domain_scores", {})
    items: dict[str, dict[str, Any]] = {}
    for key, raw in score_map.items() if isinstance(score_map, dict) else []:
        item = copy.deepcopy(raw) if isinstance(raw, dict) else {"score": raw}
        score = _number(item.get("score"))
        if score is None:
            continue
        item["score"] = score
        item["confidence"] = max(0.0, min(_number(item.get("confidence")) or 0.25, 1.0))
        item["coverage"] = max(0.0, min(_number(item.get("coverage")) or 0.25, 1.0))
        item["health_domain"] = str(item.get("health_domain") or key.replace("_", " ").title())
        items[str(key)] = item
    return items


def _target_domains(result: dict[str, Any], maximum: int = 2) -> list[tuple[str, dict[str, Any]]]:
    """Return weak health domains in true score order.

    Confidence/coverage describe certainty; they must not let a 60-point
    mid-range domain outrank a 42-point domain.  They are therefore only
    tie-breakers after the score itself.  Domains with literally no usable
    evidence signal are skipped, but a low-confidence displayed score remains
    eligible and carries that lower confidence into the recommendation UI.
    """
    ranked: list[tuple[float, float, float, str, dict[str, Any]]] = []
    for key, item in _domain_score_items(result).items():
        score = float(item["score"])
        confidence = float(item.get("confidence") or 0.25)
        coverage = float(item.get("coverage") or 0.25)
        if score >= 70.0:
            continue
        if confidence <= 0.0 and coverage <= 0.0:
            continue
        ranked.append((score, -confidence, -coverage, key, item))
    ranked.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
    return [(key, item) for _, _, _, key, item in ranked[:maximum]]


_REDUCTION_FEATURE_NUTRIENTS: dict[str, tuple[str, ...]] = {
    "energy_density": ("energy_kcal",),
    "sodium_density": ("sodium_mg",),
    "added_sugar_density": ("added_sugars_g", "sugars_g"),
    "total_sugar_density": ("sugars_g",),
    "glycemic_load": ("carbohydrate_g", "sugars_g"),
    "saturated_fat_density": ("saturated_fat_g",),
    "trans_fat_density": ("trans_fat_g",),
    "phosphorus_density": ("phosphorus_mg",),
    "protein_density": ("protein_g",),
    "cholesterol_density": ("cholesterol_mg",),
}


def _negative_features(domain: dict[str, Any]) -> set[str]:
    values = domain.get("top_negative_features")
    return {str(item).strip().lower() for item in values or [] if str(item).strip()}


def _negative_contributors(domain: dict[str, Any]) -> list[dict[str, Any]]:
    raw = domain.get("negative_contributors")
    return [dict(item) for item in raw or [] if isinstance(item, dict)]


def _is_low_adequacy_signal(item: dict[str, Any]) -> bool:
    text = " ".join(
        str(item.get(key) or "").strip().lower()
        for key in ("rule_id", "rule_name")
    )
    if any(token in text for token in ("high ", "high_", "load", "excess")):
        return False
    return any(
        token in text
        for token in ("low ", "low_", "insufficient", "inadequate", "deficien", "adequacy")
    )


def _reduction_nutrients_for_domain(domain: dict[str, Any]) -> set[str]:
    """Map adverse *excess* evidence to nutrients worth reducing.

    A negative feature name alone is not enough: ``protein_density`` can be
    negative because protein is too LOW (muscle/healthy-aging) or because the
    load is high (renal).  The old feature-only mapping treated both as
    reduction signals and could therefore reject every protein-containing
    candidate for a low-protein domain.
    """
    nutrients: set[str] = set()
    contributors = _negative_contributors(domain)
    if contributors:
        for item in contributors:
            feature = str(item.get("feature") or "").strip().lower()
            mapped = _REDUCTION_FEATURE_NUTRIENTS.get(feature, ())
            if not mapped or _is_low_adequacy_signal(item):
                continue
            if feature == "protein_density":
                text = " ".join(
                    str(item.get(key) or "").lower()
                    for key in ("rule_id", "rule_name")
                )
                if not any(token in text for token in ("high", "load", "excess")):
                    continue
            nutrients.update(mapped)
        return nutrients

    # Legacy score payloads may expose only top_negative_features.  Preserve
    # reduction behavior for unambiguous excess features, but deliberately do
    # NOT infer protein reduction without a rule-level direction.
    for feature in _negative_features(domain):
        if feature == "protein_density":
            continue
        nutrients.update(_REDUCTION_FEATURE_NUTRIENTS.get(feature, ()))
    return nutrients


def _requires_reduction(domain: dict[str, Any]) -> bool:
    features = _negative_features(domain)
    return bool(_reduction_nutrients_for_domain(domain)) or any(
        token in feature
        for feature in features
        for token in ("processed", "ultra_processed", "refined", "liquid_sugar")
    )


def _candidate_portions(candidate: dict[str, Any], calorie_cap: float) -> list[float]:
    serving = max(5.0, float(candidate.get("serving_g") or 100.0))
    per100_energy = max(0.0, float((candidate.get("nutrients") or {}).get("energy_kcal", 0.0)))
    portions = {
        round(max(5.0, serving * factor), 1)
        for factor in (0.5, 0.75, 1.0, 1.25, 1.5)
    }
    if per100_energy > 0:
        portions = {
            round(max(5.0, min(value, calorie_cap * 100.0 / per100_energy)), 1)
            for value in portions
        }
    return sorted(value for value in portions if value > 0)


async def _analyze_food_set(
    foods: list[dict[str, Any]],
    profile: dict[str, Any],
    *,
    meal_type: str = "Current meal",
) -> dict[str, Any]:
    payload = {
        "status": "completed",
        "meal": {
            "meal_type": meal_type,
            "meal_name": meal_type,
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
    return await attach_personalization(scored, profile)



def _shortfall_nutrient_keys(
    totals: dict[str, float],
    targets: dict[str, dict[str, Any]],
    *,
    maximum: int = 10,
) -> list[str]:
    """Return the most under-covered adequacy nutrients for candidate planning."""
    ranked: list[tuple[float, str]] = []
    for key, target in targets.items():
        # Missing nutrient data is unknown, not a confirmed shortfall.
        if key not in totals:
            continue
        current = max(0.0, totals.get(key, 0.0))
        kind = str(target.get("type") or "minimum")
        if kind == "maximum":
            continue
        if kind == "range":
            goal = _number(target.get("low"))
        else:
            goal = _number(target.get("value"))
        if goal is None or goal <= 0:
            continue
        coverage = current / goal
        # Recommendation is for meaningful gaps, not topping up nutrients that
        # are already in a practically adequate range. The UI can still show
        # the exact percent, but food suggestions start below 80%.
        if coverage >= _GOOD_ADEQUACY_RATIO:
            continue
        ranked.append((coverage, key))
    ranked.sort(key=lambda row: (row[0], row[1]))
    return [key for _, key in ranked[: max(1, maximum)]]

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
            low, high = float(target["low"]), float(target["high"])
            if old > high:
                goal = high
                old_gap = old - high
                new_gap = max(0.0, new - high)
            else:
                goal = low
                old_gap = max(0.0, low - old)
                new_gap = max(0.0, low - new)
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


def _exceeded_nutrient_targets(
    totals: dict[str, float],
    targets: dict[str, dict[str, Any]],
) -> list[tuple[float, str, float, dict[str, Any]]]:
    """Material nutrient excesses that deserve an explicit portion action.

    Minimum/RDA targets are never called excessive merely for being >100%. A
    real food-applicable UL can trigger an excess for any reported nutrient.
    Protein has a separate 20% balance-guidance buffer because it generally
    has no medical UL in the target registry.
    """
    rows: list[tuple[float, str, float, dict[str, Any]]] = []
    direct_balance_keys = {
        "energy_kcal", "protein_g", "carbohydrate_g", "fat_g",
        "sodium_mg", "saturated_fat_g", "added_sugars_g", "trans_fat_g",
    }
    for key, target in targets.items():
        if not isinstance(target, dict):
            continue
        current = max(0.0, totals.get(key, 0.0))
        if current <= 0:
            continue
        kind = target.get("type")
        limit: float | None = None
        scoring_target: dict[str, Any] | None = None

        upper = _number(target.get("upper_limit"))
        if upper is not None and upper > 0 and current > upper:
            limit = upper
            scoring_target = {"type": "maximum", "value": upper}
        elif key in direct_balance_keys and kind == "range":
            high = _number(target.get("high"))
            if high is not None and high > 0 and current > high:
                limit = high
                scoring_target = target
        elif key in direct_balance_keys and kind == "maximum":
            value = _number(target.get("value"))
            if value is not None and value > 0 and current > value:
                limit = value
                scoring_target = target
        elif key == "protein_g" and kind == "minimum":
            value = _number(target.get("value"))
            if value is not None and value > 0:
                guidance_limit = value * 1.20
                if current > guidance_limit:
                    limit = guidance_limit
                    scoring_target = {"type": "maximum", "value": guidance_limit}

        if limit is None or scoring_target is None:
            continue
        rows.append((current / max(limit, 0.0001), key, limit, scoring_target))
    rows.sort(reverse=True)
    return rows


def _scaled_existing_food(food: dict[str, Any], factor: float) -> dict[str, Any]:
    reduced = copy.deepcopy(food)
    for key, value in (reduced.get("nutrients") or {}).items():
        numeric = _number(value)
        reduced["nutrients"][key] = None if numeric is None else round(numeric * factor, 4)
    quantity = _number(reduced.get("estimated_weight_g")) or _number(reduced.get("quantity"))
    if quantity is not None:
        reduced["quantity"] = round(quantity * factor, 1)
        reduced["estimated_weight_g"] = round(quantity * factor, 1)
    return reduced


def _reason(action: str, changes: list[dict[str, Any]], context: str) -> str:
    labels = [item["label"] for item in changes[:3]]
    if labels:
        joined = ", ".join(labels[:-1]) + (f" and {labels[-1]}" if len(labels) > 1 else labels[0])
        verb = "reduces excess" if action in {"replace", "adjust_portion"} else "closes today’s gaps in"
        return f"This {verb} {joined} and fits {context}."
    return f"This produces a better simulated current-day balance and fits {context}."


async def _recommend_after_analysis_v1(
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
        upper_safe, _ = _personalized_upper_limit_safe(candidate, normalized_profile, baseline_totals, serving_g=serving)
        if not upper_safe:
            continue
        simulated_score, domains = await _score_food_set(simulated_foods, normalized_profile)
        if _protected_domain_decline_numbers(simulated_baseline_domains, domains, normalized_profile) > 0.75:
            continue
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
            key=lambda food: _nutrient_amount(food, nutrient_key),
            default=None,
        )
        if offender is None:
            continue
        contribution = _nutrient_amount(offender, nutrient_key)
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


def _domain_label(key: str, item: dict[str, Any]) -> str:
    if key == "kidney":
        # This score describes dietary support signals; it is not a diagnosis
        # or a measurement of kidney function.
        return "Renal dietary-support"
    explicit = str(item.get("health_domain") or "").strip()
    if explicit and _domain_token(explicit) != _domain_token(key):
        return explicit
    return DOMAIN_HEALTH_LABEL.get(key, key.replace("_", " ").title())


def _domain_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    key: str,
) -> tuple[float, float, float]:
    old = _number((before.get(key) or {}).get("score")) or 0.0
    new = _number((after.get(key) or {}).get("score")) or old
    return old, new, new - old


def _collateral_decline(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    target_key: str,
) -> float:
    declines = []
    for key, old_item in before.items():
        if key == target_key or key not in after:
            continue
        old = _number(old_item.get("score"))
        new = _number(after[key].get("score"))
        if old is not None and new is not None:
            declines.append(old - new)
    return max(declines, default=0.0)


def _recommendation_item(
    *,
    action: str,
    food: dict[str, Any],
    target_key: str,
    target_item: dict[str, Any],
    before_domains: dict[str, dict[str, Any]],
    after_domains: dict[str, dict[str, Any]],
    before_totals: dict[str, float],
    after_totals: dict[str, float],
    targets: dict[str, dict[str, Any]],
    before_overall: float,
    after_overall: float,
    context: str,
    eligibility: dict[str, bool],
    replaces: dict[str, Any] | None = None,
) -> dict[str, Any]:
    old, new, delta = _domain_delta(before_domains, after_domains, target_key)
    changes = _priority_changes(before_totals, after_totals, targets)
    label = _domain_label(target_key, target_item)
    return {
        "action": action,
        "scope": "current_meal",
        "combined_meal": True,
        "food": food,
        **({"replaces": replaces} if replaces else {}),
        "target_domain": {
            "key": target_key,
            "label": label,
            "before": round(old, 2),
            "after": round(new, 2),
            "delta": round(delta, 2),
            "confidence": round(float(target_item.get("confidence") or 0.25), 3),
        },
        "baseline_score": round(before_overall, 2),
        "predicted_score": round(after_overall, 2),
        "score_delta": round(after_overall - before_overall, 2),
        "predicted_score_low": round(max(0.0, after_overall - 1.5), 1),
        "predicted_score_high": round(min(100.0, after_overall + 1.5), 1),
        "domain_deltas": {
            key: round((_number(item.get("score")) or 0.0) -
                       (_number((before_domains.get(key) or {}).get("score")) or 0.0), 2)
            for key, item in after_domains.items()
            if abs((_number(item.get("score")) or 0.0) -
                   (_number((before_domains.get(key) or {}).get("score")) or 0.0)) >= 0.25
        },
        "nutrient_effects": changes,
        "reason": (
            f"This is simulated as part of the current meal and improves its "
            f"{label} score from {old:.0f} to {new:.0f}."
        ),
        "warnings": [
            "Apply only if the food and portion match what will actually be eaten.",
        ],
        "confidence": round(min(0.90, 0.62 + float(target_item.get("confidence") or 0.25) * 0.25), 2),
        "eligibility": eligibility,
        "_target_delta": delta,
        "_collateral": _collateral_decline(before_domains, after_domains, target_key),
        "_context": context,
    }


async def recommend_after_analysis(
    *,
    current_result: dict[str, Any],
    today_results: list[dict[str, Any]],
    profile: dict[str, Any] | None,
    local_hour: int,
    maximum_results: int = 5,
    preferred_domain_keys: list[str] | None = None,
    preferred_nutrient_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Rank safe changes by improvement to the weakest current-meal domain."""
    normalized_profile = normalize_user_profile(profile)
    _, current_foods = _collect_day_foods(current_result, [])
    if not current_foods:
        raise ValueError("No nutrient-bearing foods were available for recommendations.")

    hour = max(0, min(local_hour, 23))
    context, calorie_cap, remaining_occasions = _time_context(hour)
    root = _unwrap_result(current_result)
    meal_type = str(root.get("meal", {}).get("meal_type") or "Current meal")
    baseline_analysis = await _analyze_food_set(
        current_foods,
        normalized_profile,
        meal_type=meal_type,
    )
    before_overall, before_domain_numbers = _overall_score(baseline_analysis)
    before_domains = _domain_score_items(baseline_analysis)
    ranked_targets = _target_domains(baseline_analysis, maximum=8)
    requested = {
        str(key).strip().lower()
        for key in preferred_domain_keys or []
        if str(key).strip()
    }
    requested_nutrients = {
        _canonical_nutrient_key(str(key).strip())
        for key in preferred_nutrient_keys or []
        if str(key).strip()
    }
    # Evaluate enough domains to avoid a catalogue miss on the absolute
    # weakest score causing the engine to jump straight to one mid-range
    # module.  Normal flow is still score-first; an explicit preferred-domain
    # request moves that domain to the front without discarding the low-score
    # modules that follow it.
    # Search breadth must not be tied to the number of cards eventually shown.
    # A few of the very weakest domains may have no safe/compatible candidate,
    # so inspect every low domain exposed by _target_domains (up to eight) and
    # still return only `maximum_results` cards at the end.
    target_window = min(len(ranked_targets), 8)
    if requested:
        preferred = [
            item for item in ranked_targets if item[0].strip().lower() in requested
        ]
        remaining = [item for item in ranked_targets if item not in preferred]
        targets_to_improve = [*preferred, *remaining][
            : max(target_window, min(len(preferred), 5))
        ]
    else:
        targets_to_improve = ranked_targets[:target_window]
    targets = _resolved_targets(normalized_profile)
    before_totals = _sum_nutrients(current_foods)
    before_balance = _target_score(before_totals, targets)

    planner_domains = [
        {
            "key": key,
            "label": _domain_label(key, item),
            "score": round(float(item.get("score") or 0.0), 2),
            "negative_features": sorted(_negative_features(item)),
        }
        for key, item in targets_to_improve
    ]
    candidate_pool, candidate_provider = await discover_recommendation_candidates(
        current_result=current_result,
        current_foods=current_foods,
        profile=normalized_profile,
        target_domains=planner_domains,
        target_nutrients=_shortfall_nutrient_keys(before_totals, targets),
        local_hour=hour,
        maximum_candidates=10,
        fallback_candidates=FOOD_RECOMMENDATION_CATALOG,
    )

    # The broad internal-food-base + USDA pool remains primary, but one verified
    # batch can still be too narrow for the particular evidence rules driving
    # the weakest domain. Supplement (never replace) it with distinct legacy
    # candidates so a 200 response is much less likely to contain zero useful
    # options. This supplement performs no external candidate-generation call.
    dynamic_pool = list(candidate_pool)
    dynamic_count = len(dynamic_pool)
    seen_candidate_ids = {
        str(item.get("fdc_id") or item.get("id") or item.get("name") or "").lower()
        for item in dynamic_pool
    }
    for fallback in FOOD_RECOMMENDATION_CATALOG:
        identity = str(fallback.get("fdc_id") or fallback.get("id") or fallback.get("name") or "").lower()
        if identity in seen_candidate_ids:
            continue
        dynamic_pool.append(fallback)
        seen_candidate_ids.add(identity)
        if len(dynamic_pool) >= 16:
            break
    candidate_pool = dynamic_pool
    if isinstance(candidate_provider, dict):
        candidate_provider["curated_supplement_used"] = len(candidate_pool) > dynamic_count
        candidate_provider["supplemented_candidate_count"] = max(0, len(candidate_pool) - dynamic_count)
        candidate_provider["evaluated_candidate_count"] = len(candidate_pool)

    evaluated: list[dict[str, Any]] = []
    soft_domain_candidates: list[dict[str, Any]] = []
    candidate_index = 0

    # Deterministic nutrient-gap fallback. Health-domain evidence can be
    # intentionally conservative, so a safe food that meaningfully closes a
    # real nutrient gap must not disappear merely because the modeled module
    # score changes by <0.25 points. This is especially important in Insights,
    # where users explicitly ask for "to add" / "to reduce" actions.
    shortfall_rows: list[tuple[float, str, float, dict[str, Any]]] = []
    for nutrient_key, target in targets.items():
        if not isinstance(target, dict):
            continue
        # Missing nutrient data is unknown, not a confirmed deficiency.
        if nutrient_key not in before_totals:
            continue
        kind = str(target.get("type") or "minimum")
        if kind == "maximum":
            continue
        goal = _number(target.get("low")) if kind == "range" else _number(target.get("value"))
        if goal is None or goal <= 0:
            continue
        current = max(0.0, before_totals.get(nutrient_key, 0.0))
        coverage = current / goal
        if coverage >= _GOOD_ADEQUACY_RATIO:
            continue
        shortfall_rows.append((coverage, nutrient_key, goal, target))
    shortfall_rows.sort(
        key=lambda row: (
            0 if row[1] in requested_nutrients else 1,
            row[0],
            row[1],
        )
    )

    for coverage, nutrient_key, goal, target in shortfall_rows[:4]:
        ranked_candidates = sorted(
            candidate_pool,
            key=lambda candidate: (
                _nutrient_amount(candidate, nutrient_key)
                * max(5.0, float(candidate.get("serving_g") or 100.0))
                / 100.0
            ),
            reverse=True,
        )
        for candidate in ranked_candidates[:6]:
            if _candidate_already_present(candidate, current_foods):
                continue
            allowed, audit, _ = _candidate_eligibility(candidate, normalized_profile)
            if not allowed:
                continue
            compatible, _ = _meal_compatibility(candidate, current_result, current_foods, hour)
            if not compatible:
                continue

            grams = max(5.0, float(candidate.get("serving_g") or 100.0))
            per100_energy = _nutrient_amount(candidate, "energy_kcal")
            if per100_energy > 0 and calorie_cap > 0:
                grams = min(grams, max(5.0, calorie_cap * 100.0 / per100_energy))
            contribution = _nutrient_amount(candidate, nutrient_key) * grams / 100.0
            if contribution <= 0:
                continue

            upper_safe, _ = _personalized_upper_limit_safe(
                candidate,
                normalized_profile,
                before_totals,
                serving_g=grams,
            )
            if not upper_safe:
                continue

            candidate_index += 1
            addition = _scaled_candidate_food(candidate, grams, candidate_index)
            simulated_foods = [*copy.deepcopy(current_foods), addition]
            after_totals = _sum_nutrients(simulated_foods)
            old_amount = max(0.0, before_totals.get(nutrient_key, 0.0))
            new_amount = max(0.0, after_totals.get(nutrient_key, 0.0))
            before_percent = min(100.0, old_amount / goal * 100.0)
            after_percent = min(100.0, new_amount / goal * 100.0)
            adequacy_delta = after_percent - before_percent
            if adequacy_delta < 2.0:
                continue

            simulated = await _analyze_food_set(
                simulated_foods,
                normalized_profile,
                meal_type=meal_type,
            )
            after_domains = _domain_score_items(simulated)
            if _protected_domain_decline_items(
                before_domains,
                after_domains,
                normalized_profile,
            ) > 0.75:
                continue
            after_overall, _ = _overall_score(simulated)
            label = _NUTRIENT_LABELS.get(
                nutrient_key,
                nutrient_key.replace("_", " "),
            )
            unit = _NUTRIENT_UNITS.get(nutrient_key, "")
            evaluated.append({
                "action": "add",
                "scope": "current_meal",
                "combined_meal": True,
                "food": {
                    "catalog_id": candidate.get("id"),
                    **({"fdc_id": candidate["fdc_id"]} if isinstance(candidate.get("fdc_id"), int) else {}),
                    "candidate_source": candidate.get("candidate_source", "curated_fallback"),
                    "name": str(candidate.get("name") or "Food"),
                    "search_query": str(candidate.get("search_query") or candidate.get("name") or ""),
                    "quantity": round(grams, 1),
                    "unit": "g",
                },
                "baseline_score": before_overall,
                "predicted_score": after_overall,
                "score_delta": round(after_overall - before_overall, 2),
                "predicted_score_low": round(max(0.0, after_overall - 1.5), 1),
                "predicted_score_high": round(min(100.0, after_overall + 1.5), 1),
                "target_domain": {
                    "key": f"nutrient:{nutrient_key}",
                    "label": f"{label.title()} adequacy",
                    "before": round(before_percent, 2),
                    "after": round(after_percent, 2),
                    "delta": round(adequacy_delta, 2),
                    "confidence": 0.9,
                },
                "nutrient_effects": [{
                    "nutrient": nutrient_key,
                    "label": label,
                    "before": round(old_amount, 2),
                    "after": round(new_amount, 2),
                    "target": round(goal, 2),
                    "improvement": round(new_amount - old_amount, 2),
                }],
                "reason": (
                    f"{label.title()} is at {coverage * 100:.0f}% of its current reference. "
                    f"Adding this verified portion moves it toward {goal:.1f} {unit}."
                ),
                "warnings": [],
                "confidence": 0.9,
                "eligibility": audit,
                "_target_delta": adequacy_delta,
                "_collateral": 0.0,
                "_utility": 85.0 + adequacy_delta,
                "_nutrient_priority": True,
            })
            break

    # Nutrient-balance excesses get explicit current-meal portion actions even
    # when the corresponding health module is not one of the two weakest. This
    # prevents obvious carbohydrate/protein/fat/limit excesses from being
    # hidden behind unrelated domain recommendations.
    exceeded_rows = _exceeded_nutrient_targets(before_totals, targets)
    exceeded_rows.sort(
        key=lambda row: (
            0 if row[1] in requested_nutrients else 1,
            -row[0],
            row[1],
        )
    )
    for excess_ratio, nutrient_key, limit, scoring_target in exceeded_rows[:4]:
        offender = max(
            current_foods,
            key=lambda food: _nutrient_amount(food, nutrient_key),
            default=None,
        )
        if offender is None:
            continue
        contribution = _nutrient_amount(offender, nutrient_key)
        quantity = _number(offender.get("estimated_weight_g")) or _number(offender.get("quantity"))
        if contribution <= 0 or quantity is None or quantity <= 10:
            continue

        excess_amount = max(0.0, before_totals.get(nutrient_key, 0.0) - limit)
        reduction_needed = excess_amount / contribution if contribution > 0 else 0.1
        # General recommendations propose the smallest useful 10% step, capped
        # at a 50% reduction. Meal Guidance itself remains fully interactive in
        # 10% +/- steps before analysis.
        reduction_step = math.ceil(max(0.1, min(reduction_needed, 0.5)) * 10.0) / 10.0
        factor = max(0.5, min(0.9, 1.0 - reduction_step))
        reduced = _scaled_existing_food(offender, factor)
        simulated_foods = [
            reduced if food.get("id") == offender.get("id") else copy.deepcopy(food)
            for food in current_foods
        ]
        after_totals = _sum_nutrients(simulated_foods)
        after_amount = max(0.0, after_totals.get(nutrient_key, 0.0))
        if after_amount >= before_totals.get(nutrient_key, 0.0):
            continue
        simulated = await _analyze_food_set(
            simulated_foods, normalized_profile, meal_type=meal_type
        )
        after_domains = _domain_score_items(simulated)
        if _protected_domain_decline_items(before_domains, after_domains, normalized_profile) > 0.75:
            continue
        after_overall, _ = _overall_score(simulated)
        before_metric = _target_score(
            {nutrient_key: before_totals.get(nutrient_key, 0.0)},
            {nutrient_key: scoring_target},
        )
        after_metric = _target_score(
            {nutrient_key: after_amount},
            {nutrient_key: scoring_target},
        )
        metric_delta = after_metric - before_metric
        if metric_delta <= 0:
            continue
        label = _NUTRIENT_LABELS.get(nutrient_key, nutrient_key.replace("_", " "))
        unit = _NUTRIENT_UNITS.get(nutrient_key, "")
        new_quantity = _number(reduced.get("estimated_weight_g")) or _number(reduced.get("quantity"))
        if new_quantity is None or new_quantity <= 0:
            continue
        reference_word = "guidance reference" if nutrient_key == "protein_g" and targets.get(nutrient_key, {}).get("type") == "minimum" else "target range"
        evaluated.append({
            "action": "adjust_portion",
            "scope": "current_meal",
            "food": {
                "name": str(offender.get("display_name") or offender.get("name") or "Food"),
                "quantity": round(new_quantity, 1),
                "original_quantity": round(quantity, 1),
                "unit": "g",
            },
            "baseline_score": before_overall,
            "predicted_score": after_overall,
            "score_delta": round(after_overall - before_overall, 2),
            "predicted_score_low": round(max(0.0, after_overall - 1.5), 1),
            "predicted_score_high": round(min(100.0, after_overall + 1.5), 1),
            "target_domain": {
                "key": f"nutrient:{nutrient_key}",
                "label": f"{label.title()} balance",
                "before": round(before_metric, 2),
                "after": round(after_metric, 2),
                "delta": round(metric_delta, 2),
                "confidence": 0.9,
            },
            "nutrient_effects": [{
                "nutrient": nutrient_key,
                "label": label,
                "before": round(before_totals.get(nutrient_key, 0.0), 2),
                "after": round(after_amount, 2),
                "target": round(limit, 2),
                "improvement": round(before_totals.get(nutrient_key, 0.0) - after_amount, 2),
            }],
            "reason": (
                f"{label.title()} is above the {reference_word}. Reducing this current-meal portion "
                f"moves it from {before_totals.get(nutrient_key, 0.0):.1f} to {after_amount:.1f} {unit} "
                f"toward {limit:.1f} {unit}."
            ),
            "warnings": [
                "This is a nutrition-balance portion suggestion; confirm the portion you actually eat."
            ],
            "confidence": 0.9,
            "eligibility": {
                "diet_verified": True,
                "allergen_verified": True,
                "medical_constraints_verified": True,
                "preference_verified": True,
            },
            "combined_meal": True,
            "_target_delta": metric_delta,
            "_collateral": 0.0,
            "_utility": 100.0 + (excess_ratio - 1.0) * 40.0 + metric_delta,
            "_nutrient_priority": True,
            "_excess_priority": True,
        })

    for target_key, target_item in targets_to_improve:
        reduction_first = _requires_reduction(target_item)
        for candidate in candidate_pool:
            if _candidate_already_present(candidate, current_foods):
                continue
            allowed, audit, _ = _candidate_eligibility(candidate, normalized_profile)
            if not allowed:
                continue
            compatible, _ = _meal_compatibility(candidate, current_result, current_foods, hour)
            if not compatible:
                continue
            for grams in _candidate_portions(candidate, calorie_cap):
                candidate_index += 1
                addition = _scaled_candidate_food(candidate, grams, candidate_index)
                simulated_foods = [*copy.deepcopy(current_foods), addition]
                upper_safe, _ = _personalized_upper_limit_safe(candidate, normalized_profile, before_totals, serving_g=grams)
                if not upper_safe:
                    continue
                simulated = await _analyze_food_set(
                    simulated_foods,
                    normalized_profile,
                    meal_type=meal_type,
                )
                after_domains = _domain_score_items(simulated)
                if _protected_domain_decline_items(before_domains, after_domains, normalized_profile) > 0.75:
                    continue
                old, new, target_delta = _domain_delta(
                    before_domains, after_domains, target_key
                )
                if target_delta <= 0.005:
                    continue
                collateral = _collateral_decline(before_domains, after_domains, target_key)
                if collateral > 3.0:
                    continue
                # If the module is being held down by an excess, an addition
                # must show a strong direct gain; otherwise reduction is safer.
                if reduction_first and target_delta < 0.50:
                    continue
                after_overall, _ = _overall_score(simulated)
                after_totals = _sum_nutrients(simulated_foods)
                item = _recommendation_item(
                    action="add",
                    food={
                        "catalog_id": candidate["id"],
                        **({"fdc_id": candidate["fdc_id"]} if isinstance(candidate.get("fdc_id"), int) else {}),
                        "candidate_source": candidate.get("candidate_source", "curated_fallback"),
                        "name": candidate["name"],
                        "search_query": candidate["search_query"],
                        "quantity": round(grams, 1),
                        "unit": "g",
                    },
                    target_key=target_key,
                    target_item=target_item,
                    before_domains=before_domains,
                    after_domains=after_domains,
                    before_totals=before_totals,
                    after_totals=after_totals,
                    targets=targets,
                    before_overall=before_overall,
                    after_overall=after_overall,
                    context=context,
                    eligibility=audit,
                )
                # Target gain dominates. Overall score is only a tie-breaker,
                # so a strong module-specific recommendation is not hidden.
                item["_utility"] = (
                    target_delta * 10.0
                    + (after_overall - before_overall)
                    - collateral * 3.0
                )
                if target_delta >= 0.25:
                    evaluated.append(item)
                elif collateral <= 1.0:
                    # Do not return an empty weakest-score card when there is a
                    # genuine, safe positive movement that simply falls below
                    # the normal 0.25-point materiality threshold. This is a
                    # fallback only; strong candidates always outrank it.
                    item["_soft_domain_fallback"] = True
                    item["warnings"] = [
                        *item.get("warnings", []),
                        "The modeled target-domain improvement is small; re-analyze after applying the portion.",
                    ]
                    soft_domain_candidates.append(item)

        # When a domain's evidence points to excess, simulate reducing the
        # current food contributing most to that implicated nutrient.
        implicated = _reduction_nutrients_for_domain(target_item)
        for nutrient_key in implicated:
            offender = max(
                current_foods,
                key=lambda food: _nutrient_amount(food, nutrient_key),
                default=None,
            )
            if offender is None:
                continue
            quantity = _number(offender.get("estimated_weight_g")) or _number(offender.get("quantity"))
            contribution = _nutrient_amount(offender, nutrient_key)
            if quantity is None or quantity <= 10 or contribution <= 0:
                continue
            reduced = copy.deepcopy(offender)
            for key, value in (reduced.get("nutrients") or {}).items():
                numeric = _number(value)
                reduced["nutrients"][key] = None if numeric is None else round(numeric * 0.75, 4)
            reduced["quantity"] = round(quantity * 0.75, 1)
            reduced["estimated_weight_g"] = round(quantity * 0.75, 1)
            simulated_foods = [
                reduced if food.get("id") == offender.get("id") else copy.deepcopy(food)
                for food in current_foods
            ]
            simulated = await _analyze_food_set(simulated_foods, normalized_profile, meal_type=meal_type)
            after_domains = _domain_score_items(simulated)
            _, _, target_delta = _domain_delta(before_domains, after_domains, target_key)
            collateral = _collateral_decline(before_domains, after_domains, target_key)
            if target_delta < 0.25 or collateral > 3.0:
                continue
            after_overall, _ = _overall_score(simulated)
            item = _recommendation_item(
                action="adjust_portion",
                food={
                    "name": str(offender.get("display_name") or offender.get("name") or "Food"),
                    "quantity": round(quantity * 0.75, 1),
                    "original_quantity": round(quantity, 1),
                    "unit": "g",
                },
                target_key=target_key,
                target_item=target_item,
                before_domains=before_domains,
                after_domains=after_domains,
                before_totals=before_totals,
                after_totals=_sum_nutrients(simulated_foods),
                targets=targets,
                before_overall=before_overall,
                after_overall=after_overall,
                context=context,
                eligibility={
                    "diet_verified": True,
                    "allergen_verified": True,
                    "medical_constraints_verified": True,
                    "preference_verified": True,
                },
            )
            item["reason"] = (
                f"Reducing this current-meal portion is simulated to improve the "
                f"{_domain_label(target_key, target_item)} score without creating a separate meal."
            )
            item["_utility"] = target_delta * 10.0 - collateral * 3.0
            evaluated.append(item)

            # Also simulate a real swap when a compatible catalogue food
            # carries materially less of the implicated excess nutrient.
            for candidate in candidate_pool:
                if _candidate_already_present(candidate, current_foods):
                    continue
                allowed, audit, _ = _candidate_eligibility(candidate, normalized_profile)
                compatible, _ = _meal_compatibility(
                    candidate, current_result, current_foods, hour
                )
                if not allowed or not compatible:
                    continue
                grams = float(candidate.get("serving_g") or 100.0)
                replacement_load = _nutrient_amount(candidate, nutrient_key) * grams / 100.0
                if replacement_load >= contribution * 0.5:
                    continue
                candidate_index += 1
                replacement = _scaled_candidate_food(candidate, grams, candidate_index)
                replaced_foods = [
                    replacement
                    if food.get("id") == offender.get("id")
                    else copy.deepcopy(food)
                    for food in current_foods
                ]
                replaced_analysis = await _analyze_food_set(
                    replaced_foods,
                    normalized_profile,
                    meal_type=meal_type,
                )
                replaced_domains = _domain_score_items(replaced_analysis)
                if _protected_domain_decline_items(before_domains, replaced_domains, normalized_profile) > 0.75:
                    continue
                _, _, replacement_delta = _domain_delta(
                    before_domains, replaced_domains, target_key
                )
                replacement_collateral = _collateral_decline(
                    before_domains, replaced_domains, target_key
                )
                if replacement_delta < 0.25 or replacement_collateral > 3.0:
                    continue
                replaced_overall, _ = _overall_score(replaced_analysis)
                replacement_item = _recommendation_item(
                    action="replace",
                    food={
                        "catalog_id": candidate["id"],
                        **({"fdc_id": candidate["fdc_id"]} if isinstance(candidate.get("fdc_id"), int) else {}),
                        "candidate_source": candidate.get("candidate_source", "curated_fallback"),
                        "name": candidate["name"],
                        "search_query": candidate["search_query"],
                        "quantity": round(grams, 1),
                        "unit": "g",
                    },
                    replaces={
                        "name": str(offender.get("display_name") or offender.get("name") or "Food"),
                        "quantity": round(quantity, 1),
                        "unit": "g",
                    },
                    target_key=target_key,
                    target_item=target_item,
                    before_domains=before_domains,
                    after_domains=replaced_domains,
                    before_totals=before_totals,
                    after_totals=_sum_nutrients(replaced_foods),
                    targets=targets,
                    before_overall=before_overall,
                    after_overall=replaced_overall,
                    context=context,
                    eligibility=audit,
                )
                replacement_item["reason"] = (
                    f"Replacing {str(offender.get('display_name') or offender.get('name') or 'this food')} "
                    f"inside the current meal is simulated to improve its "
                    f"{_domain_label(target_key, target_item)} score."
                )
                replacement_item["_utility"] = (
                    replacement_delta * 10.0 - replacement_collateral * 3.0
                )
                evaluated.append(replacement_item)
            break

    # Explicit nutrient-balance actions may exist even when no health-domain
    # addition survives the normal materiality threshold. In that case, add
    # the best safe small-gain domain candidates rather than showing no module
    # recommendation at all. Medical, diet, compatibility, upper-limit and
    # protected-domain checks have already run above.
    if not any(
        not item.get("_nutrient_priority")
        for item in evaluated
    ):
        soft_domain_candidates.sort(
            key=lambda item: (
                item.get("_target_delta", 0.0),
                -item.get("_collateral", 0.0),
            ),
            reverse=True,
        )
        evaluated.extend(soft_domain_candidates)

    evaluated.sort(
        key=lambda item: (item.get("_utility", 0.0), item.get("_target_delta", 0.0)),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    seen_foods: set[str] = set()
    domain_counts: dict[str, int] = {}
    ordered: list[dict[str, Any]] = []
    preferred_foods: set[str] = set()
    # The card is titled "weakest score", so the first feasible health-domain
    # recommendation must come from the lowest score, not from whichever
    # mid-range domain has the highest confidence/coverage.  We then preserve
    # one explicit nutrient-excess action (when present), followed by the best
    # option for each next-lowest domain. Remaining options fill by utility.
    domain_best: list[dict[str, Any]] = []
    for target_key, _ in targets_to_improve:
        best = next(
            (
                item for item in evaluated
                if str((item.get("target_domain") or {}).get("key") or "") == target_key
            ),
            None,
        )
        if best is not None:
            domain_best.append(best)

    if domain_best:
        first = domain_best[0]
        ordered.append(first)
        preferred_foods.add(
            _food_identity(str((first.get("food") or {}).get("name") or ""))
        )

    # A true excess/reduction action outranks adequacy top-up suggestions.
    # When a health-domain recommendation exists it stays first (the card is
    # still score-first); otherwise the reduction becomes the first action.
    first_excess = next(
        (item for item in evaluated if item.get("_excess_priority")),
        None,
    )
    if first_excess is not None:
        food_identity = _food_identity(
            str((first_excess.get("food") or {}).get("name") or "")
        )
        if food_identity not in preferred_foods:
            ordered.append(first_excess)
            preferred_foods.add(food_identity)

    first_nutrient = next(
        (
            item for item in evaluated
            if item.get("_nutrient_priority") and not item.get("_excess_priority")
        ),
        None,
    )
    if first_nutrient is not None:
        food_identity = _food_identity(
            str((first_nutrient.get("food") or {}).get("name") or "")
        )
        if food_identity not in preferred_foods:
            ordered.append(first_nutrient)
            preferred_foods.add(food_identity)

    for best in domain_best[1:]:
        food_identity = _food_identity(
            str((best.get("food") or {}).get("name") or "")
        )
        if food_identity in preferred_foods:
            continue
        ordered.append(best)
        preferred_foods.add(food_identity)

    for item in evaluated:
        if not item.get("_nutrient_priority"):
            continue
        food_identity = _food_identity(
            str((item.get("food") or {}).get("name") or "")
        )
        if food_identity in preferred_foods:
            continue
        ordered.append(item)
        preferred_foods.add(food_identity)

    ordered.extend(item for item in evaluated if item not in ordered)
    for item in ordered:
        target_key = str((item.get("target_domain") or {}).get("key") or "")
        food_identity = _food_identity(
            str((item.get("food") or {}).get("name") or "")
        )
        if food_identity in seen_foods or domain_counts.get(target_key, 0) >= 3:
            continue
        seen_foods.add(food_identity)
        domain_counts[target_key] = domain_counts.get(target_key, 0) + 1
        cleaned = {
            key: value
            for key, value in item.items()
            if not key.startswith("_")
        }
        cleaned["id"] = f"recommendation_{len(selected) + 1:03d}"
        selected.append(cleaned)
        if len(selected) >= max(1, min(maximum_results, 8)):
            break

    return {
        "status": "completed",
        "engine_version": RECOMMENDATION_ENGINE_VERSION,
        "generated_for_analysis_id": _result_identity(current_result, "current"),
        "timing": {
            "local_hour": hour,
            "context": context,
            "estimated_eating_occasions_remaining": remaining_occasions,
        },
        "baseline": {
            "current_meal_score": before_overall,
            # Kept for older clients; this is now intentionally the current
            # meal, because every recommendation is merged into this analysis.
            "current_day_score": before_overall,
            "nutrition_balance_score": before_balance,
            "domain_scores": before_domain_numbers,
            "meals_included": 1,
        },
        "target_domains": [
            {
                "key": key,
                "label": _domain_label(key, item),
                "score": round(float(item["score"]), 2),
                "confidence": round(float(item.get("confidence") or 0.25), 3),
            }
            for key, item in targets_to_improve
        ],
        "recommendations": selected,
        "candidate_provider": candidate_provider,
        "message": (
            "No safe, meal-compatible module improvement was found from the verified candidate pool."
            if not selected
            else "Each option was USDA-verified, simulated inside this meal, and ranked by its target-module improvement."
        ),
        "disclaimer": (
            "These are dietary-support estimates, not diagnoses or treatment. "
            "Clinical restrictions fail closed when the profile lacks enough detail."
        ),
    }


def _catalog_candidate(catalog_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in FOOD_RECOMMENDATION_CATALOG if item.get("id") == catalog_id),
        None,
    )


async def _candidate_for_recommendation_food(
    food_spec: dict[str, Any],
) -> dict[str, Any] | None:
    fdc_id = food_spec.get("fdc_id")
    grams = _number(food_spec.get("quantity")) or 100.0
    if isinstance(fdc_id, int) or (isinstance(fdc_id, str) and fdc_id.isdigit()):
        return await rehydrate_usda_candidate(int(fdc_id), serving_g=grams)
    return _catalog_candidate(str(food_spec.get("catalog_id") or ""))


async def apply_recommendation(
    *,
    current_result: dict[str, Any],
    today_results: list[dict[str, Any]],
    profile: dict[str, Any] | None,
    local_hour: int,
    recommendation_id: str,
    recommendation_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a recommendation after revalidating it against current data.

    Recommendations are not regenerated from an LLM at apply time.
    The client echoes the selected recommendation payload, but its nutrient,
    diet and safety claims are NOT trusted: an exact FDC id is rehydrated from
    USDA and run through the eligibility + full simulation pipeline again.
    Legacy clients that send only recommendation_id retain the old regeneration
    path (and therefore still work with the curated fallback catalogue).
    """
    recommendation: dict[str, Any] | None = None
    if isinstance(recommendation_payload, dict):
        payload_id = str(recommendation_payload.get("id") or "")
        if payload_id and payload_id != recommendation_id:
            raise ValueError("The selected recommendation payload does not match its id.")
        recommendation = copy.deepcopy(recommendation_payload)

    if recommendation is None:
        recommendation_set = await recommend_after_analysis(
            current_result=current_result,
            today_results=today_results,
            profile=profile,
            local_hour=local_hour,
            maximum_results=8,
        )
        recommendation = next(
            (
                item for item in recommendation_set.get("recommendations", [])
                if item.get("id") == recommendation_id
            ),
            None,
        )
    if recommendation is None:
        raise ValueError("That recommendation is no longer available for this meal.")

    normalized_profile = normalize_user_profile(profile)
    _, current_foods = _collect_day_foods(current_result, [])
    if not current_foods:
        raise ValueError("The current meal no longer contains nutrient-bearing foods.")
    foods = copy.deepcopy(current_foods)
    action = str(recommendation.get("action") or "")
    food_spec = recommendation.get("food") or {}
    if not isinstance(food_spec, dict):
        raise ValueError("The recommended food specification is invalid.")
    applied_food_name = str(food_spec.get("name") or "Food")
    hour = max(0, min(local_hour, 23))

    if action == "add":
        candidate = await _candidate_for_recommendation_food(food_spec)
        if candidate is None:
            raise ValueError("The recommended food could not be revalidated.")
        if _candidate_already_present(candidate, current_foods):
            raise ValueError("That food is already part of this meal.")
        allowed, _, reasons = _candidate_eligibility(candidate, normalized_profile)
        compatible, compatibility_reason = _meal_compatibility(
            candidate, current_result, current_foods, hour
        )
        if not allowed or not compatible:
            detail = ", ".join(reasons or [compatibility_reason])
            raise ValueError(f"The recommendation is no longer safe for this profile: {detail}.")
        grams = _number(food_spec.get("quantity"))
        if grams is None or grams <= 0:
            raise ValueError("The recommended quantity is invalid.")
        upper_safe, upper_reasons = _personalized_upper_limit_safe(
            candidate,
            normalized_profile,
            _sum_nutrients(current_foods),
            serving_g=grams,
        )
        if not upper_safe:
            raise ValueError(
                "The recommendation would now exceed a personalized limit: "
                + ", ".join(upper_reasons)
            )
        foods.append(_scaled_candidate_food(candidate, grams, len(foods) + 1))

    elif action == "adjust_portion":
        wanted = str(food_spec.get("name") or "").strip().lower()
        new_quantity = _number(food_spec.get("quantity"))
        changed = False
        for food in foods:
            name = str(food.get("display_name") or food.get("name") or "").strip().lower()
            old_quantity = _number(food.get("estimated_weight_g")) or _number(food.get("quantity"))
            if changed or name != wanted or new_quantity is None or old_quantity is None or old_quantity <= 0:
                continue
            factor = new_quantity / old_quantity
            for key, value in (food.get("nutrients") or {}).items():
                numeric = _number(value)
                food["nutrients"][key] = None if numeric is None else round(numeric * factor, 4)
            food["quantity"] = round(new_quantity, 1)
            food["estimated_weight_g"] = round(new_quantity, 1)
            changed = True
        if not changed:
            raise ValueError("The original food could not be found in this meal.")

    elif action == "replace":
        candidate = await _candidate_for_recommendation_food(food_spec)
        replaces = recommendation.get("replaces") or {}
        wanted = str(replaces.get("name") or "").strip().lower() if isinstance(replaces, dict) else ""
        grams = _number(food_spec.get("quantity"))
        if candidate is None or not wanted or grams is None or grams <= 0:
            raise ValueError("The replacement recommendation is invalid.")
        allowed, _, reasons = _candidate_eligibility(candidate, normalized_profile)
        compatible, compatibility_reason = _meal_compatibility(
            candidate, current_result, current_foods, hour
        )
        if not allowed or not compatible:
            detail = ", ".join(reasons or [compatibility_reason])
            raise ValueError(f"The replacement is no longer safe for this profile: {detail}.")
        upper_safe, upper_reasons = _personalized_upper_limit_safe(
            candidate,
            normalized_profile,
            _sum_nutrients(current_foods),
            serving_g=grams,
        )
        if not upper_safe:
            raise ValueError(
                "The replacement would now exceed a personalized limit: "
                + ", ".join(upper_reasons)
            )
        replacement = _scaled_candidate_food(candidate, grams, len(foods) + 1)
        changed = False
        for index, food in enumerate(foods):
            name = str(food.get("display_name") or food.get("name") or "").strip().lower()
            if name == wanted:
                foods[index] = replacement
                changed = True
                break
        if not changed:
            raise ValueError("The food to replace could not be found in this meal.")
    else:
        raise ValueError("This recommendation action is not supported.")

    root = _unwrap_result(current_result)
    meal_type = str(root.get("meal", {}).get("meal_type") or "Current meal")
    baseline = await _analyze_food_set(current_foods, normalized_profile, meal_type=meal_type)
    combined = await _analyze_food_set(foods, normalized_profile, meal_type=meal_type)

    # The echoed payload can never force an addition that no longer improves
    # its claimed target. Recompute the target domain from the fresh pipeline.
    target = recommendation.get("target_domain")
    target_key = str(target.get("key") or "") if isinstance(target, dict) else ""
    if target_key and not target_key.startswith("nutrient:"):
        before_domains = _domain_score_items(baseline)
        after_domains = _domain_score_items(combined)
        if target_key in before_domains and target_key in after_domains:
            _, _, delta = _domain_delta(before_domains, after_domains, target_key)
            if action in {"add", "replace"} and delta <= 0.05:
                raise ValueError(
                    "That food no longer improves the selected health module after revalidation."
                )
            if _protected_domain_decline_items(
                before_domains, after_domains, normalized_profile
            ) > 0.75:
                raise ValueError(
                    "That change would now worsen a health domain protected by your profile."
                )

    combined = attach_nutrient_targets(combined, normalized_profile)
    analysis_id = _result_identity(current_result, "current")
    combined["analysis_id"] = analysis_id
    combined["status"] = "completed"
    combined["recommendation_application"] = {
        "recommendation_id": recommendation_id,
        "action": action,
        "food_name": applied_food_name,
        "target_domain": recommendation.get("target_domain"),
        "combined_with_existing_meal": True,
        "replaces_history_analysis_id": analysis_id,
        "engine_version": RECOMMENDATION_ENGINE_VERSION,
        "apply_contract_version": RECOMMENDATION_APPLY_CONTRACT_VERSION,
        "revalidated_from_usda": isinstance(food_spec.get("fdc_id"), int),
    }
    return combined

