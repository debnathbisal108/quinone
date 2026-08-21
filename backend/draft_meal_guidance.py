from __future__ import annotations

from typing import Any, Dict, Final


# =========================================================================
# VERSIONING
# =========================================================================

NUTRIENT_SCHEMA_VERSION: Final[str] = "1.0.0"
BASELINE_GUIDELINE_VERSION: Final[str] = "NASEM-DRI-2023"
TARGET_DATA_VERSION: Final[str] = "1.0.0"


# =========================================================================
# EVIDENCE QUALITY
# =========================================================================

EVIDENCE_AUTHORITATIVE_DRI: Final[str] = (
    "authoritative_dri"
)

EVIDENCE_STRONG_GUIDELINE: Final[str] = (
    "strong_guideline"
)

EVIDENCE_CONDITIONAL_GUIDELINE: Final[str] = (
    "conditional_guideline"
)

EVIDENCE_INSUFFICIENT: Final[str] = (
    "insufficient_evidence"
)


# =========================================================================
# TARGET STATUSES
# =========================================================================

TARGET_STATUS_RESOLVED: Final[str] = "resolved"

TARGET_STATUS_RESOLVED_RANGE: Final[str] = (
    "resolved_range"
)

TARGET_STATUS_MISSING_PROFILE_DATA: Final[str] = (
    "missing_profile_data"
)

TARGET_STATUS_REQUIRES_CLINICAL_INPUT: Final[str] = (
    "requires_clinical_input"
)

TARGET_STATUS_MEASUREMENT_BASIS_UNVERIFIED: Final[str] = (
    "measurement_basis_unverified"
)

TARGET_STATUS_UNRESOLVED_REGISTRY_ENTRY: Final[str] = (
    "unresolved_registry_entry"
)


# =========================================================================
# SOURCE REGISTRY
# =========================================================================

SOURCE_NASEM_ENERGY_2023: Final[
    Dict[str, Any]
] = {
    "organization": (
        "National Academies of Sciences, "
        "Engineering, and Medicine"
    ),
    "document_title": (
        "Dietary Reference Intakes for Energy"
    ),
    "publication_year": 2023,
    "recommendation_or_table": (
        "Table S-1 and chapter equations"
    ),
    "source_url": (
        "https://nap.nationalacademies.org/"
        "read/26859/chapter/11"
    ),
    "doi": None,
    "accessed_date": "2026-07-18",
}


SOURCE_NASEM_SODIUM_POTASSIUM_2019: Final[
    Dict[str, Any]
] = {
    "organization": (
        "National Academies of Sciences, "
        "Engineering, and Medicine"
    ),
    "document_title": (
        "Dietary Reference Intakes for "
        "Sodium and Potassium"
    ),
    "publication_year": 2019,
    "recommendation_or_table": (
        "Appendix J summary tables; "
        "sodium AI/CDRR and potassium AI"
    ),
    "source_url": (
        "https://nap.nationalacademies.org/"
        "read/25353/chapter/18"
    ),
    "doi": "10.17226/25353",
    "accessed_date": "2026-07-18",
}


SOURCE_NASEM_GENERAL_DRI: Final[
    Dict[str, Any]
] = {
    "organization": (
        "National Academies / "
        "NIH Office of Dietary Supplements"
    ),
    "document_title": (
        "Dietary Reference Intakes "
        "Summary Tables"
    ),
    "publication_year": 2005,
    "recommendation_or_table": (
        "Age, sex, pregnancy, lactation, "
        "RDA, AI and UL tables"
    ),
    "source_url": (
        "https://nap.nationalacademies.org/"
        "read/10490/chapter/17"
    ),
    "doi": None,
    "accessed_date": "2026-07-18",
}


# =========================================================================
# LIFE-STAGE DEFINITIONS
# =========================================================================

LIFE_STAGE_BANDS: Final[
    Dict[str, Dict[str, int | None]]
] = {
    "0_6_months": {
        "min_age_months": 0,
        "max_age_months": 6,
    },
    "7_12_months": {
        "min_age_months": 7,
        "max_age_months": 12,
    },
    "1_3_years": {
        "min_age_months": 13,
        "max_age_months": 47,
    },
    "4_8_years": {
        "min_age_months": 48,
        "max_age_months": 107,
    },
    "9_13_years": {
        "min_age_months": 108,
        "max_age_months": 167,
    },
    "14_18_years": {
        "min_age_months": 168,
        "max_age_months": 227,
    },
    "19_30_years": {
        "min_age_months": 228,
        "max_age_months": 371,
    },
    "31_50_years": {
        "min_age_months": 372,
        "max_age_months": 611,
    },
    "51_70_years": {
        "min_age_months": 612,
        "max_age_months": 851,
    },
    "71_plus_years": {
        "min_age_months": 852,
        "max_age_months": None,
    },
}


# =========================================================================
# EER EQUATION REGISTRY
# =========================================================================

EER_EQUATIONS: Final[
    Dict[str, Dict[str, Any]]
] = {
    "infants_0_2_99_months_male": {
        "min_age_months": 0,
        "max_age_months": 2,
        "sex": "male",
        "required_inputs": (
            "age_months",
            "height_cm",
            "weight_kg",
        ),
        "height_unit": "cm",
        "activity_coefficients": None,
        "equation": {
            "constant": -716.45,
            "age_years_coefficient": -1.00,
            "height_cm_coefficient": 17.82,
            "weight_kg_coefficient": 15.06,
            "growth_allowance": 200.0,
        },
        "formula_text": (
            "EER = -716.45 "
            "- (1.00 × age_years) "
            "+ (17.82 × height_cm) "
            "+ (15.06 × weight_kg) "
            "+ 200"
        ),
        "source": SOURCE_NASEM_ENERGY_2023,
    },

    "infants_0_2_99_months_female": {
        "min_age_months": 0,
        "max_age_months": 2,
        "sex": "female",
        "required_inputs": (
            "age_months",
            "height_cm",
            "weight_kg",
        ),
        "height_unit": "cm",
        "activity_coefficients": None,
        "equation": {
            "constant": -69.15,
            "age_years_coefficient": 80.0,
            "height_cm_coefficient": 2.65,
            "weight_kg_coefficient": 54.15,
            "growth_allowance": 180.0,
        },
        "formula_text": (
            "EER = -69.15 "
            "+ (80.0 × age_years) "
            "+ (2.65 × height_cm) "
            "+ (54.15 × weight_kg) "
            "+ 180"
        ),
        "source": SOURCE_NASEM_ENERGY_2023,
    },

    "infants_6_months_to_2_99_years_male": {
        "min_age_months": 6,
        "max_age_months": 35,
        "sex": "male",
        "required_inputs": (
            "age_months",
            "height_cm",
            "weight_kg",
        ),
        "height_unit": "cm",
        "activity_coefficients": None,
        "equation": {
            "constant": -716.45,
            "age_years_coefficient": -1.00,
            "height_cm_coefficient": 17.82,
            "weight_kg_coefficient": 15.06,
            "growth_allowance": 20.0,
        },
        "formula_text": (
            "EER = -716.45 "
            "- (1.00 × age_years) "
            "+ (17.82 × height_cm) "
            "+ (15.06 × weight_kg) "
            "+ 20"
        ),
        "source": SOURCE_NASEM_ENERGY_2023,
    },

    "infants_6_months_to_2_99_years_female": {
        "min_age_months": 6,
        "max_age_months": 35,
        "sex": "female",
        "required_inputs": (
            "age_months",
            "height_cm",
            "weight_kg",
        ),
        "height_unit": "cm",
        "activity_coefficients": None,
        "equation": {
            "constant": -69.15,
            "age_years_coefficient": 80.0,
            "height_cm_coefficient": 2.65,
            "weight_kg_coefficient": 54.15,
            "growth_allowance": 20.0,
        },
        "formula_text": (
            "EER = -69.15 "
            "+ (80.0 × age_years) "
            "+ (2.65 × height_cm) "
            "+ (54.15 × weight_kg) "
            "+ 20"
        ),
        "source": SOURCE_NASEM_ENERGY_2023,
    },

    "children_3_8_years_male": {
        "min_age_months": 36,
        "max_age_months": 107,
        "sex": "male",
        "required_inputs": (
            "age_months",
            "height_cm",
            "weight_kg",
            "activity_level",
        ),
        "height_unit": "m",
        "activity_coefficients": {
            "sedentary": 1.00,
            "low_active": 1.13,
            "active": 1.26,
            "very_active": 1.42,
        },
        "equation": {
            "constant": 88.5,
            "age_years_coefficient": -61.9,
            "weight_kg_coefficient": 26.7,
            "height_m_coefficient": 903.0,
            "growth_allowance": 20.0,
        },
        "formula_text": (
            "EER = 88.5 "
            "- (61.9 × age_years) "
            "+ PA × "
            "((26.7 × weight_kg) "
            "+ (903 × height_m)) "
            "+ 20"
        ),
        "source": SOURCE_NASEM_ENERGY_2023,
    },

    "children_3_8_years_female": {
        "min_age_months": 36,
        "max_age_months": 107,
        "sex": "female",
        "required_inputs": (
            "age_months",
            "height_cm",
            "weight_kg",
            "activity_level",
        ),
        "height_unit": "m",
        "activity_coefficients": {
            "sedentary": 1.00,
            "low_active": 1.16,
            "active": 1.31,
            "very_active": 1.56,
        },
        "equation": {
            "constant": 135.3,
            "age_years_coefficient": -30.8,
            "weight_kg_coefficient": 10.0,
            "height_m_coefficient": 934.0,
            "growth_allowance": 20.0,
        },
        "formula_text": (
            "EER = 135.3 "
            "- (30.8 × age_years) "
            "+ PA × "
            "((10.0 × weight_kg) "
            "+ (934 × height_m)) "
            "+ 20"
        ),
        "source": SOURCE_NASEM_ENERGY_2023,
    },

    "males_9_18_years": {
        "min_age_months": 108,
        "max_age_months": 227,
        "sex": "male",
        "required_inputs": (
            "age_months",
            "height_cm",
            "weight_kg",
            "activity_level",
        ),
        "height_unit": "m",
        "activity_coefficients": {
            "sedentary": 1.00,
            "low_active": 1.13,
            "active": 1.26,
            "very_active": 1.42,
        },
        "equation": {
            "constant": 88.5,
            "age_years_coefficient": -61.9,
            "weight_kg_coefficient": 26.7,
            "height_m_coefficient": 903.0,
            "growth_allowance": 25.0,
        },
        "formula_text": (
            "EER = 88.5 "
            "- (61.9 × age_years) "
            "+ PA × "
            "((26.7 × weight_kg) "
            "+ (903 × height_m)) "
            "+ 25"
        ),
        "source": SOURCE_NASEM_ENERGY_2023,
    },

    "females_9_18_years": {
        "min_age_months": 108,
        "max_age_months": 227,
        "sex": "female",
        "required_inputs": (
            "age_months",
            "height_cm",
            "weight_kg",
            "activity_level",
        ),
        "height_unit": "m",
        "activity_coefficients": {
            "sedentary": 1.00,
            "low_active": 1.16,
            "active": 1.31,
            "very_active": 1.56,
        },
        "equation": {
            "constant": 135.3,
            "age_years_coefficient": -30.8,
            "weight_kg_coefficient": 10.0,
            "height_m_coefficient": 934.0,
            "growth_allowance": 25.0,
        },
        "formula_text": (
            "EER = 135.3 "
            "- (30.8 × age_years) "
            "+ PA × "
            "((10.0 × weight_kg) "
            "+ (934 × height_m)) "
            "+ 25"
        ),
        "source": SOURCE_NASEM_ENERGY_2023,
    },

    "adult_males_19_plus": {
        "min_age_months": 228,
        "max_age_months": None,
        "sex": "male",
        "required_inputs": (
            "age_months",
            "height_cm",
            "weight_kg",
            "activity_level",
        ),
        "height_unit": "m",
        "activity_coefficients": {
            "sedentary": 1.00,
            "low_active": 1.11,
            "active": 1.25,
            "very_active": 1.48,
        },
        "equation": {
            "constant": 662.0,
            "age_years_coefficient": -9.53,
            "weight_kg_coefficient": 15.91,
            "height_m_coefficient": 539.6,
            "growth_allowance": 0.0,
        },
        "formula_text": (
            "EER = 662 "
            "- (9.53 × age_years) "
            "+ PA × "
            "((15.91 × weight_kg) "
            "+ (539.6 × height_m))"
        ),
        "source": SOURCE_NASEM_ENERGY_2023,
    },

    "adult_females_19_plus": {
        "min_age_months": 228,
        "max_age_months": None,
        "sex": "female",
        "required_inputs": (
            "age_months",
            "height_cm",
            "weight_kg",
            "activity_level",
        ),
        "height_unit": "m",
        "activity_coefficients": {
            "sedentary": 1.00,
            "low_active": 1.12,
            "active": 1.27,
            "very_active": 1.45,
        },
        "equation": {
            "constant": 354.0,
            "age_years_coefficient": -6.91,
            "weight_kg_coefficient": 9.36,
            "height_m_coefficient": 726.0,
            "growth_allowance": 0.0,
        },
        "formula_text": (
            "EER = 354 "
            "- (6.91 × age_years) "
            "+ PA × "
            "((9.36 × weight_kg) "
            "+ (726 × height_m))"
        ),
        "source": SOURCE_NASEM_ENERGY_2023,
    },
}


PREGNANCY_ENERGY_ADJUSTMENTS: Final[
    Dict[int, float]
] = {
    1: 0.0,
    2: 340.0,
    3: 452.0,
}


LACTATION_ENERGY_ADJUSTMENTS: Final[
    Dict[str, Dict[str, float]]
] = {
    "0_6_months": {
        "min_months_postpartum": 0.0,
        "max_months_postpartum": 6.0,
        "addition_kcal": 330.0,
    },
    "7_12_months": {
        "min_months_postpartum": 6.01,
        "max_months_postpartum": 12.0,
        "addition_kcal": 400.0,
    },
}


# =========================================================================
# SODIUM
# =========================================================================

SODIUM_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "sodium_mg",
    "official_name": "Sodium",
    "canonical_unit": "mg/day",
    "measurement_basis": "sodium",
    "reference_type": "AI",
    "source": SOURCE_NASEM_SODIUM_POTASSIUM_2019,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 110.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 370.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "AI",
            "value": 800.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "AI",
            "value": 1000.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "AI",
            "value": 1200.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "AI",
            "value": 1500.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "AI",
            "value": 1500.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "AI",
            "value": 1500.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "AI",
            "value": 1500.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "AI",
            "value": 1500.0,
        },
    ],

    "pregnancy": {
        "type": "AI",
        "value": 1500.0,
    },

    "lactation": {
        "type": "AI",
        "value": 1500.0,
    },

    "cdrr_values": [
        {
            "life_stage": "1_3_years",
            "value": 1200.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 1500.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 1800.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 2300.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 2300.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 2300.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 2300.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 2300.0,
        },
    ],

    "clinical_overrides": {
        "hypertension": {
            "override_type": "numeric_range",
            "target_low": 1500.0,
            "target_high": 2300.0,
            "unit": "mg/day",
            "target_type": "clinical_goal",
            "evidence_quality": (
                EVIDENCE_STRONG_GUIDELINE
            ),
        },

        "ckd": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "ckd_stage",
                "edema_status",
                "dialysis_modality",
                "serum_sodium",
                "blood_pressure",
                "medications",
            ],
            "evidence_quality": (
                EVIDENCE_CONDITIONAL_GUIDELINE
            ),
        },
    },

    "ul": None,
    "ul_source_type": None,
    "notes": (
        "No formal sodium UL is stored. "
        "CDRR remains separate from AI."
    ),
}


# =========================================================================
# POTASSIUM
# =========================================================================

POTASSIUM_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "potassium_mg",
    "official_name": "Potassium",
    "canonical_unit": "mg/day",
    "measurement_basis": "potassium",
    "reference_type": "AI",
    "source": SOURCE_NASEM_SODIUM_POTASSIUM_2019,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 400.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 860.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "AI",
            "value": 2000.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "AI",
            "value": 2300.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "male",
            "type": "AI",
            "value": 2500.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "female",
            "type": "AI",
            "value": 2300.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "AI",
            "value": 3000.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "AI",
            "value": 2300.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "AI",
            "value": 3400.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "AI",
            "value": 2600.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "AI",
            "value": 3400.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "AI",
            "value": 2600.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "AI",
            "value": 3400.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "AI",
            "value": 2600.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "AI",
            "value": 3400.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "AI",
            "value": 2600.0,
        },
    ],

    "pregnancy": {
        "type": "AI",
        "value": 2900.0,
    },

    "lactation": {
        "type": "AI",
        "value": 2800.0,
    },

    "clinical_overrides": {
        "hypertension": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "A higher-potassium dietary pattern "
                "may support blood-pressure management, "
                "but no separate automatic hypertension "
                "target is assigned."
            ),
        },

        "ckd": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "ckd_stage",
                "serum_potassium",
                "dialysis_modality",
                "medications",
            ],
            "evidence_quality": (
                EVIDENCE_CONDITIONAL_GUIDELINE
            ),
        },
    },

    "cdrr": None,
    "ul": None,
    "ul_source_type": None,
}

# =========================================================================
# PROTEIN
# =========================================================================

PROTEIN_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "protein_g",
    "official_name": "Protein",
    "canonical_unit": "g/day",
    "measurement_basis": "good_quality_protein",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 9.1,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "RDA",
            "value": 11.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 13.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 19.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "male",
            "type": "RDA",
            "value": 34.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "female",
            "type": "RDA",
            "value": 34.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "RDA",
            "value": 52.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "RDA",
            "value": 46.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "RDA",
            "value": 56.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "RDA",
            "value": 46.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "RDA",
            "value": 56.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "RDA",
            "value": 46.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "RDA",
            "value": 56.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "RDA",
            "value": 46.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "RDA",
            "value": 56.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "RDA",
            "value": 46.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 71.0,
    },

    "lactation": {
        "type": "RDA",
        "value": 71.0,
    },

    "secondary_reference": {
        "type": "weight_based_rda",
        "value": 0.8,
        "unit": "g/kg/day",
        "applicability": "adults",
        "implementation_policy": (
            "Retain the fixed age-sex DRI as the baseline target. "
            "The weight-based value is stored as a secondary reference "
            "and must not silently replace the fixed target."
        ),
    },

    "clinical_overrides": {
        "resistance_training": {
            "override_type": "weight_based_range",
            "range_low": 1.2,
            "range_high": 1.6,
            "unit": "g/kg/day",
            "required_inputs": [
                "weight_kg",
            ],
            "contraindications": [
                "pregnancy",
                "lactation",
                "ckd",
                "dialysis",
            ],
            "evidence_quality": (
                EVIDENCE_STRONG_GUIDELINE
            ),
        },

        "fat_loss": {
            "override_type": "weight_based_range",
            "range_low": 1.2,
            "range_high": 1.6,
            "unit": "g/kg/day",
            "required_inputs": [
                "weight_kg",
            ],
            "contraindications": [
                "pregnancy",
                "lactation",
                "ckd",
                "dialysis",
            ],
            "evidence_quality": (
                EVIDENCE_STRONG_GUIDELINE
            ),
        },

        "frailty": {
            "override_type": "weight_based_range",
            "range_low": 1.0,
            "range_high": 1.2,
            "unit": "g/kg/day",
            "required_inputs": [
                "weight_kg",
            ],
            "contraindications": [
                "ckd",
                "dialysis",
            ],
            "evidence_quality": (
                EVIDENCE_STRONG_GUIDELINE
            ),
        },

        "ckd": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "ckd_stage",
                "dialysis_modality",
                "weight_basis",
                "clinician_protein_target",
            ],
            "evidence_quality": (
                EVIDENCE_CONDITIONAL_GUIDELINE
            ),
        },

        "dialysis": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "dialysis_modality",
                "dry_weight_kg",
                "clinician_protein_target",
            ],
            "evidence_quality": (
                EVIDENCE_CONDITIONAL_GUIDELINE
            ),
        },
    },

    "ul": None,
    "ul_source_type": None,
}


# =========================================================================
# CARBOHYDRATE
# =========================================================================

CARBOHYDRATE_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "carbohydrate_g",
    "official_name": "Carbohydrate",
    "canonical_unit": "g/day",
    "measurement_basis": "total_carbohydrate",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 60.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 95.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 130.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 130.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 130.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "RDA",
            "value": 130.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "RDA",
            "value": 130.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "RDA",
            "value": 130.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "RDA",
            "value": 130.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "RDA",
            "value": 130.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 175.0,
    },

    "lactation": {
        "type": "RDA",
        "value": 210.0,
    },

    "amdr": {
        "minimum_percent_energy": 45.0,
        "maximum_percent_energy": 65.0,
        "applicability": "age_1_year_and_older",
        "conversion": {
            "kcal_per_gram": 4.0,
            "requires_input": "energy_kcal",
        },
    },

    "clinical_overrides": {
        "endurance_training": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "weight_kg",
                "training_duration",
                "training_intensity",
                "training_volume",
            ],
            "message": (
                "Endurance carbohydrate targets depend on training "
                "volume and cannot be selected from the profile alone."
            ),
            "evidence_quality": (
                EVIDENCE_CONDITIONAL_GUIDELINE
            ),
        },

        "low_carb_or_ketogenic": {
            "override_type": "diet_pattern_choice",
            "automatic_target": None,
            "message": (
                "A low-carbohydrate target is a dietary-pattern "
                "choice and does not replace the baseline DRI "
                "without an explicit configured plan."
            ),
        },
    },

    "ul": None,
    "ul_source_type": None,
}


# =========================================================================
# DIETARY FIBER
# =========================================================================

FIBER_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "fiber_g",
    "official_name": "Dietary fiber",
    "canonical_unit": "g/day",
    "measurement_basis": "total_dietary_fiber",
    "reference_type": "AI",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": None,
            "value": None,
            "status": "no_dri_established",
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": None,
            "value": None,
            "status": "no_dri_established",
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "AI",
            "value": 19.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "AI",
            "value": 25.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "male",
            "type": "AI",
            "value": 31.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "female",
            "type": "AI",
            "value": 26.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "AI",
            "value": 38.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "AI",
            "value": 26.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "AI",
            "value": 38.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "AI",
            "value": 25.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "AI",
            "value": 38.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "AI",
            "value": 25.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "AI",
            "value": 30.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "AI",
            "value": 21.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "AI",
            "value": 30.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "AI",
            "value": 21.0,
        },
    ],

    "pregnancy": {
        "type": "AI",
        "value": 28.0,
    },

    "lactation": {
        "type": "AI",
        "value": 29.0,
    },

    "clinical_overrides": {
        "ibs": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Fiber type and tolerance may matter more than "
                "the total amount. Do not automatically reduce "
                "or increase the baseline AI."
            ),
        },

        "ibd": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Disease activity and fiber tolerance require "
                "individual assessment. Do not automatically "
                "change the baseline AI."
            ),
        },

        "low_appetite": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "High-fiber foods can reduce energy intake in some "
                "people with low appetite. Keep the baseline target "
                "but show a tolerance warning."
            ),
        },
    },

    "ul": None,
    "ul_source_type": None,
}


# =========================================================================
# TOTAL FAT
# =========================================================================

TOTAL_FAT_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "fat_g",
    "official_name": "Total fat",
    "canonical_unit": "g/day",
    "measurement_basis": "total_fat",
    "reference_type": "AMDR",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": None,
            "value": None,
            "status": "infant_feeding_guidance_required",
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": None,
            "value": None,
            "status": "infant_feeding_guidance_required",
        },
    ],

    "amdr_values": [
        {
            "life_stage": "1_3_years",
            "minimum_percent_energy": 30.0,
            "maximum_percent_energy": 40.0,
        },
        {
            "life_stage": "4_8_years",
            "minimum_percent_energy": 25.0,
            "maximum_percent_energy": 35.0,
        },
        {
            "life_stage": "9_13_years",
            "minimum_percent_energy": 25.0,
            "maximum_percent_energy": 35.0,
        },
        {
            "life_stage": "14_18_years",
            "minimum_percent_energy": 25.0,
            "maximum_percent_energy": 35.0,
        },
        {
            "life_stage": "19_30_years",
            "minimum_percent_energy": 20.0,
            "maximum_percent_energy": 35.0,
        },
        {
            "life_stage": "31_50_years",
            "minimum_percent_energy": 20.0,
            "maximum_percent_energy": 35.0,
        },
        {
            "life_stage": "51_70_years",
            "minimum_percent_energy": 20.0,
            "maximum_percent_energy": 35.0,
        },
        {
            "life_stage": "71_plus_years",
            "minimum_percent_energy": 20.0,
            "maximum_percent_energy": 35.0,
        },
    ],

    "pregnancy_amdr": {
        "minimum_percent_energy": 20.0,
        "maximum_percent_energy": 35.0,
    },

    "lactation_amdr": {
        "minimum_percent_energy": 20.0,
        "maximum_percent_energy": 35.0,
    },

    "conversion": {
        "kcal_per_gram": 9.0,
        "requires_input": "energy_kcal",
        "formula": (
            "grams = energy_kcal × percent_energy / 100 / 9"
        ),
    },

    "clinical_overrides": {
        "low_carb_or_ketogenic": {
            "override_type": "diet_pattern_choice",
            "automatic_target": None,
            "message": (
                "Do not automatically raise the total-fat target "
                "without an explicitly configured dietary plan."
            ),
        },
    },

    "ul": None,
    "ul_source_type": None,
}


# =========================================================================
# SATURATED FAT
# =========================================================================

SATURATED_FAT_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "saturated_fat_g",
    "official_name": "Saturated fat",
    "canonical_unit": "g/day",
    "measurement_basis": "total_saturated_fat",
    "reference_type": "maximum",
    "source": {
        "organization": (
            "Public-health and cardiometabolic "
            "nutrition guidelines"
        ),
        "document_title": (
            "Saturated-fat intake guidance"
        ),
        "publication_year": None,
        "recommendation_or_table": (
            "General ceiling below 10 percent "
            "of total energy"
        ),
        "source_url": None,
        "doi": None,
        "accessed_date": "2026-07-18",
    },

    "baseline_limit": {
        "maximum_percent_energy": 10.0,
        "comparison": "less_than",
        "conversion": {
            "kcal_per_gram": 9.0,
            "requires_input": "energy_kcal",
            "formula": (
                "maximum_grams = "
                "energy_kcal × 0.10 / 9"
            ),
        },
    },

    "clinical_overrides": {
        "cardiometabolic_high_risk": {
            "override_type": "maximum_percent_energy",
            "maximum_percent_energy": 7.0,
            "required_conditions_any": [
                "dyslipidemia",
                "high_cholesterol",
                "coronary_artery_disease",
            ],
            "message": (
                "A stricter ceiling may be used only when "
                "enabled by the clinical policy layer."
            ),
            "evidence_quality": (
                EVIDENCE_CONDITIONAL_GUIDELINE
            ),
        },
    },

    "ul": None,
    "ul_source_type": None,
    "limit_type": "maximum",
}


# =========================================================================
# TRANS FAT
# =========================================================================

TRANS_FAT_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "trans_fat_g",
    "official_name": "Trans fat",
    "canonical_unit": "g/day",
    "measurement_basis": "total_trans_fat",
    "reference_type": "maximum",
    "source": {
        "organization": (
            "Public-health nutrition guidance"
        ),
        "document_title": (
            "Trans-fat intake guidance"
        ),
        "publication_year": None,
        "recommendation_or_table": (
            "Intake should be as low as possible"
        ),
        "source_url": None,
        "doi": None,
        "accessed_date": "2026-07-18",
    },

    "baseline_limit": {
        "value": 0.0,
        "comparison": "as_low_as_possible",
        "practical_display_target": 0.0,
    },

    "clinical_overrides": {},

    "ul": None,
    "ul_source_type": None,
    "limit_type": "maximum",
    "notes": (
        "Any measurable amount may be shown as an "
        "unfavorable intake rather than as progress "
        "toward a requirement."
    ),
}


# =========================================================================
# VITAMIN A
# =========================================================================

VITAMIN_A_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "vitamin_a_ug",
    "official_name": "Vitamin A",
    "canonical_unit": "ug RAE/day",
    "measurement_basis": "RAE",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "accepted_input_keys": [
        "vitamin_a_ug_rae",
        "vitamin_a_ug",
    ],

    "conversion_required": True,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 400.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 500.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 300.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 400.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 600.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "RDA",
            "value": 900.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "RDA",
            "value": 700.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "RDA",
            "value": 900.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "RDA",
            "value": 700.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "RDA",
            "value": 900.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "RDA",
            "value": 700.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "RDA",
            "value": 900.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "RDA",
            "value": 700.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "RDA",
            "value": 900.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "RDA",
            "value": 700.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 770.0,
    },

    "lactation": {
        "type": "RDA",
        "value": 1300.0,
    },

    "ul": {
        "adult_value": 3000.0,
        "unit": "ug RAE/day",
        "applies_to": "preformed_vitamin_a",
        "source_type": "all_sources_of_preformed_retinol",
    },

    "clinical_overrides": {
        "pregnancy_retinol_safety": {
            "override_type": "warning",
            "automatic_target": None,
            "message": (
                "The UL applies to preformed vitamin A. "
                "High supplemental retinol intake during "
                "pregnancy requires special caution."
            ),
        },
    },
}


# =========================================================================
# VITAMIN C
# =========================================================================

VITAMIN_C_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "vitamin_c_mg",
    "official_name": "Vitamin C",
    "canonical_unit": "mg/day",
    "measurement_basis": "ascorbic_acid",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 40.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 50.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 25.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 45.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "RDA",
            "value": 75.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "RDA",
            "value": 65.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "RDA",
            "value": 90.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "RDA",
            "value": 75.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "RDA",
            "value": 90.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "RDA",
            "value": 75.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "RDA",
            "value": 90.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "RDA",
            "value": 75.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "RDA",
            "value": 90.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "RDA",
            "value": 75.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 85.0,
    },

    "lactation": {
        "type": "RDA",
        "value": 120.0,
    },

    "clinical_overrides": {
        "smoker": {
            "override_type": "additive",
            "add_value": 35.0,
            "unit": "mg/day",
            "evidence_quality": (
                EVIDENCE_STRONG_GUIDELINE
            ),
        },
    },

    "ul": {
        "adult_value": 2000.0,
        "unit": "mg/day",
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },
}


# =========================================================================
# VITAMIN D
# =========================================================================

VITAMIN_D_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "vitamin_d_ug",
    "official_name": "Vitamin D",
    "canonical_unit": "ug/day",
    "measurement_basis": "vitamin_d2_plus_d3",
    "reference_type": "RDA",
    "source": {
        "organization": (
            "National Academies / "
            "NIH Office of Dietary Supplements"
        ),
        "document_title": (
            "Dietary Reference Intakes for "
            "Calcium and Vitamin D"
        ),
        "publication_year": 2011,
        "recommendation_or_table": (
            "Vitamin D life-stage DRI tables"
        ),
        "source_url": (
            "https://nap.nationalacademies.org/"
            "catalog/13050"
        ),
        "doi": None,
        "accessed_date": "2026-07-18",
    },

    "accepted_input_keys": [
        "vitamin_d_ug",
        "vitamin_d_mcg",
        "vitamin_d_iu",
    ],

    "conversion_rules": {
        "iu_to_ug": 0.025,
    },

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 10.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 10.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "RDA",
            "value": 20.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 15.0,
    },

    "lactation": {
        "type": "RDA",
        "value": 15.0,
    },

    "clinical_overrides": {
        "deficiency_or_repletion": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "serum_25_oh_vitamin_d",
                "clinician_repletion_plan",
            ],
            "message": (
                "Deficiency correction must remain separate "
                "from the dietary DRI target."
            ),
        },

        "osteoporosis_or_osteopenia": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Maintain the age-based DRI and flag the "
                "need to assess vitamin D sufficiency."
            ),
        },
    },

    "ul": {
        "adult_value": 100.0,
        "unit": "ug/day",
        "equivalent_iu": 4000.0,
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },
}


# =========================================================================
# VITAMIN E
# =========================================================================

VITAMIN_E_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "vitamin_e_mg",
    "official_name": "Vitamin E",
    "canonical_unit": "mg alpha-tocopherol/day",
    "measurement_basis": "alpha_tocopherol",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "accepted_input_keys": [
        "vitamin_e_mg_alpha_tocopherol",
        "alpha_tocopherol_mg",
        "vitamin_e_mg",
    ],

    "conversion_required": True,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 4.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 5.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 6.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 7.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 11.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "RDA",
            "value": 15.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 15.0,
    },

    "lactation": {
        "type": "RDA",
        "value": 19.0,
    },

    "clinical_overrides": {},

    "ul": {
        "adult_value": 1000.0,
        "unit": "mg/day",
        "applies_to": "supplemental_alpha_tocopherol",
        "source_type": "supplements",
    },
}


# =========================================================================
# VITAMIN K
# =========================================================================

VITAMIN_K_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "vitamin_k_ug",
    "official_name": "Vitamin K",
    "canonical_unit": "ug/day",
    "measurement_basis": "total_vitamin_k",
    "reference_type": "AI",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 2.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 2.5,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "AI",
            "value": 30.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "AI",
            "value": 55.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "AI",
            "value": 60.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "AI",
            "value": 75.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "AI",
            "value": 120.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "AI",
            "value": 90.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "AI",
            "value": 120.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "AI",
            "value": 90.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "AI",
            "value": 120.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "AI",
            "value": 90.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "AI",
            "value": 120.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "AI",
            "value": 90.0,
        },
    ],

    "pregnancy": {
        "type": "AI",
        "value": 90.0,
    },

    "lactation": {
        "type": "AI",
        "value": 90.0,
    },

    "clinical_overrides": {
        "warfarin": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Do not automatically reduce the vitamin K "
                "target. Maintain consistent intake and coordinate "
                "with anticoagulation management."
            ),
        },
    },

    "ul": None,
    "ul_source_type": None,
}

# =========================================================================
# THIAMIN — VITAMIN B1
# =========================================================================

THIAMIN_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "thiamin_mg",
    "official_name": "Thiamin",
    "canonical_unit": "mg/day",
    "measurement_basis": "thiamin",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 0.2,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 0.3,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.5,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.6,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.9,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.2,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.2,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.1,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.2,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.1,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.2,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.1,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.2,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.1,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 1.4,
    },

    "lactation": {
        "type": "RDA",
        "value": 1.4,
    },

    "clinical_overrides": {
        "alcohol_use_disorder": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Alcohol-related thiamin deficiency risk "
                "requires clinical assessment and must not "
                "be handled by silently changing the RDA."
            ),
        },
    },

    "ul": None,
    "ul_source_type": None,
}


# =========================================================================
# RIBOFLAVIN — VITAMIN B2
# =========================================================================

RIBOFLAVIN_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "riboflavin_mg",
    "official_name": "Riboflavin",
    "canonical_unit": "mg/day",
    "measurement_basis": "riboflavin",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 0.3,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 0.4,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.5,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.6,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.9,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.3,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.3,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.1,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.3,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.1,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.3,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.1,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.3,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.1,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 1.4,
    },

    "lactation": {
        "type": "RDA",
        "value": 1.6,
    },

    "clinical_overrides": {},

    "ul": None,
    "ul_source_type": None,
}


# =========================================================================
# NIACIN — VITAMIN B3
# =========================================================================

NIACIN_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "niacin_mg",
    "official_name": "Niacin",
    "canonical_unit": "mg NE/day",
    "measurement_basis": "niacin_equivalents",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "accepted_input_keys": [
        "niacin_mg_ne",
        "niacin_mg",
    ],

    "conversion_required": True,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 2.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 4.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 6.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 8.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 12.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "RDA",
            "value": 16.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "RDA",
            "value": 14.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "RDA",
            "value": 16.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "RDA",
            "value": 14.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "RDA",
            "value": 16.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "RDA",
            "value": 14.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "RDA",
            "value": 16.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "RDA",
            "value": 14.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "RDA",
            "value": 16.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "RDA",
            "value": 14.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 18.0,
    },

    "lactation": {
        "type": "RDA",
        "value": 17.0,
    },

    "clinical_overrides": {},

    "ul_by_life_stage": [
        {
            "life_stage": "1_3_years",
            "value": 10.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 15.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 20.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 30.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 35.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 35.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 35.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 35.0,
        },
    ],

    "ul": {
        "adult_value": 35.0,
        "unit": "mg/day",
        "applies_to": (
            "supplements_and_fortified_foods"
        ),
        "source_type": (
            "supplemental_and_added_niacin"
        ),
    },
}


# =========================================================================
# PANTOTHENIC ACID — VITAMIN B5
# =========================================================================

PANTOTHENIC_ACID_TARGET: Final[
    Dict[str, Any]
] = {
    "nutrient_key": "pantothenic_acid_mg",
    "official_name": "Pantothenic acid",
    "canonical_unit": "mg/day",
    "measurement_basis": "pantothenic_acid",
    "reference_type": "AI",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 1.7,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 1.8,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "AI",
            "value": 2.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "AI",
            "value": 3.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "AI",
            "value": 4.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "AI",
            "value": 5.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "AI",
            "value": 5.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "AI",
            "value": 5.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "AI",
            "value": 5.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "AI",
            "value": 5.0,
        },
    ],

    "pregnancy": {
        "type": "AI",
        "value": 6.0,
    },

    "lactation": {
        "type": "AI",
        "value": 7.0,
    },

    "clinical_overrides": {},

    "ul": None,
    "ul_source_type": None,
}


# =========================================================================
# VITAMIN B6
# =========================================================================

VITAMIN_B6_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "vitamin_b6_mg",
    "official_name": "Vitamin B6",
    "canonical_unit": "mg/day",
    "measurement_basis": "total_vitamin_b6",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 0.1,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 0.3,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.5,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.6,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 1.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.3,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.2,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "RDA",
            "value": 1.3,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "RDA",
            "value": 1.3,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.7,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.5,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "RDA",
            "value": 1.7,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "RDA",
            "value": 1.5,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 1.9,
    },

    "lactation": {
        "type": "RDA",
        "value": 2.0,
    },

    "clinical_overrides": {},

    "ul_by_life_stage": [
        {
            "life_stage": "1_3_years",
            "value": 30.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 40.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 60.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 80.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 100.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 100.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 100.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 100.0,
        },
    ],

    "ul": {
        "adult_value": 100.0,
        "unit": "mg/day",
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },
}


# =========================================================================
# FOLATE — VITAMIN B9
# =========================================================================

FOLATE_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "folate_ug",
    "official_name": "Folate",
    "canonical_unit": "ug DFE/day",
    "measurement_basis": "dietary_folate_equivalents",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "accepted_input_keys": [
        "folate_ug_dfe",
        "folate_ug",
    ],

    "conversion_required": True,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 65.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 80.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 150.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 200.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 300.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "RDA",
            "value": 400.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "RDA",
            "value": 400.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "RDA",
            "value": 400.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "RDA",
            "value": 400.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "RDA",
            "value": 400.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 600.0,
    },

    "lactation": {
        "type": "RDA",
        "value": 500.0,
    },

    "clinical_overrides": {
        "pregnancy_supplementation": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Pregnancy supplementation guidance is "
                "separate from the total dietary DFE RDA."
            ),
        },

        "malabsorption_or_deficiency": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "folate_status",
                "diagnosis",
                "clinician_treatment_plan",
            ],
        },
    },

    "ul_by_life_stage": [
        {
            "life_stage": "1_3_years",
            "value": 300.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 400.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 600.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 800.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 1000.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 1000.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 1000.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 1000.0,
        },
    ],

    "ul": {
        "adult_value": 1000.0,
        "unit": "ug/day",
        "applies_to": (
            "synthetic_folic_acid_from_supplements_"
            "and_fortified_foods"
        ),
        "source_type": (
            "supplemental_and_added_folic_acid"
        ),
    },
}


# =========================================================================
# VITAMIN B12
# =========================================================================

VITAMIN_B12_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "vitamin_b12_ug",
    "official_name": "Vitamin B12",
    "canonical_unit": "ug/day",
    "measurement_basis": "cobalamin",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 0.4,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 0.5,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.9,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 1.2,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 1.8,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "RDA",
            "value": 2.4,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "RDA",
            "value": 2.4,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "RDA",
            "value": 2.4,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "RDA",
            "value": 2.4,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "RDA",
            "value": 2.4,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 2.6,
    },

    "lactation": {
        "type": "RDA",
        "value": 2.8,
    },

    "clinical_overrides": {
        "vegan": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The official RDA is unchanged, but a "
                "reliable fortified-food or supplement "
                "source is generally required."
            ),
        },

        "vegetarian": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The official RDA is unchanged, but intake "
                "adequacy should be assessed carefully."
            ),
        },

        "metformin": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Metformin use is associated with vitamin "
                "B12 deficiency risk. The target is not "
                "automatically increased without clinical data."
            ),
        },

        "ppi": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Long-term acid suppression may impair "
                "vitamin B12 absorption."
            ),
        },

        "deficiency_or_malabsorption": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "serum_vitamin_b12",
                "methylmalonic_acid",
                "diagnosis",
                "clinician_treatment_plan",
            ],
        },
    },

    "ul": None,
    "ul_source_type": None,
}


# =========================================================================
# CHOLINE
# =========================================================================

CHOLINE_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "choline_mg",
    "official_name": "Choline",
    "canonical_unit": "mg/day",
    "measurement_basis": "total_choline",
    "reference_type": "AI",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 125.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 150.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "AI",
            "value": 200.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "AI",
            "value": 250.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "AI",
            "value": 375.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "AI",
            "value": 550.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "AI",
            "value": 400.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "AI",
            "value": 550.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "AI",
            "value": 425.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "AI",
            "value": 550.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "AI",
            "value": 425.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "AI",
            "value": 550.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "AI",
            "value": 425.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "AI",
            "value": 550.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "AI",
            "value": 425.0,
        },
    ],

    "pregnancy": {
        "type": "AI",
        "value": 450.0,
    },

    "lactation": {
        "type": "AI",
        "value": 550.0,
    },

    "clinical_overrides": {
        "vegan": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The choline AI is unchanged, but diet "
                "adequacy may require closer review."
            ),
        },

        "pregnancy": {
            "override_type": "life_stage_target",
            "automatic_target": 450.0,
            "unit": "mg/day",
        },
    },

    "ul_by_life_stage": [
        {
            "life_stage": "1_3_years",
            "value": 1000.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 1000.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 2000.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 3000.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 3500.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 3500.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 3500.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 3500.0,
        },
    ],

    "ul": {
        "adult_value": 3500.0,
        "unit": "mg/day",
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },
}

# =========================================================================
# CALCIUM
# =========================================================================

CALCIUM_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "calcium_mg",
    "official_name": "Calcium",
    "canonical_unit": "mg/day",
    "measurement_basis": "total_calcium",
    "reference_type": "RDA",
    "source": {
        "organization": (
            "National Academies / "
            "NIH Office of Dietary Supplements"
        ),
        "document_title": (
            "Dietary Reference Intakes for "
            "Calcium and Vitamin D"
        ),
        "publication_year": 2011,
        "recommendation_or_table": (
            "Calcium life-stage DRI tables"
        ),
        "source_url": (
            "https://nap.nationalacademies.org/"
            "catalog/13050"
        ),
        "doi": None,
        "accessed_date": "2026-07-18",
    },

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 200.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 260.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 700.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 1000.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 1300.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "RDA",
            "value": 1300.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "RDA",
            "value": 1000.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "RDA",
            "value": 1000.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "RDA",
            "value": 1000.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "RDA",
            "value": 1200.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "RDA",
            "value": 1200.0,
        },
    ],

    "pregnancy_by_life_stage": [
        {
            "life_stage": "14_18_years",
            "type": "RDA",
            "value": 1300.0,
        },
        {
            "life_stage": "19_30_years",
            "type": "RDA",
            "value": 1000.0,
        },
        {
            "life_stage": "31_50_years",
            "type": "RDA",
            "value": 1000.0,
        },
    ],

    "lactation_by_life_stage": [
        {
            "life_stage": "14_18_years",
            "type": "RDA",
            "value": 1300.0,
        },
        {
            "life_stage": "19_30_years",
            "type": "RDA",
            "value": 1000.0,
        },
        {
            "life_stage": "31_50_years",
            "type": "RDA",
            "value": 1000.0,
        },
    ],

    "clinical_overrides": {
        "osteoporosis_or_osteopenia": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Use the age- and sex-based RDA. "
                "Osteoporosis or osteopenia increases "
                "the importance of calcium adequacy but "
                "does not automatically create a higher "
                "dietary target."
            ),
        },

        "frailty": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Use the age-based RDA and flag low "
                "calcium intake as a higher-priority risk."
            ),
        },

        "vegan": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The official calcium target is unchanged, "
                "but inadequate intake risk may be higher "
                "without fortified foods or supplements."
            ),
        },

        "ppi": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Long-term acid suppression may affect "
                "calcium absorption or calcium-source "
                "selection. Do not automatically increase "
                "the RDA."
            ),
        },

        "ckd": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "ckd_stage",
                "serum_calcium",
                "serum_phosphorus",
                "parathyroid_hormone",
                "vitamin_d_status",
                "phosphate_binder_use",
                "dialysis_modality",
            ],
            "message": (
                "Calcium management in CKD depends on "
                "mineral-bone-disorder status and must not "
                "be resolved from the profile alone."
            ),
            "evidence_quality": (
                EVIDENCE_CONDITIONAL_GUIDELINE
            ),
        },
    },

    "ul_by_life_stage": [
        {
            "life_stage": "0_6_months",
            "value": 1000.0,
        },
        {
            "life_stage": "7_12_months",
            "value": 1500.0,
        },
        {
            "life_stage": "1_3_years",
            "value": 2500.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 2500.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 3000.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 3000.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 2500.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 2500.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 2000.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 2000.0,
        },
    ],

    "ul": {
        "adult_19_50_value": 2500.0,
        "adult_51_plus_value": 2000.0,
        "unit": "mg/day",
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },
}


# =========================================================================
# IRON
# =========================================================================

IRON_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "iron_mg",
    "official_name": "Iron",
    "canonical_unit": "mg/day",
    "measurement_basis": "total_iron",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 0.27,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "RDA",
            "value": 11.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 7.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 10.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 8.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "RDA",
            "value": 11.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "RDA",
            "value": 15.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "RDA",
            "value": 8.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "RDA",
            "value": 18.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "RDA",
            "value": 8.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "RDA",
            "value": 18.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "RDA",
            "value": 8.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "RDA",
            "value": 8.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 27.0,
    },

    "lactation_by_life_stage": [
        {
            "life_stage": "14_18_years",
            "type": "RDA",
            "value": 10.0,
        },
        {
            "life_stage": "19_30_years",
            "type": "RDA",
            "value": 9.0,
        },
        {
            "life_stage": "31_50_years",
            "type": "RDA",
            "value": 9.0,
        },
    ],

    "clinical_overrides": {
        "vegetarian": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The stored RDA is unchanged. Lower "
                "non-heme iron bioavailability should be "
                "handled as an absorption and adequacy risk."
            ),
        },

        "vegan": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The stored RDA is unchanged. Lower "
                "non-heme iron bioavailability should be "
                "handled as an absorption and adequacy risk."
            ),
        },

        "iron_deficiency": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "hemoglobin",
                "serum_ferritin",
                "transferrin_saturation",
                "diagnosis",
                "clinician_repletion_plan",
            ],
            "message": (
                "Iron-deficiency treatment is a clinical "
                "repletion plan and must remain separate "
                "from the baseline RDA."
            ),
        },

        "ppi": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Long-term acid suppression may reduce "
                "iron absorption. Do not automatically "
                "increase the RDA."
            ),
        },

        "ckd": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "ckd_stage",
                "hemoglobin",
                "serum_ferritin",
                "transferrin_saturation",
                "erythropoiesis_stimulating_agent_use",
                "clinician_iron_plan",
            ],
            "message": (
                "Iron management in CKD depends on anemia "
                "status and treatment strategy."
            ),
            "evidence_quality": (
                EVIDENCE_CONDITIONAL_GUIDELINE
            ),
        },
    },

    "ul_by_life_stage": [
        {
            "life_stage": "0_6_months",
            "value": 40.0,
        },
        {
            "life_stage": "7_12_months",
            "value": 40.0,
        },
        {
            "life_stage": "1_3_years",
            "value": 40.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 40.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 40.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 45.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 45.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 45.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 45.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 45.0,
        },
    ],

    "ul": {
        "adult_value": 45.0,
        "unit": "mg/day",
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },
}


# =========================================================================
# MAGNESIUM
# =========================================================================

MAGNESIUM_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "magnesium_mg",
    "official_name": "Magnesium",
    "canonical_unit": "mg/day",
    "measurement_basis": "total_magnesium",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 30.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 75.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 80.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 130.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 240.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "RDA",
            "value": 410.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "RDA",
            "value": 360.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "RDA",
            "value": 400.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "RDA",
            "value": 310.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "RDA",
            "value": 420.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "RDA",
            "value": 320.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "RDA",
            "value": 420.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "RDA",
            "value": 320.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "RDA",
            "value": 420.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "RDA",
            "value": 320.0,
        },
    ],

    "pregnancy_by_life_stage": [
        {
            "life_stage": "14_18_years",
            "type": "RDA",
            "value": 400.0,
        },
        {
            "life_stage": "19_30_years",
            "type": "RDA",
            "value": 350.0,
        },
        {
            "life_stage": "31_50_years",
            "type": "RDA",
            "value": 360.0,
        },
    ],

    "lactation_by_life_stage": [
        {
            "life_stage": "14_18_years",
            "type": "RDA",
            "value": 360.0,
        },
        {
            "life_stage": "19_30_years",
            "type": "RDA",
            "value": 310.0,
        },
        {
            "life_stage": "31_50_years",
            "type": "RDA",
            "value": 320.0,
        },
    ],

    "clinical_overrides": {
        "hypertension": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Adequate magnesium intake is clinically "
                "relevant, but hypertension does not "
                "automatically change the DRI."
            ),
        },

        "ppi": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Long-term proton-pump-inhibitor use may "
                "increase magnesium deficiency risk."
            ),
        },

        "diuretic": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Some diuretics may increase magnesium "
                "loss. The target should not be changed "
                "without medication and laboratory context."
            ),
        },

        "ckd": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "ckd_stage",
                "serum_magnesium",
                "dialysis_modality",
                "medications",
                "clinician_magnesium_target",
            ],
            "message": (
                "Magnesium restriction or supplementation "
                "in CKD requires laboratory and clinical "
                "assessment."
            ),
            "evidence_quality": (
                EVIDENCE_CONDITIONAL_GUIDELINE
            ),
        },
    },

    "ul": {
        "adult_value": 350.0,
        "unit": "mg/day",
        "applies_to": (
            "supplements_and_medications_only"
        ),
        "source_type": (
            "supplemental_magnesium"
        ),
        "excludes": (
            "naturally_occurring_food_magnesium"
        ),
    },
}


# =========================================================================
# PHOSPHORUS
# =========================================================================

PHOSPHORUS_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "phosphorus_mg",
    "official_name": "Phosphorus",
    "canonical_unit": "mg/day",
    "measurement_basis": "total_phosphorus",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 100.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 275.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 460.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 500.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 1250.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "RDA",
            "value": 1250.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "RDA",
            "value": 700.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "RDA",
            "value": 700.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "RDA",
            "value": 700.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "RDA",
            "value": 700.0,
        },
    ],

    "pregnancy_by_life_stage": [
        {
            "life_stage": "14_18_years",
            "type": "RDA",
            "value": 1250.0,
        },
        {
            "life_stage": "19_30_years",
            "type": "RDA",
            "value": 700.0,
        },
        {
            "life_stage": "31_50_years",
            "type": "RDA",
            "value": 700.0,
        },
    ],

    "lactation_by_life_stage": [
        {
            "life_stage": "14_18_years",
            "type": "RDA",
            "value": 1250.0,
        },
        {
            "life_stage": "19_30_years",
            "type": "RDA",
            "value": 700.0,
        },
        {
            "life_stage": "31_50_years",
            "type": "RDA",
            "value": 700.0,
        },
    ],

    "clinical_overrides": {
        "ckd": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "ckd_stage",
                "serum_phosphorus",
                "serum_calcium",
                "parathyroid_hormone",
                "dialysis_modality",
                "phosphate_binder_use",
                "dietitian_or_clinician_target",
            ],
            "message": (
                "Phosphorus restriction in CKD must be "
                "individualized and must account for "
                "laboratory values, additives and food "
                "bioavailability."
            ),
            "evidence_quality": (
                EVIDENCE_CONDITIONAL_GUIDELINE
            ),
        },
    },

    "ul_by_life_stage": [
        {
            "life_stage": "0_6_months",
            "value": None,
            "status": "not_determined",
        },
        {
            "life_stage": "7_12_months",
            "value": None,
            "status": "not_determined",
        },
        {
            "life_stage": "1_3_years",
            "value": 3000.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 3000.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 4000.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 4000.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 4000.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 4000.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 4000.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 3000.0,
        },
    ],

    "ul": {
        "adult_19_70_value": 4000.0,
        "adult_71_plus_value": 3000.0,
        "unit": "mg/day",
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },
}


# =========================================================================
# ZINC
# =========================================================================

ZINC_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "zinc_mg",
    "official_name": "Zinc",
    "canonical_unit": "mg/day",
    "measurement_basis": "total_zinc",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 2.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "RDA",
            "value": 3.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 3.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 5.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 8.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "RDA",
            "value": 11.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "RDA",
            "value": 9.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "RDA",
            "value": 11.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "RDA",
            "value": 8.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "RDA",
            "value": 11.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "RDA",
            "value": 8.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "RDA",
            "value": 11.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "RDA",
            "value": 8.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "RDA",
            "value": 11.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "RDA",
            "value": 8.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 11.0,
    },

    "lactation": {
        "type": "RDA",
        "value": 12.0,
    },

    "clinical_overrides": {
        "vegetarian": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The official zinc RDA is unchanged, but "
                "phytate-related absorption risk may be higher."
            ),
        },

        "vegan": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The official zinc RDA is unchanged, but "
                "phytate-related absorption risk may be higher."
            ),
        },

        "high_dose_zinc_supplement": {
            "override_type": "interaction_flag",
            "automatic_target": None,
            "affected_nutrients": [
                "copper_mg",
            ],
            "message": (
                "High zinc supplementation may impair "
                "copper status."
            ),
        },
    },

    "ul_by_life_stage": [
        {
            "life_stage": "0_6_months",
            "value": 4.0,
        },
        {
            "life_stage": "7_12_months",
            "value": 5.0,
        },
        {
            "life_stage": "1_3_years",
            "value": 7.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 12.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 23.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 34.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 40.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 40.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 40.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 40.0,
        },
    ],

    "ul": {
        "adult_value": 40.0,
        "unit": "mg/day",
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },
}


# =========================================================================
# COPPER
# =========================================================================

COPPER_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "copper_mg",
    "official_name": "Copper",
    "canonical_unit": "mg/day",
    "measurement_basis": "total_copper",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 0.200,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 0.220,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.340,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.440,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.700,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.900,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.900,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.900,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.900,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "RDA",
            "value": 0.900,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 1.000,
    },

    "lactation": {
        "type": "RDA",
        "value": 1.300,
    },

    "clinical_overrides": {
        "high_dose_zinc_supplement": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "High zinc supplementation may reduce "
                "copper absorption. Do not automatically "
                "increase the copper RDA."
            ),
        },

        "copper_deficiency": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "serum_copper",
                "ceruloplasmin",
                "diagnosis",
                "clinician_treatment_plan",
            ],
        },
    },

    "ul_by_life_stage": [
        {
            "life_stage": "1_3_years",
            "value": 1.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 3.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 5.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 8.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 10.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 10.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 10.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 10.0,
        },
    ],

    "ul": {
        "adult_value": 10.0,
        "unit": "mg/day",
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },
}


# =========================================================================
# MANGANESE
# =========================================================================

MANGANESE_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "manganese_mg",
    "official_name": "Manganese",
    "canonical_unit": "mg/day",
    "measurement_basis": "total_manganese",
    "reference_type": "AI",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 0.003,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 0.6,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "AI",
            "value": 1.2,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "AI",
            "value": 1.5,
        },
        {
            "life_stage": "9_13_years",
            "sex": "male",
            "type": "AI",
            "value": 1.9,
        },
        {
            "life_stage": "9_13_years",
            "sex": "female",
            "type": "AI",
            "value": 1.6,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "AI",
            "value": 2.2,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "AI",
            "value": 1.6,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "AI",
            "value": 2.3,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "AI",
            "value": 1.8,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "AI",
            "value": 2.3,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "AI",
            "value": 1.8,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "AI",
            "value": 2.3,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "AI",
            "value": 1.8,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "AI",
            "value": 2.3,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "AI",
            "value": 1.8,
        },
    ],

    "pregnancy": {
        "type": "AI",
        "value": 2.0,
    },

    "lactation": {
        "type": "AI",
        "value": 2.6,
    },

    "clinical_overrides": {},

    "ul_by_life_stage": [
        {
            "life_stage": "1_3_years",
            "value": 2.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 3.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 6.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 9.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 11.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 11.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 11.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 11.0,
        },
    ],

    "ul": {
        "adult_value": 11.0,
        "unit": "mg/day",
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },
}


# =========================================================================
# SELENIUM
# =========================================================================

SELENIUM_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "selenium_ug",
    "official_name": "Selenium",
    "canonical_unit": "ug/day",
    "measurement_basis": "total_selenium",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 15.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 20.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 20.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 30.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 40.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "RDA",
            "value": 55.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "RDA",
            "value": 55.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "RDA",
            "value": 55.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "RDA",
            "value": 55.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "RDA",
            "value": 55.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 60.0,
    },

    "lactation": {
        "type": "RDA",
        "value": 70.0,
    },

    "clinical_overrides": {
        "vegan": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The official selenium target is unchanged. "
                "Risk depends on regional soil and food sourcing."
            ),
        },

        "thyroid_disease": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Do not automatically increase selenium for "
                "thyroid disease. Excess supplementation can "
                "be harmful."
            ),
        },

        "ckd": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Keep the baseline target unless a clinician "
                "provides a condition-specific plan."
            ),
        },
    },

    "ul_by_life_stage": [
        {
            "life_stage": "0_6_months",
            "value": 45.0,
        },
        {
            "life_stage": "7_12_months",
            "value": 60.0,
        },
        {
            "life_stage": "1_3_years",
            "value": 90.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 150.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 280.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 400.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 400.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 400.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 400.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 400.0,
        },
    ],

    "ul": {
        "adult_value": 400.0,
        "unit": "ug/day",
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },
}


# =========================================================================
# IODINE
# =========================================================================

IODINE_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "iodine_ug",
    "official_name": "Iodine",
    "canonical_unit": "ug/day",
    "measurement_basis": "total_iodine",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "accepted_input_keys": [
        "iodine_ug",
        "iodine_mcg",
    ],

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 110.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 130.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 90.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 90.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 120.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "RDA",
            "value": 150.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "RDA",
            "value": 150.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "RDA",
            "value": 150.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "RDA",
            "value": 150.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "RDA",
            "value": 150.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 220.0,
    },

    "lactation": {
        "type": "RDA",
        "value": 290.0,
    },

    "clinical_overrides": {
        "vegetarian": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The official iodine target is unchanged. "
                "Risk may increase when iodized salt, dairy "
                "and seafood are limited."
            ),
        },

        "vegan": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The official iodine target is unchanged. "
                "Risk may increase when iodized salt, dairy "
                "and seafood are absent."
            ),
        },

        "low_sodium_diet": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Reducing sodium must not inadvertently "
                "remove the user's reliable iodine source. "
                "The iodine target itself remains unchanged."
            ),
        },

        "thyroid_disease": {
            "override_type": (
                TARGET_STATUS_REQUIRES_CLINICAL_INPUT
            ),
            "automatic_target": None,
            "required_inputs": [
                "thyroid_diagnosis",
                "thyroid_medications",
                "clinician_iodine_plan",
            ],
            "message": (
                "Thyroid disease may make iodine excess or "
                "restriction clinically important. Do not "
                "automatically modify the target."
            ),
        },
    },

    "ul_by_life_stage": [
        {
            "life_stage": "1_3_years",
            "value": 200.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 300.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 600.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 900.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 1100.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 1100.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 1100.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 1100.0,
        },
    ],

    "ul": {
        "adult_value": 1100.0,
        "unit": "ug/day",
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },
}

# =========================================================================
# CHROMIUM
# =========================================================================

CHROMIUM_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "chromium_ug",
    "official_name": "Chromium",
    "canonical_unit": "ug/day",
    "measurement_basis": "total_chromium",
    "reference_type": "AI",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "accepted_input_keys": [
        "chromium_ug",
        "chromium_mcg",
    ],

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 0.2,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 5.5,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "AI",
            "value": 11.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "AI",
            "value": 15.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "AI",
            "value": 25.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "AI",
            "value": 35.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "AI",
            "value": 24.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "AI",
            "value": 35.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "AI",
            "value": 25.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "AI",
            "value": 35.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "AI",
            "value": 25.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "AI",
            "value": 30.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "AI",
            "value": 20.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "AI",
            "value": 30.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "AI",
            "value": 20.0,
        },
    ],

    "pregnancy_by_life_stage": [
        {
            "life_stage": "14_18_years",
            "type": "AI",
            "value": 29.0,
        },
        {
            "life_stage": "19_30_years",
            "type": "AI",
            "value": 30.0,
        },
        {
            "life_stage": "31_50_years",
            "type": "AI",
            "value": 30.0,
        },
    ],

    "lactation_by_life_stage": [
        {
            "life_stage": "14_18_years",
            "type": "AI",
            "value": 44.0,
        },
        {
            "life_stage": "19_30_years",
            "type": "AI",
            "value": 45.0,
        },
        {
            "life_stage": "31_50_years",
            "type": "AI",
            "value": 45.0,
        },
    ],

    "clinical_overrides": {
        "diabetes_or_prediabetes": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Do not automatically increase chromium "
                "for diabetes or prediabetes. Evidence does "
                "not support changing the baseline AI."
            ),
        },

        "chromium_supplement_use": {
            "override_type": "supplement_safety_flag",
            "automatic_target": None,
            "message": (
                "Chromium supplementation must be tracked "
                "separately from the baseline food target."
            ),
        },
    },

    "ul": None,
    "ul_source_type": None,

    "evidence_quality": (
        EVIDENCE_AUTHORITATIVE_DRI
    ),

    "priority_tier": 3,
}


# =========================================================================
# MOLYBDENUM
# =========================================================================

MOLYBDENUM_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "molybdenum_ug",
    "official_name": "Molybdenum",
    "canonical_unit": "ug/day",
    "measurement_basis": "total_molybdenum",
    "reference_type": "RDA",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "accepted_input_keys": [
        "molybdenum_ug",
        "molybdenum_mcg",
    ],

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 2.0,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 3.0,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "RDA",
            "value": 17.0,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "RDA",
            "value": 22.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "RDA",
            "value": 34.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "any",
            "type": "RDA",
            "value": 45.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "any",
            "type": "RDA",
            "value": 45.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "any",
            "type": "RDA",
            "value": 45.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "any",
            "type": "RDA",
            "value": 45.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "any",
            "type": "RDA",
            "value": 45.0,
        },
    ],

    "pregnancy": {
        "type": "RDA",
        "value": 50.0,
    },

    "lactation": {
        "type": "RDA",
        "value": 50.0,
    },

    "clinical_overrides": {},

    "ul_by_life_stage": [
        {
            "life_stage": "1_3_years",
            "value": 300.0,
        },
        {
            "life_stage": "4_8_years",
            "value": 600.0,
        },
        {
            "life_stage": "9_13_years",
            "value": 1100.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 1700.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 2000.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 2000.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 2000.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 2000.0,
        },
    ],

    "ul": {
        "adult_value": 2000.0,
        "unit": "ug/day",
        "applies_to": "all_sources",
        "source_type": "all_intake",
    },

    "evidence_quality": (
        EVIDENCE_AUTHORITATIVE_DRI
    ),

    "priority_tier": 3,
}


# =========================================================================
# FLUORIDE
# =========================================================================

FLUORIDE_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "fluoride_mg",
    "official_name": "Fluoride",
    "canonical_unit": "mg/day",
    "measurement_basis": "total_fluoride",
    "reference_type": "AI",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "baseline_values": [
        {
            "life_stage": "0_6_months",
            "sex": "any",
            "type": "AI",
            "value": 0.01,
        },
        {
            "life_stage": "7_12_months",
            "sex": "any",
            "type": "AI",
            "value": 0.5,
        },
        {
            "life_stage": "1_3_years",
            "sex": "any",
            "type": "AI",
            "value": 0.7,
        },
        {
            "life_stage": "4_8_years",
            "sex": "any",
            "type": "AI",
            "value": 1.0,
        },
        {
            "life_stage": "9_13_years",
            "sex": "any",
            "type": "AI",
            "value": 2.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "male",
            "type": "AI",
            "value": 3.0,
        },
        {
            "life_stage": "14_18_years",
            "sex": "female",
            "type": "AI",
            "value": 3.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "AI",
            "value": 4.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "AI",
            "value": 3.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "AI",
            "value": 4.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "AI",
            "value": 3.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "AI",
            "value": 4.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "AI",
            "value": 3.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "AI",
            "value": 4.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "AI",
            "value": 3.0,
        },
    ],

    "pregnancy": {
        "type": "AI",
        "value": 3.0,
    },

    "lactation": {
        "type": "AI",
        "value": 3.0,
    },

    "clinical_overrides": {
        "water_fluoride_unknown": {
            "override_type": "measurement_warning",
            "automatic_target": None,
            "message": (
                "Fluoride exposure may come primarily from "
                "drinking water rather than food. Meal-only "
                "analysis can substantially underestimate "
                "total fluoride exposure."
            ),
        },
    },

    "ul_by_life_stage": [
        {
            "life_stage": "0_6_months",
            "value": 0.7,
        },
        {
            "life_stage": "7_12_months",
            "value": 0.9,
        },
        {
            "life_stage": "1_3_years",
            "value": 1.3,
        },
        {
            "life_stage": "4_8_years",
            "value": 2.2,
        },
        {
            "life_stage": "9_13_years",
            "value": 10.0,
        },
        {
            "life_stage": "14_18_years",
            "value": 10.0,
        },
        {
            "life_stage": "19_30_years",
            "value": 10.0,
        },
        {
            "life_stage": "31_50_years",
            "value": 10.0,
        },
        {
            "life_stage": "51_70_years",
            "value": 10.0,
        },
        {
            "life_stage": "71_plus_years",
            "value": 10.0,
        },
    ],

    "ul": {
        "adult_value": 10.0,
        "unit": "mg/day",
        "applies_to": "all_sources",
        "source_type": (
            "food_water_supplements_and_dental_sources"
        ),
    },

    "evidence_quality": (
        EVIDENCE_AUTHORITATIVE_DRI
    ),

    "priority_tier": 3,
}


# =========================================================================
# ESSENTIAL FATTY ACIDS
# =========================================================================
#
# The supplied reference provides adult, pregnancy, and lactation AI values
# for linoleic acid (LA) and alpha-linolenic acid (ALA). Pediatric rows remain
# incomplete, so the resolver must not extrapolate adult values to children.
# =========================================================================

LINOLEIC_ACID_TARGET: Final[Dict[str, Any]] = {
    "nutrient_key": "linoleic_acid_g",
    "official_name": "Linoleic acid",
    "canonical_unit": "g/day",
    "measurement_basis": "18_2_n_6",
    "reference_type": "AI",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "accepted_input_keys": [
        "linoleic_acid_g",
        "18_2_n_6_g",
    ],

    "baseline_values": [
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "AI",
            "value": 17.0,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "AI",
            "value": 12.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "AI",
            "value": 17.0,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "AI",
            "value": 12.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "AI",
            "value": 14.0,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "AI",
            "value": 11.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "AI",
            "value": 14.0,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "AI",
            "value": 11.0,
        },
    ],

    "pregnancy": {"type": "AI", "value": 13.0},
    "lactation": {"type": "AI", "value": 13.0},

    "clinical_overrides": {
        "vegetarian_or_vegan": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The supplied evidence does not define a "
                "different linoleic-acid AI for vegetarian "
                "or vegan users."
            ),
        },
    },

    "ul": None,
    "ul_source_type": None,

    "coverage_status": "source_data_incomplete",

    "missing_source_rows": [
        "0_6_months",
        "7_12_months",
        "1_3_years",
        "4_8_years",
        "9_13_years",
        "14_18_years",
    ],
}


ALPHA_LINOLENIC_ACID_TARGET: Final[
    Dict[str, Any]
] = {
    "nutrient_key": "alpha_linolenic_acid_g",
    "official_name": "Alpha-linolenic acid",
    "canonical_unit": "g/day",
    "measurement_basis": "18_3_n_3",
    "reference_type": "AI",
    "source": SOURCE_NASEM_GENERAL_DRI,

    "accepted_input_keys": [
        "alpha_linolenic_acid_g",
        "ala_g",
        "18_3_n_3_g",
    ],

    "baseline_values": [
        {
            "life_stage": "19_30_years",
            "sex": "male",
            "type": "AI",
            "value": 1.6,
        },
        {
            "life_stage": "19_30_years",
            "sex": "female",
            "type": "AI",
            "value": 1.1,
        },
        {
            "life_stage": "31_50_years",
            "sex": "male",
            "type": "AI",
            "value": 1.6,
        },
        {
            "life_stage": "31_50_years",
            "sex": "female",
            "type": "AI",
            "value": 1.1,
        },
        {
            "life_stage": "51_70_years",
            "sex": "male",
            "type": "AI",
            "value": 1.6,
        },
        {
            "life_stage": "51_70_years",
            "sex": "female",
            "type": "AI",
            "value": 1.1,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "male",
            "type": "AI",
            "value": 1.6,
        },
        {
            "life_stage": "71_plus_years",
            "sex": "female",
            "type": "AI",
            "value": 1.1,
        },
    ],

    "pregnancy": {"type": "AI", "value": 1.4},
    "lactation": {"type": "AI", "value": 1.3},

    "clinical_overrides": {
        "vegetarian_or_vegan": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "The supplied evidence does not define a "
                "different alpha-linolenic-acid AI for "
                "vegetarian or vegan users."
            ),
        },

        "low_long_chain_omega_3_intake": {
            "override_type": "risk_flag_only",
            "automatic_target": None,
            "message": (
                "Low EPA and DHA intake may increase the "
                "importance of omega-3 food-source review, "
                "but it does not automatically change the "
                "stored ALA AI."
            ),
        },
    },

    "ul": None,
    "ul_source_type": None,

    "coverage_status": "source_data_incomplete",

    "missing_source_rows": [
        "0_6_months",
        "7_12_months",
        "1_3_years",
        "4_8_years",
        "9_13_years",
        "14_18_years",
    ],
}


# =========================================================================
# DIET-PATTERN RISK FLAGS
# =========================================================================

DIET_PATTERN_RISK_FLAGS: Final[
    Dict[str, Dict[str, Any]]
] = {
    "vegetarian": {
        "id": "vegetarian_nutrient_risk",
        "type": "risk_flag_only",
        "affected_nutrients": [
            "iron_mg",
            "zinc_mg",
            "iodine_ug",
            "vitamin_b12_ug",
            "vitamin_d_ug",
            "choline_mg",
            "selenium_ug",
            "alpha_linolenic_acid_g",
        ],
        "automatic_target_changes": {},
        "message": (
            "Official baseline targets generally remain "
            "unchanged, but intake or absorption risk may "
            "be higher for the listed nutrients."
        ),
    },

    "vegan": {
        "id": "vegan_nutrient_risk",
        "type": "risk_flag_only",
        "affected_nutrients": [
            "vitamin_b12_ug",
            "iron_mg",
            "zinc_mg",
            "iodine_ug",
            "calcium_mg",
            "vitamin_d_ug",
            "choline_mg",
            "selenium_ug",
            "alpha_linolenic_acid_g",
        ],
        "automatic_target_changes": {},
        "message": (
            "Official baseline targets generally remain "
            "unchanged, but reliable fortified-food, "
            "supplement, and food-source planning may be "
            "required."
        ),
    },

    "low_carb": {
        "id": "low_carb_pattern",
        "type": "diet_pattern_choice",
        "affected_nutrients": [
            "carbohydrate_g",
            "fiber_g",
            "fat_g",
        ],
        "automatic_target_changes": {},
        "message": (
            "A low-carbohydrate plan must not overwrite "
            "the baseline DRI unless a separate configured "
            "diet plan is active."
        ),
    },

    "ketogenic": {
        "id": "ketogenic_pattern",
        "type": "diet_pattern_choice",
        "affected_nutrients": [
            "carbohydrate_g",
            "fiber_g",
            "fat_g",
            "saturated_fat_g",
        ],
        "automatic_target_changes": {},
        "message": (
            "Ketogenic targets are therapeutic or "
            "preference-based planning values, not "
            "replacement DRIs."
        ),
    },
}


# =========================================================================
# MEDICATION RISK FLAGS
# =========================================================================

MEDICATION_RISK_FLAGS: Final[
    Dict[str, Dict[str, Any]]
] = {
    "metformin": {
        "id": "metformin_b12_risk",
        "type": "risk_flag_only",
        "affected_nutrients": [
            "vitamin_b12_ug",
        ],
        "automatic_target_changes": {},
        "required_clinical_inputs": [
            "serum_vitamin_b12",
            "methylmalonic_acid",
        ],
        "message": (
            "Metformin may increase vitamin B12 "
            "deficiency risk. Do not automatically "
            "increase the RDA."
        ),
    },

    "ppi": {
        "id": "ppi_absorption_risk",
        "type": "risk_flag_only",
        "affected_nutrients": [
            "vitamin_b12_ug",
            "magnesium_mg",
            "iron_mg",
            "calcium_mg",
        ],
        "automatic_target_changes": {},
        "message": (
            "Long-term proton-pump-inhibitor use may "
            "increase deficiency or absorption risk."
        ),
    },

    "warfarin": {
        "id": "warfarin_vitamin_k_consistency",
        "type": "interaction_flag",
        "affected_nutrients": [
            "vitamin_k_ug",
        ],
        "automatic_target_changes": {},
        "message": (
            "Vitamin K intake should remain consistent. "
            "Do not automatically lower the vitamin K AI."
        ),
    },

    "loop_diuretic": {
        "id": "loop_diuretic_mineral_loss",
        "type": "risk_flag_only",
        "affected_nutrients": [
            "potassium_mg",
            "magnesium_mg",
            "calcium_mg",
        ],
        "automatic_target_changes": {},
        "required_clinical_inputs": [
            "serum_potassium",
            "serum_magnesium",
            "serum_calcium",
        ],
        "message": (
            "Electrolyte targets depend on the medication, "
            "dose, laboratory values, and clinical context."
        ),
    },

    "thiazide_diuretic": {
        "id": "thiazide_electrolyte_risk",
        "type": "risk_flag_only",
        "affected_nutrients": [
            "sodium_mg",
            "potassium_mg",
            "magnesium_mg",
            "calcium_mg",
        ],
        "automatic_target_changes": {},
        "required_clinical_inputs": [
            "serum_sodium",
            "serum_potassium",
            "serum_magnesium",
            "serum_calcium",
        ],
        "message": (
            "Electrolyte planning must account for "
            "laboratory values and clinical monitoring."
        ),
    },

    "raas_inhibitor": {
        "id": "raas_potassium_risk",
        "type": "risk_flag_only",
        "affected_nutrients": [
            "potassium_mg",
        ],
        "automatic_target_changes": {},
        "required_clinical_inputs": [
            "serum_potassium",
            "kidney_function",
        ],
        "message": (
            "RAAS-inhibitor therapy may increase "
            "hyperkalemia risk. Do not apply the general "
            "potassium AI as an unrestricted target when "
            "clinical risk is present."
        ),
    },

    "potassium_sparing_diuretic": {
        "id": "potassium_sparing_hyperkalemia_risk",
        "type": "risk_flag_only",
        "affected_nutrients": [
            "potassium_mg",
        ],
        "automatic_target_changes": {},
        "required_clinical_inputs": [
            "serum_potassium",
            "kidney_function",
        ],
        "message": (
            "Potassium intake may require individual "
            "management because of hyperkalemia risk."
        ),
    },
}


# =========================================================================
# CONDITION RISK AND OVERRIDE INDEX
# =========================================================================

CONDITION_TARGET_POLICY: Final[
    Dict[str, Dict[str, Any]]
] = {
    "hypertension": {
        "true_overrides": [
            "sodium_mg",
        ],
        "emphasis_only": [
            "potassium_mg",
            "magnesium_mg",
            "calcium_mg",
            "fiber_g",
        ],
        "requires_clinical_input": [],
    },

    "chronic_kidney_disease": {
        "true_overrides": [],
        "emphasis_only": [],
        "requires_clinical_input": [
            "protein_g",
            "sodium_mg",
            "potassium_mg",
            "phosphorus_mg",
            "calcium_mg",
            "magnesium_mg",
        ],
    },

    "dialysis": {
        "true_overrides": [],
        "emphasis_only": [],
        "requires_clinical_input": [
            "protein_g",
            "sodium_mg",
            "potassium_mg",
            "phosphorus_mg",
            "calcium_mg",
            "magnesium_mg",
            "fluid_ml",
        ],
    },

    "osteoporosis": {
        "true_overrides": [],
        "emphasis_only": [
            "calcium_mg",
            "vitamin_d_ug",
            "protein_g",
            "vitamin_k_ug",
        ],
        "requires_clinical_input": [],
    },

    "iron_deficiency": {
        "true_overrides": [],
        "emphasis_only": [],
        "requires_clinical_input": [
            "iron_mg",
        ],
    },

    "ibs": {
        "true_overrides": [],
        "emphasis_only": [],
        "requires_clinical_input": [],
        "risk_flags": [
            "fiber_type_and_tolerance",
        ],
    },

    "ibd": {
        "true_overrides": [],
        "emphasis_only": [],
        "requires_clinical_input": [],
        "risk_flags": [
            "disease_activity_and_fiber_tolerance",
        ],
    },
}


# =========================================================================
# CANONICAL KEY COMPATIBILITY
# =========================================================================

CANONICAL_KEY_COMPATIBILITY: Final[
    Dict[str, Dict[str, Any]]
] = {
    "energy_kcal": {
        "preferred_canonical_key": "energy_kcal",
        "accepted_input_keys": [
            "energy_kcal",
            "calories",
            "calories_kcal",
        ],
        "measurement_basis": "kcal",
        "conversion_required": False,
    },

    "protein_g": {
        "preferred_canonical_key": "protein_g",
        "accepted_input_keys": [
            "protein_g",
            "protein",
        ],
        "measurement_basis": "g",
        "conversion_required": False,
    },

    "carbohydrate_g": {
        "preferred_canonical_key": "carbohydrate_g",
        "accepted_input_keys": [
            "carbohydrate_g",
            "carbohydrates_g",
            "carbs_g",
            "carbs",
        ],
        "measurement_basis": "g",
        "conversion_required": False,
    },

    "fat_g": {
        "preferred_canonical_key": "fat_g",
        "accepted_input_keys": [
            "fat_g",
            "total_fat_g",
            "fat",
        ],
        "measurement_basis": "g",
        "conversion_required": False,
    },

    "saturated_fat_g": {
        "preferred_canonical_key": "saturated_fat_g",
        "accepted_input_keys": [
            "saturated_fat_g",
            "saturated_fat",
        ],
        "measurement_basis": "g",
        "conversion_required": False,
    },

    "trans_fat_g": {
        "preferred_canonical_key": "trans_fat_g",
        "accepted_input_keys": [
            "trans_fat_g",
            "trans_fat",
        ],
        "measurement_basis": "g",
        "conversion_required": False,
    },

    "fiber_g": {
        "preferred_canonical_key": "fiber_g",
        "accepted_input_keys": [
            "fiber_g",
            "fibre_g",
            "dietary_fiber_g",
        ],
        "measurement_basis": "g",
        "conversion_required": False,
    },

    "linoleic_acid_g": {
        "preferred_canonical_key": "linoleic_acid_g",
        "accepted_input_keys": [
            "linoleic_acid_g",
            "18_2_n_6_g",
        ],
        "measurement_basis": "g",
        "conversion_required": False,
    },

    "alpha_linolenic_acid_g": {
        "preferred_canonical_key": (
            "alpha_linolenic_acid_g"
        ),
        "accepted_input_keys": [
            "alpha_linolenic_acid_g",
            "ala_g",
            "18_3_n_3_g",
        ],
        "measurement_basis": "g",
        "conversion_required": False,
    },

    "vitamin_a_ug": {
        "preferred_canonical_key": (
            "vitamin_a_ug_rae"
        ),
        "accepted_input_keys": [
            "vitamin_a_ug_rae",
            "vitamin_a_ug",
        ],
        "measurement_basis": "RAE",
        "conversion_required": True,
        "unsafe_legacy_assumption": (
            "Do not assume generic vitamin_a_ug is "
            "already expressed as RAE."
        ),
    },

    "vitamin_c_mg": {
        "preferred_canonical_key": "vitamin_c_mg",
        "accepted_input_keys": [
            "vitamin_c_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "vitamin_d_ug": {
        "preferred_canonical_key": "vitamin_d_ug",
        "accepted_input_keys": [
            "vitamin_d_ug",
            "vitamin_d_mcg",
            "vitamin_d_iu",
        ],
        "measurement_basis": "ug",
        "conversion_required": True,
        "conversion_rules": {
            "vitamin_d_iu_to_ug": 0.025,
        },
    },

    "vitamin_e_mg": {
        "preferred_canonical_key": (
            "vitamin_e_mg_alpha_tocopherol"
        ),
        "accepted_input_keys": [
            "vitamin_e_mg_alpha_tocopherol",
            "alpha_tocopherol_mg",
            "vitamin_e_mg",
        ],
        "measurement_basis": "alpha_tocopherol",
        "conversion_required": True,
    },

    "vitamin_k_ug": {
        "preferred_canonical_key": "vitamin_k_ug",
        "accepted_input_keys": [
            "vitamin_k_ug",
            "vitamin_k_mcg",
        ],
        "measurement_basis": "ug",
        "conversion_required": False,
    },

    "thiamin_mg": {
        "preferred_canonical_key": "thiamin_mg",
        "accepted_input_keys": [
            "thiamin_mg",
            "vitamin_b1_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "riboflavin_mg": {
        "preferred_canonical_key": "riboflavin_mg",
        "accepted_input_keys": [
            "riboflavin_mg",
            "vitamin_b2_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "niacin_mg": {
        "preferred_canonical_key": "niacin_mg_ne",
        "accepted_input_keys": [
            "niacin_mg_ne",
            "niacin_mg",
        ],
        "measurement_basis": "NE",
        "conversion_required": True,
    },

    "pantothenic_acid_mg": {
        "preferred_canonical_key": (
            "pantothenic_acid_mg"
        ),
        "accepted_input_keys": [
            "pantothenic_acid_mg",
            "vitamin_b5_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "vitamin_b6_mg": {
        "preferred_canonical_key": "vitamin_b6_mg",
        "accepted_input_keys": [
            "vitamin_b6_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "folate_ug": {
        "preferred_canonical_key": "folate_ug_dfe",
        "accepted_input_keys": [
            "folate_ug_dfe",
            "folate_ug",
        ],
        "measurement_basis": "DFE",
        "conversion_required": True,
        "unsafe_legacy_assumption": (
            "Do not equate naturally occurring food "
            "folate with folic acid."
        ),
    },

    "vitamin_b12_ug": {
        "preferred_canonical_key": "vitamin_b12_ug",
        "accepted_input_keys": [
            "vitamin_b12_ug",
            "vitamin_b12_mcg",
        ],
        "measurement_basis": "ug",
        "conversion_required": False,
    },

    "choline_mg": {
        "preferred_canonical_key": "choline_mg",
        "accepted_input_keys": [
            "choline_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "calcium_mg": {
        "preferred_canonical_key": "calcium_mg",
        "accepted_input_keys": [
            "calcium_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "iron_mg": {
        "preferred_canonical_key": "iron_mg",
        "accepted_input_keys": [
            "iron_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "magnesium_mg": {
        "preferred_canonical_key": "magnesium_mg",
        "accepted_input_keys": [
            "magnesium_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "phosphorus_mg": {
        "preferred_canonical_key": "phosphorus_mg",
        "accepted_input_keys": [
            "phosphorus_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "potassium_mg": {
        "preferred_canonical_key": "potassium_mg",
        "accepted_input_keys": [
            "potassium_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "sodium_mg": {
        "preferred_canonical_key": "sodium_mg",
        "accepted_input_keys": [
            "sodium_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "zinc_mg": {
        "preferred_canonical_key": "zinc_mg",
        "accepted_input_keys": [
            "zinc_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "copper_mg": {
        "preferred_canonical_key": "copper_mg",
        "accepted_input_keys": [
            "copper_mg",
            "copper_ug",
            "copper_mcg",
        ],
        "measurement_basis": "mg",
        "conversion_required": True,
        "conversion_rules": {
            "ug_to_mg": 0.001,
            "mcg_to_mg": 0.001,
        },
    },

    "manganese_mg": {
        "preferred_canonical_key": "manganese_mg",
        "accepted_input_keys": [
            "manganese_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },

    "selenium_ug": {
        "preferred_canonical_key": "selenium_ug",
        "accepted_input_keys": [
            "selenium_ug",
            "selenium_mcg",
        ],
        "measurement_basis": "ug",
        "conversion_required": False,
    },

    "iodine_ug": {
        "preferred_canonical_key": "iodine_ug",
        "accepted_input_keys": [
            "iodine_ug",
            "iodine_mcg",
        ],
        "measurement_basis": "ug",
        "conversion_required": False,
    },

    "chromium_ug": {
        "preferred_canonical_key": "chromium_ug",
        "accepted_input_keys": [
            "chromium_ug",
            "chromium_mcg",
        ],
        "measurement_basis": "ug",
        "conversion_required": False,
    },

    "molybdenum_ug": {
        "preferred_canonical_key": "molybdenum_ug",
        "accepted_input_keys": [
            "molybdenum_ug",
            "molybdenum_mcg",
        ],
        "measurement_basis": "ug",
        "conversion_required": False,
    },

    "fluoride_mg": {
        "preferred_canonical_key": "fluoride_mg",
        "accepted_input_keys": [
            "fluoride_mg",
        ],
        "measurement_basis": "mg",
        "conversion_required": False,
    },
}


# =========================================================================
# OVERRIDE PRECEDENCE
# =========================================================================

TARGET_OVERRIDE_PRECEDENCE: Final[
    tuple[str, ...]
] = (
    "pregnancy",
    "lactation",
    "infancy_childhood_adolescence",
    "dialysis",
    "advanced_ckd",
    "earlier_ckd",
    "major_disease_guideline",
    "medication_safety_interaction",
    "age_sex_baseline_dri",
    "activity_training",
    "goal_based",
    "diet_pattern",
    "anthropometrics_and_appetite",
)


# =========================================================================
# MASTER TARGET REGISTRY
# =========================================================================

NUTRIENT_TARGET_REGISTRY: Final[
    Dict[str, Dict[str, Any]]
] = {
    "protein_g": PROTEIN_TARGET,
    "carbohydrate_g": CARBOHYDRATE_TARGET,
    "fat_g": TOTAL_FAT_TARGET,
    "saturated_fat_g": SATURATED_FAT_TARGET,
    "trans_fat_g": TRANS_FAT_TARGET,
    "fiber_g": FIBER_TARGET,
    "linoleic_acid_g": LINOLEIC_ACID_TARGET,
    "alpha_linolenic_acid_g": (
        ALPHA_LINOLENIC_ACID_TARGET
    ),

    "vitamin_a_ug": VITAMIN_A_TARGET,
    "vitamin_c_mg": VITAMIN_C_TARGET,
    "vitamin_d_ug": VITAMIN_D_TARGET,
    "vitamin_e_mg": VITAMIN_E_TARGET,
    "vitamin_k_ug": VITAMIN_K_TARGET,

    "thiamin_mg": THIAMIN_TARGET,
    "riboflavin_mg": RIBOFLAVIN_TARGET,
    "niacin_mg": NIACIN_TARGET,
    "pantothenic_acid_mg": (
        PANTOTHENIC_ACID_TARGET
    ),
    "vitamin_b6_mg": VITAMIN_B6_TARGET,
    "folate_ug": FOLATE_TARGET,
    "vitamin_b12_ug": VITAMIN_B12_TARGET,
    "choline_mg": CHOLINE_TARGET,

    "calcium_mg": CALCIUM_TARGET,
    "iron_mg": IRON_TARGET,
    "magnesium_mg": MAGNESIUM_TARGET,
    "phosphorus_mg": PHOSPHORUS_TARGET,
    "potassium_mg": POTASSIUM_TARGET,
    "sodium_mg": SODIUM_TARGET,
    "zinc_mg": ZINC_TARGET,
    "copper_mg": COPPER_TARGET,
    "manganese_mg": MANGANESE_TARGET,
    "selenium_ug": SELENIUM_TARGET,
    "iodine_ug": IODINE_TARGET,
    "chromium_ug": CHROMIUM_TARGET,
    "molybdenum_ug": MOLYBDENUM_TARGET,
    "fluoride_mg": FLUORIDE_TARGET,
}


# =========================================================================
# REGISTRY COVERAGE
# =========================================================================

FULL_LIFE_STAGE_TARGET_KEYS: Final[
    tuple[str, ...]
] = tuple(
    key
    for key, definition
    in NUTRIENT_TARGET_REGISTRY.items()
    if definition.get(
        "coverage_status",
        "complete",
    ) == "complete"
)


PARTIAL_SOURCE_TARGET_KEYS: Final[
    tuple[str, ...]
] = tuple(
    key
    for key, definition
    in NUTRIENT_TARGET_REGISTRY.items()
    if definition.get(
        "coverage_status"
    ) == "source_data_incomplete"
)


TARGET_DATA_COVERAGE: Final[
    Dict[str, Any]
] = {
    "schema_version": NUTRIENT_SCHEMA_VERSION,
    "target_data_version": TARGET_DATA_VERSION,

    "registered_target_count": len(
        NUTRIENT_TARGET_REGISTRY
    ),

    "fully_life_stage_resolved_keys": (
        FULL_LIFE_STAGE_TARGET_KEYS
    ),

    "partial_source_keys": (
        PARTIAL_SOURCE_TARGET_KEYS
    ),

    "partial_source_reason": {
        "linoleic_acid_g": (
            "The supplied research contains adult "
            "summary values but not the complete "
            "life-stage lookup table."
        ),
        "alpha_linolenic_acid_g": (
            "The supplied research contains adult "
            "summary values but not the complete "
            "life-stage lookup table."
        ),
    },

    "contains_eer_registry": True,

    "contains_diet_risk_flags": True,

    "contains_medication_risk_flags": True,

    "contains_condition_policy": True,

    "contains_canonical_compatibility": True,

    "production_blockers": [
        "Complete source-backed life-stage tables "
        "for linoleic_acid_g.",
        "Complete source-backed life-stage tables "
        "for alpha_linolenic_acid_g.",
    ],
}


# =========================================================================
# DATA VALIDATION
# =========================================================================

def validate_target_registry() -> None:
    """
    Validate static registry integrity.

    This checks structure and key consistency. It does not independently
    prove that a scientific value is correct; scientific provenance is
    stored in each target definition.
    """
    expected_keys = set(
        NUTRIENT_TARGET_REGISTRY
    )

    compatibility_keys = set(
        CANONICAL_KEY_COMPATIBILITY
    )

    missing_compatibility = (
        expected_keys - compatibility_keys
    )

    if missing_compatibility:
        raise ValueError(
            "Missing canonical compatibility "
            "definitions for: "
            f"{sorted(missing_compatibility)}"
        )

    for key, definition in (
        NUTRIENT_TARGET_REGISTRY.items()
    ):
        declared_key = definition.get(
            "nutrient_key"
        )

        if declared_key != key:
            raise ValueError(
                "Registry key mismatch: "
                f"{key!r} declares "
                f"{declared_key!r}."
            )

        if not definition.get(
            "official_name"
        ):
            raise ValueError(
                f"{key!r} has no official_name."
            )

        if not definition.get(
            "canonical_unit"
        ):
            raise ValueError(
                f"{key!r} has no canonical_unit."
            )

        if not definition.get(
            "reference_type"
        ):
            raise ValueError(
                f"{key!r} has no reference_type."
            )

        baseline_values = definition.get(
            "baseline_values"
        )

        amdr_values = definition.get(
            "amdr_values"
        )

        baseline_limit = definition.get(
            "baseline_limit"
        )

        if (
            not baseline_values
            and not amdr_values
            and not baseline_limit
        ):
            raise ValueError(
                f"{key!r} has no baseline "
                "value, AMDR, or limit."
            )

        if (
            definition.get(
                "coverage_status"
            )
            == "source_data_incomplete"
            and not definition.get(
                "missing_source_rows"
            )
        ):
            raise ValueError(
                f"{key!r} is marked partial "
                "without missing_source_rows."
            )

    life_stage_names = set(
        LIFE_STAGE_BANDS
    )

    for key, definition in (
        NUTRIENT_TARGET_REGISTRY.items()
    ):
        for field_name in (
            "baseline_values",
            "ul_by_life_stage",
            "pregnancy_by_life_stage",
            "lactation_by_life_stage",
            "amdr_values",
        ):
            rows = definition.get(
                field_name,
                [],
            )

            if not isinstance(rows, list):
                continue

            for row in rows:
                life_stage = row.get(
                    "life_stage"
                )

                if (
                    life_stage is not None
                    and life_stage
                    not in life_stage_names
                ):
                    raise ValueError(
                        f"{key!r}.{field_name} "
                        "contains unknown "
                        f"life stage {life_stage!r}."
                    )


validate_target_registry()
