from google import genai
# from google.colab import files
from PIL import Image, ImageOps
import json
import copy
import math
import logging
import time
from pathlib import Path
from typing import Any
from difflib import SequenceMatcher

# API_KEY = "YOUR_API_KEY"

# client = genai.Client(api_key=API_KEY)

import os

API_KEY = os.environ.get(
    "GEMINI_API_KEY"
)

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not configured."
    )

client = genai.Client(
    api_key=API_KEY
)

logger = logging.getLogger("quinone.analysis_engine")

GEMINI_MEAL_MODEL = (
    os.environ.get("GEMINI_MEAL_MODEL", "").strip()
    or "gemini-3.5-flash"
)
GEMINI_LABEL_MODEL = (
    os.environ.get("GEMINI_LABEL_MODEL", "").strip()
    or GEMINI_MEAL_MODEL
)

# Phone cameras commonly produce 12-50 MP files. Gemini does not need the
# original pixels for ordinary food recognition, and transmitting them adds a
# large fixed cost. Labels keep a larger edge because small printed text needs
# more detail than a meal photograph.
MEAL_IMAGE_MAX_EDGE = int(os.environ.get("MEAL_IMAGE_MAX_EDGE", "1280"))
LABEL_IMAGE_MAX_EDGE = int(os.environ.get("LABEL_IMAGE_MAX_EDGE", "2048"))
GEMINI_JSON_MAX_ATTEMPTS = max(
    1,
    int(os.environ.get("GEMINI_JSON_MAX_ATTEMPTS", "3")),
)
ENABLE_MEAL_INVENTORY_AUDIT = os.environ.get(
    "ENABLE_MEAL_INVENTORY_AUDIT",
    "true",
).strip().lower() in {"1", "true", "yes", "on"}


class ModelJSONResponseError(RuntimeError):
    """Raised after Gemini repeatedly returns unusable structured output."""


_NULLABLE_STRING_SCHEMA = {
    "anyOf": [{"type": "string"}, {"type": "null"}],
}
_NULLABLE_NUMBER_SCHEMA = {
    "anyOf": [{"type": "number"}, {"type": "null"}],
}
_NULLABLE_BOOLEAN_SCHEMA = {
    "anyOf": [{"type": "boolean"}, {"type": "null"}],
}

_VARIANT_SCHEMA = {
    "anyOf": [
        {
            "type": "object",
            "properties": {
                "canonical_name": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["canonical_name", "confidence"],
        },
        {"type": "null"},
    ],
}

_INGREDIENT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "canonical_name": {"type": "string"},
        "ingredient_category": {"type": "string"},
        "usda_food_description": {"type": "string"},
        "possible_usda_queries": {
            "type": "array",
            "items": {"type": "string"},
        },
        "estimated_percentage": {"type": "number"},
        "estimated_weight_g": {"type": "number"},
        "confidence": {"type": "number"},
    },
    "required": [
        "name", "canonical_name", "ingredient_category",
        "usda_food_description", "possible_usda_queries",
        "estimated_percentage", "estimated_weight_g", "confidence",
    ],
}

_SPICE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "canonical_name": {"type": "string"},
        "usda_food_description": {"type": "string"},
        "possible_usda_queries": {
            "type": "array",
            "items": {"type": "string"},
        },
        "estimated_weight_g": {"type": "number"},
        "confidence": {"type": "number"},
    },
    "required": [
        "name", "canonical_name", "usda_food_description",
        "possible_usda_queries", "estimated_weight_g", "confidence",
    ],
}

_MEAL_FOOD_PROPERTIES = {
    "id": {"type": "string"},
    "name": {"type": "string"},
    "canonical_name": {"type": "string"},
    "ingredient_type": _NULLABLE_STRING_SCHEMA,
    "canonical_variants": {
        "type": "object",
        "properties": {
            "legume": _VARIANT_SCHEMA,
            "oil": _VARIANT_SCHEMA,
        },
        "required": ["legume", "oil"],
    },
    "category": {"type": "string"},
    "container": {"type": "string"},
    "cuisine": _NULLABLE_STRING_SCHEMA,
    "food_source": {
        "type": "string",
        "enum": ["Generic", "Branded", "Restaurant", "Homemade"],
    },
    "brand": _NULLABLE_STRING_SCHEMA,
    "role": {"type": "string"},
    "served_separately": {"type": "boolean"},
    "belongs_to_food_id": _NULLABLE_STRING_SCHEMA,
    "preparation": {"type": "string"},
    "preparation_confidence": {"type": "number"},
    "quantity": {"type": "number"},
    "quantity_confidence": {"type": "number"},
    "unit": {
        "type": "string",
        "enum": ["g", "ml", "piece", "slice", "cup", "tbsp", "tsp"],
    },
    "edible_fraction": {"type": "number"},
    "detection_confidence": {"type": "number"},
    "analysis_route": {
        "type": "string",
        "enum": ["DIRECT_USDA", "DECOMPOSE", "NUTRITION_LABEL"],
    },
    "usda_food_description": _NULLABLE_STRING_SCHEMA,
    "possible_usda_queries": {
        "type": "array",
        "items": {"type": "string"},
    },
    "requires_back_image": {"type": "boolean"},
    "ingredients": {
        "type": "array",
        "items": _INGREDIENT_SCHEMA,
    },
    "spices": {
        "type": "array",
        "items": _SPICE_SCHEMA,
    },
}

_MEAL_FOOD_REQUIRED = list(_MEAL_FOOD_PROPERTIES.keys())

MEAL_RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "meal": {
            "type": "object",
            "properties": {
                "meal_type": {"type": "string"},
                "estimated_visible_food_weight_g": {"type": "number"},
                "foods": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": _MEAL_FOOD_PROPERTIES,
                        "required": _MEAL_FOOD_REQUIRED,
                    },
                },
            },
            "required": [
                "meal_type", "estimated_visible_food_weight_g", "foods",
            ],
        },
    },
    "required": ["meal"],
}

# Last-resort structured extraction remains sufficient for USDA lookup. It
# deliberately returns only core nutrient-bearing foods and disallows a mixed
# dish parent, so analysis can continue without accepting incomplete JSON.
SIMPLE_MEAL_RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "meal": {
            "type": "object",
            "properties": {
                "meal_type": {"type": "string"},
                "estimated_visible_food_weight_g": {"type": "number"},
                "foods": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "canonical_name": {"type": "string"},
                            "category": {"type": "string"},
                            "food_source": {
                                "type": "string",
                                "enum": [
                                    "Generic", "Branded", "Restaurant", "Homemade",
                                ],
                            },
                            "brand": _NULLABLE_STRING_SCHEMA,
                            "quantity": {"type": "number"},
                            "quantity_confidence": {"type": "number"},
                            "unit": {
                                "type": "string",
                                "enum": [
                                    "g", "ml", "piece", "slice", "cup", "tbsp", "tsp",
                                ],
                            },
                            "preparation": {"type": "string"},
                            "detection_confidence": {"type": "number"},
                            "analysis_route": {
                                "type": "string",
                                "enum": ["DIRECT_USDA", "NUTRITION_LABEL"],
                            },
                            "usda_food_description": _NULLABLE_STRING_SCHEMA,
                            "requires_back_image": {"type": "boolean"},
                        },
                        "required": [
                            "id", "name", "canonical_name", "category",
                            "food_source", "brand", "quantity",
                            "quantity_confidence", "unit", "preparation",
                            "detection_confidence", "analysis_route",
                            "usda_food_description", "requires_back_image",
                        ],
                    },
                },
            },
            "required": [
                "meal_type", "estimated_visible_food_weight_g", "foods",
            ],
        },
    },
    "required": ["meal"],
}

# Every meal image receives a second, independent inventory pass. This schema
# intentionally has no mixed-dish parent or nested ingredient field: each item
# must be one atomic nutrient-bearing food. That makes it impossible for the
# auditor to return both "sandwich" and its bread/filling, or "oatmeal" and its
# oats/toppings, in the same accepted response.
ATOMIC_MEAL_INVENTORY_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "meal_type": {"type": "string"},
        "items": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "canonical_name": {"type": "string"},
                    "category": {"type": "string"},
                    "container": {"type": "string"},
                    "role": {"type": "string"},
                    "food_source": {
                        "type": "string",
                        "enum": ["Generic", "Branded", "Restaurant", "Homemade"],
                    },
                    "brand": _NULLABLE_STRING_SCHEMA,
                    "quantity": {"type": "number"},
                    "unit": {"type": "string", "enum": ["g", "ml"]},
                    "preparation": {"type": "string"},
                    "confidence": {"type": "number"},
                    "analysis_route": {
                        "type": "string",
                        "enum": ["DIRECT_USDA", "NUTRITION_LABEL"],
                    },
                    "usda_food_description": _NULLABLE_STRING_SCHEMA,
                    "requires_back_image": {"type": "boolean"},
                    "visual_evidence": {"type": "string"},
                },
                "required": [
                    "name", "canonical_name", "category", "container", "role",
                    "food_source", "brand", "quantity", "unit", "preparation",
                    "confidence", "analysis_route", "usda_food_description",
                    "requires_back_image", "visual_evidence",
                ],
            },
        },
    },
    "required": ["meal_type", "items"],
}

_LABEL_NUTRIENT_PROPERTIES = {
    key: _NULLABLE_NUMBER_SCHEMA
    for key in (
        "energy_kcal", "protein_g", "fat_g", "saturated_fat_g",
        "trans_fat_g", "carbohydrate_g", "sugars_g", "added_sugars_g",
        "fiber_g", "sodium_mg", "cholesterol_mg", "potassium_mg",
        "calcium_mg", "iron_mg", "caffeine_mg",
    )
}
_LABEL_NUTRIENT_SCHEMA = {
    "type": "object",
    "properties": _LABEL_NUTRIENT_PROPERTIES,
    "required": list(_LABEL_NUTRIENT_PROPERTIES.keys()),
}
_LABEL_QUANTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "value": _NULLABLE_NUMBER_SCHEMA,
        "unit": _NULLABLE_STRING_SCHEMA,
    },
    "required": ["value", "unit"],
}
LABEL_RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "brand": _NULLABLE_STRING_SCHEMA,
        "product_name": {"type": "string"},
        "barcode": _NULLABLE_STRING_SCHEMA,
        "net_weight": _LABEL_QUANTITY_SCHEMA,
        "serving_size": _LABEL_QUANTITY_SCHEMA,
        "nutrition_basis": _LABEL_QUANTITY_SCHEMA,
        "servings_per_container": _NULLABLE_NUMBER_SCHEMA,
        "nutrition_per_serving": _LABEL_NUTRIENT_SCHEMA,
        "nutrition_per_100g": _LABEL_NUTRIENT_SCHEMA,
        "ingredients": {"type": "array", "items": {"type": "string"}},
        "allergens": {"type": "array", "items": {"type": "string"}},
        "claims": {"type": "array", "items": {"type": "string"}},
        "ocr_confidence": {"type": "number"},
    },
    "required": [
        "brand", "product_name", "barcode", "net_weight", "serving_size",
        "nutrition_basis", "servings_per_container",
        "nutrition_per_serving", "nutrition_per_100g", "ingredients",
        "allergens", "claims", "ocr_confidence",
    ],
}

MEAL_GENERATION_CONFIG = {
    "response_mime_type": "application/json",
    "response_json_schema": MEAL_RESPONSE_JSON_SCHEMA,
    "max_output_tokens": 8192,
}

LABEL_GENERATION_CONFIG = {
    "response_mime_type": "application/json",
    "response_json_schema": LABEL_RESPONSE_JSON_SCHEMA,
    "max_output_tokens": 4096,
}

# =============================================================================
# MAIN VISION PROMPT (unchanged)
# =============================================================================
prompt = """
You are Nutrica's Food Vision Engine.

Your task is to convert a food image into structured data for a nutrition analysis engine.

Return ONLY valid JSON.

==========================
GENERAL RULES
==========================

1. Every physically distinct edible mass must be returned separately.

If the same food appears in multiple disconnected locations,
return separate food objects.

Example

Butter on roti

↓

Food object

Butter

belongs_to_food_id = roti

------------------

Butter on dal

↓

Another food object

Butter

belongs_to_food_id = dal

Never merge physically separate edible masses into one object,
even if they are the same ingredient.

2. Ignore:
- plates
- bowls (unless they contain food)
- utensils
- napkins
- table

3. Never merge independent foods.

Rice and Lentils are two foods.

Rice and Chicken Curry are two foods.

CRITICAL MIXED-DISH RULE

Do NOT return a prepared mixed-dish parent as a top-level food when its
core components can be identified or reasonably inferred. The nutrition
engine operates on the core foods, not on a duplicate parent dish.

For a bowl of oatmeal porridge with oats, milk, banana, blueberries, chia
seeds and almonds, return the core foods only:

Rolled Oats
Milk
Banana
Blueberries
Chia Seeds
Almonds

Do NOT additionally return:
Oatmeal Porridge

For lentil curry, return the core components such as the identified lentil
variant, onion, tomato, cooking oil and other substantial ingredients.
Do NOT additionally return Dal, Daal, Dhal, Lentil Curry or Dal Tadka as
a second parent food.

For chicken curry, return Chicken, Onion, Tomato, cooking fat/oil and other
substantial core foods. Do NOT additionally return Chicken Curry.

Every gram of edible mass must belong to exactly one returned core food.

==========================
ONE PHYSICAL INGREDIENT = ONE FOOD OBJECT
==========================

This rule is mandatory and overrides naming/preparation differences.

A physical ingredient must appear EXACTLY ONCE in meal.foods.
Preparation state, cutting style, cooking state, moisture state, serving form,
or USDA database wording must NEVER create a second food object.

The `name` field must contain the CORE FOOD NAME ONLY.
Put preparation information only in the `preparation` field.

FORBIDDEN:
- Rolled Oats (Cooked) + Rolled Oats (Dry)
- Cooked Rolled Oats + Dry Rolled Oats
- Rice (Cooked) + Rice (Dry)
- Lentils (Cooked) + Lentils (Dry)
- Banana + Sliced Banana when both refer to the same banana
- Almonds + Sliced Almonds when both refer to the same almonds
- Potato + Boiled Potato when both refer to the same potato

CORRECT:
- name: Rolled Oats
  preparation: Cooked

If a cooked food was prepared from a dry ingredient, DO NOT return both the
cooked mass and the dry/raw-equivalent mass. Return only ONE physical food
entity representing what is actually present in the photographed meal.
The dry/raw-equivalent amount may be useful internally for recipe reasoning,
but it must NEVER become another item in meal.foods.

USDA matching also MUST NOT create a second detected food. Different USDA
descriptions are alternative database candidates for the SAME physical food.

Before returning JSON perform this mandatory duplicate audit:
1. Remove preparation/state words mentally from every name, including:
   cooked, dry, dried, raw, boiled, steamed, baked, fried, roasted, grilled,
   simmered, soaked, sliced, chopped, diced, minced, crushed, ground.
2. Remove parenthetical preparation labels such as (Cooked), (Dry), (Raw).
3. Singularize trivial plural differences.
4. Compare the remaining core food identities.
5. If two entries resolve to the same physical ingredient, KEEP ONLY ONE.
6. NEVER add their quantities together when they are alternate estimates of
   the same physical mass. Choose the estimate that is consistent with the
   parent dish mass/ingredient percentages and has higher confidence.

Example — oatmeal bowl:
CORRECT FINAL meal.foods:
- Rolled Oats
- Milk
- Banana
- Blueberries
- Chia Seeds
- Almonds

INCORRECT FINAL meal.foods:
- Rolled Oats (Cooked)
- Rolled Oats (Dry)
- Oatmeal Porridge

==========================
FOOD ID
==========================

Assign every food object a unique sequential id.

Format: food_0001, food_0002, food_0003, ...

Rules

- IDs must start at food_0001.
- IDs must increase by exactly 1 for every new food object, in the
  order the foods are listed in the JSON output.
- IDs must NEVER skip a number.
- IDs must NEVER repeat.
- EVERY food object must include an "id" field — this applies to
  ALL foods, including Branded / NUTRITION_LABEL foods. Do not omit
  the id field for any food, even packaged products.

Before returning the JSON, re-check the full food list from top to
bottom and confirm the ids read food_0001, food_0002, food_0003, ...
with no gaps. Renumber if necessary.

==========================
PREPARATION
==========================

Choose ONE:

Raw
Boiled
Cooked
Steamed
Grilled
Roasted
Baked
Fried
Simmered
Fermented
Unknown

Also estimate

preparation_confidence

between 0.0 and 1.0.

==========================
QUANTITY ESTIMATION
==========================

Estimate the edible quantity for EVERY detected food.

CRITICAL MASS-CONSISTENCY RULE:
- For every DECOMPOSE food, the parent food quantity is the total visible mass
  budget for its substantial ingredients.
- Ingredient estimated_weight_g values must be derived from that parent mass
  budget and estimated_percentage values.
- Never independently assign an ingredient weight that contradicts its
  percentage of the parent.
- Tiny seasonings/garnishes such as curry leaves, dried chilies, turmeric,
  cumin, mustard seeds, salt, and similar spices must never be estimated as
  meal-sized 50-100 g portions. If visually countable, use "piece"; otherwise
  use a small gram estimate and lower confidence when uncertain.

Use visual reasoning based on:

- container size
- plate size
- bowl size
- food volume
- typical serving sizes
- relative size compared to nearby foods

Prefer grams whenever possible.

Use "g" whenever the edible mass can be reasonably estimated.

Use "piece" only for naturally countable foods such as:
- egg
- papad
- lime
- chili
- bread slice
- cookie

Do not use "piece" for rice, curries, vegetables, pasta, noodles, salads, or mixed dishes.

When using "piece", quantity must represent the number of visible pieces.

For whole dried or fresh chilies, use piece when the individual chilies are
visible. Never assign a large gram quantity to one or a few visible chilies.
A garnish or spice must never be assigned a mass comparable to the main dish.
If its mass cannot be estimated reliably, prefer piece or omit it rather than
inventing a large gram value.

Allowed units:

g
ml
piece
slice
cup
tbsp
tsp

Never invent units.

Examples

❌ wedge

❌ bowl

❌ handful

❌ serving

Convert these into one of the allowed units.

Do NOT return quantity 0.

Examples

Cooked rice
250 g

Lentils in serving bowl
650 g

Papad
1 piece

Lime
2 piece

Green chili
1 piece

Also estimate

quantity_confidence

between 0.0 and 1.0.

This represents your confidence in the estimated quantity only,
not the confidence that the food was correctly detected.

Examples

A fully visible banana
quantity_confidence = 0.99

A full bowl of rice
quantity_confidence = 0.90

A partially occluded curry
quantity_confidence = 0.60

A soup in a deep bowl with unknown depth
quantity_confidence = 0.45

==========================
FOOD CATEGORY
==========================

Choose ONE:

Fruit
Vegetable
Grain
Meat
Seafood
Egg
Dairy
Legume
Nut
Seed
Beverage
Dessert
Snack
Condiment
Mixed Dish
Unknown

==========================
CUISINE
==========================

Estimate the most likely cuisine.

Use "Unknown" only if the cuisine cannot be reasonably inferred.

Examples:

Indian
Italian
Chinese
Japanese
Mexican
American
Mediterranean
French
Thai
Unknown

==========================
FOOD SOURCE
==========================

Determine the origin of the detected food.

Choose exactly ONE:

Generic
Branded
Restaurant
Homemade

Definitions

Generic
- A naturally occurring or common food.
- No identifiable brand.
- Examples:
  Banana
  Apple
  White Rice
  Boiled Egg
  Milk

Branded
- A packaged commercial product whose brand or packaging is visible or highly recognizable.
- Examples:
  Lay's Chips
  Doritos
  Coca-Cola
  Oreo
  KitKat
  Maggi Instant Noodles

  For Branded foods, identify the commercial product as accurately as possible.

  Return:

  - brand
  - product name

  Do not try to convert the product into a generic food.

  Examples

  Lay's Flamin' Hot Potato Chips

  brand = "Lay's"

  name = "Lay's Flamin' Hot Potato Chips"

  Bingo! Tedhe Medhe Masala Tadka

  brand = "Bingo!"

  name = "Bingo! Tedhe Medhe Masala Tadka Namkeen"

Restaurant
- A prepared food from a known restaurant or fast-food chain.
- Examples:
  McDonald's Fries
  KFC Fried Chicken
  Domino's Pizza

Homemade
- Freshly prepared meals, curries, mixed dishes, cooked vegetables, homemade snacks and similar foods.
- Examples:
  Chicken Curry
  Lentils
  Potato Curry
  Biryani
  Pasta
  Vegetable Stir Fry

If uncertain, choose Generic rather than Branded.

==========================
BRAND
==========================

Determine whether the food belongs to a recognizable commercial brand.

Return one field:

brand

Rules

• Return the visible or highly recognizable consumer brand name only.

• Do NOT include the product name.

Correct

Lay's Flamin' Hot Potato Chips

brand = "Lay's"

--------------------------

Coca-Cola Zero

brand = "Coca-Cola"

--------------------------

KitKat

brand = "KitKat"

--------------------------

Maggi 2-Minute Noodles

brand = "Maggi"

--------------------------

Oreo Cookies

brand = "Oreo"

--------------------------

For Generic, Homemade, or Restaurant foods, return

brand = null

Examples

White Rice

brand = null

Chicken Curry

brand = null

Dal

brand = null

Restaurant Pizza

brand = null

Return only the brand name or null.

==========================
BACK LABEL REQUIREMENT
==========================

For foods whose analysis_route is NUTRITION_LABEL, return

requires_back_image

true

For all other foods

requires_back_image

false

The back image should contain the Nutrition Facts panel.

The nutrition label will be used instead of USDA for nutrient analysis.

==========================
ANALYSIS ROUTE
==========================

Choose exactly ONE:

DIRECT_USDA
DECOMPOSE
NUTRITION_LABEL

Rules

DIRECT_USDA

Use for Generic foods that can be represented by a single USDA FoodData Central entry.

Examples

White Rice
Boiled Egg
Banana
Milk
Apple
Naan

--------------------------

DECOMPOSE

LEGACY / FALLBACK ONLY. Prefer returning the core ingredients directly as
separate top-level DIRECT_USDA foods. Use DECOMPOSE only when the dish cannot
be broken into meaningful core foods with reasonable confidence.

If DECOMPOSE is used as a fallback, its parent object is an internal analysis
container and must not be presented as an additional edible food alongside
its ingredients.

--------------------------

NUTRITION_LABEL

Use for Branded packaged foods whenever the product is identifiable.

Examples

Lay's Chips
Doritos
Bingo! Tedhe Medhe
Oreo
KitKat
Maggi
Coca-Cola
Pepsi

Do NOT search USDA for these foods.

Instead, they should be analyzed from the Nutrition Facts panel on the back of the package.

If analysis_route is NUTRITION_LABEL:

- requires_back_image must be true.
- usda_food_description must be null.
- possible_usda_queries must be an empty list.
- ingredients must be an empty list.
- spices must be an empty list.

==========================
INGREDIENTS
==========================

Only for DECOMPOSE foods.

Return the core recipe ingredients that are visually identifiable or can be
inferred with high confidence from the appearance of the dish. Ingredients
are the substantial, weight-bearing components of the dish (proteins,
vegetables, legumes, grains, dairy, oils). Spices and seasonings do NOT
belong in this list — they go in the separate "spices" array covered in
the SPICES section below.

DO NOT include visible garnishes or foods that are already detected as
their own separate top-level food object elsewhere in the meal — see
DUPLICATE PREVENTION below for the full rule and example.

Return ingredients ordered from highest estimated_percentage to lowest.

Example — Chicken Curry

ingredients:
  Chicken
  Tomato
  Onion
  Garlic
  Ginger
  Butter
  Cream

spices:
  Ground turmeric
  Ground cumin
  Ground coriander
  Paprika
  Ground black pepper
  Ground cinnamon
  Ground cloves
  Ground cardamom
  Bay leaf
  Curry leaves
  Salt

Note: fresh herbs (cilantro, parsley, dill, etc.) belong in the spices
list ONLY if they are visually mixed into the dish itself. If the same
herb is ALSO visible separately as its own garnish (e.g. a small pile of
chopped cilantro on top, detected as its own food object), it must be
excluded from this list per DUPLICATE PREVENTION — do not list it twice.

Never use regional spice blend names as a single ingredient or spice.

Do NOT return names such as:

Garam masala
Panch phoron
Sambar powder
Rasam powder
Tandoori masala
Curry powder
Chaat masala
Berbere
Ras el hanout
Herbes de Provence
Cajun seasoning
Chinese five spice

Instead, decompose spice blends into their likely individual spices
whenever they can be reasonably inferred.

Example

Incorrect

Garam masala

Correct

Ground cumin
Ground coriander
Ground black pepper
Ground cinnamon
Ground cloves
Ground cardamom

Each ingredient or spice must represent ONE ingredient only.

Examples

Correct

Chicken

Tomato

Ground turmeric

Ground cumin

Mustard seeds

Ground cardamom

Incorrect

Mixed spices

Indian spices

Masala

Whole spices

Incorrect

Chicken & Tomato

Cream/Yogurt

Oil/Ghee

Onion/Garlic/Ginger

Each ingredient must include

estimated_percentage

confidence

confidence represents how certain you are that the ingredient or spice is actually present.

Examples

Chicken
confidence = 0.99

Onion
confidence = 0.96

Ground turmeric
confidence = 0.93

Ground cumin
confidence = 0.72

Ground cardamom
confidence = 0.55

The percentages should sum to exactly 100.

Adjust the final ingredient if necessary.

Example

Chicken 55

Tomato 15

Onion 10

Cream 10

Butter 5

Garlic 5

For every DECOMPOSE food, also estimate the edible weight of each
ingredient and spice.

The sum of all ingredient estimated_weight_g values (the "ingredients"
array only — spices are trace amounts and are not part of this sum) must
equal the parent food's quantity in grams.

Each ingredient must contain

estimated_weight_g
estimated_percentage
confidence

Each spice must also contain

estimated_weight_g
confidence

If the parent food quantity is not expressed in grams, first estimate an
equivalent edible gram weight before distributing ingredient weights.

Every ingredient and every spice must additionally include:

canonical_name — the USDA-friendly English name (see CANONICAL INGREDIENT
NAMES below)

usda_food_description — the single most likely USDA FoodData Central
entry for that ingredient/spice on its own (NOT the parent dish)

possible_usda_queries — exactly FIVE search queries for that
ingredient/spice, ordered most specific to most general (see USDA SEARCH
below — the same five-query rule that applies to top-level foods applies
here too)

Example — Onion (as an ingredient inside Chicken Curry)

usda_food_description: "Onions, raw"

possible_usda_queries:
  Onion raw
  Red onion raw
  Yellow onion raw
  Sliced onion raw
  Onion

This ensures ingredient resolution always has a specific, USDA-shaped
description to search first, instead of only ever searching a bare
one-word ingredient name (which risks matching an unrelated compound
dish that merely contains that word, e.g. "Onion" incorrectly resolving
to "Bread, onion" instead of "Onions, raw").

==========================
PRIMARY VARIANT
==========================

For foods whose nutritional profile depends heavily on the underlying ingredient type,
identify the most likely biological or commercial variant.

Only return a primary_variant for:

• Legumes
• Beans
• Lentils
• Peas
• Oils

Return internationally recognized English names that closely match USDA FoodData Central terminology.

Examples

Lentil Curry

primary_variant = "Red Lentil"

or

"Green Lentil"

or

"Brown Lentil"

--------------------

Dal

primary_variant = "Yellow Split Pigeon Pea"

or

"Split Chickpea"

or

"Black Gram"

or

"Green Gram"

--------------------

Cooking Oil

primary_variant = "Peanut Oil"

or

"Canola Oil"

or

"Olive Oil"

or

"Sunflower Oil"

or

"Soybean Oil"

or

"Mustard Seed Oil"

or

"Sesame Oil"

--------------------

If the variant cannot be inferred confidently,
return null.

==========================
INGREDIENT VARIANTS
==========================

Only infer these when confidence is reasonably high.

This section describes a FOOD-LEVEL field (applies to the whole detected
food object, e.g. a "Lentil Curry" food classified overall as a Legume
dish) — this is a different, separate field from the per-ingredient
"ingredient_category" described later in CANONICAL INGREDIENT NAMES. Do
not confuse the two: this one is called ingredient_type and lives on the
food object itself; the other is called ingredient_category and lives
inside each item of the food's "ingredients" array.

Return

ingredient_type

One of

Legume
Cooking Oil
null

----------------------------------

If ingredient_type = Legume

return

legume_variant

{
    "canonical_name": "...",
    "confidence": 0.95
}

Allowed canonical names include

Red lentils
Yellow split pigeon peas
Split chickpeas
Whole mung beans
Split mung beans
Black gram
Kidney beans
Black-eyed peas
Green peas
Soybeans
Other

----------------------------------

If ingredient_type = Cooking Oil

return

oil_variant

{
    "canonical_name": "...",
    "confidence": 0.82
}

Allowed canonical names include

Mustard oil
Sunflower oil
Groundnut oil
Soybean oil
Canola oil
Corn oil
Rice bran oil
Olive oil
Coconut oil
Palm oil
Sesame oil
Ghee
Butter
Other

Only infer the oil when it can reasonably be inferred from cuisine, appearance, or preparation.

If uncertain, return

oil_variant = null.

==========================
CANONICAL INGREDIENT NAMES
==========================

Every ingredient and spice must be returned using internationally
recognized English food names.

Top-level food names must follow the same rule. Never use local, regional,
or language-specific names for the user-facing name.

Examples:
Dal / Daal / Dhal -> Lentils or the specific lentil variant
Toor dal -> Yellow split pigeon peas
Moong dal -> Split mung beans
Masoor dal -> Red lentils

Never use local, regional, or language-specific names.

Examples

Incorrect
Masoor Dal

Correct
Red lentils

Incorrect
Moong Dal

Correct
Split mung beans

Incorrect
Urad Dal

Correct
Black gram

Incorrect
Toor Dal

Correct
Yellow split pigeon peas

Incorrect
Besan

Correct
Chickpea flour

Incorrect
Maida

Correct
Refined wheat flour

Incorrect
Atta

Correct
Whole wheat flour

Incorrect
Paneer

Correct
Fresh cheese

Incorrect
Desi Ghee

Correct
Ghee

Return ingredients that best match USDA FoodData Central terminology whenever possible.

Every ingredient and spice must additionally include

canonical_name

usda_food_description

possible_usda_queries

as described in the INGREDIENTS section above — canonical_name should be
the USDA-friendly English ingredient name.

If the exact variety cannot be determined confidently, choose the most
likely variety and reduce its confidence value accordingly (the
confidence field inside legume_variant / oil_variant, where applicable).

For every item in the "ingredients" array (not spices), also return

ingredient_category

using one of

Protein
Legume
Vegetable
Fruit
Grain
Oil
Dairy
Spice
Nut
Seed
Sweetener
Flavoring
Additive
Other

(This is the per-ingredient field described in the INGREDIENT VARIANTS
note above — distinct from the food-level ingredient_type field.)

==========================
SPICES
==========================

Include major spices or seasonings whenever they are visually identifiable or can be inferred with high confidence from the dish.

Examples

Dal Tadka

Lentils
Onion
Tomato
Garlic
Ground turmeric
Ground cumin
Mustard seeds

Chicken Curry

Chicken
Onion
Tomato
Garlic
Ginger
Ground turmeric
Ground coriander
Chili powder
(see spice blend decomposition rule in INGREDIENTS above — never
"Garam masala")

Aloo Sabzi

Potato
Onion
Ground turmeric
Ground cumin
Mustard seeds
Green chili

Do NOT invent spices.

If uncertain, omit them.

Do NOT return generic entries such as

Spices
Mixed spices
Indian spices
Masala
Seasoning

Every spice must be listed separately, and every spice must include
canonical_name, usda_food_description, possible_usda_queries (exactly
five, see USDA SEARCH), estimated_weight_g, and confidence — the same
fields required for ingredients (spices do not need estimated_percentage,
since they are not part of the ingredient weight-percentage breakdown).

==========================
USDA SEARCH
==========================

Generate exactly FIVE USDA search queries for every entity that requires
USDA resolution. This includes:

- DIRECT_USDA foods
- every ingredient inside a DECOMPOSE food
- every spice inside a DECOMPOSE food

The parent object of a DECOMPOSE food is not resolved directly through
USDA. Its nutrients are calculated by summing its resolved ingredients
and spices.

For the parent object of a DECOMPOSE food:

- usda_food_description must be null
- possible_usda_queries must be an empty list

NUTRITION_LABEL foods are the only exception — possible_usda_queries must
be an empty list for those, since no USDA search is performed.

For DIRECT_USDA foods, the queries should describe the food itself.

Example

Cooked White Rice

↓

Cooked white rice
Basmati rice cooked
Long grain white rice cooked
White rice cooked
Rice

For ingredients and spices WITHIN a DECOMPOSE food, the queries should
describe that single ingredient/spice as it would appear in USDA
FoodData Central — not the parent dish.

Example

Onion (ingredient inside Chicken Curry)

↓

Onions, raw
Onion raw
Red onion raw
Yellow onion raw
Onion

The queries must be ordered from MOST SPECIFIC to MOST GENERAL.

The five queries must be unique.

Do not repeat the same query using different word order.

==========================
USDA DESCRIPTION
==========================

Generate usda_food_description only for:

- DIRECT_USDA foods
- ingredients inside DECOMPOSE foods
- spices inside DECOMPOSE foods

Do NOT generate a USDA description for the parent object of a DECOMPOSE food.

For every DECOMPOSE parent food, return:

usda_food_description = null

possible_usda_queries = []

The parent DECOMPOSE food is an aggregation object. Its nutrients are
calculated by resolving and summing its ingredients and spices.

For every DIRECT_USDA food, DECOMPOSE ingredient, and DECOMPOSE spice,
generate ONE field:

usda_food_description

This field should contain the SINGLE FoodData Central description most
likely to exist for that exact food, ingredient, or spice.

Think like you are selecting the exact USDA entry, not describing the food.

Rules

• Use official USDA wording whenever possible.

• Prefer generic USDA descriptions over restaurant names or regional names.

• Include cooking state if known.

• Include grain type if known.

• Include preparation if known.

• Do NOT include brands.

• Do NOT include explanations.

• Return exactly one description.

Examples

White Rice
→
Rice, white, long-grain, regular, cooked

Brown Rice
→
Rice, brown, long-grain, cooked

Boiled Egg
→
Egg, whole, cooked, hard-boiled

French Fries
→
Potatoes, french fried

Naan
→
Naan bread

Mashed Potato
→
Potatoes, mashed

Onion as an ingredient inside a DECOMPOSE food
→
Onions, raw

Fresh cheese as an ingredient inside Paneer Tikka
→
Cheese, fresh

Yogurt as an ingredient inside Paneer Tikka
→
Yogurt, plain, whole milk

Example of a DECOMPOSE parent

Paneer Tikka
→
usda_food_description = null
possible_usda_queries = []

Chicken Curry
→
usda_food_description = null
possible_usda_queries = []

Dal Tadka
→
usda_food_description = null
possible_usda_queries = []

The description should maximize the probability of finding the correct
USDA FoodData Central entry for the exact DIRECT_USDA food, ingredient,
or spice.

==========================
FOOD ROLE
==========================

Choose ONE:

main

side

garnish

drink

dessert

condiment

ingredient

==========================
CONTAINER
==========================

Estimate where the food is served.

Choose ONE:

plate
bowl
serving_bowl
small_bowl
glass
cup
bottle
tray
basket
unknown

The container identifies where the food is located.

It MUST NOT be included in the food name.

Examples

Correct

name: Dal (Lentil Curry)
container: serving_bowl

Correct

name: Dal (Lentil Curry)
container: plate

Incorrect

name: Dal in serving bowl

Incorrect

name: Rice on plate

==========================
SERVED SEPARATELY
==========================

Return

true

or

false

Examples

Cilantro sprinkled on curry

served_separately = false

Cilantro in a small bowl

served_separately = true

==========================
MULTIPLE SERVINGS
==========================

If the SAME food appears in MORE THAN ONE container,
return EACH serving as a separate food object.

Each serving must have:

- its own id
- its own container
- its own quantity
- its own served_separately value

Do NOT merge the quantities.

Do NOT rename the food because of the container.

Correct

Food 1

name = Dal (Lentil Curry)

container = plate

quantity = 250 g

served_separately = false

-------------------------

Food 2

name = Dal (Lentil Curry)

container = serving_bowl

quantity = 650 g

served_separately = true

-------------------------

Incorrect

Dal in bowl

Dal on plate

Dal (extra)

Dal (serving bowl)

Do NOT include the container in the food name.

Use the container field instead.

==========================
BELONGS TO
==========================

Use belongs_to_food_id ONLY when a food is physically attached to, placed on, or served as part of another detected food.

Foods in different containers must NEVER reference each other using belongs_to_food_id.

Dal in serving bowl

belongs_to_food_id = null

Dal on plate

belongs_to_food_id = null

Typical examples include:

- Garnishes
- Toppings
- Sauces poured over another food
- Decorative edible items

Do NOT use belongs_to_food_id simply because two foods are served together.

Examples

Correct

Chicken Curry

id = food_0002

Fresh Cilantro sprinkled on the curry

belongs_to_food_id = food_0002

Butter spread on bread,
ghee brushed on naan,
oil drizzled over vegetables,
or melted cheese on fries
must be returned as separate foods.

Example

{
    "name":"Butter",
    "belongs_to_food_id":"food_0002"
}

--------------------------

Correct

Ice Cream

id = food_0005

Chocolate Syrup poured on top

belongs_to_food_id = food_0005

--------------------------

Correct

Pizza

id = food_0008

Extra Cheese topping

belongs_to_food_id = food_0008

--------------------------

Correct

Rice

belongs_to_food_id = null

Chicken Curry

belongs_to_food_id = null

Although served together, they are separate foods.

--------------------------

Correct

Naan

belongs_to_food_id = null

Butter Chicken

belongs_to_food_id = null

--------------------------

Correct

Papad

belongs_to_food_id = null

Dal

belongs_to_food_id = null

--------------------------

Correct

Side Salad

belongs_to_food_id = null

Main Curry

belongs_to_food_id = null

--------------------------

If the food is served in a separate bowl, plate, cup, or container, it MUST have

belongs_to_food_id = null

unless it is physically attached to another food.

==========================
CONFIDENCE
==========================

Return

detection_confidence

between

0.0

and

1.0

==========================
EDIBLE FRACTION
==========================

Estimate

edible_fraction

between

0

and

1

Examples

Banana with peel

0.65

Orange

0.72

Cooked rice

1.0

Chicken curry

1.0

==========================
DUPLICATE PREVENTION
==========================

Every edible item must appear exactly once.

If a food is detected separately, it must NOT also appear inside another detected food.

Examples

Rice on plate + Curry

Return

Rice

Curry

NOT

Curry with Rice

If Fresh Cilantro is detected separately as its own food object,

remove Fresh Cilantro from the Curry's ingredients/spices list.

If Fried Onions are detected separately as their own food object,

remove Fried Onions from the Curry's ingredients/spices list.

This is the only place this rule needs to be applied — it covers both
the "ingredients" array and the "spices" array of every DECOMPOSE food.

Never duplicate edible mass.

==========================
TOPPINGS & SPREADS
==========================

Carefully inspect EVERY detected food INDEPENDENTLY for visible toppings,
spreads, coatings, melted fats and finishing ingredients.

These include but are not limited to

• Butter
• Ghee
• Margarine
• Cheese
• Cream
• Mayonnaise
• Nut butters
• Chocolate spread
• Jam
• Honey
• Olive oil drizzle
• Chili oil
• Herb butter

You must check EACH main food item separately — rice, roti/naan, dal,
curry, vegetables, and so on — one at a time. Finding a topping on one
food does NOT mean the same topping should be skipped on another food.
Do NOT stop scanning once a topping has been found once. A topping can
legitimately appear on more than one food in the same image.

Example

If butter is visible on BOTH the roti AND the dal, you MUST return
TWO separate Butter objects — do not report only one and skip the
other:

Food: Butter
belongs_to_food_id = roti_id

Food: Butter
belongs_to_food_id = dal_id

If clearly visible, detect every occurrence as a SEPARATE food object.

Examples

Butter on naan

Food 1
Naan

Food 2
Butter

belongs_to_food_id = naan_id

----------------------

Butter on toast

Toast

Butter

----------------------

Cheese on pizza

Pizza

Cheese

----------------------

Olive oil on salad

Salad

Olive oil

Do NOT merge these into the parent food.

Estimate their quantity separately.

If only a thin coating is visible,
estimate 2–10 g rather than ignoring it.

If uncertain whether a topping exists,
omit it rather than hallucinating it.

Before returning the JSON, go back through each main food item one by
one and explicitly re-check: "does this specific food also have a
visible topping or spread that hasn't been listed yet?" Add any that
were missed.

==========================
VISIBLE FOOD ONLY
==========================

Estimate quantities only for visible food.

estimated_visible_food_weight_g must equal the sum of the quantities of all foods whose unit is "g".

Foods measured in "piece", "slice", "cup", "tbsp", or "tsp" must NOT be converted into grams when calculating estimated_visible_food_weight_g.

Do not estimate hidden food.

Do not estimate food outside the image.

Do not estimate leftovers inside opaque containers.

If only part of a food is visible,
estimate only the visible edible amount.

==========================
NO HALLUCINATION
==========================

Only detect foods that are visually identifiable.

Do not invent ingredients,
sides,
or beverages that are not visible.

If uncertain,
lower the confidence instead of inventing foods.

==========================
RETURN JSON ONLY
==========================

Schema

{
  "meal": {
    "meal_type": "Lunch",
    "estimated_visible_food_weight_g": 685,
    "foods": [
      {
        "id": "food_0001",
        "name": "White Rice",
        "ingredient_type": null,
        "canonical_variants": {
          "legume": null,
          "oil": null
        },
        "container": "plate",
        "category": "Grain",
        "cuisine": "Indian",
        "food_source": "Generic",
        "brand": null,
        "role": "side",
        "served_separately": false,
        "belongs_to_food_id": null,
        "preparation": "Boiled",
        "preparation_confidence": 0.98,
        "quantity": 250,
        "quantity_confidence": 0.93,
        "unit": "g",
        "edible_fraction": 1.0,
        "detection_confidence": 0.99,
        "analysis_route": "DIRECT_USDA",
        "usda_food_description": "Rice, white, long-grain, regular, cooked",
        "possible_usda_queries": [
          "Cooked white rice",
          "White rice cooked",
          "Long grain white rice cooked",
          "Basmati rice cooked",
          "Rice cooked"
        ],
        "ingredients": [],
        "spices": []
      },
      {
        "id": "food_0002",
        "name": "Chicken Curry",
        "ingredient_type": null,
        "canonical_variants": {
          "legume": null,
          "oil": {
            "canonical_name": "Sunflower oil",
            "confidence": 0.53
          }
        },
        "container": "plate",
        "category": "Mixed Dish",
        "cuisine": "Indian",
        "food_source": "Homemade",
        "brand": null,
        "role": "main",
        "served_separately": false,
        "belongs_to_food_id": null,
        "preparation": "Simmered",
        "preparation_confidence": 0.95,
        "quantity": 320,
        "quantity_confidence": 0.8,
        "unit": "g",
        "edible_fraction": 1.0,
        "detection_confidence": 0.96,
        "analysis_route": "DECOMPOSE",
        "usda_food_description": "Chicken curry",
        "possible_usda_queries": [
          "Chicken curry",
          "Indian chicken curry",
          "Butter chicken",
          "Chicken tikka masala",
          "Creamy chicken curry"
        ],
        "ingredients": [
          {
            "name": "Chicken",
            "canonical_name": "Chicken",
            "ingredient_category": "Protein",
            "usda_food_description": "Chicken, broilers or fryers, meat only, cooked, roasted",
            "possible_usda_queries": [
              "Chicken meat cooked",
              "Roasted chicken meat",
              "Chicken breast cooked",
              "Cooked chicken",
              "Chicken"
            ],
            "estimated_percentage": 55,
            "estimated_weight_g": 176,
            "confidence": 0.98
          },
          {
            "name": "Tomato",
            "canonical_name": "Tomato",
            "ingredient_category": "Vegetable",
            "usda_food_description": "Tomatoes, red, ripe, raw",
            "possible_usda_queries": [
              "Tomato raw",
              "Fresh tomato",
              "Ripe tomato raw",
              "Red tomato raw",
              "Tomato"
            ],
            "estimated_percentage": 15,
            "estimated_weight_g": 48,
            "confidence": 0.9
          },
          {
            "name": "Onion",
            "canonical_name": "Onion",
            "ingredient_category": "Vegetable",
            "usda_food_description": "Onions, raw",
            "possible_usda_queries": [
              "Onion raw",
              "Red onion raw",
              "Yellow onion raw",
              "Sliced onion raw",
              "Onion"
            ],
            "estimated_percentage": 10,
            "estimated_weight_g": 32,
            "confidence": 0.88
          },
          {
            "name": "Garlic",
            "canonical_name": "Garlic",
            "ingredient_category": "Vegetable",
            "usda_food_description": "Garlic, raw",
            "possible_usda_queries": [
              "Garlic raw",
              "Fresh garlic",
              "Garlic clove raw",
              "Minced garlic raw",
              "Garlic"
            ],
            "estimated_percentage": 4,
            "estimated_weight_g": 12.8,
            "confidence": 0.86
          },
          {
            "name": "Ginger",
            "canonical_name": "Ginger",
            "ingredient_category": "Vegetable",
            "usda_food_description": "Ginger root, raw",
            "possible_usda_queries": [
              "Ginger raw",
              "Fresh ginger root",
              "Ginger root raw",
              "Minced ginger raw",
              "Ginger"
            ],
            "estimated_percentage": 3,
            "estimated_weight_g": 9.6,
            "confidence": 0.84
          },
          {
            "name": "Butter",
            "canonical_name": "Butter",
            "ingredient_category": "Dairy",
            "usda_food_description": "Butter, salted",
            "possible_usda_queries": [
              "Butter salted",
              "Butter unsalted",
              "Dairy butter",
              "Cooking butter",
              "Butter"
            ],
            "estimated_percentage": 8,
            "estimated_weight_g": 25.6,
            "confidence": 0.8
          },
          {
            "name": "Cream",
            "canonical_name": "Heavy cream",
            "ingredient_category": "Dairy",
            "usda_food_description": "Cream, heavy whipping",
            "possible_usda_queries": [
              "Heavy cream",
              "Whipping cream",
              "Cream fluid",
              "Dairy cream",
              "Cream"
            ],
            "estimated_percentage": 5,
            "estimated_weight_g": 16,
            "confidence": 0.78
          }
        ],
        "spices": [
          {
            "name": "Ground turmeric",
            "canonical_name": "Turmeric, ground",
            "usda_food_description": "Spices, turmeric, ground",
            "possible_usda_queries": [
              "Turmeric ground",
              "Turmeric powder",
              "Ground turmeric spice",
              "Turmeric spice",
              "Turmeric"
            ],
            "estimated_weight_g": 2,
            "confidence": 0.91
          },
          {
            "name": "Ground cumin",
            "canonical_name": "Cumin, ground",
            "usda_food_description": "Spices, cumin seed, ground",
            "possible_usda_queries": [
              "Cumin ground",
              "Cumin powder",
              "Ground cumin spice",
              "Cumin seed ground",
              "Cumin"
            ],
            "estimated_weight_g": 1.5,
            "confidence": 0.78
          },
          {
            "name": "Mustard seeds",
            "canonical_name": "Mustard seeds",
            "usda_food_description": "Spices, mustard seed, ground",
            "possible_usda_queries": [
              "Mustard seeds whole",
              "Yellow mustard seeds",
              "Black mustard seeds",
              "Mustard seed",
              "Mustard"
            ],
            "estimated_weight_g": 1,
            "confidence": 0.72
          },
          {
            "name": "Chili powder",
            "canonical_name": "Chili powder",
            "usda_food_description": "Spices, chili powder",
            "possible_usda_queries": [
              "Chili powder",
              "Red chili powder",
              "Ground chili",
              "Chile powder",
              "Chili"
            ],
            "estimated_weight_g": 1.5,
            "confidence": 0.83
          }
        ]
      },
      {
        "id": "food_0003",
        "name": "Lentil Curry",
        "canonical_name": "Lentil Curry",
        "ingredient_type": "Legume",
        "canonical_variants": {
          "legume": {
            "canonical_name": "Split pigeon peas",
            "confidence": 0.94
          },
          "oil": {
            "canonical_name": "Mustard oil",
            "confidence": 0.71
          }
        },
        "container": "serving_bowl",
        "category": "Mixed Dish",
        "cuisine": "Indian",
        "food_source": "Homemade",
        "brand": null,
        "role": "main",
        "served_separately": true,
        "belongs_to_food_id": null,
        "preparation": "Simmered",
        "preparation_confidence": 0.96,
        "quantity": 600,
        "quantity_confidence": 0.74,
        "unit": "g",
        "edible_fraction": 1.0,
        "detection_confidence": 0.98,
        "analysis_route": "DECOMPOSE",
        "usda_food_description": "Lentil curry",
        "possible_usda_queries": [
          "Dal tadka",
          "Indian lentil curry",
          "Yellow lentil curry",
          "Split pea curry",
          "Lentil curry"
        ],
        "ingredients": [
          {
            "name": "Split pigeon peas",
            "canonical_name": "Split pigeon peas",
            "ingredient_category": "Legume",
            "usda_food_description": "Pigeon peas, mature seeds, cooked, boiled, without salt",
            "possible_usda_queries": [
              "Split pigeon peas cooked",
              "Pigeon peas cooked",
              "Toor dal cooked",
              "Yellow split peas cooked",
              "Pigeon peas"
            ],
            "estimated_percentage": 78,
            "estimated_weight_g": 468,
            "confidence": 0.95
          },
          {
            "name": "Onion",
            "canonical_name": "Onion",
            "ingredient_category": "Vegetable",
            "usda_food_description": "Onions, raw",
            "possible_usda_queries": [
              "Onion raw",
              "Red onion raw",
              "Yellow onion raw",
              "Sliced onion raw",
              "Onion"
            ],
            "estimated_percentage": 12,
            "estimated_weight_g": 72,
            "confidence": 0.96
          },
          {
            "name": "Tomato",
            "canonical_name": "Tomato",
            "ingredient_category": "Vegetable",
            "usda_food_description": "Tomatoes, red, ripe, raw",
            "possible_usda_queries": [
              "Tomato raw",
              "Fresh tomato",
              "Ripe tomato raw",
              "Red tomato raw",
              "Tomato"
            ],
            "estimated_percentage": 10,
            "estimated_weight_g": 60,
            "confidence": 0.91
          }
        ],
        "spices": [
          {
            "name": "Ground turmeric",
            "canonical_name": "Turmeric, ground",
            "usda_food_description": "Spices, turmeric, ground",
            "possible_usda_queries": [
              "Turmeric ground",
              "Turmeric powder",
              "Ground turmeric spice",
              "Turmeric spice",
              "Turmeric"
            ],
            "estimated_weight_g": 2,
            "confidence": 0.95
          },
          {
            "name": "Ground cumin",
            "canonical_name": "Cumin, ground",
            "usda_food_description": "Spices, cumin seed, ground",
            "possible_usda_queries": [
              "Cumin ground",
              "Cumin powder",
              "Ground cumin spice",
              "Cumin seed ground",
              "Cumin"
            ],
            "estimated_weight_g": 1.5,
            "confidence": 0.84
          },
          {
            "name": "Mustard seeds",
            "canonical_name": "Mustard seeds",
            "usda_food_description": "Spices, mustard seed, ground",
            "possible_usda_queries": [
              "Mustard seeds whole",
              "Yellow mustard seeds",
              "Black mustard seeds",
              "Mustard seed",
              "Mustard"
            ],
            "estimated_weight_g": 1,
            "confidence": 0.76
          },
          {
            "name": "Chili powder",
            "canonical_name": "Chili powder",
            "usda_food_description": "Spices, chili powder",
            "possible_usda_queries": [
              "Chili powder",
              "Red chili powder",
              "Ground chili",
              "Chile powder",
              "Chili"
            ],
            "estimated_weight_g": 1,
            "confidence": 0.73
          }
        ]
      },
      {
        "id": "food_0004",
        "name": "Naan",
        "ingredient_type": null,
        "canonical_variants": {
          "legume": null,
          "oil": null
        },
        "container": "plate",
        "category": "Grain",
        "cuisine": "Indian",
        "food_source": "Homemade",
        "brand": null,
        "role": "side",
        "served_separately": false,
        "belongs_to_food_id": null,
        "preparation": "Baked",
        "preparation_confidence": 0.97,
        "quantity": 2,
        "quantity_confidence": 0.99,
        "unit": "piece",
        "edible_fraction": 1.0,
        "detection_confidence": 0.98,
        "analysis_route": "DIRECT_USDA",
        "usda_food_description": "Naan bread",
        "possible_usda_queries": [
          "Naan bread",
          "Garlic naan",
          "Indian flatbread",
          "Plain naan",
          "Leavened flatbread"
        ],
        "ingredients": [],
        "spices": []
      },
      {
        "id": "food_0005",
        "name": "Lay's Flamin' Hot Potato Chips",
        "ingredient_type": null,
        "canonical_variants": {
          "legume": null,
          "oil": null
        },
        "food_source": "Branded",
        "brand": "Lay's",
        "analysis_route": "NUTRITION_LABEL",
        "requires_back_image": true,
        "usda_food_description": null,
        "possible_usda_queries": [],
        "ingredients": [],
        "spices": []
      }
    ]
  }
}

Before returning the JSON, perform a final validation.

Requirements

- estimated_visible_food_weight_g must be greater than 0.
- estimated_visible_food_weight_g must equal the sum of all food quantities measured in grams.
- Every food object must have a unique id.
- Food ids must be sequential (food_0001, food_0002, food_0003, ...) with no gaps or skipped numbers, in the order the foods appear in the output.
- Every food object, including NUTRITION_LABEL / Branded foods, must include an id field.
- Every food must have quantity greater than 0.
- Every food must use one of the allowed units:
  g
  ml
  piece
  slice
  cup
  tbsp
  tsp
- Every food must have a preparation value.
- Every food must have preparation_confidence greater than 0.
- Every food must have detection_confidence greater than 0.
- Every DIRECT_USDA food, every DECOMPOSE ingredient, and every DECOMPOSE spice must contain exactly FIVE USDA search queries.

  The parent object of every DECOMPOSE food must contain:

  usda_food_description = null
  possible_usda_queries = []
- Every DECOMPOSE food must contain at least one ingredient.
- Every DECOMPOSE ingredient must contain canonical_name, ingredient_category, usda_food_description, possible_usda_queries, estimated_percentage, estimated_weight_g, and confidence.
- Every DECOMPOSE spice must contain canonical_name, usda_food_description, possible_usda_queries, estimated_weight_g, and confidence.
- No ingredient or spice may be named after a regional spice blend (e.g. garam masala, curry powder, tandoori masala) - decompose blends into individual spices instead.
- Every food must contain food_source.
- food_source must be exactly one of:
  Generic
  Branded
  Restaurant
  Homemade
- Ingredient estimated_percentage values for every DECOMPOSE food must sum to exactly 100.
- The sum of ingredient estimated_weight_g values for every DECOMPOSE food must equal that food's quantity in grams (spice weights are not included in this sum).
- No garnish or separately detected food may also appear as an ingredient or spice.
- Foods appearing in different containers must be returned as separate food objects.
- Every main food item (rice, roti/naan, dal, curry, vegetables, etc.) must be individually re-checked for visible toppings or spreads before finalizing - do not skip a topping on one food just because the same topping was already reported on another food.
- belongs_to_food_id may only reference an existing food id.
- belongs_to_food_id must be null unless the food is physically attached to another detected food.
- If a visible topping, spread or garnish contributes meaningful edible mass,
  it must appear as a separate food object.
- If food_source is Branded:

  - analysis_route must be NUTRITION_LABEL.
  - brand must not be null.
  - requires_back_image must be true.
  - usda_food_description may be null.
  - possible_usda_queries may be an empty list.
- If analysis_route is NUTRITION_LABEL

  - requires_back_image must be true.
  - usda_food_description must be null.
  - possible_usda_queries must be empty.
  - ingredients must be empty.
  - spices must be empty.
- Never return placeholder values such as:
  - quantity = 0
  - ""
  - []
unless they are genuinely required by the schema.
- Null values are allowed only where explicitly defined by the schema.

If any validation fails, correct the JSON before returning it.

Return ONLY valid JSON that exactly conforms to the schema.
"""

# =============================================================================
# LOW-LATENCY MEAL PROMPT
# =============================================================================
#
# The legacy prompt above is deliberately retained as a reference for the
# domain rules accumulated during development. It is not sent to Gemini: at
# roughly 49k characters it made every request expensive, including a photo
# containing one obvious food. This compact contract keeps the fields consumed
# by post_process(), food_resolver.py and the review UI without the repeated
# prose and large worked examples.
optimized_meal_prompt = """
You are Quinone's food-vision extraction engine. Inspect ONE meal photograph
and return one JSON object only. The first image is the complete photograph;
any later images are overlapping detail crops of that SAME photograph. Use the
crops to find partially covered bases and small components, but never count an
item twice because it occurs in more than one view. Do not add markdown or
commentary.

Goal: identify the physical edible items and estimate the amount actually
visible. One physical ingredient must appear once. Never return both a mixed
dish parent and the same ingredients as separate nutrition entities.

Return this shape:
{
  "meal": {
    "meal_type": "short meal description",
    "estimated_visible_food_weight_g": 0,
    "foods": [
      {
        "id": "food_0001",
        "name": "core food name",
        "canonical_name": "USDA-friendly core name",
        "ingredient_type": "Legume|Cooking Oil|null",
        "canonical_variants": {
          "legume": null,
          "oil": null
        },
        "category": "food category",
        "container": "plate|bowl|cup|wrapper|other",
        "cuisine": null,
        "food_source": "Generic|Branded|Restaurant|Homemade",
        "brand": null,
        "role": "main|side|topping|ingredient|beverage|snack",
        "served_separately": true,
        "belongs_to_food_id": null,
        "preparation": "raw/cooked/baked/fried/etc.",
        "preparation_confidence": 0.0,
        "quantity": 0,
        "quantity_confidence": 0.0,
        "unit": "g|ml|piece|slice|cup|tbsp|tsp",
        "edible_fraction": 1.0,
        "detection_confidence": 0.0,
        "analysis_route": "DIRECT_USDA|DECOMPOSE|NUTRITION_LABEL",
        "usda_food_description": "one precise USDA search phrase or null",
        "possible_usda_queries": ["at most one useful fallback"],
        "requires_back_image": false,
        "ingredients": [],
        "spices": []
      }
    ]
  }
}

Rules:
- Ignore plates, cutlery, napkins and other non-food objects.
- Build a complete visual coverage ledger before naming foods. For every
  occupied container, sweep left-to-right and top-to-bottom, then inspect all
  visible layers: dominant mass, secondary masses, fillings, mix-ins, sauces,
  spreads, toppings, garnish and beverages. Every visually distinct edible
  region must map to exactly one returned atomic food, regardless of its food
  category. A large or partly covered component must never be omitted because
  smaller, clearer components are easier to recognize.
- Reconcile the ledger before returning. The final list must cover the entire
  defensible visible edible mass, contain no duplicate/synonym/preparation
  variants, and contain no generic dish or combined-food parent when the same
  mass is already represented by its atomic components. This applies equally
  to bowls, plates, curries, sandwiches, wraps, salads, soups, drinks, desserts
  and isolated foods.
- Break foods down only as far as the photograph supports. Never invent a
  fully hidden ingredient, but never replace multiple clearly visible foods
  with one vague combined label. A prepared dish name belongs in meal_type,
  not as an extra nutrient-bearing food when its components are listed.
- Hydration-expanded staple ingredients must use their dry foundational
  reference basis when they are recovered from a prepared dish. This includes
  oats, rice, barley, quinoa, couscous, bulgur, millet, pasta/noodles,
  buckwheat, semolina/cornmeal, lentils, beans and chickpeas. Return the
  ingredient itself (not the prepared dish), preparation="dry",
  served_preparation="cooked" when applicable,
  usda_preparation_basis="dry", and
  quantity_basis="dry_ingredient_equivalent". Estimate quantity as the dry
  ingredient grams before absorbed cooking water, and request a dry/raw/
  uncooked USDA record. Never substitute an instant, ready-to-eat, fat-added,
  seasoned, sweetened or flavoured prepared product. This rule does not apply
  to meat, eggs, vegetables, bread, or other foods whose actual cooked state
  should be matched as served.
- Keep independent foods separate. A topping/spread physically attached to a
  food is a separate object with belongs_to_food_id pointing to that food.
- Never return a prepared meal name alongside its ingredients. In particular,
  if rolled oats, milk, fruit, seeds or nuts are returned, do not also return
  Oatmeal, Oatmeal Porridge or Porridge. The prepared name may be used only as
  meal_type; it is not a nutrient-bearing food object.
- Use DIRECT_USDA for an identifiable single food. Use one precise
  usda_food_description and zero or one fallback query; do not generate lists
  of near-duplicate searches.
- Set ingredient_type only for legumes and visible cooking oils/fats. For a
  legume, populate canonical_variants.legume with the specific variety and set
  oil to null. For a cooking oil, ghee or butter, populate
  canonical_variants.oil and set legume to null. Otherwise ingredient_type and
  both variants are null. Do not infer a specific variant at low confidence.
- For homemade/restaurant mixed dishes whose components cannot be represented
  as visible independent foods, use DECOMPOSE. Its quantity must be grams and
  its ingredients must cover the whole edible mass. Each ingredient object
  contains: name, canonical_name, ingredient_category,
  usda_food_description, possible_usda_queries (zero or one fallback),
  estimated_percentage, estimated_weight_g, confidence. Percentages sum to
  100 and ingredient weights sum to the parent quantity. Each spice contains:
  name, canonical_name, usda_food_description, possible_usda_queries (zero or
  one fallback), estimated_weight_g, confidence. Do not also emit the parent
  and its ingredients as separate top-level foods.
- For clearly branded packaged products use NUTRITION_LABEL, set brand,
  requires_back_image=true, usda_food_description=null,
  possible_usda_queries=[], ingredients=[], spices=[]. Do not invent printed
  nutrition values from the front package.
- Use sequential IDs in visual order. All quantities and confidence values
  must be positive. Use only the allowed units. Prefer grams or millilitres
  when the visual estimate supports them.
- estimated_visible_food_weight_g is the sum of top-level gram quantities that
  represent distinct visible masses. Do not include ml or double-count a
  DECOMPOSE parent and its ingredients.
- If nothing edible is visible, return an empty foods list and weight 0.
- Be concise: output only fields in the schema and only one USDA fallback.
"""

# =============================================================================
# LABEL EXTRACTION PROMPT
# =============================================================================
label_prompt = """
You are Nutrica's Packaged Food Analyzer.

Your task is to extract the nutrition facts from the uploaded nutrition label.

Return ONLY valid JSON.

Schema

{
  "brand": "...",

  "product_name": "...",

  "barcode": null,

  "net_weight": {
      "value": 52,
      "unit": "g"
  },

  "serving_size": {
        "value": null,
        "unit": null
    },
    
    "nutrition_basis": {
        "value": null,
        "unit": null
    },
    
    "nutrition_per_serving": {
        "energy_kcal": null,
        "protein_g": null,
        "fat_g": null,
        "saturated_fat_g": null,
        "trans_fat_g": null,
        "carbohydrate_g": null,
        "sugars_g": null,
        "added_sugars_g": null,
        "fiber_g": null,
        "sodium_mg": null,
        "cholesterol_mg": null,
        "potassium_mg": null,
        "calcium_mg": null,
        "iron_mg": null,
        "caffeine_mg": null
    },
    
    "nutrition_per_100g": {
        "energy_kcal": null,
        "protein_g": null,
        "fat_g": null,
        "saturated_fat_g": null,
        "trans_fat_g": null,
        "carbohydrate_g": null,
        "sugars_g": null,
        "added_sugars_g": null,
        "fiber_g": null,
        "sodium_mg": null,
        "cholesterol_mg": null,
        "potassium_mg": null,
        "calcium_mg": null,
        "iron_mg": null,
        "caffeine_mg": null
    },
  "ingredients": [],

  "allergens": [],

  "claims": [],

  "ocr_confidence": 0.95
}

Rules

- Read the complete Nutrition Facts panel exactly as printed.

  Extract every nutrient shown.
- Nutrition labels may be bilingual (for example English/French). Treat
  "Carbohydrate / Glucides", "Sugars / Sucres", "Sodium", etc. as the
  corresponding schema nutrients.
- If a label says something like "Per 1 can (355 mL)", store:
    serving_size.value = 355
    serving_size.unit = "ml"
  Do NOT use "can" as the serving_size unit when a gram or millilitre amount
  is printed in parentheses.
- If the label says "Per 1 bottle (500 mL)", use 500 ml by the same rule.
- If a servings-per-container count is explicitly printed, store it in
  servings_per_container. Otherwise use null.

  Do not infer or calculate missing nutrients.

  If both "per serving" and "per 100 g" are present,
  return BOTH.
- Never estimate values.
- Missing values must be null.
- Use the exact field names shown in the schema.
- For beverages, values printed per 100 mL belong in nutrition_per_100g,
  but nutrition_basis.unit MUST be "ml".
- Never convert beverage millilitres to grams.
- If both "per serving" and "per 100 g/ml" are present, return BOTH.
- Set nutrition_basis.value to the printed reference quantity, usually 100.
- Set nutrition_basis.unit to "g" or "ml" exactly as printed.
- Return each ingredient as a separate string in the ingredients list.
- Preserve the printed ingredient order.
- Extract allergens and claims when visible.
- Do not calculate per-serving or per-100 values when they are not printed.
- Return valid JSON only.
"""

# =============================================================================
# CLASSIFIER PROMPT
# =============================================================================
classify_prompt = """
Classify this nutrition-app image as NUTRITION_LABEL or FOOD.

Choose NUTRITION_LABEL whenever readable printed nutrition quantities,
Nutrition Facts/Nutritional Information, serving information, values per
100 g/ml, OR a printed ingredients list appears anywhere in the image.

The image may show the entire back of a pouch, bottle, box, wrapper or can. It
does not need to be tightly cropped. The label may occupy only one part of the
frame, be angled or rotated, and appear beside branding, product artwork,
directions, legal text or a barcode. Readable label evidence takes priority.

Choose FOOD for a prepared meal, loose ingredients, or a front-only package
without readable nutrition/ingredient information.

Return exactly one token and nothing else: NUTRITION_LABEL or FOOD.
"""

# =============================================================================
# HELPERS
# =============================================================================
def similarity(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def prepare_image_for_model(
    image: Image.Image,
    *,
    max_edge: int,
) -> Image.Image:
    """Auto-orient and downscale an image without mutating the caller's copy."""
    prepared = ImageOps.exif_transpose(image)
    if prepared.mode != "RGB":
        prepared = prepared.convert("RGB")
    else:
        prepared = prepared.copy()

    width, height = prepared.size
    longest_edge = max(width, height)
    if longest_edge > max_edge:
        scale = max_edge / float(longest_edge)
        prepared = prepared.resize(
            (
                max(1, round(width * scale)),
                max(1, round(height * scale)),
            ),
            Image.Resampling.LANCZOS,
        )
    return prepared


def _label_detail_views(image: Image.Image) -> list[Image.Image]:
    """Return the complete package photo plus enlarged overlapping regions."""
    prepared = prepare_image_for_model(
        image,
        max_edge=LABEL_IMAGE_MAX_EDGE,
    )
    width, height = prepared.size
    if width < 500 or height < 500:
        return [prepared]

    x_mid = width // 2
    y_mid = height // 2
    overlap_x = max(30, round(width * 0.10))
    overlap_y = max(30, round(height * 0.10))
    boxes = [
        (0, 0, min(width, x_mid + overlap_x), min(height, y_mid + overlap_y)),
        (max(0, x_mid - overlap_x), 0, width, min(height, y_mid + overlap_y)),
        (0, max(0, y_mid - overlap_y), min(width, x_mid + overlap_x), height),
        (
            max(0, x_mid - overlap_x),
            max(0, y_mid - overlap_y),
            width,
            height,
        ),
    ]
    return [prepared, *(prepared.crop(box) for box in boxes)]


def _generate_plain_meal_json(
    image: Image.Image,
    *,
    image_index: int,
) -> dict[str, Any]:
    """Generate meal JSON without the failing nested SDK response schema."""
    last_error: Exception | None = None
    views = _meal_inventory_views(image)
    for attempt in range(1, GEMINI_JSON_MAX_ATTEMPTS + 1):
        if attempt == GEMINI_JSON_MAX_ATTEMPTS:
            # Compatibility fallback: this is the original full prompt from
            # the working engine, with no response schema/config attached.
            instruction = prompt
        elif attempt == 1:
            instruction = optimized_meal_prompt
        else:
            instruction = (
                f"{optimized_meal_prompt}\n\n"
                "Return one COMPLETE valid JSON object. Keep names, evidence "
                "and USDA queries concise so the response cannot be truncated."
            )

        started = time.perf_counter()
        try:
            response = client.models.generate_content(
                model=GEMINI_MEAL_MODEL,
                contents=[instruction, *views],
            )
            result = parse_model_json(response.text or "")
            _validate_model_contract(
                result,
                SIMPLE_MEAL_RESPONSE_JSON_SCHEMA,
            )
            logger.info(
                "Gemini meal image %d completed in %.1f ms on attempt %d",
                image_index,
                (time.perf_counter() - started) * 1000,
                attempt,
            )
            return result
        except Exception as error:
            last_error = error
            logger.warning(
                "Gemini plain meal image %d failed on attempt %d/%d: %s",
                image_index,
                attempt,
                GEMINI_JSON_MAX_ATTEMPTS,
                error,
            )

    raise ModelJSONResponseError(
        "Meal detection failed after compact and original-prompt retries."
    ) from last_error


def _generate_json(
    *,
    model: str,
    instruction: str,
    image: Any,
    config: dict[str, Any],
    operation: str,
) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, GEMINI_JSON_MAX_ATTEMPTS + 1):
        started = time.perf_counter()
        retry_instruction = instruction
        retry_config = dict(config)

        if attempt > 1:
            if (
                config.get("response_json_schema") is MEAL_RESPONSE_JSON_SCHEMA
                or config.get("response_json_schema")
                is SIMPLE_MEAL_RESPONSE_JSON_SCHEMA
            ):
                retry_instruction = (
                    "Inspect this meal image and return its nutrient-bearing "
                    "core foods. Return ingredients such as rolled oats, milk, "
                    "fruit, nuts, and seeds—not a parent name such as oatmeal. "
                    "Use DIRECT_USDA for ordinary foods. Use NUTRITION_LABEL "
                    "only for clearly branded packaged foods. Keep every name "
                    "and USDA description short."
                )
                retry_config["response_json_schema"] = (
                    SIMPLE_MEAL_RESPONSE_JSON_SCHEMA
                )
                retry_config["max_output_tokens"] = min(
                    int(retry_config.get("max_output_tokens", 8192)),
                    3072,
                )
            elif (
                config.get("response_json_schema")
                is ATOMIC_MEAL_INVENTORY_JSON_SCHEMA
            ):
                retry_instruction = (
                    "Re-inspect every supplied view of this one meal. Return "
                    "the complete atomic food inventory required by the "
                    "schema. Each item must be one ingredient only. Split "
                    "combined dishes into visually supportable ingredients; "
                    "never include a dish parent, never join names with and, "
                    "slash or ampersand, and never repeat an ingredient."
                )
                retry_config["max_output_tokens"] = min(
                    int(retry_config.get("max_output_tokens", 6144)),
                    4096,
                )
            else:
                retry_instruction = (
                    f"{instruction}\n\n"
                    "Read the label again and return every field required by "
                    "the supplied schema. Keep text fields concise."
                )

        try:
            images = list(image) if isinstance(image, (list, tuple)) else [image]
            response = client.models.generate_content(
                model=model,
                contents=[retry_instruction, *images],
                config=retry_config,
            )
        except Exception as error:
            last_error = error
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            logger.warning(
                "Gemini %s request failed on attempt %d/%d "
                "(elapsed_ms=%.1f): %s",
                operation,
                attempt,
                GEMINI_JSON_MAX_ATTEMPTS,
                elapsed_ms,
                error,
            )
            continue
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        response_text = response.text or ""

        try:
            result = parse_model_json(response_text)
            _validate_model_contract(
                result,
                retry_config.get("response_json_schema"),
            )
        except (json.JSONDecodeError, ValueError) as error:
            last_error = error
            finish_reason = _model_finish_reason(response)
            logger.warning(
                "Gemini %s returned invalid JSON on attempt %d/%d "
                "(elapsed_ms=%.1f, chars=%d, finish_reason=%s): %s",
                operation,
                attempt,
                GEMINI_JSON_MAX_ATTEMPTS,
                elapsed_ms,
                len(response_text),
                finish_reason,
                error,
            )
            continue

        logger.info(
            "Gemini %s completed in %.1f ms on attempt %d",
            operation,
            elapsed_ms,
            attempt,
        )
        return result

    raise ModelJSONResponseError(
        "The AI could not complete a structured analysis response. "
        "Please retry the same image."
    ) from last_error


def _validate_model_contract(
    result: dict[str, Any],
    schema: Any,
) -> None:
    """Defensive validation in case an SDK/model ignores response schema."""
    if (
        schema is MEAL_RESPONSE_JSON_SCHEMA
        or schema is SIMPLE_MEAL_RESPONSE_JSON_SCHEMA
    ):
        meal = result.get("meal")
        if not isinstance(meal, dict):
            raise ValueError("The AI response did not contain a meal object.")
        foods = meal.get("foods")
        if not isinstance(foods, list):
            raise ValueError("The AI response did not contain a foods array.")
        for food in foods:
            if not isinstance(food, dict):
                raise ValueError("The AI returned an invalid food item.")
            if not str(food.get("name") or "").strip():
                raise ValueError("The AI returned a food without a name.")
            try:
                quantity = float(food.get("quantity"))
            except (TypeError, ValueError) as error:
                raise ValueError("The AI returned an invalid food quantity.") from error
            if quantity <= 0:
                raise ValueError("The AI returned a non-positive food quantity.")
        return

    if schema is LABEL_RESPONSE_JSON_SCHEMA:
        if not str(result.get("product_name") or "").strip():
            raise ValueError("The AI response did not identify the product.")
        if not any(
            isinstance(result.get(key), dict)
            for key in ("nutrition_per_serving", "nutrition_per_100g")
        ):
            raise ValueError("The AI response did not contain label nutrition.")

    if schema is ATOMIC_MEAL_INVENTORY_JSON_SCHEMA:
        import re

        items = result.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("The AI returned an empty food inventory.")
        identities: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("The AI returned an invalid inventory item.")
            name = str(item.get("name") or "").strip()
            canonical = str(item.get("canonical_name") or name).strip()
            if not name or not canonical:
                raise ValueError("The AI returned an unnamed inventory item.")
            if re.search(r"\s(?:and|&)\s|/", canonical, re.IGNORECASE):
                raise ValueError(
                    f"The AI returned a combined food item: {canonical}."
                )
            identity = _identity_text(canonical)
            if not identity or identity in identities:
                raise ValueError(
                    f"The AI returned a repeated food item: {canonical}."
                )
            identities.add(identity)
            try:
                quantity = float(item.get("quantity"))
                confidence = float(item.get("confidence"))
            except (TypeError, ValueError) as error:
                raise ValueError("The AI returned invalid inventory values.") from error
            if quantity <= 0 or not 0 <= confidence <= 1:
                raise ValueError("The AI returned invalid inventory measurements.")


def _model_finish_reason(response: Any) -> str:
    """Read finish metadata defensively without depending on one SDK shape."""
    try:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return "unknown"
        reason = getattr(candidates[0], "finish_reason", None)
        return str(reason or "unknown")
    except Exception:
        return "unknown"


def classify_image(client, image):
    """Route a full image without using structured JSON output."""
    last_error: Exception | None = None
    views = _label_detail_views(image)
    for attempt in range(1, 3):
        try:
            response = client.models.generate_content(
                model=GEMINI_MEAL_MODEL,
                contents=[classify_prompt, *views],
                config={
                    "temperature": 0.0,
                    "max_output_tokens": 128,
                },
            )
            decision = str(response.text or "").strip().upper()
            decision = decision.replace("-", "_").replace(" ", "_")
            if "NUTRITION_LABEL" in decision or decision == "LABEL":
                return {
                    "type": "nutrition_label",
                    "confidence": 1.0,
                    "reason": "readable printed label information",
                }
            if decision == "FOOD" or decision.endswith("_FOOD"):
                return {
                    "type": "food",
                    "confidence": 1.0,
                    "reason": "meal or food image",
                }
            raise ValueError(f"Unsupported route token: {decision[:80]}")
        except Exception as error:
            last_error = error
            logger.warning(
                "Image route classification failed on attempt %d/2: %s",
                attempt,
                error,
            )

    # Unknown is deliberately non-fatal. analyze_meal performs a strict label
    # probe and then safely falls through to ordinary meal detection.
    return {
        "type": "unknown",
        "confidence": 0.0,
        "reason": f"classification unavailable: {last_error}",
    }


def _coerce_optional_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if not cleaned or cleaned.lower() in {"null", "none", "n/a", "na"}:
            return None
        if cleaned.startswith("<"):
            cleaned = cleaned[1:].strip()
        value = cleaned
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalize_label_result(label: dict[str, Any]) -> dict[str, Any]:
    """Restore a stable downstream label shape without inventing values."""
    normalized = dict(label)
    normalized.pop("is_nutrition_label", None)
    normalized["brand"] = normalized.get("brand") or None
    normalized["product_name"] = str(
        normalized.get("product_name")
        or normalized.get("brand")
        or "Packaged Food"
    ).strip()
    normalized["barcode"] = normalized.get("barcode") or None
    for key in ("net_weight", "serving_size", "nutrition_basis"):
        quantity = normalized.get(key)
        if not isinstance(quantity, dict):
            quantity = {}
        normalized[key] = {
            "value": _coerce_optional_number(quantity.get("value")),
            "unit": quantity.get("unit"),
        }
    normalized["servings_per_container"] = _coerce_optional_number(
        normalized.get("servings_per_container")
    )
    for key in ("nutrition_per_serving", "nutrition_per_100g"):
        supplied = normalized.get(key)
        if not isinstance(supplied, dict):
            supplied = {}
        normalized[key] = {
            nutrient: _coerce_optional_number(supplied.get(nutrient))
            for nutrient in _LABEL_NUTRIENT_PROPERTIES
        }
    for key in ("ingredients", "allergens", "claims"):
        values = normalized.get(key)
        normalized[key] = (
            [
                str(value).strip()
                for value in values
                if value is not None and str(value).strip()
            ]
            if isinstance(values, list)
            else []
        )
    try:
        normalized["ocr_confidence"] = max(
            0.0,
            min(1.0, float(normalized.get("ocr_confidence") or 0.0)),
        )
    except (TypeError, ValueError):
        normalized["ocr_confidence"] = 0.0
    return normalized


def _label_contains_evidence(label: dict[str, Any]) -> bool:
    for key in ("nutrition_per_serving", "nutrition_per_100g"):
        nutrients = label.get(key)
        if isinstance(nutrients, dict) and any(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            for value in nutrients.values()
        ):
            return True
    ingredients = label.get("ingredients")
    return isinstance(ingredients, list) and any(
        str(item or "").strip() for item in ingredients
    )


def extract_label(client, image):
    """Extract a full package label without forcing an SDK response schema."""
    views = _label_detail_views(image)
    last_error: Exception | None = None
    base_instruction = (
        "The first image is the user's complete package photograph and all "
        "later images are enlarged crops of that SAME photograph. Combine "
        "readable evidence across them. If no printed nutrition quantities "
        "and no printed ingredients list are readable, return exactly "
        '{"is_nutrition_label": false}. Otherwise set '
        '"is_nutrition_label": true and return the requested label JSON.\n\n'
        f"{label_prompt}"
    )

    for attempt in range(1, GEMINI_JSON_MAX_ATTEMPTS + 1):
        instruction = base_instruction
        if attempt > 1:
            instruction = (
                f"{base_instruction}\n\n"
                "Your previous output was incomplete. Return one complete JSON "
                "object only. Exclude addresses, directions, legal paragraphs "
                "and marketing copy. Keep ingredient names concise."
            )
        try:
            response = client.models.generate_content(
                model=GEMINI_LABEL_MODEL,
                contents=[instruction, *views],
            )
            raw = parse_model_json(response.text or "")
            if raw.get("is_nutrition_label") is False:
                raise ValueError(
                    "No readable nutrition table or ingredients list was found."
                )
            result = _normalize_label_result(raw)
            if not _label_contains_evidence(result):
                raise ValueError(
                    "The label response contained no printed nutrition or ingredients."
                )
            return result
        except Exception as error:
            last_error = error
            logger.warning(
                "Back-label extraction failed on attempt %d/%d: %s",
                attempt,
                GEMINI_JSON_MAX_ATTEMPTS,
                error,
            )

    raise ModelJSONResponseError(
        "The nutrition label could not be read after retries."
    ) from last_error


def _meal_inventory_views(image: Image.Image) -> list[Image.Image]:
    """Return a full view plus overlapping detail crops of the same meal."""
    width, height = image.size
    # The reported missed-oats image is 598x442. The former 640px cutoff sent
    # only the full frame, even though a focused bowl crop materially improves
    # recognition of the partially covered base. Avoid crops only when the
    # source is genuinely too small to provide useful local detail.
    if width < 320 or height < 320:
        return [image]

    x_mid = width // 2
    y_mid = height // 2
    overlap_x = max(40, round(width * 0.08))
    overlap_y = max(40, round(height * 0.08))
    boxes = [
        (0, 0, min(width, x_mid + overlap_x), min(height, y_mid + overlap_y)),
        (max(0, x_mid - overlap_x), 0, width, min(height, y_mid + overlap_y)),
        (0, max(0, y_mid - overlap_y), min(width, x_mid + overlap_x), height),
        (max(0, x_mid - overlap_x), max(0, y_mid - overlap_y), width, height),
    ]
    return [image, *(image.crop(box) for box in boxes)]


def _atomic_inventory_food(
    item: dict[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    name = str(item.get("name") or "").strip()
    canonical_name = str(item.get("canonical_name") or name).strip()
    identity = _identity_text(canonical_name or name)
    served_preparation = str(
        item.get("served_preparation")
        or item.get("preparation")
        or "unknown"
    )

    quantity = float(item.get("quantity"))
    confidence = max(0.0, min(float(item.get("confidence")), 1.0))
    route = str(item.get("analysis_route") or "DIRECT_USDA")
    is_label = route == "NUTRITION_LABEL"
    usda_description = item.get("usda_food_description")
    if not is_label and not str(usda_description or "").strip():
        usda_description = canonical_name

    food = {
        "id": f"audited_food_{index:04d}",
        "name": name,
        "canonical_name": canonical_name,
        "ingredient_type": None,
        "canonical_variants": {"legume": None, "oil": None},
        "category": str(item.get("category") or "Food"),
        "container": str(item.get("container") or "other"),
        "cuisine": None,
        "food_source": str(item.get("food_source") or "Generic"),
        "brand": item.get("brand"),
        "role": str(item.get("role") or "ingredient"),
        "served_separately": True,
        "belongs_to_food_id": None,
        "preparation": str(item.get("preparation") or "unknown"),
        "served_preparation": served_preparation,
        "usda_preparation_basis": item.get("usda_preparation_basis"),
        "quantity_basis": item.get("quantity_basis") or "as_served",
        "preparation_confidence": confidence,
        "quantity": round(quantity, 3),
        "quantity_confidence": confidence,
        "unit": str(item.get("unit") or "g"),
        "edible_fraction": 1.0,
        "detection_confidence": confidence,
        "analysis_route": route,
        "usda_food_description": None if is_label else str(usda_description),
        "possible_usda_queries": [] if is_label else [canonical_name],
        "requires_back_image": bool(item.get("requires_back_image")) if is_label else False,
        "ingredients": [],
        "spices": [],
        "recovered_by": "complete_atomic_inventory_audit",
        "visual_evidence": str(item.get("visual_evidence") or ""),
    }
    _enforce_core_reference_basis(food)
    return food


def _audit_and_correct_complete_food_inventory(
    image: Image.Image,
    result: dict[str, Any],
    *,
    image_index: int,
) -> dict[str, Any]:
    """Recover omissions with a compact, schema-free second visual pass.

    The previous auditor forced a large SDK response schema, which could make
    the entire analysis fail. This pass requests a small JSON object in the
    prompt, retries locally, and is still non-fatal to the primary result.
    """
    provisional_foods = result.get("meal", {}).get("foods", [])
    provisional = []
    for food in provisional_foods if isinstance(provisional_foods, list) else []:
        if not isinstance(food, dict):
            continue
        provisional.append({
            "name": food.get("name"),
            "canonical_name": food.get("canonical_name"),
            "quantity": food.get("quantity"),
            "unit": food.get("unit"),
            "route": food.get("analysis_route"),
        })

    audit_instruction = (
        "You are the final completeness auditor for one meal photograph. The "
        "first image is the full meal; any additional images are overlapping "
        "detail crops of that same meal and must never create duplicates. "
        f"The provisional detector returned: {json.dumps(provisional)}. Treat "
        "that list only as a checklist: preserve items verified in the image, "
        "remove false positives, and recover every missed edible component.\n\n"
        "Build a visual coverage ledger for every container: sweep left-to-right "
        "and top-to-bottom, then inspect every visible layer and region, including "
        "dominant and secondary masses, fillings, mix-ins, spreads, sauces, "
        "toppings, garnishes and beverages. Every defensible visible edible "
        "region must map to exactly one returned item, regardless of food category. "
        "Return ONE flat inventory of atomic nutrient-bearing foods. Split "
        "sandwiches into bread/fillings/spreads, salads into their visible "
        "ingredients, bowls into base/mix-ins/toppings, and mixed dishes into "
        "the smallest ingredients the visual evidence can support. Never "
        "return the complete dish or meal parent when its ingredients are "
        "listed. Never join two foods in one item. Never repeat the same "
        "ingredient because it appears in multiple crops or locations, has a "
        "synonym, or has both a prepared and ingredient name; aggregate its "
        "mass into one item unless the foods are different branded products. "
        "A prepared dish name is not an extra food when its constituent "
        "ingredients are present. Before returning, reconcile the coverage ledger: "
        "(1) no visible edible region may be unrepresented; (2) no physical food "
        "may appear twice through a synonym, prepared name, crop, or combined parent; "
        "and (3) no vague combined label may remain when the image supports its "
        "individual foods. Apply these rules to every food type, not a preset list. "
        "For hydration-expanded staple bases such "
        "as oats, rice, barley, quinoa, couscous, bulgur, millet, pasta, "
        "noodles, buckwheat, semolina, cornmeal, lentils, beans or chickpeas, "
        "return the dry foundational ingredient and estimate its dry grams "
        "before absorbed cooking water. Set preparation='dry', preserve the "
        "observed state in served_preparation, set usda_preparation_basis="
        "'dry' and quantity_basis='dry_ingredient_equivalent', and request a "
        "dry/raw/uncooked USDA record. Never select an instant, ready-to-eat, "
        "fat-added, seasoned, sweetened or flavoured prepared variant. Do not "
        "apply this conversion to meat, eggs, vegetables, bread, or ordinary "
        "foods whose cooked state should be matched as served.\n\n"
        "Do not fabricate an ingredient that is fully hidden and has no "
        "defensible visual evidence. When exact seasoning cannot be seen, do "
        "not guess it. Quantities must represent each ingredient's own edible "
        "mass so totals do not double count. Use DIRECT_USDA for generic "
        "ingredients and NUTRITION_LABEL only for a clearly branded packaged "
        "product. Return only one JSON object in this exact compact shape: "
        '{"meal_type":"...","items":[{"name":"...",'
        '"canonical_name":"...","category":"...","container":"...",'
        '"role":"...","food_source":"Generic","brand":null,'
        '"quantity":1,"unit":"g","preparation":"...",'
        '"served_preparation":"...","usda_preparation_basis":"...",'
        '"quantity_basis":"as_served|dry_ingredient_equivalent",'
        '"confidence":0.8,"analysis_route":"DIRECT_USDA",'
        '"usda_food_description":"...","requires_back_image":false,'
        '"visual_evidence":"..."}]}. '
        "The items list is the complete corrected inventory, not merely the "
        "newly found foods. Keep text concise."
    )
    views = _meal_inventory_views(image)
    audited: dict[str, Any] | None = None
    last_error: Exception | None = None
    for attempt in range(1, 3):
        instruction = audit_instruction
        if attempt > 1:
            instruction = (
                f"{audit_instruction}\n\nYour previous response was invalid or "
                "incomplete. Return the complete compact JSON object only."
            )
        try:
            response = client.models.generate_content(
                model=GEMINI_MEAL_MODEL,
                contents=[instruction, *views],
            )
            candidate = parse_model_json(response.text or "")
            _validate_model_contract(
                candidate,
                ATOMIC_MEAL_INVENTORY_JSON_SCHEMA,
            )
            audited = candidate
            break
        except Exception as error:
            last_error = error
            logger.warning(
                "Compact inventory audit image %d failed on attempt %d/2: %s",
                image_index,
                attempt,
                error,
            )

    if audited is None:
        raise ModelJSONResponseError(
            "The compact inventory audit could not return valid JSON."
        ) from last_error

    items = audited.get("items", [])
    audited_foods = [
        _atomic_inventory_food(item, index=index)
        for index, item in enumerate(items, start=1)
        if isinstance(item, dict)
    ]

    # A successful audit returns the complete corrected inventory, not a list
    # of additions. Treating every omitted provisional item as mandatory used
    # to re-introduce false positives and combined-dish parents that the audit
    # had explicitly removed. If the audit fails validation it is discarded
    # before this point and the untouched primary result remains the fallback.
    foods = list(audited_foods)

    primary_identities = {
        _canonical_food_identity(food)
        for food in provisional_foods
        if isinstance(food, dict)
    }
    recovered = [
        food.get("name")
        for food in audited_foods
        if _canonical_food_identity(food) not in primary_identities
    ]
    logger.info(
        "Complete inventory audit image=%d provisional=%s corrected=%s recovered=%s",
        image_index,
        [entry.get("name") for entry in provisional],
        [food.get("name") for food in foods],
        recovered,
    )
    return {
        "meal": {
            "meal_type": str(audited.get("meal_type") or "Mixed"),
            "estimated_visible_food_weight_g": sum(
                float(food.get("quantity", 0) or 0)
                for food in foods
                if food.get("unit") == "g"
            ),
            "foods": foods,
        },
    }


def _should_audit_complete_food_inventory(result: dict[str, Any]) -> bool:
    """Audit any draft whose own structure suggests incomplete coverage.

    Isolated main foods avoid a second model call. Compound meals and drafts
    containing only sides/toppings/ingredients receive the universal visual
    ledger audit, independent of any particular cuisine or food name.
    """
    meal = result.get("meal")
    if not isinstance(meal, dict):
        return False
    foods = meal.get("foods")
    if not isinstance(foods, list):
        return False
    valid_foods = [food for food in foods if isinstance(food, dict)]
    if len(valid_foods) >= 2:
        return True
    if any(food.get("analysis_route") == "DECOMPOSE" for food in valid_foods):
        return True
    meal_type = _identity_text(meal.get("meal_type"))
    if any(
        token in meal_type
        for token in (
            "mixed", "bowl", "plate", "salad", "sandwich", "wrap",
            "burger", "curry", "stew", "soup", "porridge", "meal",
            "platter", "dessert",
        )
    ):
        return True
    if not valid_foods:
        return False
    roles = {
        str(food.get("role") or "").lower().strip()
        for food in valid_foods
    }
    return not roles or roles.isdisjoint({"main", "beverage", "snack"})


SEPARATORS = ["/", "&", ",", " and "]


def split_entry_by_name(entry):
    names = [entry.get("name", "")]
    for sep in SEPARATORS:
        temp = []
        for n in names:
            temp.extend(n.split(sep))
        names = temp

    split_entries = []
    for n in names:
        n = n.strip()
        if n:
            new_entry = copy.deepcopy(entry)
            new_entry["name"] = n
            split_entries.append(new_entry)
    return split_entries


def is_combinable(food):
    return food.get("belongs_to_food_id") is not None


def attach_label_to_food(
    food: dict[str, Any],
    label: dict[str, Any],
) -> None:
    """
    Attach a successfully extracted package label.

    Printed label ingredients are descriptive only.
    They must not enter the USDA ingredient pipeline.
    """

    if not isinstance(label, dict):
        raise ValueError(
            "The extracted nutrition label is invalid."
        )

    food["nutrition_label"] = label
    food["requires_back_image"] = False
    food["back_image_received"] = True

    raw_ingredients = label.get("ingredients")

    food["label_ingredients"] = (
        [
            str(item).strip()
            for item in raw_ingredients
            if str(item).strip()
        ]
        if isinstance(raw_ingredients, list)
        else []
    )

    # Important:
    # NUTRITION_LABEL foods must not contain recipe ingredients.
    food["ingredients"] = []
    food["spices"] = []

    raw_allergens = label.get("allergens")
    food["allergens"] = (
        raw_allergens
        if isinstance(raw_allergens, list)
        else []
    )

    raw_claims = label.get("claims")
    food["claims"] = (
        raw_claims
        if isinstance(raw_claims, list)
        else []
    )
    
def create_food_from_label(label):
    """Create a proper food object when only a nutrition label was uploaded."""
    brand = label.get("brand") or None
    product_name = label.get("product_name") or "Packaged Food"

    # Try to get a reasonable quantity from net_weight
    net = label.get("net_weight") or {}
    qty = net.get("value")
    unit = (net.get("unit") or "g").lower()

    if qty is None or qty <= 0:
        # Fallback: try serving size, otherwise default to 1 piece
        serving = label.get("serving_size") or {}
        qty = serving.get("value") or 1
        unit = (serving.get("unit") or "piece").lower()

    # Normalize unit
    unit_map = {
        "gram": "g", "grams": "g", "g": "g",
        "milliliter": "ml", "milliliters": "ml", "ml": "ml",
        "liter": "l", "liters": "l", "l": "l",
        "piece": "piece", "pieces": "piece",
        "slice": "slice", "slices": "slice"
    }
    unit = unit_map.get(unit, "g")

    # Simple category guess
    name_lower = product_name.lower()
    if any(w in name_lower for w in ["cola", "pepsi", "soda", "juice", "water", "drink", "beverage", "tea", "coffee"]):
        category = "Beverage"
        role = "drink"
    elif any(w in name_lower for w in ["chip", "cookie", "biscuit", "snack", "namkeen", "cracker"]):
        category = "Snack"
        role = "snack"
    elif any(w in name_lower for w in ["chocolate", "candy", "bar", "dessert", "ice cream"]):
        category = "Dessert"
        role = "dessert"
    else:
        category = "Unknown"
        role = "main"

    food = {
        "id": "food_0001",  # will be renumbered later
        "name": product_name,
        "ingredient_type": None,
        "canonical_variants": {
            "legume": None,
            "oil": None
        },
        "container": "unknown",
        "category": category,
        "cuisine": "Unknown",
        "food_source": "Branded",
        "brand": brand,
        "role": role,
        "served_separately": True,
        "belongs_to_food_id": None,
        "preparation": "Unknown",
        "preparation_confidence": 0.5,
        "quantity": float(qty) if qty else 1.0,
        "quantity_confidence": 0.85,
        "unit": unit,
        "edible_fraction": 1.0,
        "detection_confidence": 0.95,
        # "analysis_route": "NUTRITION_LABEL",
        # # "requires_back_image": False,
        # "requires_back_image": True,
        # "back_image_received": True,          
        # "usda_food_description": None,
        # "possible_usda_queries": [],
        # "ingredients": [],
        # "spices": [],
        # "nutrition_label": label
        "analysis_route": "NUTRITION_LABEL",
        "requires_back_image": False,
        "back_image_received": True,
        "usda_food_description": None,
        "possible_usda_queries": [],
        "ingredients": [],
        "spices": [],
        "nutrition_label": label,
        "label_ingredients": (
            label.get("ingredients")
            if isinstance(
                label.get("ingredients"),
                list,
            )
            else []
        ),
        "allergens": (
            label.get("allergens")
            if isinstance(
                label.get("allergens"),
                list,
            )
            else []
        ),
        "claims": (
            label.get("claims")
            if isinstance(
                label.get("claims"),
                list,
            )
            else []
        ),
    }
    attach_label_to_food(
        food=food,
        label=label,
    )
    return food

def namespace_food_ids(
    foods: list[dict[str, Any]],
    image_index: int,
) -> list[dict[str, Any]]:
    """
    Give every food a temporary unique ID before combining
    results from multiple images.
    """

    id_mapping: dict[str, str] = {}

    for food_index, food in enumerate(
        foods,
        start=1,
    ):
        old_id = food.get("id")

        temporary_id = (
            f"image_{image_index:04d}_"
            f"food_{food_index:04d}"
        )

        if isinstance(old_id, str):
            id_mapping[old_id] = temporary_id

        food["id"] = temporary_id

    for food in foods:
        parent_id = food.get(
            "belongs_to_food_id"
        )

        if isinstance(parent_id, str):
            food["belongs_to_food_id"] = (
                id_mapping.get(
                    parent_id,
                    parent_id,
                )
            )

    return foods


# def post_process(result):
#     """Normalize units, split combined names, merge repeated toppings,
#     re-number ALL ids sequentially from food_0001, recompute total weight."""
#     if "meal" not in result or "foods" not in result["meal"]:
#         return result

#     foods = result["meal"]["foods"]

#     # Normalize units
#     UNIT_MAP = {
#         "gram": "g", "grams": "g", "g": "g",
#         "kilogram": "kg", "kilograms": "kg", "kg": "kg",
#         "milliliter": "ml", "milliliters": "ml", "ml": "ml",
#         "liter": "l", "liters": "l", "l": "l",
#         "pieces": "piece", "piece": "piece",
#         "slices": "slice", "slice": "slice",
#         "cups": "cup", "cup": "cup",
#         "tablespoon": "tbsp", "tbsp": "tbsp",
#         "teaspoon": "tsp", "tsp": "tsp"
#     }

#     for food in foods:
#         unit = food.get("unit", "g")
#         food["unit"] = UNIT_MAP.get(str(unit).lower().strip(), str(unit).lower().strip())

#     # Split combined ingredient / spice names
#     for food in foods:
#         new_ingredients = []
#         for ingredient in food.get("ingredients", []):
#             new_ingredients.extend(split_entry_by_name(ingredient))
#         food["ingredients"] = new_ingredients

#         new_spices = []
#         for spice in food.get("spices", []):
#             new_spices.extend(split_entry_by_name(spice))
#         food["spices"] = new_spices

#     # Combine repeated toppings/spreads that belong to different parents
#     final_foods = []

#     for food in foods:
#         if not is_combinable(food):
#             final_foods.append(food)
#             continue

#         merged_into_existing = False

#         for existing in final_foods:
#             if (existing.get("belongs_to_food_id") is not None
#                     and existing.get("unit") == food.get("unit")
#                     and similarity(existing.get("name", ""), food.get("name", "")) > 0.92):

#                 if "components" not in existing:
#                     first_component = {
#                         "id": existing["id"],
#                         "container": existing.get("container"),
#                         "belongs_to_food_id": existing.get("belongs_to_food_id"),
#                         "quantity": existing["quantity"],
#                         "unit": existing["unit"],
#                         "quantity_confidence": existing.get("quantity_confidence"),
#                         "detection_confidence": existing.get("detection_confidence"),
#                     }
#                     existing["components"] = [first_component]
#                     existing["is_combined"] = True

#                 existing["components"].append({
#                     "id": food["id"],
#                     "container": food.get("container"),
#                     "belongs_to_food_id": food.get("belongs_to_food_id"),
#                     "quantity": food["quantity"],
#                     "unit": food["unit"],
#                     "quantity_confidence": food.get("quantity_confidence"),
#                     "detection_confidence": food.get("detection_confidence"),
#                 })

#                 existing["quantity"] += food["quantity"]
#                 existing["total_quantity"] = existing["quantity"]

#                 existing_parents = {c["belongs_to_food_id"] for c in existing["components"]}
#                 existing["belongs_to_food_id"] = (
#                     existing["components"][0]["belongs_to_food_id"]
#                     if len(existing_parents) == 1
#                     else list(existing_parents)
#                 )

#                 merged_into_existing = True
#                 break

#         if not merged_into_existing:
#             final_foods.append(food)

#     for food in final_foods:
#         food.setdefault("is_combined", False)
#         food.setdefault("components", None)
#         food.setdefault("total_quantity", food.get("quantity", 0))

#     # Re-number ALL ids sequentially across the entire merged list
#     id_mapping = {}
#     for idx, food in enumerate(final_foods, start=1):
#         old_id = food.get("id")
#         new_id = f"food_{idx:04d}"
#         if old_id:
#             id_mapping[old_id] = new_id
#         food["id"] = new_id

#     for food in final_foods:
#         belongs_to = food.get("belongs_to_food_id")
#         if isinstance(belongs_to, list):
#             food["belongs_to_food_id"] = [id_mapping.get(b, b) for b in belongs_to]
#         elif isinstance(belongs_to, str):
#             food["belongs_to_food_id"] = id_mapping.get(belongs_to, belongs_to)

#         for component in (food.get("components") or []):
#             if component.get("id") in id_mapping:
#                 component["id"] = id_mapping[component["id"]]
#             comp_belongs_to = component.get("belongs_to_food_id")
#             if isinstance(comp_belongs_to, str) and comp_belongs_to in id_mapping:
#                 component["belongs_to_food_id"] = id_mapping[comp_belongs_to]

#     result["meal"]["foods"] = final_foods

#     # Recompute total visible weight
#     result["meal"]["estimated_visible_food_weight_g"] = sum(
#         f.get("quantity", 0) for f in final_foods if f.get("unit") == "g"
#     )

#     return result

def _normalize_core_food_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name:
        return "Detected food"

    lowered = " ".join(name.lower().split())
    aliases = {
        "dal": "Lentils",
        "daal": "Lentils",
        "dhal": "Lentils",
        "dal tadka": "Lentils",
        "lentil curry": "Lentils",
        "toor dal": "Yellow split pigeon peas",
        "tuvar dal": "Yellow split pigeon peas",
        "arhar dal": "Yellow split pigeon peas",
        "moong dal": "Split mung beans",
        "mung dal": "Split mung beans",
        "masoor dal": "Red lentils",
        "urad dal": "Black gram",
    }
    return aliases.get(lowered, name)


def _is_oat_core_identity(identity: str) -> bool:
    normalized = _identity_text(identity)
    tokens = set(normalized.split())
    return bool(tokens & {"oat", "oats", "oatmeal"}) or normalized in {
        "oat porridge",
        "oatmeal porridge",
    }


_HYDRATION_EXPANDED_CATEGORIES = {
    "grain",
    "cereal",
    "legume",
    "pulse",
    "pasta",
    "noodle",
}

_HYDRATION_EXPANDED_TOKENS = {
    "oat",
    "oats",
    "oatmeal",
    "rice",
    "barley",
    "quinoa",
    "couscous",
    "bulgur",
    "millet",
    "pasta",
    "noodle",
    "noodles",
    "lentil",
    "lentils",
    "bean",
    "beans",
    "chickpea",
    "chickpeas",
    "buckwheat",
    "semolina",
    "cornmeal",
    "polenta",
}

_HYDRATED_PREPARATION_TOKENS = {
    "cooked",
    "boiled",
    "simmered",
    "steamed",
    "hydrated",
    "porridge",
    "prepared",
}

_DRY_PREPARATION_TOKENS = {
    "dry",
    "raw",
    "uncooked",
    "unprepared",
}

_DRY_REFERENCE_STOP_TOKENS = (
    _HYDRATED_PREPARATION_TOKENS
    | _DRY_PREPARATION_TOKENS
    | {"instant", "ready", "to", "eat", "with", "water", "fat", "added"}
)


def _is_hydration_expanded_core(food: dict[str, Any]) -> bool:
    # A mixed-dish parent must first be decomposed; a packaged-label item must
    # retain its printed nutrition. Only atomic generic ingredients are
    # eligible for foundational dry-reference enforcement.
    if food.get("analysis_route") in {"DECOMPOSE", "NUTRITION_LABEL"}:
        return False

    identity = _identity_text(
        food.get("canonical_name")
        or food.get("name")
        or ""
    )
    identity_tokens = set(identity.split())
    category = _identity_text(food.get("category") or "")
    preparation = str(
        food.get("served_preparation")
        or food.get("preparation")
        or ""
    ).lower().replace("_", " ").replace("-", " ")
    preparation_tokens = set(preparation.split())

    # Avoid treating vegetables such as green/string beans and bean sprouts as
    # dry pulses merely because their names contain "bean".
    excluded_vegetable = (
        "sprout" in identity_tokens
        or "sprouts" in identity_tokens
        or "green beans" in identity
        or "string beans" in identity
        or "wax beans" in identity
    )
    if excluded_vegetable:
        return False

    is_staple = (
        category in _HYDRATION_EXPANDED_CATEGORIES
        or bool(identity_tokens & _HYDRATION_EXPANDED_TOKENS)
    )
    has_relevant_state = bool(
        preparation_tokens
        & (_HYDRATED_PREPARATION_TOKENS | _DRY_PREPARATION_TOKENS)
    )
    usda_basis = str(food.get("usda_preparation_basis") or "").lower().strip()
    quantity_basis = (
        str(food.get("quantity_basis") or "")
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .strip()
    )
    already_explicit = (
        usda_basis == "dry"
        or quantity_basis == "dry ingredient equivalent"
    )
    return is_staple and (has_relevant_state or already_explicit)


def _dry_reference_identity(food: dict[str, Any]) -> str:
    identity = _identity_text(
        food.get("canonical_name")
        or food.get("name")
        or ""
    )
    tokens = [
        token
        for token in identity.split()
        if token not in _DRY_REFERENCE_STOP_TOKENS
    ]
    return " ".join(tokens).strip() or identity


def _enforce_core_reference_basis(food: dict[str, Any]) -> None:
    identity = _identity_text(
        food.get("canonical_name")
        or food.get("name")
        or ""
    )
    if not _is_hydration_expanded_core(food):
        return

    served_preparation = str(
        food.get("served_preparation")
        or food.get("preparation")
        or "unknown"
    )
    dry_identity = _dry_reference_identity(food)
    if _is_oat_core_identity(identity):
        food["name"] = "Rolled oats"
        food["canonical_name"] = "rolled oats"
        dry_identity = "rolled oats"
        usda_description = "oats, regular and quick, not fortified, dry"
        fallback_query = "rolled oats dry raw"
        food["category"] = "Grain"
    else:
        food["name"] = dry_identity.title() if dry_identity else food.get("name")
        food["canonical_name"] = dry_identity
        usda_description = f"{dry_identity} dry raw"
        fallback_query = usda_description

    food["served_preparation"] = served_preparation
    food["preparation"] = "dry"
    food["usda_preparation_basis"] = "dry"
    food["quantity_basis"] = "dry_ingredient_equivalent"
    food["usda_food_description"] = usda_description
    food["possible_usda_queries"] = [fallback_query]
    food["analysis_route"] = "DIRECT_USDA"
    food["requires_back_image"] = False


def _category_from_ingredient(value: Any) -> str:
    mapping = {
        "protein": "Meat",
        "legume": "Legume",
        "vegetable": "Vegetable",
        "fruit": "Fruit",
        "grain": "Grain",
        "oil": "Condiment",
        "dairy": "Dairy",
        "spice": "Condiment",
        "nut": "Nut",
        "seed": "Seed",
        "sweetener": "Condiment",
        "flavoring": "Condiment",
        "additive": "Condiment",
    }
    return mapping.get(str(value or "").strip().lower(), "Unknown")


def _promote_decomposed_food(
    food: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Convert a DECOMPOSE analysis container into the actual core food
    entities used by the nutrition pipeline. The parent itself is not an
    edible row and therefore never survives into meal.foods.
    """
    parent_id = str(food.get("id") or "")
    parent_name = str(food.get("name") or "Mixed dish")
    parent_quantity_confidence = float(food.get("quantity_confidence", 0) or 0)
    parent_detection_confidence = float(food.get("detection_confidence", 0) or 0)

    promoted: list[dict[str, Any]] = []

    # The DECOMPOSE parent is the mass budget. Gemini also returns ingredient
    # percentages, so do not trust an independently hallucinated
    # estimated_weight_g when it conflicts with that budget.
    ingredients = [
        item
        for item in (food.get("ingredients") or [])
        if isinstance(item, dict)
    ]
    parent_quantity = float(food.get("quantity", 0) or 0)
    parent_unit = str(food.get("unit") or "").lower().strip()
    percentage_sum = sum(
        max(0.0, float(item.get("estimated_percentage", 0) or 0))
        for item in ingredients
    )
    use_parent_mass_budget = (
        parent_unit == "g"
        and parent_quantity > 0
        and percentage_sum > 0
    )

    for index, ingredient in enumerate(ingredients, start=1):
        reported_weight = float(ingredient.get("estimated_weight_g", 0) or 0)
        percentage = max(
            0.0,
            float(ingredient.get("estimated_percentage", 0) or 0),
        )

        if use_parent_mass_budget and percentage > 0:
            weight = parent_quantity * percentage / percentage_sum
            if (
                reported_weight <= 0
                or abs(reported_weight - weight) / max(weight, 1.0) > 0.20
            ):
                ingredient["quantity_reconciliation"] = {
                    "reported_estimated_weight_g": reported_weight,
                    "reconciled_weight_g": round(weight, 4),
                    "basis": "parent_mass_x_normalized_percentage",
                }
        else:
            weight = reported_weight

        if weight <= 0:
            continue
        confidence = float(ingredient.get("confidence", 0) or 0)
        raw_name = ingredient.get("canonical_name") or ingredient.get("name")
        name = _normalize_core_food_name(raw_name)

        promoted.append({
            "id": f"{parent_id}_ingredient_{index:03d}",
            "name": name,
            "canonical_name": name,
            "ingredient_type": None,
            "canonical_variants": {"legume": None, "oil": None},
            "container": food.get("container", "unknown"),
            "category": _category_from_ingredient(ingredient.get("ingredient_category")),
            "cuisine": food.get("cuisine", "Unknown"),
            "food_source": "Generic",
            "brand": None,
            "role": "ingredient",
            "served_separately": False,
            "belongs_to_food_id": None,
            "preparation": food.get("preparation", "Cooked"),
            "preparation_confidence": food.get("preparation_confidence", 0.5),
            "quantity": weight,
            "quantity_confidence": min(
                parent_quantity_confidence if parent_quantity_confidence > 0 else 1.0,
                confidence if confidence > 0 else 1.0,
            ),
            "unit": "g",
            "edible_fraction": 1.0,
            "detection_confidence": min(
                parent_detection_confidence if parent_detection_confidence > 0 else 1.0,
                confidence if confidence > 0 else 1.0,
            ),
            "analysis_route": "DIRECT_USDA",
            "requires_back_image": False,
            "usda_food_description": ingredient.get("usda_food_description"),
            "possible_usda_queries": list(ingredient.get("possible_usda_queries") or []),
            "ingredients": [],
            "spices": [],
            "source_parent_food_id": parent_id or None,
            "source_parent_food_name": parent_name,
            "counts_toward_visible_weight": True,
            "display_in_food_list": True,
        })

    # Spices are promoted for nutrient resolution but kept out of the normal
    # detected-food list. Their weights are trace additions and do not count
    # toward the parent food's visible-mass budget.
    for index, spice in enumerate(food.get("spices") or [], start=1):
        if not isinstance(spice, dict):
            continue
        weight = float(spice.get("estimated_weight_g", 0) or 0)
        if weight <= 0:
            continue
        confidence = float(spice.get("confidence", 0) or 0)
        raw_name = spice.get("canonical_name") or spice.get("name")
        name = _normalize_core_food_name(raw_name)
        promoted.append({
            "id": f"{parent_id}_spice_{index:03d}",
            "name": name,
            "canonical_name": name,
            "ingredient_type": None,
            "canonical_variants": {"legume": None, "oil": None},
            "container": food.get("container", "unknown"),
            "category": "Condiment",
            "cuisine": food.get("cuisine", "Unknown"),
            "food_source": "Generic",
            "brand": None,
            "role": "ingredient",
            "served_separately": False,
            "belongs_to_food_id": None,
            "preparation": food.get("preparation", "Cooked"),
            "preparation_confidence": food.get("preparation_confidence", 0.5),
            "quantity": weight,
            "quantity_confidence": confidence,
            "unit": "g",
            "edible_fraction": 1.0,
            "detection_confidence": confidence,
            "analysis_route": "DIRECT_USDA",
            "requires_back_image": False,
            "usda_food_description": spice.get("usda_food_description"),
            "possible_usda_queries": list(spice.get("possible_usda_queries") or []),
            "ingredients": [],
            "spices": [],
            "source_parent_food_id": parent_id or None,
            "source_parent_food_name": parent_name,
            "counts_toward_visible_weight": False,
            "display_in_food_list": False,
        })

    return promoted



def _identity_text(value: Any) -> str:
    """Return a preparation-insensitive identity for ONE physical food."""
    import re

    text = str(value or "").lower().strip()
    if not text:
        return ""

    # Parenthetical preparation/state labels must not create a second food.
    # Examples: "Rolled Oats (Cooked)" and "Rolled Oats (Dry)".
    preparation_terms = {
        "cooked", "dry", "dried", "raw", "boiled", "steamed",
        "roasted", "baked", "fried", "grilled", "simmered",
        "soaked", "fresh", "sliced", "slice", "chopped", "diced",
        "minced", "crushed", "ground", "whole", "plain",
    }

    def clean_parenthetical(match: re.Match[str]) -> str:
        content = match.group(1).lower()
        words = set(re.findall(r"[a-z]+", content))
        if words and words.issubset(preparation_terms):
            return " "
        return " " + content + " "

    text = re.sub(r"\(([^)]*)\)", clean_parenthetical, text)

    # Remove preparation/state words as standalone tokens only; never use
    # substring replacement (which can corrupt legitimate food names).
    tokens = re.findall(r"[a-z0-9]+", text)
    tokens = [token for token in tokens if token not in preparation_terms]

    # Presentation words that do not change physical identity.
    tokens = [
        token for token in tokens
        if token not in {"porridge", "serving", "pieces", "piece"}
    ]

    singular_words: list[str] = []
    for word in tokens:
        # Foods conventionally plural in English remain unchanged.
        if word in {"oats", "lentils", "almonds", "peas", "beans"}:
            singular_words.append(word)
        elif word.endswith("ies") and len(word) > 4:
            singular_words.append(word[:-3] + "y")
        elif word.endswith("s") and not word.endswith("ss") and len(word) > 3:
            singular_words.append(word[:-1])
        else:
            singular_words.append(word)

    return " ".join(singular_words)


def _canonical_food_identity(food: dict[str, Any]) -> str:
    candidates = [
        food.get("canonical_name"),
        food.get("name"),
        food.get("usda_food_description"),
    ]
    identities = [_identity_text(value) for value in candidates]
    identities = [value for value in identities if value]
    if not identities:
        return ""

    # Prefer the shortest useful identity; USDA descriptions often contain
    # extra qualifiers while the canonical/name field carries the food core.
    return min(identities, key=lambda value: (len(value.split()), len(value)))


def _same_core_food(a: dict[str, Any], b: dict[str, Any]) -> bool:
    key_a = _canonical_food_identity(a)
    key_b = _canonical_food_identity(b)
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True

    tokens_a = set(key_a.split())
    tokens_b = set(key_b.split())
    if not tokens_a or not tokens_b:
        return False

    # Preparation wording often makes one identity a strict superset of the
    # other (e.g. "rolled oats" vs "oats rolled regular"). Only allow a
    # token-overlap match when at least one side came from a decomposed parent,
    # so independent foods are not collapsed aggressively.
    if a.get("source_parent_food_id") or b.get("source_parent_food_id"):
        overlap = len(tokens_a & tokens_b) / max(1, min(len(tokens_a), len(tokens_b)))
        return overlap >= 0.8

    return False


def _prefer_food_candidate(a: dict[str, Any], b: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (winner, discarded) for two estimates of one physical food."""
    a_promoted = bool(a.get("source_parent_food_id"))
    b_promoted = bool(b.get("source_parent_food_id"))

    # A decomposed ingredient belongs to the parent dish's mass budget. When
    # Gemini also emits the same ingredient independently, keep the promoted
    # ingredient rather than summing two visual estimates of the same mass.
    if a_promoted != b_promoted:
        return (a, b) if a_promoted else (b, a)

    def score(food: dict[str, Any]) -> tuple[float, float, float]:
        return (
            float(food.get("quantity_confidence", 0) or 0),
            float(food.get("detection_confidence", 0) or 0),
            -float(food.get("quantity", 0) or 0),
        )

    return (a, b) if score(a) >= score(b) else (b, a)


def _reconcile_core_food_duplicates(
    foods: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reconciled: list[dict[str, Any]] = []
    discarded_log: list[dict[str, Any]] = []

    for candidate in foods:
        duplicate_index = None
        for index, existing in enumerate(reconciled):
            if _same_core_food(existing, candidate):
                # Hidden trace spices should only reconcile with other hidden
                # trace spices, never with a visible core food card.
                if bool(existing.get("display_in_food_list", True)) != bool(candidate.get("display_in_food_list", True)):
                    continue
                duplicate_index = index
                break

        if duplicate_index is None:
            reconciled.append(candidate)
            continue

        existing = reconciled[duplicate_index]
        winner, discarded = _prefer_food_candidate(existing, candidate)
        reconciled[duplicate_index] = winner
        discarded_log.append({
            "reason": "duplicate_core_food_estimate",
            "canonical_identity": _canonical_food_identity(winner),
            "kept_name": winner.get("name"),
            "kept_quantity": winner.get("quantity"),
            "discarded_name": discarded.get("name"),
            "discarded_quantity": discarded.get("quantity"),
            "kept_source_parent_food_name": winner.get("source_parent_food_name"),
            "discarded_source_parent_food_name": discarded.get("source_parent_food_name"),
        })

    return reconciled, discarded_log


_COMPOSITE_PARENT_COMPONENT_ALIASES: dict[str, set[str]] = {
    "oatmeal": {"oats", "rolled oats"},
    "oatmeal porridge": {"oats", "rolled oats"},
    "oat porridge": {"oats", "rolled oats"},
    "porridge": {"oats", "rolled oats"},
}

_GENERIC_COMPOSITE_FAMILIES: dict[str, tuple[str, int]] = {
    "mixed vegetable": ("vegetable", 2),
    "vegetable mix": ("vegetable", 2),
    "mixed veg": ("vegetable", 2),
    "vegetable medley": ("vegetable", 2),
    "mixed fruit": ("fruit", 2),
    "fruit salad": ("fruit", 2),
    "mixed berry": ("fruit", 2),
    "mixed nut": ("nut_seed", 2),
    "mixed seed": ("nut_seed", 2),
    "mixed seafood": ("protein", 2),
    "mixed grill": ("protein", 2),
    "garden salad": ("produce", 2),
    "mixed salad": ("produce", 2),
}


def _atomic_food_families(food: dict[str, Any]) -> set[str]:
    """Broad families used only to prove that a generic parent is redundant."""
    identity = _canonical_food_identity(food)
    tokens = set(identity.split())
    category = str(food.get("category") or "").lower().strip()
    families: set[str] = set()

    vegetable_tokens = {
        "pea", "onion", "carrot", "pepper", "chilli", "chili", "tomato",
        "cucumber", "spinach", "broccoli", "cauliflower", "cabbage", "okra",
        "zucchini", "eggplant", "aubergine", "corn", "lettuce", "radish",
        "beet", "mushroom", "vegetable",
    }
    fruit_tokens = {
        "apple", "banana", "orange", "berry", "blueberry", "strawberry",
        "grape", "mango", "melon", "watermelon", "papaya", "pineapple",
        "fruit", "pear", "peach", "plum", "kiwi",
    }
    nut_seed_tokens = {
        "nut", "almond", "cashew", "walnut", "peanut", "pistachio",
        "seed", "chia", "flax", "sesame", "sunflower",
    }
    protein_tokens = {
        "chicken", "fish", "salmon", "tuna", "prawn", "shrimp", "meat",
        "beef", "pork", "lamb", "egg", "paneer", "tofu", "lentil", "bean",
        "chickpea", "seafood",
    }

    if category == "vegetable" or tokens & vegetable_tokens:
        families.update(("vegetable", "produce"))
    if category == "fruit" or tokens & fruit_tokens:
        families.update(("fruit", "produce"))
    if category in {"nut", "seed", "nuts and seeds"} or tokens & nut_seed_tokens:
        families.add("nut_seed")
    if category in {"meat", "fish", "seafood", "egg", "legume", "dairy"} or tokens & protein_tokens:
        families.add("protein")
    return families


def _generic_composite_components(
    identity: str,
    foods: list[dict[str, Any]],
    parent_index: int,
) -> list[dict[str, Any]]:
    rule = _GENERIC_COMPOSITE_FAMILIES.get(identity)
    if rule is None:
        return []
    family, minimum = rule
    matches = [
        food
        for index, food in enumerate(foods)
        if index != parent_index and family in _atomic_food_families(food)
    ]
    return matches if len(matches) >= minimum else []


def _suppress_redundant_composite_parents(
    foods: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Remove a prepared-dish parent when its core food is already present.

    The model occasionally returns both `Oatmeal` and `Rolled oats` despite the
    core-food contract. They are not two edible masses: oatmeal is the prepared
    dish name and rolled oats is its nutrient-bearing ingredient. Suppression is
    deliberately evidence-based (known alias, explicit child link, or matching
    nested ingredient), so an undecomposed dish is not silently deleted.
    """
    identities = [
        _canonical_food_identity(food)
        for food in foods
    ]
    kept: list[dict[str, Any]] = []
    discarded: list[dict[str, Any]] = []

    for index, food in enumerate(foods):
        identity = identities[index]
        other_identities = {
            value
            for other_index, value in enumerate(identities)
            if other_index != index and value
        }
        parent_id = str(food.get("id") or "")
        explicit_child_present = bool(parent_id) and any(
            str(other.get("belongs_to_food_id") or "") == parent_id
            for other_index, other in enumerate(foods)
            if other_index != index
        )

        nested_names = {
            _identity_text(
                ingredient.get("canonical_name")
                or ingredient.get("name")
            )
            for ingredient in (food.get("ingredients") or [])
            if isinstance(ingredient, dict)
        }
        nested_match_present = bool(nested_names & other_identities)
        alias_match_present = bool(
            _COMPOSITE_PARENT_COMPONENT_ALIASES.get(identity, set())
            & other_identities
        )

        generic_components = _generic_composite_components(
            identity,
            foods,
            index,
        )

        if (
            explicit_child_present
            or nested_match_present
            or alias_match_present
            or generic_components
        ):
            discarded.append({
                "reason": "redundant_prepared_dish_parent",
                "discarded_name": food.get("name"),
                "canonical_identity": identity,
                "matching_core_foods": sorted(
                    other_identities
                    & (
                        nested_names
                        | _COMPOSITE_PARENT_COMPONENT_ALIASES.get(identity, set())
                    )
                ),
                "matching_atomic_components": sorted(
                    _canonical_food_identity(item)
                    for item in generic_components
                ),
            })
            continue

        kept.append(food)

    return kept, discarded


def _clean_display_core_name(food: dict[str, Any]) -> None:
    """Keep preparation in metadata; display only the core food name."""
    import re

    name = str(food.get("name") or "").strip()
    if not name:
        return

    prep_words = (
        "cooked", "dry", "dried", "raw", "boiled", "steamed",
        "roasted", "baked", "fried", "grilled", "simmered", "soaked",
    )

    # Strip parenthetical preparation labels anywhere in the display name.
    pattern = r"\s*\((?:" + "|".join(prep_words) + r")\)\s*"
    name = re.sub(pattern, " ", name, flags=re.IGNORECASE).strip()

    # Strip leading preparation labels such as "Cooked Rolled Oats".
    prefix_pattern = r"^(?:" + "|".join(prep_words) + r")\s+"
    name = re.sub(prefix_pattern, "", name, flags=re.IGNORECASE).strip()

    # Strip trailing state labels such as "Rolled Oats Dry".
    suffix_pattern = r"\s+(?:" + "|".join(prep_words) + r")$"
    name = re.sub(suffix_pattern, "", name, flags=re.IGNORECASE).strip()

    if name:
        food["name"] = name
        # Do not overwrite a more specific canonical_name unless it is itself
        # only a preparation variant of the same identity.
        canonical = str(food.get("canonical_name") or "").strip()
        if not canonical or _identity_text(canonical) == _identity_text(name):
            food["canonical_name"] = name


_TRACE_FOOD_TOKENS = {
    "turmeric",
    "cumin",
    "coriander",
    "mustard seed",
    "mustard seeds",
    "black pepper",
    "white pepper",
    "chili powder",
    "chilli powder",
    "dried red chili",
    "dried red chilli",
    "red chili",
    "red chilli",
    "curry leaf",
    "curry leaves",
    "bay leaf",
    "bay leaves",
    "cardamom",
    "clove",
    "cloves",
    "cinnamon",
    "salt",
}


def _is_trace_food(food: dict[str, Any]) -> bool:
    identity = _identity_text(
        food.get("canonical_name")
        or food.get("name")
        or ""
    )
    category = str(food.get("category") or "").lower().strip()
    role = str(food.get("role") or "").lower().strip()

    if category in {"spice", "condiment"} and role in {
        "ingredient", "garnish", "condiment",
    }:
        return True

    return any(
        token in identity
        for token in _TRACE_FOOD_TOKENS
    )


def _sanitize_trace_food_quantities(
    foods: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Defensive guard for visually tiny seasonings.

    These items remain available to nutrient resolution, but they are not
    presented as primary detected-food cards. A 100 g curry-leaf/chili
    hallucination must never reach nutrition as a 100 g serving.
    """
    for food in foods:
        if not isinstance(food, dict) or not _is_trace_food(food):
            continue

        food["display_in_food_list"] = False
        food["counts_toward_visible_weight"] = False

        unit = str(food.get("unit") or "").lower().strip()
        quantity = float(food.get("quantity", 0) or 0)

        # Trace seasonings measured in grams are bounded defensively. This is
        # a plausibility guard, not a claim that every recipe uses this amount.
        if unit == "g" and quantity > 5.0:
            food["quantity_reconciliation"] = {
                "reported_quantity": quantity,
                "reported_unit": unit,
                "reconciled_quantity": 5.0,
                "reconciled_unit": "g",
                "basis": "trace_seasoning_plausibility_guard",
            }
            food["quantity"] = 5.0
            food["quantity_confidence"] = min(
                float(food.get("quantity_confidence", 0) or 0),
                0.35,
            )

        # Countable trace items should stay countable. We keep the count for
        # display/debugging rather than pretending a piece count is grams.
        if unit == "piece" and quantity > 12:
            food["quantity_reconciliation"] = {
                "reported_quantity": quantity,
                "reported_unit": unit,
                "reconciled_quantity": 12.0,
                "reconciled_unit": "piece",
                "basis": "trace_count_plausibility_guard",
            }
            food["quantity"] = 12.0
            food["quantity_confidence"] = min(
                float(food.get("quantity_confidence", 0) or 0),
                0.35,
            )

    return foods


def post_process(
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize the vision response and enforce the core-food contract:
    DECOMPOSE parents are analysis containers only and are replaced by their
    ingredient entities before downstream nutrition resolution.
    """
    if "meal" not in result or "foods" not in result["meal"]:
        return result

    foods = result["meal"]["foods"]
    if not isinstance(foods, list):
        return result

    unit_map = {
        "gram": "g", "grams": "g", "g": "g",
        "milliliter": "ml", "milliliters": "ml", "ml": "ml",
        "pieces": "piece", "piece": "piece",
        "slices": "slice", "slice": "slice",
        "cups": "cup", "cup": "cup",
        "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsp": "tbsp",
        "teaspoon": "tsp", "teaspoons": "tsp", "tsp": "tsp",
    }

    for food in foods:
        if not isinstance(food, dict):
            continue
        food["name"] = _normalize_core_food_name(food.get("name"))
        _enforce_core_reference_basis(food)
        # Most photo quantities are as served. Hydration-expanded staple bases
        # are the exception: _enforce_core_reference_basis marks their model-
        # estimated pre-hydration ingredient grams explicitly.
        food.setdefault("quantity_basis", "as_served")
        unit = str(food.get("unit", "g")).lower().strip()
        food["unit"] = unit_map.get(unit, unit)

        if food.get("analysis_route") == "NUTRITION_LABEL":
            food.setdefault("ingredients", [])
            food.setdefault("spices", [])
            continue

        new_ingredients = []
        for ingredient in food.get("ingredients", []):
            new_ingredients.extend(split_entry_by_name(ingredient))
        food["ingredients"] = new_ingredients

        new_spices = []
        for spice in food.get("spices", []):
            new_spices.extend(split_entry_by_name(spice))
        food["spices"] = new_spices

    # Track explicit child foods so they are not re-created from a parent's
    # nested ingredient list as well.
    explicit_child_keys: set[tuple[str, str]] = set()
    for food in foods:
        if not isinstance(food, dict):
            continue
        parent_id = food.get("belongs_to_food_id")
        if isinstance(parent_id, str):
            explicit_child_keys.add((parent_id, _normalize_core_food_name(food.get("name")).lower()))

    core_foods: list[dict[str, Any]] = []
    for food in foods:
        if not isinstance(food, dict):
            continue
        if food.get("analysis_route") != "DECOMPOSE":
            food.setdefault("counts_toward_visible_weight", True)
            food.setdefault("display_in_food_list", True)
            core_foods.append(food)
            continue

        parent_id = str(food.get("id") or "")
        for promoted in _promote_decomposed_food(food):
            key = (parent_id, str(promoted.get("name") or "").lower())
            if key in explicit_child_keys and promoted.get("display_in_food_list") is True:
                continue
            core_foods.append(promoted)

    core_foods, parent_log = _suppress_redundant_composite_parents(core_foods)

    # DECOMPOSE ingredients are promoted only after the first normalization
    # loop, so apply the same staple-basis policy to the complete flattened
    # inventory before any USDA resolution or duplicate reconciliation.
    for food in core_foods:
        _enforce_core_reference_basis(food)
        food.setdefault("quantity_basis", "as_served")

    # Reconcile alternate estimates of the same physical core food BEFORE
    # USDA lookup. This is what prevents a decomposed "Cooked Rolled Oats"
    # entry and a separate "Rolled Oats" detection from both surviving.
    core_foods, reconciliation_log = _reconcile_core_food_duplicates(core_foods)
    reconciliation_log = [*parent_log, *reconciliation_log]

    # Second deterministic pass after display-name cleanup semantics. This is
    # intentionally redundant with the first pass: Gemini must not be able to
    # bypass one-physical-food-one-entity merely by writing preparation in
    # parentheses or using Dry/Dried wording.
    for food in core_foods:
        _clean_display_core_name(food)
    core_foods, second_log = _reconcile_core_food_duplicates(core_foods)
    reconciliation_log.extend(second_log)

    core_foods = _sanitize_trace_food_quantities(core_foods)

    for food in core_foods:
        _clean_display_core_name(food)

    # Sequential IDs are assigned only after parents and duplicate estimates
    # have been removed.
    old_to_new: dict[str, str] = {}
    for index, food in enumerate(core_foods, start=1):
        old_id = str(food.get("id") or "")
        new_id = f"food_{index:04d}"
        if old_id:
            old_to_new[old_id] = new_id
        food["id"] = new_id

    for food in core_foods:
        parent_id = food.get("belongs_to_food_id")
        if isinstance(parent_id, str):
            food["belongs_to_food_id"] = old_to_new.get(parent_id)

    result["meal"]["foods"] = core_foods
    if reconciliation_log:
        result["meal"]["food_reconciliation"] = {
            "discarded_duplicate_estimates": reconciliation_log,
            "rule": "one_physical_core_food_one_final_entity",
        }
    result["meal"]["estimated_visible_food_weight_g"] = sum(
        float(food.get("quantity", 0) or 0)
        for food in core_foods
        if food.get("unit") == "g"
        and food.get("counts_toward_visible_weight", True) is not False
    )
    return result


# =============================================================================
# MAIN FLOW – MULTIPLE FILES → SINGLE MERGED RESULT
# =============================================================================

# from PIL import Image


def continue_with_back_label(
    partial_result: dict[str, Any],
    label_image_path: str,
    target_food_id: str | None = None,
) -> dict[str, Any]:
    try:
        with Image.open(
            label_image_path
        ) as image:
            image.load()
            label_image = image.copy()

    except Exception as error:
        raise ValueError(
            "Could not open the nutrition "
            f"label: {error}"
        ) from error

    label_result = extract_label(
        client,
        label_image,
    )

    meal = partial_result.get(
        "meal",
        {},
    )

    foods = meal.get(
        "foods",
        [],
    )

    if not isinstance(foods, list):
        raise ValueError(
            "The partial result contains "
            "an invalid food list."
        )

    target_food = None

    if target_food_id:
        target_food = next(
            (
                food
                for food in foods
                if food.get("id")
                == target_food_id
            ),
            None,
        )

        if target_food is None:
            raise ValueError(
                "The selected food was "
                "not found."
            )

    if target_food is None:
        target_food = next(
            (
                food
                for food in foods
                if (
                    food.get(
                        "analysis_route"
                    )
                    == "NUTRITION_LABEL"
                    and not food.get(
                        "nutrition_label"
                    )
                )
            ),
            None,
        )

    if target_food is None:
        raise ValueError(
            "No packaged food is waiting "
            "for a nutrition label."
        )

    if (
        target_food.get(
            "analysis_route"
        )
        != "NUTRITION_LABEL"
    ):
        raise ValueError(
            "The selected food does not "
            "require a nutrition label."
        )

    if target_food.get(
        "nutrition_label"
    ):
        raise ValueError(
            "A nutrition label is already "
            "attached to this food."
        )

    # target_food["nutrition_label"] = (
    #     label_result
    # )

    # target_food["requires_back_image"] = (
    #     True
    # )

    # target_food["back_image_received"] = (
    #     True
    # )

    attach_label_to_food(
        food=target_food,
        label=label_result,
    )

    remaining = [
        food
        for food in foods
        if (
            food.get("analysis_route")
            == "NUTRITION_LABEL"
            and not food.get(
                "nutrition_label"
            )
        )
    ]

    if remaining:
        return {
            "status": (
                "waiting_for_back_label"
            ),
            "message": (
                "Another packaged food "
                "requires a nutrition label."
            ),
            "foods_requiring_back_label": [
                {
                    "id": food.get("id"),
                    "name": food.get("name"),
                    "brand": food.get(
                        "brand"
                    ),
                }
                for food in remaining
            ],
            "partial_result": (
                partial_result
            ),
        }

    return {
        "status": "completed",
        **partial_result,
    }

def analyze_meal(
    image_paths: list[str],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Analyse one or more images supplied by the backend server.

    Images may include:
    - meal photographs
    - packaged-food nutrition labels
    """

    if not image_paths:
        raise ValueError(
            "At least one image must be provided."
        )

    all_images: list[tuple[str, Image.Image]] = []

    for image_path in image_paths:
        try:
            image = Image.open(image_path)
            image.load()

            all_images.append(
                (
                    image_path,
                    prepare_image_for_model(
                        image,
                        # Preserve printed text until routing is complete.
                        max_edge=max(
                            MEAL_IMAGE_MAX_EDGE,
                            LABEL_IMAGE_MAX_EDGE,
                        ),
                    ),
                )
            )

            image.close()
        except Exception as error:
            raise ValueError(
                f"Could not open image "
                f"{Path(image_path).name}: {error}"
            ) from error

    all_foods: list[dict[str, Any]] = []

    # ---------------------------------------------------------
    # Analyse food photographs
    # ---------------------------------------------------------

    for image_index, (_, classification_image) in enumerate(
          all_images,
          start=1,
    ):
        classification = classify_image(client, classification_image)
        image_type = str(classification.get("type") or "").strip().lower()

        if image_type in {"nutrition_label", "back_label", "label"}:
            label_result = extract_label(client, classification_image)
            label_food = create_food_from_label(label_result)
            label_food["id"] = f"img_{image_index:03d}_food_0001"
            all_foods.append(label_food)
            continue

        if image_type == "unknown":
            # A routing outage must not fail a normal meal. Probe strictly for
            # printed label evidence; if absent/unreadable, continue as food.
            try:
                label_result = extract_label(client, classification_image)
            except Exception as error:
                logger.warning(
                    "Unknown-route label probe failed for image %d; "
                    "continuing as meal: %s",
                    image_index,
                    error,
                )
            else:
                label_food = create_food_from_label(label_result)
                label_food["id"] = f"img_{image_index:03d}_food_0001"
                all_foods.append(label_food)
                continue

        image = prepare_image_for_model(
            classification_image,
            max_edge=MEAL_IMAGE_MAX_EDGE,
        )
        result = _generate_plain_meal_json(
            image,
            image_index=image_index,
        )

        # This second Gemini pass was the other shared failure point. It is
        # opt-in and non-fatal; the complete primary result remains usable.
        if (
            ENABLE_MEAL_INVENTORY_AUDIT
            and _should_audit_complete_food_inventory(result)
        ):
            try:
                result = _audit_and_correct_complete_food_inventory(
                    image,
                    result,
                    image_index=image_index,
                )
            except Exception as error:
                logger.warning(
                    "Optional inventory audit failed for image %d; using "
                    "primary detection: %s",
                    image_index,
                    error,
                )

        foods = (
            result
            .get("meal", {})
            .get("foods", [])
        )

        if not isinstance(foods, list):
            continue

        foods = namespace_food_ids(
            foods=foods,
            image_index=image_index,
        )

        for food in foods:
            if food.get("analysis_route") == "NUTRITION_LABEL":
                food.setdefault("requires_back_image", True)
                food.setdefault(
                    "back_image_received",
                    bool(food.get("nutrition_label")),
                )

        all_foods.extend(foods)

    if not all_foods:
        return {
            "status": "no_food_detected",
            "message": (
                "No food was detected in the "
                "uploaded images."
            ),
        }

    merged_result = {
        "meal": {
            "meal_type": "Mixed",
            "estimated_visible_food_weight_g": 0,
            "foods": all_foods,
        }
    }

    final_result = post_process(
        merged_result
    )

    foods_missing_labels = [
        food
        for food in final_result["meal"]["foods"]
        if (
            food.get("analysis_route")
            == "NUTRITION_LABEL"
            and not food.get("nutrition_label")
        )
    ]

    if foods_missing_labels:
        return {
            "status": "waiting_for_back_label",
            "message": (
                "Upload the nutrition label for "
                "the identified packaged food."
            ),
            "foods_requiring_back_label": [
                {
                    "id": food.get("id"),
                    "name": food.get("name"),
                    "brand": food.get("brand"),
                }
                for food in foods_missing_labels
            ],
            "partial_result": final_result,
            # "profile": profile,
        }

    return {
        "status": "completed",
        **final_result,
    }


def analyze_label_only(
    image_path: str,
) -> dict[str, Any]:
    """
    Analyse a single image that is already known to be a nutrition/back
    label (not a meal photo). This is the "direct upload" flow — it never
    goes through analyze_meal, so it cannot come back waiting for a back
    label it was just given.
    """
    try:
        with Image.open(image_path) as image:
            image.load()
            label_image = image.copy()
    except Exception as error:
        raise ValueError(
            f"Could not open the nutrition label: {error}"
        ) from error

    label_result = extract_label(client, label_image)

    food = create_food_from_label(label_result)

    merged_result = {
        "meal": {
            "meal_type": "Mixed",
            "estimated_visible_food_weight_g": 0,
            "foods": [food],
        }
    }

    final_result = post_process(merged_result)

    return {
        "status": "completed",
        **final_result,
    }

def parse_model_json(
    response_text: str,
) -> dict[str, Any]:
    text = response_text.lstrip("\ufeff").strip()

    if text.startswith("```"):
        first_line_end = text.find("\n")
        text = text[first_line_end + 1:] if first_line_end >= 0 else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    object_start = text.find("{")
    if object_start < 0:
        raise ValueError("The AI response did not contain a JSON object.")

    # raw_decode accepts harmless trailing whitespace/commentary while still
    # rejecting incomplete strings, arrays, or objects. Incomplete output is
    # retried by `_generate_json`; it is never silently patched into data.
    result, _ = json.JSONDecoder().raw_decode(text[object_start:])

    if not isinstance(result, dict):
        raise ValueError(
            "The AI response was not a JSON object."
        )

    return result


def find_matching_label(
    food: dict[str, Any],
    labels: list[dict[str, Any]],
    used_indices: set[int],
) -> tuple[int, dict[str, Any], float] | None:
    best_index = -1
    best_label: dict[str, Any] | None = None
    best_score = 0.0

    for index, label in enumerate(labels):
        if index in used_indices:
            continue

        brand_similarity = similarity(
            str(label.get("brand") or ""),
            str(food.get("brand") or ""),
        )

        product_similarity = similarity(
            str(
                label.get(
                    "product_name",
                )
                or ""
            ),
            str(food.get("name") or ""),
        )

        score = (
            brand_similarity
            + product_similarity
        ) / 2

        if score > best_score:
            best_index = index
            best_label = label
            best_score = score

    if (
        best_label is None
        or best_score < 0.55
    ):
        return None

    return (
        best_index,
        best_label,
        best_score,
    )
