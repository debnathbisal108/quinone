from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from nutrient_target_data import (
    ADULT_BASELINES,
    ADULT_PA_COEFFICIENTS,
    EVIDENCE_AUTHORITATIVE_DRI,
    EVIDENCE_CONDITIONAL_GUIDELINE,
    EVIDENCE_STRONG_GUIDELINE,
    MEASUREMENT_COMPATIBILITY,
    NASEM_ENERGY_SOURCE,
    RISK_FLAGS,
    TARGET_ENGINE_VERSION,
)

SUPPORTED_SEXES = {"male", "female"}
SUPPORTED_ACTIVITY_LEVELS = {"sedentary", "low_active", "active", "very_active"}
CKD_CONDITIONS = {"ckd", "chronic_kidney_disease", "kidney_disease"}


def normalize_target_profile(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(profile, dict):
        return {}
    result: Dict[str, Any] = {}

    def clean(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
        return normalized or None

    age = profile.get("age")
    if isinstance(age, (int, float)) and not isinstance(age, bool) and 0 < float(age) < 130:
        result["age"] = float(age)

    for key in ("height_cm", "weight_kg"):
        value = profile.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) > 0:
            result[key] = float(value)

    sex = clean(profile.get("sex") or profile.get("gender"))
    if sex in SUPPORTED_SEXES:
        result["sex"] = sex

    activity = clean(profile.get("activity_level"))
    aliases = {"inactive": "sedentary", "lightly_active": "low_active", "moderately_active": "active", "highly_active": "very_active"}
    if activity:
        activity = aliases.get(activity, activity)
    if activity in SUPPORTED_ACTIVITY_LEVELS:
        result["activity_level"] = activity

    for key in ("goal", "diet_type", "smoking_status", "ckd_stage", "dialysis_modality", "blood_pressure_status"):
        value = clean(profile.get(key))
        if value:
            result[key] = value

    for key in ("pregnant", "lactating", "frailty", "low_appetite", "resistance_training", "endurance_training"):
        if isinstance(profile.get(key), bool):
            result[key] = profile[key]

    trimester = profile.get("trimester")
    if isinstance(trimester, int) and trimester in (1, 2, 3):
        result["trimester"] = trimester

    months = profile.get("lactation_stage_months")
    if isinstance(months, (int, float)) and float(months) >= 0:
        result["lactation_stage_months"] = float(months)

    raw_conditions = profile.get("conditions", profile.get("chronic_conditions", []))
    conditions: List[str] = []
    if isinstance(raw_conditions, dict):
        conditions = [clean(key) for key, enabled in raw_conditions.items() if enabled and clean(key)]
    elif isinstance(raw_conditions, (list, tuple, set)):
        conditions = [value for item in raw_conditions if (value := clean(item))]
    result["conditions"] = list(dict.fromkeys(conditions))

    raw_medications = profile.get("medications", [])
    medications: List[str] = []
    if isinstance(raw_medications, (list, tuple, set)):
        medications = [value for item in raw_medications if (value := clean(item))]
    result["medications"] = list(dict.fromkeys(medications))
    return result


def _base_target(nutrient_key: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    record = ADULT_BASELINES[nutrient_key]
    age = profile.get("age")
    sex = profile.get("sex")
    pregnant = profile.get("pregnant") is True
    lactating = profile.get("lactating") is True

    output = {
        "nutrient_key": nutrient_key,
        "nutrient_name": record["name"],
        "reference_type": record["reference_type"],
        "baseline_value": None,
        "resolved_value": None,
        "resolved_unit": record["unit"],
        "range_low": None,
        "range_high": None,
        "ul": record.get("ul"),
        "cdrr": record.get("cdrr"),
        "status": "missing_profile_data",
        "evidence_quality": EVIDENCE_AUTHORITATIVE_DRI,
        "override_chain": [],
        "required_inputs": [],
        "warnings": [],
        "measurement_basis": record.get("measurement_basis"),
        "source": copy.deepcopy(record["source"]),
    }

    if not isinstance(age, (int, float)) or age < 19:
        output["status"] = "unsupported_profile"
        output["required_inputs"] = ["adult_age_19_plus"]
        return output
    if sex not in SUPPORTED_SEXES:
        output["required_inputs"] = ["sex"]
        return output

    if pregnant and sex != "female":
        output["status"] = "invalid_profile"
        output["warnings"].append("Pregnancy requires sex=female for DRI resolution.")
        return output
    if lactating and sex != "female":
        output["status"] = "invalid_profile"
        output["warnings"].append("Lactation requires sex=female for DRI resolution.")
        return output

    if pregnant:
        selector = "pregnancy"
        output["override_chain"].append("pregnancy_life_stage")
    elif lactating:
        selector = "lactation"
        output["override_chain"].append("lactation_life_stage")
    elif nutrient_key == "fiber_g":
        selector = f"{sex}_{'19_50' if age <= 50 else '51_plus'}"
    elif nutrient_key == "vitamin_d_ug":
        selector = "adult_19_70" if age <= 70 else "adult_71_plus"
    elif nutrient_key == "vitamin_b6_mg":
        selector = "adult_19_50" if age <= 50 else f"{sex}_51_plus"
    elif nutrient_key == "calcium_mg":
        selector = "adult_19_50" if age <= 50 else (f"{sex}_51_70" if age <= 70 else "adult_71_plus")
    elif nutrient_key == "iron_mg":
        selector = "male_19_plus" if sex == "male" else ("female_19_50" if age <= 50 else "female_51_plus")
    elif nutrient_key == "magnesium_mg":
        selector = ("pregnancy_19_30" if age <= 30 else "pregnancy_31_plus") if pregnant else (f"{sex}_19_30" if age <= 30 else f"{sex}_31_plus")
    else:
        selector = sex

    value = record.get(selector)
    if value is None and selector in {"pregnancy", "lactation"}:
        value = record.get(sex)
    if not isinstance(value, (int, float)):
        output["status"] = "unresolved_registry_entry"
        output["required_inputs"] = [f"registry_value:{selector}"]
        return output

    output["baseline_value"] = float(value)
    output["resolved_value"] = float(value)
    output["status"] = "resolved"
    output["override_chain"].insert(0, f"adult_{sex}_{record['reference_type'].lower()}")
    return output


def _resolve_energy(profile: Dict[str, Any]) -> Dict[str, Any]:
    output = {
        "nutrient_key": "energy_kcal",
        "nutrient_name": "Energy",
        "reference_type": "EER",
        "baseline_value": None,
        "resolved_value": None,
        "resolved_unit": "kcal/day",
        "range_low": None,
        "range_high": None,
        "status": "missing_profile_data",
        "evidence_quality": EVIDENCE_AUTHORITATIVE_DRI,
        "override_chain": [],
        "required_inputs": [],
        "warnings": [],
        "source": copy.deepcopy(NASEM_ENERGY_SOURCE),
    }
    required = ["age", "sex", "height_cm", "weight_kg", "activity_level"]
    missing = [key for key in required if profile.get(key) is None]
    if missing:
        output["required_inputs"] = missing
        return output

    age = float(profile["age"])
    if age < 19:
        output["status"] = "unsupported_profile"
        output["required_inputs"] = ["adult_age_19_plus"]
        return output

    sex = profile["sex"]
    height_m = float(profile["height_cm"]) / 100.0
    weight_kg = float(profile["weight_kg"])
    pa = ADULT_PA_COEFFICIENTS[sex][profile["activity_level"]]
    if sex == "male":
        eer = 662.0 - (9.53 * age) + pa * ((15.91 * weight_kg) + (539.6 * height_m))
    else:
        eer = 354.0 - (6.91 * age) + pa * ((9.36 * weight_kg) + (726.0 * height_m))

    output["baseline_value"] = round(eer, 2)
    output["resolved_value"] = round(eer, 2)
    output["status"] = "resolved"
    output["override_chain"] = [f"adult_{sex}_eer_2023"]

    if profile.get("pregnant") is True:
        trimester = profile.get("trimester")
        if trimester not in (1, 2, 3):
            output["status"] = "missing_profile_data"
            output["resolved_value"] = None
            output["required_inputs"] = ["trimester"]
            return output
        increment = {1: 0.0, 2: 340.0, 3: 452.0}[trimester]
        output["resolved_value"] = round(eer + increment, 2)
        output["override_chain"].append(f"pregnancy_trimester_{trimester}")
    elif profile.get("lactating") is True:
        months = profile.get("lactation_stage_months")
        if not isinstance(months, (int, float)):
            output["status"] = "missing_profile_data"
            output["resolved_value"] = None
            output["required_inputs"] = ["lactation_stage_months"]
            return output
        increment = 330.0 if float(months) <= 6 else 400.0
        output["resolved_value"] = round(eer + increment, 2)
        output["override_chain"].append("lactation_0_6_months" if float(months) <= 6 else "lactation_7_12_months")
    return output


def _apply_supported_overrides(targets: Dict[str, Dict[str, Any]], profile: Dict[str, Any]) -> None:
    conditions = set(profile.get("conditions", []))
    medications = set(profile.get("medications", []))

    if profile.get("smoking_status") == "smoker":
        target = targets.get("vitamin_c_mg")
        if target and target["status"] == "resolved":
            target["resolved_value"] = round(float(target["resolved_value"]) + 35.0, 2)
            target["reference_type"] = "RDA_plus_smoking_adjustment"
            target["override_chain"].append("smoker_plus_35_mg_vitamin_c")
            target["evidence_quality"] = EVIDENCE_STRONG_GUIDELINE

    if "hypertension" in conditions or "high_blood_pressure" in conditions:
        target = targets.get("sodium_mg")
        if target:
            target["range_low"] = 1500.0
            target["range_high"] = 2300.0
            target["resolved_value"] = None
            target["reference_type"] = "clinical_goal_range"
            target["status"] = "resolved_range"
            target["override_chain"].append("hypertension_sodium_goal_range")
            target["evidence_quality"] = EVIDENCE_STRONG_GUIDELINE

    ckd = bool(CKD_CONDITIONS & conditions) or profile.get("ckd_stage") not in (None, "none")
    if ckd:
        clinical_map = {
            "protein_g": ["ckd_stage", "clinician_protein_target"],
            "sodium_mg": ["ckd_stage", "edema_status", "blood_pressure", "medications"],
            "potassium_mg": ["ckd_stage", "serum_potassium", "medications"],
            "phosphorus_mg": ["ckd_stage", "serum_phosphorus"],
            "calcium_mg": ["ckd_stage", "serum_calcium", "pth"],
            "magnesium_mg": ["ckd_stage", "serum_magnesium", "medications"],
        }
        for key, required in clinical_map.items():
            target = targets.get(key)
            if not target:
                continue
            target["resolved_value"] = None
            target["range_low"] = None
            target["range_high"] = None
            target["status"] = "requires_clinical_input"
            target["required_inputs"] = required
            target["override_chain"].append("ckd_safety_override")
            target["evidence_quality"] = EVIDENCE_CONDITIONAL_GUIDELINE

    target = targets.get("protein_g")
    if target and target["status"] == "resolved" and not ckd and profile.get("pregnant") is not True and profile.get("lactating") is not True:
        weight = profile.get("weight_kg")
        if isinstance(weight, (int, float)):
            if profile.get("resistance_training") is True or profile.get("goal") == "fat_loss":
                target["range_low"] = round(1.2 * float(weight), 2)
                target["range_high"] = round(1.6 * float(weight), 2)
                target["resolved_value"] = None
                target["reference_type"] = "clinical_target_range"
                target["status"] = "resolved_range"
                target["override_chain"].append("training_or_fat_loss_protein_range")
                target["evidence_quality"] = EVIDENCE_STRONG_GUIDELINE
            elif profile.get("frailty") is True:
                target["resolved_value"] = round(max(float(target["baseline_value"]), float(weight)), 2)
                target["reference_type"] = "clinical_target"
                target["override_chain"].append("frailty_minimum_1_0_g_per_kg")
                target["evidence_quality"] = EVIDENCE_STRONG_GUIDELINE

    for key, compatibility in MEASUREMENT_COMPATIBILITY.items():
        target = targets.get(key)
        if not target:
            continue
        target["accepted_input_keys"] = compatibility["accepted_input_keys"]
        target["legacy_input_keys"] = compatibility["legacy_keys"]
        target["measurement_basis_verified"] = False
        target["warnings"].append(f"Percentages require nutrient input measured as {compatibility['required_basis']}.")

    if "warfarin" in medications:
        target = targets.get("vitamin_k_ug")
        if target:
            target["warnings"].append("Warfarin interaction: keep vitamin K intake consistent; do not automatically lower the target.")


def _build_risk_flags(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    flags: List[Dict[str, Any]] = []
    diet_type = profile.get("diet_type")
    medications = set(profile.get("medications", []))

    if diet_type in ("vegetarian", "vegan"):
        definition = RISK_FLAGS[diet_type]
        flags.append({"id": f"{diet_type}_nutrient_risk", "type": "risk_flag_only", "nutrients": definition["nutrients"], "message": definition["message"]})

    if profile.get("smoking_status") == "smoker":
        definition = RISK_FLAGS["smoker"]
        flags.append({"id": "smoking_vitamin_c_requirement", "type": "target_adjustment", "nutrients": definition["nutrients"], "message": definition["message"]})

    medication_aliases = {"metformin": "metformin", "ppi": "ppi", "proton_pump_inhibitor": "ppi", "warfarin": "warfarin"}
    for medication in medications:
        key = medication_aliases.get(medication)
        if key and key in RISK_FLAGS:
            definition = RISK_FLAGS[key]
            flags.append({"id": f"{key}_nutrient_risk", "type": "risk_flag_only", "nutrients": definition["nutrients"], "message": definition["message"]})
    return flags


def calculate_nutrient_targets(user_profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    profile = normalize_target_profile(user_profile)
    targets = {key: _base_target(key, profile) for key in ADULT_BASELINES}
    targets["energy_kcal"] = _resolve_energy(profile)
    _apply_supported_overrides(targets, profile)
    return {
        "engine_version": TARGET_ENGINE_VERSION,
        "profile_applied": bool(profile),
        "profile": profile,
        "targets": targets,
        "risk_flags": _build_risk_flags(profile),
        "warnings": [
            "This engine resolves adult targets only in version 1.0.0.",
            "Targets marked requires_clinical_input must not be displayed as personalized percentages.",
        ],
    }


def attach_nutrient_targets(meal_json: Dict[str, Any], user_profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(meal_json, dict):
        raise ValueError("Meal JSON must be a dictionary.")
    result = copy.deepcopy(meal_json)
    meal = result.get("meal")
    if not isinstance(meal, dict):
        raise ValueError("Meal JSON must contain a top-level meal object.")
    personalization = meal.get("personalization")
    if not isinstance(personalization, dict):
        personalization = {}
        meal["personalization"] = personalization
    target_result = calculate_nutrient_targets(user_profile)
    personalization["nutrient_targets"] = target_result["targets"]
    personalization["nutrient_risk_flags"] = target_result["risk_flags"]
    personalization["nutrient_target_warnings"] = target_result["warnings"]
    personalization["nutrient_target_engine_version"] = target_result["engine_version"]
    personalization["profile_applied"] = target_result["profile_applied"]
    return result
