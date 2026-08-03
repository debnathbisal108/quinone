from __future__ import annotations

TARGET_ENGINE_VERSION = "1.0.0"

EVIDENCE_AUTHORITATIVE_DRI = "authoritative_dri"
EVIDENCE_STRONG_GUIDELINE = "strong_guideline"
EVIDENCE_CONDITIONAL_GUIDELINE = "conditional_guideline"

NASEM_ENERGY_SOURCE = {
    "organization": "National Academies of Sciences, Engineering, and Medicine",
    "document_title": "Dietary Reference Intakes for Energy",
    "publication_year": 2023,
    "recommendation_or_table": "Table S-1 and chapter equations",
    "source_url": "https://nap.nationalacademies.org/read/26859/chapter/11",
    "doi": None,
}

NASEM_SODIUM_POTASSIUM_SOURCE = {
    "organization": "National Academies of Sciences, Engineering, and Medicine",
    "document_title": "Dietary Reference Intakes for Sodium and Potassium",
    "publication_year": 2019,
    "recommendation_or_table": "Appendix J; sodium AI/CDRR and potassium AI tables",
    "source_url": "https://nap.nationalacademies.org/read/25353/chapter/18",
    "doi": "10.17226/25353",
}

NASEM_GENERAL_DRI_SOURCE = {
    "organization": "National Academies / NIH Office of Dietary Supplements",
    "document_title": "Dietary Reference Intakes summary tables",
    "publication_year": 2005,
    "recommendation_or_table": "Age, sex, pregnancy, and lactation DRI tables",
    "source_url": None,
    "doi": None,
}

NASEM_CALCIUM_VITAMIN_D_SOURCE = {
    "organization": "National Academies / NIH Office of Dietary Supplements",
    "document_title": "Dietary Reference Intakes for Calcium and Vitamin D",
    "publication_year": 2011,
    "recommendation_or_table": "Calcium and vitamin D DRI tables",
    "source_url": "https://nap.nationalacademies.org/catalog/13050",
    "doi": None,
}

ADULT_PA_COEFFICIENTS = {
    "male": {"sedentary": 1.00, "low_active": 1.11, "active": 1.25, "very_active": 1.48},
    "female": {"sedentary": 1.00, "low_active": 1.12, "active": 1.27, "very_active": 1.45},
}

ADULT_BASELINES = {
    "protein_g": {"name": "Protein", "unit": "g/day", "reference_type": "RDA", "male": 56.0, "female": 46.0, "pregnancy": 71.0, "lactation": 71.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "carbohydrate_g": {"name": "Carbohydrate", "unit": "g/day", "reference_type": "RDA", "male": 130.0, "female": 130.0, "pregnancy": 175.0, "lactation": 210.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "fiber_g": {"name": "Dietary fiber", "unit": "g/day", "reference_type": "AI", "male_19_50": 38.0, "female_19_50": 25.0, "male_51_plus": 30.0, "female_51_plus": 21.0, "pregnancy": 28.0, "lactation": 29.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "vitamin_a_ug": {"name": "Vitamin A", "unit": "ug RAE/day", "reference_type": "RDA", "male": 900.0, "female": 700.0, "pregnancy": 770.0, "lactation": 1300.0, "ul": 3000.0, "measurement_basis": "RAE", "source": NASEM_GENERAL_DRI_SOURCE},
    "vitamin_c_mg": {"name": "Vitamin C", "unit": "mg/day", "reference_type": "RDA", "male": 90.0, "female": 75.0, "pregnancy": 85.0, "lactation": 120.0, "ul": 2000.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "vitamin_d_ug": {"name": "Vitamin D", "unit": "ug/day", "reference_type": "RDA", "adult_19_70": 15.0, "adult_71_plus": 20.0, "pregnancy": 15.0, "lactation": 15.0, "ul": 100.0, "source": NASEM_CALCIUM_VITAMIN_D_SOURCE},
    "vitamin_e_mg": {"name": "Vitamin E", "unit": "mg alpha-tocopherol/day", "reference_type": "RDA", "male": 15.0, "female": 15.0, "pregnancy": 15.0, "lactation": 19.0, "ul": 1000.0, "measurement_basis": "alpha_tocopherol", "source": NASEM_GENERAL_DRI_SOURCE},
    "vitamin_k_ug": {"name": "Vitamin K", "unit": "ug/day", "reference_type": "AI", "male": 120.0, "female": 90.0, "pregnancy": 90.0, "lactation": 90.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "thiamin_mg": {"name": "Thiamin", "unit": "mg/day", "reference_type": "RDA", "male": 1.2, "female": 1.1, "pregnancy": 1.4, "lactation": 1.4, "source": NASEM_GENERAL_DRI_SOURCE},
    "riboflavin_mg": {"name": "Riboflavin", "unit": "mg/day", "reference_type": "RDA", "male": 1.3, "female": 1.1, "pregnancy": 1.4, "lactation": 1.6, "source": NASEM_GENERAL_DRI_SOURCE},
    "niacin_mg": {"name": "Niacin", "unit": "mg NE/day", "reference_type": "RDA", "male": 16.0, "female": 14.0, "pregnancy": 18.0, "lactation": 17.0, "ul": 35.0, "measurement_basis": "NE", "source": NASEM_GENERAL_DRI_SOURCE},
    "vitamin_b6_mg": {"name": "Vitamin B6", "unit": "mg/day", "reference_type": "RDA", "adult_19_50": 1.3, "male_51_plus": 1.7, "female_51_plus": 1.5, "pregnancy": 1.9, "lactation": 2.0, "ul": 100.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "folate_ug": {"name": "Folate", "unit": "ug DFE/day", "reference_type": "RDA", "male": 400.0, "female": 400.0, "pregnancy": 600.0, "lactation": 500.0, "ul": 1000.0, "measurement_basis": "DFE", "source": NASEM_GENERAL_DRI_SOURCE},
    "vitamin_b12_ug": {"name": "Vitamin B12", "unit": "ug/day", "reference_type": "RDA", "male": 2.4, "female": 2.4, "pregnancy": 2.6, "lactation": 2.8, "source": NASEM_GENERAL_DRI_SOURCE},
    "choline_mg": {"name": "Choline", "unit": "mg/day", "reference_type": "AI", "male": 550.0, "female": 425.0, "pregnancy": 450.0, "lactation": 550.0, "ul": 3500.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "calcium_mg": {"name": "Calcium", "unit": "mg/day", "reference_type": "RDA", "adult_19_50": 1000.0, "male_51_70": 1000.0, "female_51_70": 1200.0, "adult_71_plus": 1200.0, "pregnancy": 1000.0, "lactation": 1000.0, "source": NASEM_CALCIUM_VITAMIN_D_SOURCE},
    "iron_mg": {"name": "Iron", "unit": "mg/day", "reference_type": "RDA", "male_19_plus": 8.0, "female_19_50": 18.0, "female_51_plus": 8.0, "pregnancy": 27.0, "lactation": 9.0, "ul": 45.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "magnesium_mg": {"name": "Magnesium", "unit": "mg/day", "reference_type": "RDA", "male_19_30": 400.0, "female_19_30": 310.0, "male_31_plus": 420.0, "female_31_plus": 320.0, "pregnancy_19_30": 350.0, "pregnancy_31_plus": 360.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "phosphorus_mg": {"name": "Phosphorus", "unit": "mg/day", "reference_type": "RDA", "male": 700.0, "female": 700.0, "pregnancy": 700.0, "lactation": 700.0, "ul": 4000.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "potassium_mg": {"name": "Potassium", "unit": "mg/day", "reference_type": "AI", "male": 3400.0, "female": 2600.0, "pregnancy": 2900.0, "lactation": 2800.0, "source": NASEM_SODIUM_POTASSIUM_SOURCE},
    "sodium_mg": {"name": "Sodium", "unit": "mg/day", "reference_type": "AI", "male": 1500.0, "female": 1500.0, "pregnancy": 1500.0, "lactation": 1500.0, "cdrr": 2300.0, "source": NASEM_SODIUM_POTASSIUM_SOURCE},
    "zinc_mg": {"name": "Zinc", "unit": "mg/day", "reference_type": "RDA", "male": 11.0, "female": 8.0, "pregnancy": 11.0, "lactation": 12.0, "ul": 40.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "copper_mg": {"name": "Copper", "unit": "mg/day", "reference_type": "RDA", "male": 0.9, "female": 0.9, "pregnancy": 1.0, "lactation": 1.3, "ul": 10.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "manganese_mg": {"name": "Manganese", "unit": "mg/day", "reference_type": "AI", "male": 2.3, "female": 1.8, "pregnancy": 2.0, "lactation": 2.6, "ul": 11.0, "source": NASEM_GENERAL_DRI_SOURCE},
    "selenium_ug": {"name": "Selenium", "unit": "ug/day", "reference_type": "RDA", "male": 55.0, "female": 55.0, "pregnancy": 60.0, "lactation": 70.0, "ul": 400.0, "source": NASEM_GENERAL_DRI_SOURCE},
}

MEASUREMENT_COMPATIBILITY = {
    "vitamin_a_ug": {"required_basis": "RAE", "accepted_input_keys": ["vitamin_a_ug_rae"], "legacy_keys": ["vitamin_a_ug"]},
    "folate_ug": {"required_basis": "DFE", "accepted_input_keys": ["folate_ug_dfe"], "legacy_keys": ["folate_ug"]},
    "niacin_mg": {"required_basis": "NE", "accepted_input_keys": ["niacin_mg_ne"], "legacy_keys": ["niacin_mg"]},
    "vitamin_e_mg": {"required_basis": "alpha_tocopherol", "accepted_input_keys": ["vitamin_e_mg_alpha_tocopherol", "alpha_tocopherol_mg"], "legacy_keys": ["vitamin_e_mg"]},
}

RISK_FLAGS = {
    "vegetarian": {"nutrients": ["vitamin_b12_ug", "iron_mg", "zinc_mg", "iodine_ug", "vitamin_d_ug", "choline_mg"], "message": "Official DRI values are unchanged, but deficiency risk may be higher."},
    "vegan": {"nutrients": ["vitamin_b12_ug", "iron_mg", "zinc_mg", "iodine_ug", "vitamin_d_ug", "choline_mg", "calcium_mg"], "message": "Official DRI values are unchanged, but deficiency risk may be higher."},
    "smoker": {"nutrients": ["vitamin_c_mg"], "message": "Vitamin C requirement increases by 35 mg/day."},
    "metformin": {"nutrients": ["vitamin_b12_ug"], "message": "Metformin use increases vitamin B12 deficiency risk."},
    "ppi": {"nutrients": ["vitamin_b12_ug", "magnesium_mg", "iron_mg", "calcium_mg"], "message": "Long-term acid suppression may increase deficiency risk."},
    "warfarin": {"nutrients": ["vitamin_k_ug"], "message": "Vitamin K intake should remain consistent; the biological target is not automatically reduced."},
}
