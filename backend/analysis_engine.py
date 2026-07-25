from google import genai
# from google.colab import files
from PIL import Image
import json
import copy
import math
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

A mixed dish should contain ONLY the mixed dish.

Do NOT include separately detected foods inside another food name.

Correct

Lentils

Rice

Incorrect

Lentils with Rice

Correct

Chicken Curry

Rice

Incorrect

Chicken Curry with Rice

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

Use for Homemade or Restaurant foods whose nutrition should be estimated from their ingredients.

Examples

Chicken Curry
Dal
Aloo Sabzi
Biryani
Pasta
Vegetable Stir Fry
Pizza
Burger

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

Generate exactly FIVE USDA search queries for EVERY food, ingredient, and
spice that requires USDA resolution. This includes:

- DIRECT_USDA foods
- the parent dish itself of DECOMPOSE foods
- every ingredient inside a DECOMPOSE food
- every spice inside a DECOMPOSE food

NUTRITION_LABEL foods are the only exception — possible_usda_queries must
be an empty list for those, since no USDA search is performed.

For DIRECT_USDA foods (and the parent dish of DECOMPOSE foods),
the queries should describe the food itself.

Example

Cooked White Rice

↓

Cooked white rice
Basmati rice cooked
Long grain white rice cooked
White rice cooked
Rice

For DECOMPOSE foods,
the queries should describe the COMPLETE DISH,
NOT the ingredients.

Example

Chicken Curry

↓

Chicken curry
Indian chicken curry
Butter chicken
Chicken tikka masala
Creamy chicken curry

Incorrect

Chicken
Tomato
Onion
Garlic
Butter

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

For every food, ingredient, and spice that requires USDA resolution
(i.e. everything except NUTRITION_LABEL foods), generate ONE field:

usda_food_description

This field should contain the SINGLE FoodData Central (USDA) food description that is most likely to exist in the USDA database.

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

Chicken Curry
→
Chicken curry

Dal Tadka
→
Lentil curry

Aloo Bhujia
→
Potato curry

Naan
→
Naan bread

Vegetable Salad
→
Salad, vegetable

Mashed Potato
→
Potatoes, mashed

Onion (as an ingredient)
→
Onions, raw

The description should maximize the probability of finding the correct USDA FoodData Central entry.

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
- Every food, every DECOMPOSE ingredient, and every DECOMPOSE spice must contain exactly FIVE USDA search queries (NUTRITION_LABEL foods are the only exception - their possible_usda_queries must be empty).
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

  "serving_size": {...},

  "nutrition_per_serving": {...},

  "nutrition_per_100g": {...},

  "ingredients": [],

  "allergens": [],

  "claims": [],

  "ocr_confidence": 0.95
}

Rules

- Read the complete Nutrition Facts panel exactly as printed.

  Extract every nutrient shown.

  Do not infer or calculate missing nutrients.

  If both "per serving" and "per 100 g" are present,
  return BOTH.
- Never estimate values.
- Missing values must be null.
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


def classify_image(client, image):
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[classify_prompt, image]
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception:
        return {"type": "food", "confidence": 0.5, "reason": "classification failed"}


def extract_label(client, image):
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[label_prompt, image]
    )
    txt = response.text.strip()
    if txt.startswith("```"):
        txt = txt.replace("```json", "").replace("```", "").strip()
    return json.loads(txt)


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
        "analysis_route": "NUTRITION_LABEL",
        # "requires_back_image": False,
        "requires_back_image": True,
        "back_image_received": True,          
        "usda_food_description": None,
        "possible_usda_queries": [],
        "ingredients": [],
        "spices": [],
        "nutrition_label": label
    }
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

def post_process(
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize units, split combined ingredient/spice names,
    renumber food IDs, preserve parent relationships,
    and recompute visible gram weight.
    """

    if (
        "meal" not in result
        or "foods" not in result["meal"]
    ):
        return result

    foods = result["meal"]["foods"]

    unit_map = {
        "gram": "g",
        "grams": "g",
        "g": "g",
        "milliliter": "ml",
        "milliliters": "ml",
        "ml": "ml",
        "pieces": "piece",
        "piece": "piece",
        "slices": "slice",
        "slice": "slice",
        "cups": "cup",
        "cup": "cup",
        "tablespoon": "tbsp",
        "tablespoons": "tbsp",
        "tbsp": "tbsp",
        "teaspoon": "tsp",
        "teaspoons": "tsp",
        "tsp": "tsp",
    }

    for food in foods:
        unit = str(
            food.get("unit", "g")
        ).lower().strip()

        food["unit"] = unit_map.get(
            unit,
            unit,
        )

    for food in foods:
        new_ingredients = []

        for ingredient in food.get(
            "ingredients",
            [],
        ):
            new_ingredients.extend(
                split_entry_by_name(
                    ingredient
                )
            )

        food["ingredients"] = (
            new_ingredients
        )

        new_spices = []

        for spice in food.get(
            "spices",
            [],
        ):
            new_spices.extend(
                split_entry_by_name(
                    spice
                )
            )

        food["spices"] = new_spices

    id_mapping: dict[str, str] = {}

    for index, food in enumerate(
        foods,
        start=1,
    ):
        old_id = food.get("id")
        new_id = f"food_{index:04d}"

        if isinstance(old_id, str):
            id_mapping[old_id] = new_id

        food["id"] = new_id

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

    result["meal"]["foods"] = foods

    result["meal"][
        "estimated_visible_food_weight_g"
    ] = sum(
        float(food.get("quantity", 0) or 0)
        for food in foods
        if food.get("unit") == "g"
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

    target_food["nutrition_label"] = (
        label_result
    )

    target_food["requires_back_image"] = (
        True
    )

    target_food["back_image_received"] = (
        True
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
                    image.copy(),
                )
            )

            image.close()
        except Exception as error:
            raise ValueError(
                f"Could not open image "
                f"{Path(image_path).name}: {error}"
            ) from error

    available_labels: list[dict[str, Any]] = []
    food_images: list[tuple[str, Image.Image]] = []

    # ---------------------------------------------------------
    # Classify every uploaded image
    # ---------------------------------------------------------

    for image_path, image in all_images:
        classification = classify_image(
            client,
            image,
        )

        confidence = float(
            classification.get(
                "confidence",
                0,
            )
            or 0
        )

        image_type = classification.get(
            "type",
            "food",
        )

        if (
            image_type == "nutrition_label"
            and confidence > 0.55
        ):
            try:
                label_result = extract_label(
                    client,
                    image,
                )

                available_labels.append(
                    label_result
                )
            except Exception:
                # If label extraction fails, analyse it
                # as a normal food image.
                food_images.append(
                    (
                        image_path,
                        image,
                    )
                )
        else:
            food_images.append(
                (
                    image_path,
                    image,
                )
            )

    all_foods: list[dict[str, Any]] = []
    used_label_indices: set[int] = set()

    # ---------------------------------------------------------
    # Analyse food photographs
    # ---------------------------------------------------------

    # for _, image in food_images:
    for image_index, (_, image) in enumerate(
          food_images,
          start=1,
    ):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                prompt,
                image,
            ],
        )

        result = parse_model_json(
            response.text
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
          if (
              food.get("analysis_route")
              == "NUTRITION_LABEL"
          ):
              food.setdefault(
                  "requires_back_image",
                  True,
              )

              food.setdefault(
                  "back_image_received",
                  bool(
                      food.get(
                          "nutrition_label"
                      )
                  ),
              )


        foods_needing_labels = [
            food
            for food in foods
            if food.get("analysis_route")
            == "NUTRITION_LABEL"
        ]

        for food in foods_needing_labels:
            match = find_matching_label(
                food=food,
                labels=available_labels,
                used_indices=used_label_indices,
            )

            if match is None:
                continue

            label_index, label, score = match

            # food["nutrition_label"] = label
            # food["requires_back_image"] = False
            # food["label_match_confidence"] = score

            food["nutrition_label"] = label
            food["requires_back_image"] = True
            food["back_image_received"] = True
            food["label_match_confidence"] = score

            used_label_indices.add(
                label_index
            )

        all_foods.extend(foods)

    # ---------------------------------------------------------
    # Nutrition-label-only upload
    # ---------------------------------------------------------

    if not all_foods and available_labels:
        for label in available_labels:
            all_foods.append(
                create_food_from_label(label)
            )

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
