from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Optional, Tuple

from nutrient_target_data import (
    CANONICAL_KEY_COMPATIBILITY,
    CONDITION_TARGET_POLICY,
    DIET_PATTERN_RISK_FLAGS,
    EER_EQUATIONS,
    LACTATION_ENERGY_ADJUSTMENTS,
    LIFE_STAGE_BANDS,
    MEDICATION_RISK_FLAGS,
    NUTRIENT_SCHEMA_VERSION,
    NUTRIENT_TARGET_REGISTRY,
    PREGNANCY_ENERGY_ADJUSTMENTS,
    TARGET_DATA_VERSION,
    TARGET_OVERRIDE_PRECEDENCE,
    TARGET_STATUS_MEASUREMENT_BASIS_UNVERIFIED,
    TARGET_STATUS_MISSING_PROFILE_DATA,
    TARGET_STATUS_REQUIRES_CLINICAL_INPUT,
    TARGET_STATUS_RESOLVED,
    TARGET_STATUS_RESOLVED_RANGE,
    TARGET_STATUS_UNRESOLVED_REGISTRY_ENTRY,
    validate_target_registry,
)

# =========================================================================
# NUTRITION IMMUTABILITY GUARD
# =========================================================================

def _nutrition_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Capture fields that personalization is never allowed to change."""
    meal = payload.get("meal")
    if not isinstance(meal, dict):
        return {}

    return copy.deepcopy({
        "foods": meal.get("foods"),
        "nutrition": meal.get("nutrition"),
        "nutrition_totals": meal.get("nutrition_totals"),
        "total_nutrition": meal.get("total_nutrition"),
        "nutrition_summary": meal.get("nutrition_summary"),
        "estimated_visible_food_weight_g": meal.get(
            "estimated_visible_food_weight_g"
        ),
    })


def _assert_nutrition_unchanged(
    before: Dict[str, Any],
    payload: Dict[str, Any],
    *,
    stage: str,
) -> None:
    after = _nutrition_snapshot(payload)
    if before != after:
        raise RuntimeError(
            f"{stage} attempted to modify detected foods or nutrition. "
            "Personalization may only add data under meal.personalization."
        )


TARGET_ENGINE_VERSION = "2.0.0"
SUPPORTED_SEXES = {"male", "female"}
SUPPORTED_ACTIVITY_LEVELS = {"sedentary", "low_active", "active", "very_active"}
CKD_IDS = {"ckd", "chronic_kidney_disease", "kidney_disease"}
DIALYSIS_MODALITIES = {"hemodialysis", "peritoneal_dialysis"}
HYPERTENSION_IDS = {"hypertension", "high_blood_pressure"}


def calculate_nutrient_targets(user_profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    validate_target_registry()
    profile = normalize_target_profile(user_profile)
    life_stage = resolve_life_stage(profile)
    energy = resolve_energy_target(profile, life_stage)

    targets: Dict[str, Dict[str, Any]] = {"energy_kcal": energy}
    for key, definition in NUTRIENT_TARGET_REGISTRY.items():
        targets[key] = resolve_nutrient_target(
            nutrient_key=key,
            definition=definition,
            profile=profile,
            life_stage=life_stage,
            energy_target=energy,
        )

    return {
        "engine_version": TARGET_ENGINE_VERSION,
        "schema_version": NUTRIENT_SCHEMA_VERSION,
        "target_data_version": TARGET_DATA_VERSION,
        "precedence": list(TARGET_OVERRIDE_PRECEDENCE),
        "profile_applied": bool(profile),
        "normalized_profile": profile,
        "life_stage": life_stage,
        "targets": targets,
        "risk_flags": build_global_risk_flags(profile),
        "warnings": build_engine_warnings(profile, life_stage, targets),
    }


def attach_nutrient_targets(
    meal_json: Dict[str, Any],
    user_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(meal_json, dict):
        raise ValueError("Meal JSON must be a dictionary.")

    nutrition_before = _nutrition_snapshot(meal_json)
    result = copy.deepcopy(meal_json)
    meal = result.get("meal")
    if not isinstance(meal, dict):
        raise ValueError("Meal JSON must contain a top-level 'meal' dictionary.")

    personalization = meal.get("personalization")
    if not isinstance(personalization, dict):
        personalization = {}
        meal["personalization"] = personalization

    resolved = calculate_nutrient_targets(user_profile)
    personalization["nutrient_targets"] = resolved["targets"]
    personalization["nutrient_risk_flags"] = resolved["risk_flags"]
    personalization["nutrient_target_warnings"] = resolved["warnings"]
    personalization["nutrient_target_profile"] = resolved["normalized_profile"]
    personalization["nutrient_target_life_stage"] = resolved["life_stage"]
    personalization["nutrient_target_engine_version"] = resolved["engine_version"]
    personalization["nutrient_target_schema_version"] = resolved["schema_version"]
    personalization["nutrient_target_data_version"] = resolved["target_data_version"]
    personalization["profile_applied"] = resolved["profile_applied"]
    _assert_nutrition_unchanged(
        nutrition_before,
        result,
        stage="Nutrient-target attachment",
    )
    return result


def normalize_target_profile(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(profile, dict):
        return {}

    out: Dict[str, Any] = {}

    def text(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        value = value.strip().lower().replace(" ", "_").replace("-", "_")
        return value or None

    age_months = profile.get("age_months")
    if isinstance(age_months, (int, float)) and not isinstance(age_months, bool) and 0 <= float(age_months) < 1560:
        out["age_months"] = int(round(float(age_months)))

    age = profile.get("age")
    if isinstance(age, (int, float)) and not isinstance(age, bool) and 0 <= float(age) < 130:
        out["age"] = float(age)
        out.setdefault("age_months", int(round(float(age) * 12)))

    for key in ("height_cm", "weight_kg", "lactation_stage_months"):
        value = profile.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) >= 0:
            out[key] = float(value)

    sex = text(profile.get("sex") or profile.get("gender"))
    if sex in SUPPORTED_SEXES:
        out["sex"] = sex

    activity = text(profile.get("activity_level"))
    aliases = {
        "inactive": "sedentary",
        "lightly_active": "low_active",
        "moderately_active": "active",
        "highly_active": "very_active",
    }
    if activity:
        activity = aliases.get(activity, activity)
    if activity in SUPPORTED_ACTIVITY_LEVELS:
        out["activity_level"] = activity

    for key in (
        "goal", "diet_type", "smoking_status", "ckd_stage",
        "dialysis_modality", "blood_pressure_status", "glycemic_status",
        "diet_pattern",
    ):
        value = text(profile.get(key))
        if value:
            out[key] = value

    trimester = profile.get("trimester")
    if isinstance(trimester, int) and not isinstance(trimester, bool) and trimester in (1, 2, 3):
        out["trimester"] = trimester

    for key in (
        "pregnant", "lactating", "frailty", "low_appetite",
        "resistance_training", "endurance_training",
    ):
        if isinstance(profile.get(key), bool):
            out[key] = profile[key]

    out["chronic_conditions"] = _normalize_collection(
        profile.get("chronic_conditions", profile.get("conditions")), text
    )
    out["medications"] = _normalize_collection(profile.get("medications"), text)
    out["allergies"] = _normalize_collection(profile.get("allergies"), text)
    return out


def _normalize_collection(value: Any, cleaner: Any) -> List[str]:
    values: List[str] = []
    if isinstance(value, dict):
        iterable = [key for key, enabled in value.items() if enabled]
    elif isinstance(value, (list, tuple, set)):
        iterable = list(value)
    else:
        iterable = []
    for raw in iterable:
        cleaned = cleaner(raw)
        if cleaned:
            values.append(cleaned)
    return list(dict.fromkeys(values))


def resolve_life_stage(profile: Dict[str, Any]) -> Dict[str, Any]:
    age_months = profile.get("age_months")
    if not isinstance(age_months, int):
        return {
            "status": TARGET_STATUS_MISSING_PROFILE_DATA,
            "life_stage": None,
            "age_months": None,
            "age_years": None,
            "required_inputs": ["age_or_age_months"],
        }

    matches: List[Tuple[str, Dict[str, Any]]] = []
    for name, band in LIFE_STAGE_BANDS.items():
        minimum = int(band["min_age_months"])
        maximum = band["max_age_months"]
        if age_months < minimum:
            continue
        if maximum is not None and age_months > int(maximum):
            continue
        matches.append((name, band))

    if not matches:
        return {
            "status": TARGET_STATUS_UNRESOLVED_REGISTRY_ENTRY,
            "life_stage": None,
            "age_months": age_months,
            "age_years": age_months / 12.0,
            "required_inputs": [],
        }

    matches.sort(key=lambda item: int(item[1]["min_age_months"]), reverse=True)
    name, band = matches[0]
    return {
        "status": TARGET_STATUS_RESOLVED,
        "life_stage": name,
        "age_months": age_months,
        "age_years": round(age_months / 12.0, 4),
        "min_age_months": band["min_age_months"],
        "max_age_months": band["max_age_months"],
        "required_inputs": [],
    }


def resolve_energy_target(profile: Dict[str, Any], life_stage: Dict[str, Any]) -> Dict[str, Any]:
    result = _base_result("energy_kcal", "Energy", "kcal/day", "EER", None)
    if life_stage.get("status") != TARGET_STATUS_RESOLVED:
        result["required_inputs"] = life_stage.get("required_inputs", ["age_or_age_months"])
        return result

    sex = profile.get("sex")
    if sex not in SUPPORTED_SEXES:
        result["required_inputs"] = ["sex"]
        return result

    equation_id, equation = _select_eer_equation(life_stage["age_months"], sex)
    if equation is None:
        result["status"] = TARGET_STATUS_UNRESOLVED_REGISTRY_ENTRY
        return result

    missing = []
    for key in equation.get("required_inputs", ()):
        if key == "age_months":
            continue
        if profile.get(key) is None:
            missing.append(key)
    if missing:
        result["required_inputs"] = missing
        result["source"] = copy.deepcopy(equation.get("source"))
        result["equation_id"] = equation_id
        return result

    activity_map = equation.get("activity_coefficients")
    pa = 1.0
    if isinstance(activity_map, dict):
        activity = profile.get("activity_level")
        if activity not in activity_map:
            result["required_inputs"] = ["activity_level"]
            result["equation_id"] = equation_id
            return result
        pa = float(activity_map[activity])

    value = _evaluate_eer(
        equation["equation"],
        float(life_stage["age_years"]),
        float(profile["height_cm"]),
        float(profile["weight_kg"]),
        pa,
    )
    result.update({
        "baseline_value": round(value, 2),
        "resolved_value": round(value, 2),
        "status": TARGET_STATUS_RESOLVED,
        "source": copy.deepcopy(equation.get("source")),
        "equation_id": equation_id,
        "override_chain": [equation_id],
    })

    if profile.get("pregnant") is True:
        trimester = profile.get("trimester")
        if trimester not in (1, 2, 3):
            result["resolved_value"] = None
            result["status"] = TARGET_STATUS_MISSING_PROFILE_DATA
            result["required_inputs"] = ["trimester"]
            return result
        result["resolved_value"] = round(value + float(PREGNANCY_ENERGY_ADJUSTMENTS[trimester]), 2)
        result["override_chain"].append(f"pregnancy_trimester_{trimester}")
    elif profile.get("lactating") is True:
        months = profile.get("lactation_stage_months")
        if not isinstance(months, (int, float)):
            result["resolved_value"] = None
            result["status"] = TARGET_STATUS_MISSING_PROFILE_DATA
            result["required_inputs"] = ["lactation_stage_months"]
            return result
        addition = _lactation_addition(float(months))
        if addition is None:
            result["resolved_value"] = None
            result["status"] = TARGET_STATUS_UNRESOLVED_REGISTRY_ENTRY
            return result
        result["resolved_value"] = round(value + addition, 2)
        result["override_chain"].append("lactation_energy_adjustment")

    return result


def _select_eer_equation(age_months: int, sex: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    candidates = []
    for equation_id, definition in EER_EQUATIONS.items():
        if definition.get("sex") != sex:
            continue
        minimum = definition.get("min_age_months")
        maximum = definition.get("max_age_months")
        if isinstance(minimum, int) and age_months < minimum:
            continue
        if isinstance(maximum, int) and age_months > maximum:
            continue
        candidates.append((equation_id, definition))
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: int(item[1].get("min_age_months", 0)), reverse=True)
    return candidates[0]


def _evaluate_eer(c: Dict[str, Any], age_years: float, height_cm: float, weight_kg: float, pa: float) -> float:
    constant = float(c.get("constant", 0.0))
    age_term = float(c.get("age_years_coefficient", 0.0)) * age_years
    weight_term = float(c.get("weight_kg_coefficient", 0.0)) * weight_kg
    growth = float(c.get("growth_allowance", 0.0))
    if "height_cm_coefficient" in c:
        return constant + age_term + float(c["height_cm_coefficient"]) * height_cm + weight_term + growth
    height_term = float(c.get("height_m_coefficient", 0.0)) * (height_cm / 100.0)
    return constant + age_term + pa * (weight_term + height_term) + growth


def _lactation_addition(months: float) -> Optional[float]:
    for definition in LACTATION_ENERGY_ADJUSTMENTS.values():
        if float(definition["min_months_postpartum"]) <= months <= float(definition["max_months_postpartum"]):
            return float(definition["addition_kcal"])
    return None


def resolve_nutrient_target(
    nutrient_key: str,
    definition: Dict[str, Any],
    profile: Dict[str, Any],
    life_stage: Dict[str, Any],
    energy_target: Dict[str, Any],
) -> Dict[str, Any]:
    result = _base_result(
        nutrient_key,
        definition.get("official_name", nutrient_key),
        definition.get("canonical_unit"),
        definition.get("reference_type"),
        definition.get("source"),
    )
    result["measurement_basis"] = definition.get("measurement_basis")
    result["coverage_status"] = definition.get("coverage_status", "complete")

    if life_stage.get("status") != TARGET_STATUS_RESOLVED:
        result["required_inputs"] = life_stage.get("required_inputs", ["age_or_age_months"])
        return result

    stage = life_stage["life_stage"]
    sex = profile.get("sex")
    record = _life_stage_record(definition, profile, stage, sex)

    if record is None:
        computed = _resolve_amdr_or_limit(definition, profile, stage, energy_target)
        if computed is None:
            result["status"] = TARGET_STATUS_UNRESOLVED_REGISTRY_ENTRY
            if definition.get("coverage_status") == "source_data_incomplete":
                result["warnings"].append("No source-backed value exists for this life stage.")
            return result
        result.update(computed)
    else:
        if record.get("status") in {"no_dri_established", "infant_feeding_guidance_required"}:
            result["status"] = record["status"]
            result["target_type"] = None
            return result
        value = record.get("value")
        if not isinstance(value, (int, float)):
            result["status"] = TARGET_STATUS_UNRESOLVED_REGISTRY_ENTRY
            return result
        result.update({
            "target_type": record.get("type") or definition.get("reference_type"),
            "baseline_value": float(value),
            "resolved_value": float(value),
            "status": TARGET_STATUS_RESOLVED,
            "override_chain": [_baseline_label(profile, stage)],
        })

    _attach_ul(result, definition, stage)
    _apply_compatibility(result, nutrient_key)
    _apply_overrides(result, nutrient_key, definition, profile, energy_target)
    _attach_risk_flags(result, nutrient_key, definition, profile)
    return result


def _base_result(key: str, name: str, unit: Optional[str], target_type: Optional[str], source: Any) -> Dict[str, Any]:
    return {
        "nutrient_key": key,
        "nutrient_name": name,
        "target_type": target_type,
        "baseline_value": None,
        "resolved_value": None,
        "resolved_unit": unit,
        "range_low": None,
        "range_high": None,
        "upper_limit": None,
        "upper_limit_scope": None,
        "status": TARGET_STATUS_MISSING_PROFILE_DATA,
        "override_chain": [],
        "risk_flags": [],
        "required_inputs": [],
        "warnings": [],
        "evidence_quality": "authoritative_dri",
        "source": copy.deepcopy(source),
        "accepted_input_keys": [],
        "measurement_basis_verified": True,
        "version": TARGET_ENGINE_VERSION,
    }


def _life_stage_record(definition: Dict[str, Any], profile: Dict[str, Any], stage: str, sex: Optional[str]) -> Optional[Dict[str, Any]]:
    if profile.get("pregnant") is True:
        by_stage = definition.get("pregnancy_by_life_stage")
        if isinstance(by_stage, list):
            row = _find_stage_row(by_stage, stage)
            if row:
                return row
        if isinstance(definition.get("pregnancy"), dict):
            return definition["pregnancy"]
    if profile.get("lactating") is True:
        by_stage = definition.get("lactation_by_life_stage")
        if isinstance(by_stage, list):
            row = _find_stage_row(by_stage, stage)
            if row:
                return row
        if isinstance(definition.get("lactation"), dict):
            return definition["lactation"]
    return _find_baseline(definition.get("baseline_values", []), stage, sex)


def _find_baseline(rows: Any, stage: str, sex: Optional[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(rows, list):
        return None
    exact, neutral = [], []
    for row in rows:
        if row.get("life_stage") != stage:
            continue
        row_sex = row.get("sex", "any")
        if sex is not None and row_sex == sex:
            exact.append(row)
        elif row_sex == "any":
            neutral.append(row)
    return exact[0] if exact else (neutral[0] if neutral else None)


def _find_stage_row(rows: Iterable[Dict[str, Any]], stage: str) -> Optional[Dict[str, Any]]:
    for row in rows:
        if row.get("life_stage") == stage:
            return row
    return None


def _resolve_amdr_or_limit(definition: Dict[str, Any], profile: Dict[str, Any], stage: str, energy_target: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    energy = energy_target.get("resolved_value")
    selected = None
    if profile.get("pregnant") is True and isinstance(definition.get("pregnancy_amdr"), dict):
        selected = definition["pregnancy_amdr"]
    elif profile.get("lactating") is True and isinstance(definition.get("lactation_amdr"), dict):
        selected = definition["lactation_amdr"]
    elif isinstance(definition.get("amdr_values"), list):
        selected = _find_stage_row(definition["amdr_values"], stage)

    if selected is not None:
        if not isinstance(energy, (int, float)):
            return {"status": TARGET_STATUS_MISSING_PROFILE_DATA, "required_inputs": ["resolved_energy_kcal"]}
        kcal_per_gram = definition.get("conversion", {}).get("kcal_per_gram")
        low_pct = selected.get("minimum_percent_energy")
        high_pct = selected.get("maximum_percent_energy")
        if not all(isinstance(v, (int, float)) for v in (kcal_per_gram, low_pct, high_pct)):
            return None
        return {
            "target_type": "AMDR",
            "range_low": round(float(energy) * float(low_pct) / 100 / float(kcal_per_gram), 2),
            "range_high": round(float(energy) * float(high_pct) / 100 / float(kcal_per_gram), 2),
            "status": TARGET_STATUS_RESOLVED_RANGE,
            "override_chain": [f"{stage}_amdr"],
        }

    baseline_limit = definition.get("baseline_limit")
    if isinstance(baseline_limit, dict):
        if isinstance(baseline_limit.get("value"), (int, float)):
            value = float(baseline_limit["value"])
            return {"target_type": "maximum", "baseline_value": value, "resolved_value": value, "status": TARGET_STATUS_RESOLVED, "override_chain": ["baseline_limit"]}
        pct = baseline_limit.get("maximum_percent_energy")
        kcal_per_gram = baseline_limit.get("conversion", {}).get("kcal_per_gram")
        if isinstance(pct, (int, float)) and isinstance(kcal_per_gram, (int, float)):
            if not isinstance(energy, (int, float)):
                return {"status": TARGET_STATUS_MISSING_PROFILE_DATA, "required_inputs": ["resolved_energy_kcal"]}
            value = round(float(energy) * float(pct) / 100 / float(kcal_per_gram), 2)
            return {"target_type": "maximum", "baseline_value": value, "resolved_value": value, "range_high": value, "status": TARGET_STATUS_RESOLVED, "override_chain": ["percent_energy_limit"]}

    standalone = definition.get("amdr")
    if isinstance(standalone, dict):
        if not isinstance(energy, (int, float)):
            return {"status": TARGET_STATUS_MISSING_PROFILE_DATA, "required_inputs": ["resolved_energy_kcal"]}
        low_pct = standalone.get("minimum_percent_energy")
        high_pct = standalone.get("maximum_percent_energy")
        kcal_per_gram = standalone.get("conversion", {}).get("kcal_per_gram")
        if not all(isinstance(v, (int, float)) for v in (low_pct, high_pct, kcal_per_gram)):
            return None
        return {
            "target_type": "AMDR",
            "range_low": round(float(energy) * float(low_pct) / 100 / float(kcal_per_gram), 2),
            "range_high": round(float(energy) * float(high_pct) / 100 / float(kcal_per_gram), 2),
            "status": TARGET_STATUS_RESOLVED_RANGE,
            "override_chain": ["amdr"],
        }
    return None


def _baseline_label(profile: Dict[str, Any], stage: str) -> str:
    if profile.get("pregnant") is True:
        return "pregnancy_life_stage"
    if profile.get("lactating") is True:
        return "lactation_life_stage"
    return f"{stage}_baseline"


def _attach_ul(result: Dict[str, Any], definition: Dict[str, Any], stage: str) -> None:
    rows = definition.get("ul_by_life_stage")
    if isinstance(rows, list):
        row = _find_stage_row(rows, stage)
        if row and isinstance(row.get("value"), (int, float)):
            result["upper_limit"] = float(row["value"])
            if isinstance(definition.get("ul"), dict):
                result["upper_limit_scope"] = definition["ul"].get("source_type")
            return
    generic = definition.get("ul")
    if not isinstance(generic, dict):
        return
    for key in ("adult_value", "adult_19_50_value", "adult_19_70_value", "adult_51_plus_value", "adult_71_plus_value"):
        if isinstance(generic.get(key), (int, float)):
            result["upper_limit"] = float(generic[key])
            result["upper_limit_scope"] = generic.get("source_type")
            return


def _apply_compatibility(result: Dict[str, Any], nutrient_key: str) -> None:
    compatibility = CANONICAL_KEY_COMPATIBILITY.get(nutrient_key)
    if not isinstance(compatibility, dict):
        return
    result["accepted_input_keys"] = list(compatibility.get("accepted_input_keys", []))
    required = bool(compatibility.get("conversion_required", False))
    result["measurement_basis_verified"] = not required
    if required:
        result["warnings"].append("Convert the nutrient amount to the registry measurement basis before showing a percentage.")
        if result["status"] in {TARGET_STATUS_RESOLVED, TARGET_STATUS_RESOLVED_RANGE}:
            result["comparison_status"] = TARGET_STATUS_MEASUREMENT_BASIS_UNVERIFIED


def _apply_overrides(result: Dict[str, Any], nutrient_key: str, definition: Dict[str, Any], profile: Dict[str, Any], energy_target: Dict[str, Any]) -> None:
    conditions = set(profile.get("chronic_conditions", []))
    is_ckd = bool(conditions & CKD_IDS) or profile.get("ckd_stage") not in (None, "none")
    dialysis = profile.get("dialysis_modality") in DIALYSIS_MODALITIES
    overrides = definition.get("clinical_overrides", {})

    if dialysis and isinstance(overrides.get("dialysis"), dict):
        _apply_override(result, "dialysis", overrides["dialysis"], profile, energy_target)
        return
    if is_ckd and isinstance(overrides.get("ckd"), dict):
        _apply_override(result, "ckd", overrides["ckd"], profile, energy_target)
        return
    if nutrient_key == "sodium_mg" and conditions & HYPERTENSION_IDS and isinstance(overrides.get("hypertension"), dict):
        _apply_override(result, "hypertension", overrides["hypertension"], profile, energy_target)
    if nutrient_key == "vitamin_c_mg" and profile.get("smoking_status") == "smoker" and isinstance(overrides.get("smoker"), dict):
        _apply_override(result, "smoker", overrides["smoker"], profile, energy_target)

    if nutrient_key == "protein_g" and not (is_ckd or dialysis or profile.get("pregnant") or profile.get("lactating")):
        override_id = None
        if profile.get("resistance_training") is True:
            override_id = "resistance_training"
        elif profile.get("goal") in {"fat_loss", "weight_loss"}:
            override_id = "fat_loss"
        elif profile.get("frailty") is True:
            override_id = "frailty"
        if override_id and isinstance(overrides.get(override_id), dict):
            _apply_override(result, override_id, overrides[override_id], profile, energy_target)

    if nutrient_key == "saturated_fat_g" and conditions & {"dyslipidemia", "high_cholesterol", "coronary_artery_disease"}:
        override = overrides.get("cardiometabolic_high_risk")
        if isinstance(override, dict):
            _apply_override(result, "cardiometabolic_high_risk", override, profile, energy_target)


def _apply_override(result: Dict[str, Any], override_id: str, override: Dict[str, Any], profile: Dict[str, Any], energy_target: Dict[str, Any]) -> None:
    kind = override.get("override_type")
    if kind == TARGET_STATUS_REQUIRES_CLINICAL_INPUT:
        result.update({
            "resolved_value": None,
            "range_low": None,
            "range_high": None,
            "status": TARGET_STATUS_REQUIRES_CLINICAL_INPUT,
            "required_inputs": list(override.get("required_inputs", [])),
        })
        result["override_chain"].append(override_id)
    elif kind == "numeric_range":
        low, high = override.get("target_low"), override.get("target_high")
        if isinstance(low, (int, float)) and isinstance(high, (int, float)):
            result.update({"resolved_value": None, "range_low": float(low), "range_high": float(high), "status": TARGET_STATUS_RESOLVED_RANGE, "target_type": override.get("target_type", "clinical_goal_range")})
            result["override_chain"].append(override_id)
    elif kind == "weight_based_range":
        weight = profile.get("weight_kg")
        low, high = override.get("range_low"), override.get("range_high")
        if not isinstance(weight, (int, float)):
            result["status"] = TARGET_STATUS_MISSING_PROFILE_DATA
            result["required_inputs"] = ["weight_kg"]
        elif isinstance(low, (int, float)) and isinstance(high, (int, float)):
            result.update({"resolved_value": None, "range_low": round(float(weight) * float(low), 2), "range_high": round(float(weight) * float(high), 2), "status": TARGET_STATUS_RESOLVED_RANGE, "target_type": "clinical_target_range"})
            result["override_chain"].append(override_id)
    elif kind == "additive":
        add = override.get("add_value")
        if isinstance(add, (int, float)) and isinstance(result.get("resolved_value"), (int, float)):
            result["resolved_value"] = round(float(result["resolved_value"]) + float(add), 2)
            result["override_chain"].append(override_id)
    elif kind == "maximum_percent_energy":
        pct = override.get("maximum_percent_energy")
        energy = energy_target.get("resolved_value")
        if isinstance(pct, (int, float)) and isinstance(energy, (int, float)):
            value = round(float(energy) * float(pct) / 100 / 9.0, 2)
            result.update({"resolved_value": value, "range_high": value, "target_type": "maximum", "status": TARGET_STATUS_RESOLVED})
            result["override_chain"].append(override_id)
    elif kind in {"risk_flag_only", "interaction_flag", "warning", "supplement_safety_flag", "measurement_warning", "diet_pattern_choice"}:
        result["risk_flags"].append({"id": override_id, "type": kind, "message": override.get("message")})


def _attach_risk_flags(result: Dict[str, Any], nutrient_key: str, definition: Dict[str, Any], profile: Dict[str, Any]) -> None:
    conditions = set(profile.get("chronic_conditions", []))
    diet = profile.get("diet_type")
    triggers = {
        "osteoporosis_or_osteopenia": {"osteoporosis", "osteopenia", "osteoporosis_or_osteopenia"},
        "iron_deficiency": {"iron_deficiency", "iron_deficiency_anemia", "anemia"},
        "ibs": {"ibs", "irritable_bowel_syndrome"},
        "ibd": {"ibd", "inflammatory_bowel_disease"},
    }
    overrides = definition.get("clinical_overrides", {})
    for override_id, aliases in triggers.items():
        if conditions & aliases and isinstance(overrides.get(override_id), dict):
            _apply_override(result, override_id, overrides[override_id], profile, {})
    if diet in {"vegetarian", "vegan"} and isinstance(overrides.get(diet), dict):
        _apply_override(result, diet, overrides[diet], profile, {})
    for medication in profile.get("medications", []):
        if isinstance(overrides.get(medication), dict):
            _apply_override(result, medication, overrides[medication], profile, {})


def build_global_risk_flags(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    flags: List[Dict[str, Any]] = []
    for key in (profile.get("diet_type"), profile.get("diet_pattern")):
        if isinstance(key, str) and key in DIET_PATTERN_RISK_FLAGS:
            flags.append(copy.deepcopy(DIET_PATTERN_RISK_FLAGS[key]))
    for medication in profile.get("medications", []):
        if medication in MEDICATION_RISK_FLAGS:
            flags.append(copy.deepcopy(MEDICATION_RISK_FLAGS[medication]))
    conditions = set(profile.get("chronic_conditions", []))
    policy_aliases = {
        "hypertension": HYPERTENSION_IDS,
        "chronic_kidney_disease": CKD_IDS,
        "osteoporosis": {"osteoporosis", "osteopenia", "osteoporosis_or_osteopenia"},
        "iron_deficiency": {"iron_deficiency", "iron_deficiency_anemia", "anemia"},
        "ibs": {"ibs", "irritable_bowel_syndrome"},
        "ibd": {"ibd", "inflammatory_bowel_disease"},
    }
    for policy_id, aliases in policy_aliases.items():
        if conditions & aliases and policy_id in CONDITION_TARGET_POLICY:
            flags.append({"id": f"{policy_id}_target_policy", "type": "condition_target_policy", "policy": copy.deepcopy(CONDITION_TARGET_POLICY[policy_id])})
    return flags


def build_engine_warnings(profile: Dict[str, Any], life_stage: Dict[str, Any], targets: Dict[str, Dict[str, Any]]) -> List[str]:
    warnings: List[str] = []
    if not profile:
        warnings.append("No profile was supplied; targets remain unresolved instead of using a generic adult profile.")
    if life_stage.get("status") != TARGET_STATUS_RESOLVED:
        warnings.append("Age or age in months is required for life-stage resolution.")
    unresolved = sorted(key for key, target in targets.items() if target.get("status") in {TARGET_STATUS_UNRESOLVED_REGISTRY_ENTRY, TARGET_STATUS_MISSING_PROFILE_DATA})
    clinical = sorted(key for key, target in targets.items() if target.get("status") == TARGET_STATUS_REQUIRES_CLINICAL_INPUT)
    if unresolved:
        warnings.append("Some targets are unresolved: " + ", ".join(unresolved) + ".")
    if clinical:
        warnings.append("Clinical input is required for: " + ", ".join(clinical) + ".")
    return warnings
