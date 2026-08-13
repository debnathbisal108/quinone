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

GEMINI_MEAL_MODEL = os.environ.get(
    "GEMINI_MEAL_MODEL",
    "gemini-3-flash-preview",
)
GEMINI_LABEL_MODEL = os.environ.get(
    "GEMINI_LABEL_MODEL",
    GEMINI_MEAL_MODEL,
)

# Phone cameras commonly produce 12-50 MP files. Gemini does not need the
# original pixels for ordinary food recognition, and transmitting them adds a
# large fixed cost. Labels keep a larger edge because small printed text needs
# more detail than a meal photograph.
MEAL_IMAGE_MAX_EDGE = int(os.environ.get("MEAL_IMAGE_MAX_EDGE", "1280"))
LABEL_IMAGE_MAX_EDGE = int(os.environ.get("LABEL_IMAGE_MAX_EDGE", "2048"))

MEAL_GENERATION_CONFIG = {
    "response_mime_type": "application/json",
    "temperature": 0.1,
    "max_output_tokens": 8192,
}

LABEL_GENERATION_CONFIG = {
    "response_mime_type": "application/json",
    "temperature": 0.0,
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
and return one JSON object only. Do not add markdown or commentary.

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
You are an image classifier for a nutrition app.

Determine if this image is primarily:

- A photo of prepared food, meal, ingredients, dish, or edible items (type: "food")
- OR a close-up photo of a packaged food's Nutrition Facts panel / nutrition label / back of package showing nutritional information, ingredients list, or barcode area (type: "nutrition_label")

Return ONLY valid JSON:
{
  "type": "food" or "nutrition_label",
  "confidence": 0.0 to 1.0,
  "reason": "one short sentence"
}

If the image is ambiguous or mostly packaging without a clear Nutrition Facts panel, prefer "food".
If you can clearly read nutrient numbers / "Nutrition Facts" / "per 100g" / "Serving Size", choose "nutrition_label".
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


def _generate_json(
    *,
    model: str,
    instruction: str,
    image: Image.Image,
    config: dict[str, Any],
    operation: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.models.generate_content(
        model=model,
        contents=[instruction, image],
        config=config,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    logger.info("Gemini %s completed in %.1f ms", operation, elapsed_ms)
    return parse_model_json(response.text or "")


def classify_image(client, image):
    """Legacy compatibility helper; normal uploads no longer call it."""
    try:
        response = client.models.generate_content(
            model=GEMINI_MEAL_MODEL,
            contents=[classify_prompt, image],
            config={
                "response_mime_type": "application/json",
                "temperature": 0.0,
                "max_output_tokens": 256,
            },
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception:
        return {"type": "food", "confidence": 0.5, "reason": "classification failed"}


def extract_label(client, image):
    prepared = prepare_image_for_model(
        image,
        max_edge=LABEL_IMAGE_MAX_EDGE,
    )
    return _generate_json(
        model=GEMINI_LABEL_MODEL,
        instruction=label_prompt,
        image=prepared,
        config=LABEL_GENERATION_CONFIG,
        operation="back-label extraction",
    )


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

        if explicit_child_present or nested_match_present or alias_match_present:
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
                        max_edge=MEAL_IMAGE_MAX_EDGE,
                    ),
                )
            )

            image.close()
        except Exception as error:
            raise ValueError(
                f"Could not open image "
                f"{Path(image_path).name}: {error}"
            ) from error

    # Initial uploads are meal photographs by API contract. Nutrition labels
    # are uploaded through /analyze/back-label/start, so classifying every meal
    # photo with a separate Gemini request was pure fixed latency. Each image
    # now goes directly to the meal extractor.
    food_images = all_images

    all_foods: list[dict[str, Any]] = []

    # ---------------------------------------------------------
    # Analyse food photographs
    # ---------------------------------------------------------

    # for _, image in food_images:
    for image_index, (_, image) in enumerate(
          food_images,
          start=1,
    ):
        result = _generate_json(
            model=GEMINI_MEAL_MODEL,
            instruction=optimized_meal_prompt,
            image=image,
            config=MEAL_GENERATION_CONFIG,
            operation=f"meal image {image_index}",
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


def parse_model_json(
    response_text: str,
) -> dict[str, Any]:
    text = response_text.strip()

    if text.startswith("```"):
        text = (
            text
            .replace("```json", "")
            .replace("```JSON", "")
            .replace("```", "")
            .strip()
        )

    result = json.loads(text)

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
