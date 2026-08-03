"""
Nutrica Feature Engineering
============================

Pure feature-engineering phase for already-resolved and already-enriched
Nutrica meal JSON. No API calls, caching, interpolation, or orchestration.
Missing values remain None.
"""

from __future__ import annotations

import copy
import logging
import math
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("nutrica.feature_engineering")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(os.environ.get("NUTRICA_LOG_LEVEL", "INFO"))
logger.propagate = False

FEATURE_VERSION = "1.1"
_ROUND_DP = 6
_VALID_ENTITY_TYPES = {"food", "ingredient", "spice"}
_GRAM_UNITS = {"g", "gram", "grams"}


def _to_valid_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _to_valid_fraction(value: Any) -> Optional[float]:
    number = _to_valid_float(value)
    if number is None or number > 1:
        return None
    return number


def _build_raw_index(all_nutrients: List[Dict[str, Any]]) -> Tuple[Dict[str, float], Dict[str, float]]:
    by_number: Dict[str, float] = {}
    by_name: Dict[str, float] = {}
    for item in all_nutrients or []:
        if not isinstance(item, dict):
            continue
        amount = _to_valid_float(item.get("amount"))
        if amount is None:
            continue
        number = str(item.get("number") or "").strip()
        name = str(item.get("name") or "").strip().lower()
        if number and number not in by_number:
            by_number[number] = amount
        if name and name not in by_name:
            by_name[name] = amount
    return by_number, by_name


def get_raw_nutrient(
    raw_index: Tuple[Dict[str, float], Dict[str, float]],
    numbers: Iterable[str] = (),
    names: Iterable[str] = (),
) -> Optional[float]:
    by_number, by_name = raw_index
    for number in numbers:
        key = str(number).strip()
        if key in by_number:
            return by_number[key]
    for name in names:
        key = str(name).strip().lower()
        if key in by_name:
            return by_name[key]
    return None


def get_nutrient(
    nutrients: Dict[str, Optional[float]],
    raw_index: Tuple[Dict[str, float], Dict[str, float]],
    canonical_key: Optional[str] = None,
    numbers: Iterable[str] = (),
    names: Iterable[str] = (),
) -> Optional[float]:
    if canonical_key is not None:
        value = _to_valid_float(nutrients.get(canonical_key))
        if value is not None:
            return value
    return get_raw_nutrient(raw_index, numbers=numbers, names=names)


def safe_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round(numerator / denominator, _ROUND_DP)


def safe_density_per_100kcal(amount: Optional[float], energy_kcal: Optional[float]) -> Optional[float]:
    ratio = safe_ratio(amount, energy_kcal)
    return None if ratio is None else round(ratio * 100.0, _ROUND_DP)


_RED_MEAT_KEYWORDS = {"beef", "lamb", "mutton", "pork", "goat", "venison", "veal", "bacon", "ham", "sausage", "steak", "brisket"}
_WHITE_MEAT_KEYWORDS = {"chicken", "turkey", "duck", "poultry", "quail"}
_FISH_KEYWORDS = {"fish", "salmon", "tuna", "cod", "tilapia", "sardine", "mackerel", "trout", "anchovy", "herring", "hilsa", "rohu", "pomfret", "catfish", "halibut", "snapper", "bass"}
_SHELLFISH_KEYWORDS = {"shrimp", "prawn", "crab", "lobster", "oyster", "clam", "mussel", "scallop", "squid", "octopus", "crayfish"}
_EGG_KEYWORDS = {"egg", "eggs", "omelette", "omelet", "egg white", "egg yolk", "frittata"}
_CHEESE_KEYWORDS = {"cheese", "paneer", "mozzarella", "cheddar", "feta", "ricotta", "parmesan"}
_YOGURT_KEYWORDS = {"yogurt", "yoghurt", "curd", "dahi"}
_MILK_KEYWORDS = {"milk", "buttermilk"}
_PLANT_OIL_KEYWORDS = {"sunflower oil", "olive oil", "mustard oil", "canola oil", "soybean oil", "coconut oil", "palm oil", "groundnut oil", "peanut oil", "sesame oil", "corn oil", "rice bran oil", "vegetable oil"}
_ANIMAL_FAT_KEYWORDS = {"ghee", "butter", "lard", "tallow", "schmaltz"}
_OIL_KEYWORDS = _PLANT_OIL_KEYWORDS | _ANIMAL_FAT_KEYWORDS | {"oil", "fat"}
_WHOLE_GRAIN_KEYWORDS = {"whole wheat", "whole grain", "brown rice", "oats", "oatmeal", "quinoa", "millet", "barley", "buckwheat", "whole wheat flour", "atta", "whole meal", "bulgur", "farro"}
_REFINED_GRAIN_KEYWORDS = {"white rice", "refined flour", "maida", "white flour", "all-purpose flour", "refined wheat flour", "white bread", "polished rice"}
_PULSE_EXCLUSION_KEYWORDS = {"green pea", "green peas", "green bean", "green beans", "edamame", "fresh pea", "snap pea", "snow pea", "sprout", "sprouts"}
_ADDED_FAT_KEYWORDS = _OIL_KEYWORDS | {"cream", "margarine", "mayonnaise"}
_ADDED_SUGAR_KEYWORDS = {"sugar", "honey", "jaggery", "syrup", "molasses", "brown sugar", "corn syrup"}
_ADDED_SALT_KEYWORDS = {"salt", "sodium chloride"}


def _text_for_matching(entity: Dict[str, Any]) -> str:
    return " ".join([str(entity.get("name") or ""), str(entity.get("canonical_name") or "")]).strip().lower()


def _contains_keyword(text: str, keyword: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(keyword.lower())}(?!\w)", text.lower()) is not None


def _any_keyword(text: str, keywords: Iterable[str]) -> bool:
    return any(_contains_keyword(text, keyword) for keyword in keywords)


def _build_macronutrients(nutrients, raw_index):
    return {
        "protein_g": get_nutrient(nutrients, raw_index, "protein_g"),
        "fat_g": get_nutrient(nutrients, raw_index, "fat_g"),
        "carbohydrate_g": get_nutrient(nutrients, raw_index, "carbohydrate_g"),
        "fiber_g": get_nutrient(nutrients, raw_index, "fiber_g"),
        "sugars_g": get_nutrient(nutrients, raw_index, "sugars_g"),
        "water_g": get_nutrient(nutrients, raw_index, "water_g"),
        "ash_g": get_nutrient(nutrients, raw_index, "ash_g"),
        "alcohol_g": get_nutrient(nutrients, raw_index, "alcohol_g", numbers=("221",), names=("alcohol, ethyl",)),
        "energy_kcal": get_nutrient(nutrients, raw_index, "energy_kcal"),
    }


def _build_fat_profile(nutrients, raw_index):
    return {
        "saturated_fat_g": get_nutrient(nutrients, raw_index, "saturated_fat_g"),
        "monounsaturated_fat_g": get_nutrient(nutrients, raw_index, "monounsaturated_fat_g"),
        "polyunsaturated_fat_g": get_nutrient(nutrients, raw_index, "polyunsaturated_fat_g"),
        "trans_fat_g": get_nutrient(nutrients, raw_index, "trans_fat_g"),
        "cholesterol_mg": get_nutrient(nutrients, raw_index, "cholesterol_mg"),
        "omega3_g": get_nutrient(nutrients, raw_index, "omega3_g"),
        "omega6_g": get_nutrient(nutrients, raw_index, "omega6_g"),
    }


def _build_vitamins(nutrients, raw_index):
    keys = ["vitamin_a_ug", "vitamin_c_mg", "vitamin_d_ug", "vitamin_e_mg", "vitamin_k_ug", "thiamin_mg", "riboflavin_mg", "niacin_mg", "pantothenic_acid_mg", "vitamin_b6_mg", "folate_ug", "vitamin_b12_ug", "choline_mg"]
    return {key: get_nutrient(nutrients, raw_index, key) for key in keys}


def _build_minerals(nutrients, raw_index):
    keys = ["calcium_mg", "iron_mg", "magnesium_mg", "phosphorus_mg", "potassium_mg", "sodium_mg", "zinc_mg", "copper_mg", "manganese_mg", "selenium_ug"]
    return {key: get_nutrient(nutrients, raw_index, key) for key in keys}


_AMINO_ACID_MATCHERS = {
    "tryptophan_g": (("501",), ("tryptophan",)), "threonine_g": (("502",), ("threonine",)),
    "isoleucine_g": (("503",), ("isoleucine",)), "leucine_g": (("504",), ("leucine",)),
    "lysine_g": (("505",), ("lysine",)), "methionine_g": (("506",), ("methionine",)),
    "cystine_g": (("507",), ("cystine",)), "phenylalanine_g": (("508",), ("phenylalanine",)),
    "tyrosine_g": (("509",), ("tyrosine",)), "valine_g": (("510",), ("valine",)),
    "arginine_g": (("511",), ("arginine",)), "histidine_g": (("512",), ("histidine",)),
    "alanine_g": (("513",), ("alanine",)), "aspartic_acid_g": (("514",), ("aspartic acid",)),
    "glutamic_acid_g": (("515",), ("glutamic acid",)), "glycine_g": (("516",), ("glycine",)),
    "proline_g": (("517",), ("proline",)), "serine_g": (("518",), ("serine",)),
}


def _build_amino_acids(raw_index):
    return {key: get_raw_nutrient(raw_index, numbers=numbers, names=names) for key, (numbers, names) in _AMINO_ACID_MATCHERS.items()}


_FATTY_ACID_MATCHERS = {
    "ala_g": (("851",), ("18:3 n-3", "18:3 n-3 c,c,c", "alpha-linolenic acid")),
    "epa_g": (("629",), ("20:5 n-3", "20:5 n-3 (epa)", "eicosapentaenoic acid")),
    "dha_g": (("621",), ("22:6 n-3", "22:6 n-3 (dha)", "docosahexaenoic acid")),
    "dpa_g": (("631",), ("22:5 n-3", "22:5 n-3 (dpa)", "docosapentaenoic acid")),
    "linoleic_acid_g": (("675",), ("18:2 n-6 c,c", "18:2 n-6", "linoleic acid")),
    "arachidonic_acid_g": ((), ("20:4", "20:4 undifferentiated", "arachidonic acid")),
    "oleic_acid_g": (("617",), ("18:1", "18:1 undifferentiated", "oleic acid")),
    "palmitic_acid_g": ((), ("16:0", "palmitic acid")),
    "stearic_acid_g": ((), ("18:0", "stearic acid")),
    "cla_g": (("670",), ("18:2 conjugated linoleic acid (clas)", "conjugated linoleic acid", "cla")),
}


def _build_fatty_acids(raw_index):
    return {key: get_raw_nutrient(raw_index, numbers=numbers, names=names) for key, (numbers, names) in _FATTY_ACID_MATCHERS.items()}


def _build_sugars(nutrients, raw_index):
    return {
        "total_sugar_g": get_nutrient(nutrients, raw_index, "sugars_g"),
        "added_sugar_g": get_nutrient(
            nutrients,
            raw_index,
            "added_sugars_g",
            numbers=("539",),
            names=("sugars, added", "added sugars"),
        ),
        "fructose_g": get_raw_nutrient(raw_index, numbers=("212",), names=("fructose",)),
        "glucose_g": get_raw_nutrient(raw_index, numbers=("211",), names=("glucose",)),
        "sucrose_g": get_raw_nutrient(raw_index, numbers=("210",), names=("sucrose",)),
        "lactose_g": get_raw_nutrient(raw_index, numbers=("213",), names=("lactose",)),
        "maltose_g": get_raw_nutrient(raw_index, numbers=("214",), names=("maltose",)),
        "galactose_g": get_raw_nutrient(raw_index, numbers=("287",), names=("galactose",)),
    }


def _build_sterols(nutrients, raw_index):
    return {
        "cholesterol_mg": get_nutrient(nutrients, raw_index, "cholesterol_mg"),
        "campesterol_mg": get_raw_nutrient(raw_index, names=("campesterol",)),
        "stigmasterol_mg": get_raw_nutrient(raw_index, names=("stigmasterol",)),
        "beta_sitosterol_mg": get_raw_nutrient(raw_index, names=("beta-sitosterol", "sitosterol")),
        "phytosterols_mg": get_raw_nutrient(raw_index, names=("phytosterols", "phytosterols, other")),
    }


def _build_bioactives(nutrients, raw_index):
    return {
        "lycopene_ug": get_raw_nutrient(raw_index, numbers=("337",), names=("lycopene",)),
        "lutein_ug": get_raw_nutrient(raw_index, names=("lutein",)),
        "zeaxanthin_ug": get_raw_nutrient(raw_index, names=("zeaxanthin",)),
        "lutein_zeaxanthin_combined_ug": get_raw_nutrient(raw_index, numbers=("338",), names=("lutein + zeaxanthin", "lutein and zeaxanthin")),
        "beta_carotene_ug": get_raw_nutrient(raw_index, numbers=("321",), names=("carotene, beta",)),
        "alpha_carotene_ug": get_raw_nutrient(raw_index, numbers=("322",), names=("carotene, alpha",)),
        "cryptoxanthin_beta_ug": get_raw_nutrient(raw_index, numbers=("334",), names=("cryptoxanthin, beta",)),
        "betaine_mg": get_raw_nutrient(raw_index, numbers=("454",), names=("betaine",)),
        "caffeine_mg": get_nutrient(nutrients, raw_index, "caffeine_mg"),
        "theobromine_mg": get_raw_nutrient(raw_index, numbers=("263",), names=("theobromine",)),
    }


def _resolve_weight_g(entity: Dict[str, Any]) -> Optional[float]:
    explicit_weight = _to_valid_float(entity.get("estimated_weight_g"))
    if explicit_weight is not None:
        return explicit_weight
    quantity = _to_valid_float(entity.get("quantity"))
    unit = str(entity.get("unit") or "").strip().lower()
    return quantity if quantity is not None and unit in _GRAM_UNITS else None


def _build_densities(macronutrients, weight_g):
    energy = macronutrients.get("energy_kcal")
    energy_density = None
    if energy is not None and weight_g is not None and weight_g > 0:
        energy_density = round((energy / weight_g) * 100.0, _ROUND_DP)
    return {
        "protein_g_per_100kcal": safe_density_per_100kcal(macronutrients.get("protein_g"), energy),
        "fat_g_per_100kcal": safe_density_per_100kcal(macronutrients.get("fat_g"), energy),
        "carbohydrate_g_per_100kcal": safe_density_per_100kcal(macronutrients.get("carbohydrate_g"), energy),
        "fiber_g_per_100kcal": safe_density_per_100kcal(macronutrients.get("fiber_g"), energy),
        "sugars_g_per_100kcal": safe_density_per_100kcal(macronutrients.get("sugars_g"), energy),
        "water_g_per_100kcal": safe_density_per_100kcal(macronutrients.get("water_g"), energy),
        "energy_kcal_per_100g": energy_density,
        "mineral_density": None,
        "vitamin_density": None,
    }


def _build_ratios(macronutrients, fat_profile, minerals, vitamins):
    protein, carb, fat = macronutrients.get("protein_g"), macronutrients.get("carbohydrate_g"), macronutrients.get("fat_g")
    fiber, sugar, energy, water = macronutrients.get("fiber_g"), macronutrients.get("sugars_g"), macronutrients.get("energy_kcal"), macronutrients.get("water_g")
    saturated = fat_profile.get("saturated_fat_g")
    mono, poly = fat_profile.get("monounsaturated_fat_g"), fat_profile.get("polyunsaturated_fat_g")
    unsaturated = round(mono + poly, _ROUND_DP) if mono is not None and poly is not None else None
    return {
        "protein_carb_ratio": safe_ratio(protein, carb), "protein_fat_ratio": safe_ratio(protein, fat),
        "protein_kcal_ratio": safe_ratio(protein, energy), "fiber_carb_ratio": safe_ratio(fiber, carb),
        "fiber_kcal_ratio": safe_ratio(fiber, energy), "sugar_carb_ratio": safe_ratio(sugar, carb),
        "sugar_fiber_ratio": safe_ratio(sugar, fiber),
        "sodium_potassium_ratio": safe_ratio(minerals.get("sodium_mg"), minerals.get("potassium_mg")),
        "calcium_phosphorus_ratio": safe_ratio(minerals.get("calcium_mg"), minerals.get("phosphorus_mg")),
        "unsaturated_saturated_ratio": safe_ratio(unsaturated, saturated),
        "pufa_mufa_ratio": safe_ratio(poly, mono), "pufa_sfa_ratio": safe_ratio(poly, saturated),
        "omega3_omega6_ratio": safe_ratio(fat_profile.get("omega3_g"), fat_profile.get("omega6_g")),
        "vitamin_c_iron_ratio": safe_ratio(vitamins.get("vitamin_c_mg"), minerals.get("iron_mg")),
        "water_energy_ratio": safe_ratio(water, energy), "fat_protein_ratio": safe_ratio(fat, protein),
        "carb_protein_ratio": safe_ratio(carb, protein),
    }


_SHARED_CATEGORY_VALUES = {"Fruit", "Vegetable", "Grain", "Dairy", "Nut", "Seed", "Legume"}


def _effective_category(entity):
    category = str(entity.get("category") or "").strip()
    if category:
        return category
    ingredient_category = str(entity.get("ingredient_category") or "").strip()
    return ingredient_category if ingredient_category in _SHARED_CATEGORY_VALUES else ""


def _build_food_matrix(entity, entity_type):
    text, category = _text_for_matching(entity), _effective_category(entity)
    food_source = str(entity.get("food_source") or "").strip()
    ingredient_category = str(entity.get("ingredient_category") or "").strip()
    is_legume = category == "Legume" if category else None
    if is_legume is True:
        is_pulse = not _any_keyword(text, _PULSE_EXCLUSION_KEYWORDS)
    elif is_legume is False:
        is_pulse = False
    else:
        is_pulse = None

    red_hit, white_hit = _any_keyword(text, _RED_MEAT_KEYWORDS), _any_keyword(text, _WHITE_MEAT_KEYWORDS)
    if red_hit and not white_hit:
        is_red_meat, is_white_meat = True, False
    elif white_hit and not red_hit:
        is_red_meat, is_white_meat = False, True
    elif category and category != "Meat":
        is_red_meat, is_white_meat = False, False
    else:
        is_red_meat, is_white_meat = None, None

    fish_hit, shellfish_hit = _any_keyword(text, _FISH_KEYWORDS), _any_keyword(text, _SHELLFISH_KEYWORDS)
    if shellfish_hit:
        is_fish, is_shellfish = False, True
    elif fish_hit:
        is_fish, is_shellfish = True, False
    elif category and category != "Seafood":
        is_fish, is_shellfish = False, False
    else:
        is_fish, is_shellfish = None, None

    egg_hit = _any_keyword(text, _EGG_KEYWORDS)
    is_egg = True if egg_hit else (False if category and category != "Egg" else None)

    cheese_hit, yogurt_hit, milk_hit = _any_keyword(text, _CHEESE_KEYWORDS), _any_keyword(text, _YOGURT_KEYWORDS), _any_keyword(text, _MILK_KEYWORDS)
    dairy_hit = cheese_hit or yogurt_hit or milk_hit
    is_dairy = True if category == "Dairy" or dairy_hit else (False if category else None)
    is_cheese = True if cheese_hit else (False if is_dairy is False else None)
    is_yogurt = True if yogurt_hit else (False if is_dairy is False else None)
    is_milk = True if milk_hit else (False if is_dairy is False else None)

    is_cooking_oil_type = entity.get("ingredient_type") == "Cooking Oil" or ingredient_category == "Oil"
    plant_hit, animal_hit = _any_keyword(text, _PLANT_OIL_KEYWORDS), _any_keyword(text, _ANIMAL_FAT_KEYWORDS)
    is_oil = is_cooking_oil_type or plant_hit or animal_hit or _any_keyword(text, _OIL_KEYWORDS)
    if not is_oil:
        is_animal_fat, is_plant_oil = False, False
    elif animal_hit:
        is_animal_fat, is_plant_oil = True, False
    elif plant_hit:
        is_animal_fat, is_plant_oil = False, True
    else:
        is_animal_fat, is_plant_oil = None, None

    if category == "Grain":
        if _any_keyword(text, _WHOLE_GRAIN_KEYWORDS):
            is_whole_grain, is_refined_grain = True, False
        elif _any_keyword(text, _REFINED_GRAIN_KEYWORDS):
            is_whole_grain, is_refined_grain = False, True
        else:
            is_whole_grain, is_refined_grain = None, None
    elif category:
        is_whole_grain, is_refined_grain = False, False
    else:
        is_whole_grain, is_refined_grain = None, None

    metadata = {
        "category_source": "vision_enum" if entity.get("category") else ("ingredient_enum" if category else "unknown"),
        "keyword_classification_used": any([red_hit, white_hit, fish_hit, shellfish_hit, egg_hit, dairy_hit, plant_hit, animal_hit]),
    }
    return {
        "is_fruit": category == "Fruit" if category else None,
        "is_vegetable": category == "Vegetable" if category else None,
        "is_legume": is_legume, "is_pulse": is_pulse,
        "is_seed": category == "Seed" if category else None, "is_nut": category == "Nut" if category else None,
        "is_whole_grain": is_whole_grain, "is_refined_grain": is_refined_grain,
        "is_red_meat": is_red_meat, "is_white_meat": is_white_meat, "is_fish": is_fish, "is_shellfish": is_shellfish,
        "is_egg": is_egg, "is_dairy": is_dairy, "is_cheese": is_cheese, "is_yogurt": is_yogurt, "is_milk": is_milk,
        "is_oil": is_oil, "is_animal_fat": is_animal_fat, "is_plant_oil": is_plant_oil,
        "is_spice": True if entity_type == "spice" else (category == "Condiment" if category else None),
        "is_beverage": category == "Beverage" if category else None,
        "is_condiment": category == "Condiment" if category else None,
        "is_branded_food": food_source == "Branded" if food_source else None,
        "is_restaurant_food": food_source == "Restaurant" if food_source else None,
        "is_processed_food": None, "is_ultra_processed_food": None,
        "food_matrix_metadata": metadata,
    }


_PREPARATION_FLAG_MAP = {"is_raw": "Raw", "is_boiled": "Boiled", "is_steamed": "Steamed", "is_grilled": "Grilled", "is_roasted": "Roasted", "is_baked": "Baked", "is_fried": "Fried"}
_UNSUPPORTED_PREPARATION_FLAGS = ("is_smoked", "is_pickled", "is_pressure_cooked", "is_microwaved")


def _build_cooking(entity):
    preparation = str(entity.get("preparation") or "").strip()
    flags = {}
    if not preparation or preparation == "Unknown":
        flags.update({key: None for key in _PREPARATION_FLAG_MAP})
        flags["is_fermented"] = None
    else:
        flags.update({key: preparation == value for key, value in _PREPARATION_FLAG_MAP.items()})
        flags["is_fermented"] = preparation == "Fermented"
    flags["is_deep_fried"] = None
    flags.update({key: None for key in _UNSUPPORTED_PREPARATION_FLAGS})
    return flags


def _build_ingredient_structure(entity, sugars, entity_type):
    has_structure = isinstance(entity.get("ingredients"), list) and isinstance(entity.get("spices"), list) and (entity_type != "food" or entity.get("analysis_route") == "DECOMPOSE")
    ingredients, spices = entity.get("ingredients") or [], entity.get("spices") or []
    ingredient_count, spice_count = len(ingredients), len(spices)
    total = ingredient_count + spice_count
    if entity_type in {"ingredient", "spice"}:
        single, composite = True, False
    elif has_structure and total > 0:
        single, composite = total == 1, total > 1
    else:
        single, composite = None, None
    added_sugar = sugars.get("added_sugar_g")
    if added_sugar is not None:
        contains_added_sugar = added_sugar > 0
    elif has_structure and total > 0:
        contains_added_sugar = any(_any_keyword(_text_for_matching(item), _ADDED_SUGAR_KEYWORDS) for item in ingredients + spices if isinstance(item, dict))
    else:
        contains_added_sugar = None
    if has_structure and total > 0:
        contains_added_fat = any(_any_keyword(_text_for_matching(item), _ADDED_FAT_KEYWORDS) for item in ingredients + spices if isinstance(item, dict))
        contains_added_salt = any(_any_keyword(_text_for_matching(item), _ADDED_SALT_KEYWORDS) for item in ingredients + spices if isinstance(item, dict))
    else:
        contains_added_fat = contains_added_salt = None
    return {
        "ingredient_count": ingredient_count if has_structure else None,
        "spice_count": spice_count if has_structure else None,
        "contains_spices": spice_count > 0 if has_structure else None,
        "contains_multiple_foods": ingredient_count > 1 if has_structure else None,
        "is_single_ingredient": single, "is_composite_food": composite,
        "contains_added_fat": contains_added_fat, "contains_added_sugar": contains_added_sugar, "contains_added_salt": contains_added_salt,
        "added_component_detection_metadata": {"source": "nutrient_value_or_ingredient_keyword" if has_structure else "unknown", "ingredient_list_completeness_known": entity.get("ingredient_list_complete") if "ingredient_list_complete" in entity else None},
    }


def _build_physical(entity, macronutrients):
    weight_g = _resolve_weight_g(entity)
    edible_fraction = _to_valid_fraction(entity.get("edible_fraction"))
    edible_weight = round(weight_g * edible_fraction, _ROUND_DP) if weight_g is not None and edible_fraction is not None else None
    return {
        "weight_g": weight_g, "edible_fraction": edible_fraction, "estimated_edible_weight_g": edible_weight,
        "serving_size_g": weight_g, "energy_per_serving_kcal": macronutrients.get("energy_kcal"),
        "protein_per_serving_g": macronutrients.get("protein_g"), "fat_per_serving_g": macronutrients.get("fat_g"),
        "fiber_per_serving_g": macronutrients.get("fiber_g"),
    }


def _build_presence_flags(macronutrients, minerals, vitamins, fat_profile, bioactives):
    def present(value):
        return None if value is None else value > 0
    carotenoids = [bioactives.get(key) for key in ("lycopene_ug", "lutein_ug", "zeaxanthin_ug", "lutein_zeaxanthin_combined_ug", "beta_carotene_ug", "alpha_carotene_ug", "cryptoxanthin_beta_ug")]
    known = [value for value in carotenoids if value is not None]
    return {
        "contains_vitamin_c": present(vitamins.get("vitamin_c_mg")), "contains_fiber": present(macronutrients.get("fiber_g")),
        "contains_choline": present(vitamins.get("choline_mg")), "contains_omega3": present(fat_profile.get("omega3_g")),
        "contains_iron": present(minerals.get("iron_mg")), "contains_magnesium": present(minerals.get("magnesium_mg")),
        "contains_vitamin_k": present(vitamins.get("vitamin_k_ug")), "contains_protein": present(macronutrients.get("protein_g")),
        "contains_calcium": present(minerals.get("calcium_mg")), "contains_potassium": present(minerals.get("potassium_mg")),
        "contains_polyphenols": None, "contains_carotenoids": any(value > 0 for value in known) if known else None,
    }


EXPECTED_CANONICAL_KEYS = {"energy_kcal", "protein_g", "fat_g", "carbohydrate_g", "fiber_g", "sugars_g", "water_g", "ash_g", "saturated_fat_g", "monounsaturated_fat_g", "polyunsaturated_fat_g", "trans_fat_g", "cholesterol_mg", "omega3_g", "omega6_g", "calcium_mg", "iron_mg", "magnesium_mg", "phosphorus_mg", "potassium_mg", "sodium_mg", "zinc_mg", "copper_mg", "manganese_mg", "selenium_ug"}


def _count_values(*groups):
    values = [value for group in groups for value in group.values()]
    return sum(value is not None for value in values), len(values)


def _build_completeness_metadata(nutrients, all_nutrients, canonical_groups):
    missing_canonical = sum(_to_valid_float(nutrients.get(key)) is None for key in EXPECTED_CANONICAL_KEYS)
    available_features, total_features = _count_values(*canonical_groups)
    valid_raw = sum(isinstance(item, dict) and _to_valid_float(item.get("amount")) is not None for item in all_nutrients or [])
    return {
        "missing_canonical_nutrients": missing_canonical,
        "available_canonical_nutrients": len(EXPECTED_CANONICAL_KEYS) - missing_canonical,
        "missing_nutrient_features": total_features - available_features,
        "available_nutrient_features": available_features,
        "total_nutrient_features": total_features,
        "nutrient_feature_coverage": round(available_features / total_features, _ROUND_DP) if total_features else None,
        "raw_nutrient_record_count": len(all_nutrients or []),
        "valid_raw_nutrient_record_count": valid_raw,
        "feature_version": FEATURE_VERSION,
    }


def build_features(entity: Dict[str, Any], entity_type: str = "food") -> Dict[str, Any]:
    if not isinstance(entity, dict):
        raise TypeError("entity must be a dictionary")
    if entity_type not in _VALID_ENTITY_TYPES:
        raise ValueError(f"Invalid entity_type {entity_type!r}; expected one of {sorted(_VALID_ENTITY_TYPES)}")
    nutrients, all_nutrients = entity.get("nutrients") or {}, entity.get("all_nutrients") or []
    if not isinstance(nutrients, dict):
        raise ValueError("entity['nutrients'] must be a dictionary")
    if not isinstance(all_nutrients, list):
        raise ValueError("entity['all_nutrients'] must be a list")
    raw_index = _build_raw_index(all_nutrients)
    macronutrients = _build_macronutrients(nutrients, raw_index)
    fat_profile = _build_fat_profile(nutrients, raw_index)
    vitamins = _build_vitamins(nutrients, raw_index)
    minerals = _build_minerals(nutrients, raw_index)
    amino_acids = _build_amino_acids(raw_index)
    fatty_acids = _build_fatty_acids(raw_index)
    sugars = _build_sugars(nutrients, raw_index)
    sterols = _build_sterols(nutrients, raw_index)
    bioactives = _build_bioactives(nutrients, raw_index)
    densities = _build_densities(macronutrients, _resolve_weight_g(entity))
    ratios = _build_ratios(macronutrients, fat_profile, minerals, vitamins)
    food_matrix = _build_food_matrix(entity, entity_type)
    cooking = _build_cooking(entity)
    ingredient_structure = _build_ingredient_structure(entity, sugars, entity_type)
    physical = _build_physical(entity, macronutrients)
    presence_flags = _build_presence_flags(macronutrients, minerals, vitamins, fat_profile, bioactives)
    metadata = _build_completeness_metadata(nutrients, all_nutrients, (macronutrients, fat_profile, vitamins, minerals, amino_acids, fatty_acids, sugars, sterols, bioactives))
    return {"macronutrients": macronutrients, "fat_profile": fat_profile, "vitamins": vitamins, "minerals": minerals, "amino_acids": amino_acids, "fatty_acids": fatty_acids, "sugars": sugars, "sterols": sterols, "bioactives": bioactives, "densities": densities, "ratios": ratios, "food_matrix": food_matrix, "processing": cooking, "ingredient_structure": ingredient_structure, "physical": physical, "presence_flags": presence_flags, "metadata": metadata}


def _featurize_entity_tree(entity: Dict[str, Any], entity_type: str = "food") -> Dict[str, Any]:
    if not isinstance(entity, dict):
        raise ValueError(f"Every {entity_type} must be a dictionary")
    entity["features"] = build_features(entity, entity_type)
    ingredients, spices = entity.get("ingredients") or [], entity.get("spices") or []
    if not isinstance(ingredients, list):
        raise ValueError(f"{entity_type}['ingredients'] must be a list")
    if not isinstance(spices, list):
        raise ValueError(f"{entity_type}['spices'] must be a list")
    for ingredient in ingredients:
        if not isinstance(ingredient, dict):
            raise ValueError("Every ingredient must be a dictionary")
        _featurize_entity_tree(ingredient, "ingredient")
    for spice in spices:
        if not isinstance(spice, dict):
            raise ValueError("Every spice must be a dictionary")
        _featurize_entity_tree(spice, "spice")
    return entity


def _compute_features_sync(meal_json: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(meal_json, dict) or "meal" not in meal_json:
        raise ValueError("Input must be a dict with a top-level 'meal' key")
    if not isinstance(meal_json.get("meal"), dict):
        raise ValueError("meal_json['meal'] must be a dictionary")
    foods = meal_json["meal"].get("foods", [])
    if foods is None:
        foods = []
    if not isinstance(foods, list):
        raise ValueError("meal_json['meal']['foods'] must be a list")
    result = copy.deepcopy(meal_json)
    for food in result["meal"].get("foods", []) or []:
        if not isinstance(food, dict):
            raise ValueError("Every food must be a dictionary")
        _featurize_entity_tree(food, "food")
    return result


async def compute_features(meal_json: Dict[str, Any]) -> Dict[str, Any]:
    return _compute_features_sync(meal_json)


def compute_features_sync(meal_json: Dict[str, Any]) -> Dict[str, Any]:
    return _compute_features_sync(meal_json)
