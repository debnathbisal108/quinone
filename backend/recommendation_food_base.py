"""Quinone's deterministic recommendation candidate base.

This file intentionally stores *food identities and search metadata*, not
nutrition claims. Nutrient values are always hydrated from USDA FoodData
Central before a candidate can be simulated or shown to the user.

The base is deliberately broad and uses concise American-English food names so
recommendations are not tied to a country, cuisine, or locale. The engine only
searches the subset relevant to the current nutrient/domain problem, then runs
all normal personalization, allergy, medical, and scoring checks.
"""

from __future__ import annotations

from typing import Any


def _seed(
    seed_id: str,
    name: str,
    query: str,
    serving_g: float,
    group: str,
    focus: tuple[str, ...],
    roles: tuple[str, ...],
    *,
    diet_tags: tuple[str, ...] = (),
    allergens: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "id": seed_id,
        "name": name,
        "search_query": query,
        "serving_g": serving_g,
        "food_group": group,
        "focus_nutrients": list(focus),
        "meal_roles": list(roles),
        "diet_tags": list(diet_tags),
        "allergens": list(allergens),
    }


P = ("vegan", "vegetarian")
PG = ("vegan", "vegetarian", "gluten_free")
V = ("vegetarian",)
VG = ("vegetarian", "gluten_free")

RECOMMENDATION_FOOD_BASE: tuple[dict[str, Any], ...] = (
    # Fruit
    _seed("apple", "Apple", "apples raw with skin", 150, "fruit", ("fiber_g", "vitamin_c_mg", "potassium_mg"), ("breakfast", "snack", "dessert"), diet_tags=PG),
    _seed("pear", "Pear", "pears raw", 160, "fruit", ("fiber_g", "vitamin_c_mg", "potassium_mg"), ("breakfast", "snack", "dessert"), diet_tags=PG),
    _seed("orange", "Orange", "oranges raw all commercial varieties", 130, "fruit", ("vitamin_c_mg", "folate_ug", "fiber_g"), ("breakfast", "snack", "dessert"), diet_tags=PG),
    _seed("grapefruit", "Grapefruit", "grapefruit raw pink and red", 150, "fruit", ("vitamin_c_mg", "vitamin_a_ug", "fiber_g"), ("breakfast", "snack"), diet_tags=PG),
    _seed("kiwi", "Kiwi", "kiwifruit green raw", 100, "fruit", ("vitamin_c_mg", "vitamin_k_ug", "fiber_g", "potassium_mg"), ("breakfast", "snack", "dessert"), diet_tags=PG),
    _seed("strawberries", "Strawberries", "strawberries raw", 150, "fruit", ("vitamin_c_mg", "folate_ug", "fiber_g"), ("breakfast", "snack", "dessert"), diet_tags=PG),
    _seed("blueberries", "Blueberries", "blueberries raw", 120, "fruit", ("fiber_g", "vitamin_c_mg", "vitamin_k_ug"), ("breakfast", "snack", "dessert", "topping"), diet_tags=PG),
    _seed("raspberries", "Raspberries", "raspberries raw", 120, "fruit", ("fiber_g", "vitamin_c_mg", "manganese_mg"), ("breakfast", "snack", "dessert"), diet_tags=PG),
    _seed("blackberries", "Blackberries", "blackberries raw", 120, "fruit", ("fiber_g", "vitamin_c_mg", "vitamin_k_ug", "manganese_mg"), ("breakfast", "snack", "dessert"), diet_tags=PG),
    _seed("banana", "Banana", "bananas raw", 120, "fruit", ("potassium_mg", "vitamin_b6_mg", "fiber_g", "magnesium_mg"), ("breakfast", "snack"), diet_tags=PG),
    _seed("mango", "Mango", "mangos raw", 140, "fruit", ("vitamin_c_mg", "vitamin_a_ug", "folate_ug"), ("breakfast", "snack", "dessert"), diet_tags=PG),
    _seed("papaya", "Papaya", "papayas raw", 140, "fruit", ("vitamin_c_mg", "vitamin_a_ug", "folate_ug"), ("breakfast", "snack", "dessert"), diet_tags=PG),
    _seed("guava", "Guava", "guavas common raw", 120, "fruit", ("vitamin_c_mg", "fiber_g", "potassium_mg", "folate_ug"), ("breakfast", "snack"), diet_tags=PG),
    _seed("pineapple", "Pineapple", "pineapple raw all varieties", 140, "fruit", ("vitamin_c_mg", "manganese_mg"), ("snack", "dessert"), diet_tags=PG),
    _seed("watermelon", "Watermelon", "watermelon raw", 200, "fruit", ("vitamin_c_mg", "potassium_mg"), ("snack", "dessert"), diet_tags=PG),
    _seed("cantaloupe", "Cantaloupe", "melons cantaloupe raw", 160, "fruit", ("vitamin_a_ug", "vitamin_c_mg", "potassium_mg"), ("breakfast", "snack"), diet_tags=PG),
    _seed("peach", "Peach", "peaches yellow raw", 150, "fruit", ("vitamin_c_mg", "fiber_g", "potassium_mg"), ("snack", "dessert"), diet_tags=PG),
    _seed("plum", "Plum", "plums raw", 140, "fruit", ("vitamin_c_mg", "fiber_g", "potassium_mg"), ("snack", "dessert"), diet_tags=PG),
    _seed("cherries", "Cherries", "cherries sweet raw", 120, "fruit", ("fiber_g", "vitamin_c_mg", "potassium_mg"), ("snack", "dessert"), diet_tags=PG),
    _seed("pomegranate", "Pomegranate", "pomegranates raw", 120, "fruit", ("fiber_g", "vitamin_c_mg", "vitamin_k_ug", "folate_ug"), ("snack", "dessert"), diet_tags=PG),
    _seed("avocado", "Avocado", "avocados raw all commercial varieties", 80, "fruit", ("fiber_g", "potassium_mg", "folate_ug", "vitamin_e_mg", "magnesium_mg"), ("breakfast", "lunch", "dinner", "side"), diet_tags=PG),

    # Vegetables
    _seed("spinach", "Spinach", "spinach cooked boiled drained without salt", 100, "vegetable", ("vitamin_k_ug", "folate_ug", "iron_mg", "magnesium_mg", "calcium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("kale", "Kale", "kale cooked boiled drained without salt", 100, "vegetable", ("vitamin_k_ug", "vitamin_c_mg", "vitamin_a_ug", "calcium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("collard_greens", "Collard greens", "collards cooked boiled drained without salt", 100, "vegetable", ("vitamin_k_ug", "calcium_mg", "folate_ug", "vitamin_a_ug"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("mustard_greens", "Mustard greens", "mustard greens cooked boiled drained without salt", 100, "vegetable", ("vitamin_k_ug", "vitamin_a_ug", "vitamin_c_mg", "calcium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("swiss_chard", "Swiss chard", "chard swiss cooked boiled drained without salt", 100, "vegetable", ("vitamin_k_ug", "magnesium_mg", "potassium_mg", "vitamin_a_ug"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("broccoli", "Broccoli", "broccoli cooked boiled drained without salt", 120, "vegetable", ("vitamin_c_mg", "vitamin_k_ug", "folate_ug", "fiber_g"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("cauliflower", "Cauliflower", "cauliflower cooked boiled drained without salt", 120, "vegetable", ("vitamin_c_mg", "folate_ug", "fiber_g"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("brussels_sprouts", "Brussels sprouts", "brussels sprouts cooked boiled drained without salt", 120, "vegetable", ("vitamin_c_mg", "vitamin_k_ug", "fiber_g", "folate_ug"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("cabbage", "Cabbage", "cabbage green cooked boiled drained without salt", 120, "vegetable", ("vitamin_c_mg", "vitamin_k_ug", "fiber_g"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("carrots", "Carrots", "carrots cooked boiled drained without salt", 120, "vegetable", ("vitamin_a_ug", "fiber_g", "potassium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("sweet_potato", "Sweet potato", "sweet potato cooked baked in skin flesh without salt", 150, "vegetable", ("vitamin_a_ug", "fiber_g", "potassium_mg", "vitamin_c_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("pumpkin", "Pumpkin", "pumpkin cooked boiled drained without salt", 150, "vegetable", ("vitamin_a_ug", "potassium_mg", "fiber_g"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("butternut_squash", "Butternut squash", "squash winter butternut cooked baked without salt", 150, "vegetable", ("vitamin_a_ug", "vitamin_c_mg", "potassium_mg", "fiber_g"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("red_bell_pepper", "Red bell pepper", "peppers sweet red raw", 120, "vegetable", ("vitamin_c_mg", "vitamin_a_ug", "vitamin_b6_mg"), ("lunch", "dinner", "side", "snack"), diet_tags=PG),
    _seed("green_bell_pepper", "Green bell pepper", "peppers sweet green raw", 120, "vegetable", ("vitamin_c_mg", "fiber_g"), ("lunch", "dinner", "side", "snack"), diet_tags=PG),
    _seed("tomato", "Tomato", "tomatoes red ripe raw", 150, "vegetable", ("vitamin_c_mg", "potassium_mg", "folate_ug"), ("breakfast", "lunch", "dinner", "side"), diet_tags=PG),
    _seed("okra", "Okra", "okra cooked boiled drained without salt", 120, "vegetable", ("fiber_g", "folate_ug", "magnesium_mg", "vitamin_c_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("green_beans", "Green beans", "beans snap green cooked boiled drained without salt", 120, "vegetable", ("fiber_g", "vitamin_c_mg", "vitamin_k_ug", "folate_ug"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("peas", "Green peas", "peas green cooked boiled drained without salt", 120, "vegetable", ("protein_g", "fiber_g", "vitamin_c_mg", "folate_ug"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("asparagus", "Asparagus", "asparagus cooked boiled drained without salt", 120, "vegetable", ("folate_ug", "vitamin_k_ug", "fiber_g"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("artichoke", "Artichoke", "artichokes globe cooked boiled drained without salt", 120, "vegetable", ("fiber_g", "magnesium_mg", "folate_ug", "potassium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("beets", "Beets", "beets cooked boiled drained", 120, "vegetable", ("folate_ug", "potassium_mg", "fiber_g"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("eggplant", "Eggplant", "eggplant cooked boiled drained without salt", 140, "vegetable", ("fiber_g", "manganese_mg", "potassium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("mushrooms", "Mushrooms", "mushrooms white cooked boiled drained without salt", 120, "vegetable", ("selenium_ug", "riboflavin_mg", "niacin_mg", "potassium_mg"), ("breakfast", "lunch", "dinner", "side"), diet_tags=PG),
    _seed("zucchini", "Zucchini", "squash summer zucchini cooked boiled drained without salt", 150, "vegetable", ("vitamin_c_mg", "potassium_mg", "fiber_g"), ("lunch", "dinner", "side"), diet_tags=PG),

    # Beans / legumes / soy
    _seed("lentils", "Lentils", "lentils mature seeds cooked boiled without salt", 150, "legume", ("protein_g", "fiber_g", "iron_mg", "folate_ug", "magnesium_mg", "potassium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("chickpeas", "Chickpeas", "chickpeas cooked boiled without salt", 140, "legume", ("protein_g", "fiber_g", "folate_ug", "iron_mg", "magnesium_mg"), ("lunch", "dinner", "side", "snack"), diet_tags=PG),
    _seed("kidney_beans", "Kidney beans", "beans kidney red mature seeds cooked boiled without salt", 150, "legume", ("protein_g", "fiber_g", "folate_ug", "iron_mg", "potassium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("black_beans", "Black beans", "beans black mature seeds cooked boiled without salt", 150, "legume", ("protein_g", "fiber_g", "folate_ug", "magnesium_mg", "iron_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("pinto_beans", "Pinto beans", "beans pinto mature seeds cooked boiled without salt", 150, "legume", ("protein_g", "fiber_g", "folate_ug", "magnesium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("navy_beans", "Navy beans", "beans navy mature seeds cooked boiled without salt", 150, "legume", ("protein_g", "fiber_g", "folate_ug", "magnesium_mg", "iron_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("lima_beans", "Lima beans", "lima beans large mature seeds cooked boiled without salt", 150, "legume", ("protein_g", "fiber_g", "potassium_mg", "magnesium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("mung_beans", "Mung beans", "mung beans mature seeds cooked boiled without salt", 150, "legume", ("protein_g", "fiber_g", "folate_ug", "magnesium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("black_eyed_peas", "Black-eyed peas", "cowpeas common cooked boiled without salt", 150, "legume", ("protein_g", "fiber_g", "folate_ug", "iron_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("split_peas", "Split peas", "peas split mature seeds cooked boiled without salt", 150, "legume", ("protein_g", "fiber_g", "folate_ug", "potassium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("edamame", "Edamame", "soybeans green cooked boiled drained without salt", 120, "soy", ("protein_g", "fiber_g", "folate_ug", "iron_mg", "magnesium_mg"), ("lunch", "dinner", "snack", "side"), diet_tags=PG, allergens=("soy",)),
    _seed("tofu", "Firm tofu", "tofu firm prepared with calcium", 120, "soy", ("protein_g", "calcium_mg", "iron_mg", "magnesium_mg"), ("lunch", "dinner"), diet_tags=PG, allergens=("soy",)),
    _seed("tempeh", "Tempeh", "tempeh cooked", 100, "soy", ("protein_g", "iron_mg", "magnesium_mg", "riboflavin_mg"), ("lunch", "dinner"), diet_tags=PG, allergens=("soy",)),

    # Whole grains / starches
    _seed("oats", "Oats", "oats regular quick dry", 50, "grain", ("fiber_g", "protein_g", "magnesium_mg", "iron_mg", "manganese_mg"), ("breakfast", "snack"), diet_tags=P, allergens=("gluten",)),
    _seed("barley", "Barley", "barley pearled cooked", 150, "grain", ("fiber_g", "selenium_ug", "manganese_mg", "magnesium_mg"), ("lunch", "dinner", "side"), diet_tags=V, allergens=("gluten",)),
    _seed("brown_rice", "Brown rice", "rice brown long grain cooked", 160, "grain", ("manganese_mg", "magnesium_mg", "fiber_g"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("wild_rice", "Wild rice", "wild rice cooked", 160, "grain", ("protein_g", "fiber_g", "magnesium_mg", "zinc_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("quinoa", "Quinoa", "quinoa cooked", 160, "grain", ("protein_g", "fiber_g", "magnesium_mg", "iron_mg", "folate_ug"), ("breakfast", "lunch", "dinner", "side"), diet_tags=PG),
    _seed("buckwheat", "Buckwheat", "buckwheat groats roasted cooked", 160, "grain", ("fiber_g", "magnesium_mg", "manganese_mg", "protein_g"), ("breakfast", "lunch", "dinner"), diet_tags=PG),
    _seed("bulgur", "Bulgur", "bulgur cooked", 160, "grain", ("fiber_g", "manganese_mg", "magnesium_mg"), ("lunch", "dinner", "side"), diet_tags=V, allergens=("wheat", "gluten")),
    _seed("whole_wheat_pasta", "Whole-wheat pasta", "spaghetti whole wheat cooked", 160, "grain", ("fiber_g", "protein_g", "selenium_ug", "magnesium_mg"), ("lunch", "dinner"), diet_tags=V, allergens=("wheat", "gluten")),
    _seed("whole_wheat_bread", "Whole-wheat bread", "bread whole wheat", 60, "grain", ("fiber_g", "iron_mg", "folate_ug", "selenium_ug"), ("breakfast", "lunch", "snack"), diet_tags=V, allergens=("wheat", "gluten")),
    _seed("corn", "Corn", "corn sweet yellow cooked boiled drained without salt", 140, "grain", ("fiber_g", "folate_ug", "magnesium_mg"), ("lunch", "dinner", "side"), diet_tags=PG),
    _seed("millet", "Millet", "millet cooked", 160, "grain", ("magnesium_mg", "phosphorus_mg", "protein_g"), ("breakfast", "lunch", "dinner"), diet_tags=PG),
    _seed("amaranth", "Amaranth", "amaranth grain cooked", 160, "grain", ("protein_g", "iron_mg", "magnesium_mg", "calcium_mg"), ("breakfast", "lunch", "dinner"), diet_tags=PG),

    # Nuts / seeds
    _seed("almonds", "Almonds", "almonds raw", 28, "nuts_seeds", ("vitamin_e_mg", "magnesium_mg", "calcium_mg", "protein_g", "fiber_g"), ("snack", "topping"), diet_tags=PG, allergens=("tree_nuts", "almond")),
    _seed("walnuts", "Walnuts", "walnuts english raw", 28, "nuts_seeds", ("omega3_g", "magnesium_mg", "copper_mg", "protein_g"), ("snack", "topping"), diet_tags=PG, allergens=("tree_nuts", "walnut")),
    _seed("pistachios", "Pistachios", "pistachio nuts raw", 28, "nuts_seeds", ("protein_g", "fiber_g", "vitamin_b6_mg", "potassium_mg"), ("snack", "topping"), diet_tags=PG, allergens=("tree_nuts", "pistachio")),
    _seed("cashews", "Cashews", "cashew nuts raw", 28, "nuts_seeds", ("magnesium_mg", "zinc_mg", "copper_mg", "protein_g"), ("snack", "topping"), diet_tags=PG, allergens=("tree_nuts", "cashew")),
    _seed("pecans", "Pecans", "pecans raw", 28, "nuts_seeds", ("fiber_g", "manganese_mg", "zinc_mg"), ("snack", "topping"), diet_tags=PG, allergens=("tree_nuts", "pecan")),
    _seed("hazelnuts", "Hazelnuts", "hazelnuts filberts raw", 28, "nuts_seeds", ("vitamin_e_mg", "manganese_mg", "magnesium_mg"), ("snack", "topping"), diet_tags=PG, allergens=("tree_nuts", "hazelnut")),
    _seed("peanuts", "Peanuts", "peanuts all types raw", 28, "nuts_seeds", ("protein_g", "niacin_mg", "magnesium_mg", "folate_ug"), ("snack", "topping"), diet_tags=PG, allergens=("peanut",)),
    _seed("chia", "Chia seeds", "seeds chia dried", 20, "nuts_seeds", ("fiber_g", "omega3_g", "calcium_mg", "magnesium_mg"), ("breakfast", "snack", "topping"), diet_tags=PG),
    _seed("flax", "Flax seeds", "seeds flaxseed", 20, "nuts_seeds", ("fiber_g", "omega3_g", "magnesium_mg"), ("breakfast", "snack", "topping"), diet_tags=PG),
    _seed("pumpkin_seeds", "Pumpkin seeds", "seeds pumpkin and squash kernels roasted without salt", 28, "nuts_seeds", ("magnesium_mg", "zinc_mg", "iron_mg", "protein_g"), ("snack", "topping"), diet_tags=PG),
    _seed("sunflower_seeds", "Sunflower seeds", "seeds sunflower seed kernels dry roasted without salt", 28, "nuts_seeds", ("vitamin_e_mg", "magnesium_mg", "selenium_ug", "protein_g"), ("snack", "topping"), diet_tags=PG),
    _seed("sesame_seeds", "Sesame seeds", "seeds sesame whole dried", 20, "nuts_seeds", ("calcium_mg", "iron_mg", "magnesium_mg", "zinc_mg"), ("snack", "topping"), diet_tags=PG, allergens=("sesame",)),
    _seed("hemp_seeds", "Hemp seeds", "seeds hemp seed hulled", 28, "nuts_seeds", ("protein_g", "magnesium_mg", "iron_mg", "omega3_g"), ("breakfast", "snack", "topping"), diet_tags=PG),

    # Dairy / eggs
    _seed("plain_greek_yogurt", "Plain Greek yogurt", "yogurt greek plain nonfat", 170, "dairy", ("protein_g", "calcium_mg", "vitamin_b12_ug", "phosphorus_mg"), ("breakfast", "snack", "side"), diet_tags=VG, allergens=("milk", "dairy")),
    _seed("plain_lowfat_yogurt", "Plain low-fat yogurt", "yogurt plain low fat", 170, "dairy", ("calcium_mg", "protein_g", "vitamin_b12_ug", "phosphorus_mg"), ("breakfast", "snack", "side"), diet_tags=VG, allergens=("milk", "dairy")),
    _seed("cottage_cheese", "Low-fat cottage cheese", "cheese cottage lowfat 2 percent milkfat", 120, "dairy", ("protein_g", "calcium_mg", "vitamin_b12_ug", "selenium_ug"), ("breakfast", "snack", "lunch"), diet_tags=VG, allergens=("milk", "dairy")),
    _seed("milk_1pct", "Low-fat milk", "milk lowfat 1 percent milkfat", 240, "dairy", ("calcium_mg", "protein_g", "vitamin_d_ug", "vitamin_b12_ug"), ("breakfast", "snack"), diet_tags=VG, allergens=("milk", "dairy")),
    _seed("mozzarella_partskim", "Part-skim mozzarella", "cheese mozzarella part skim milk", 50, "dairy", ("protein_g", "calcium_mg", "vitamin_b12_ug"), ("lunch", "dinner", "snack"), diet_tags=VG, allergens=("milk", "dairy")),
    _seed("ricotta_partskim", "Part-skim ricotta", "cheese ricotta part skim milk", 100, "dairy", ("protein_g", "calcium_mg", "vitamin_b12_ug"), ("breakfast", "lunch", "snack"), diet_tags=VG, allergens=("milk", "dairy")),
    _seed("egg", "Boiled egg", "egg whole cooked hard boiled", 50, "egg", ("protein_g", "vitamin_b12_ug", "selenium_ug", "vitamin_d_ug"), ("breakfast", "lunch", "snack"), diet_tags=("ovo_vegetarian", "gluten_free"), allergens=("egg",)),
    _seed("egg_whites", "Egg whites", "egg white cooked", 100, "egg", ("protein_g", "selenium_ug", "riboflavin_mg"), ("breakfast", "lunch", "snack"), diet_tags=("ovo_vegetarian", "gluten_free"), allergens=("egg",)),

    # Fish / seafood
    _seed("salmon", "Salmon", "salmon atlantic cooked dry heat", 100, "fish", ("protein_g", "omega3_g", "vitamin_d_ug", "vitamin_b12_ug", "selenium_ug"), ("lunch", "dinner"), diet_tags=("pescatarian", "gluten_free"), allergens=("fish",)),
    _seed("sardines", "Sardines", "sardine canned in oil drained solids with bone", 90, "fish", ("omega3_g", "calcium_mg", "vitamin_d_ug", "vitamin_b12_ug", "protein_g"), ("lunch", "dinner", "snack"), diet_tags=("pescatarian", "gluten_free"), allergens=("fish",)),
    _seed("trout", "Trout", "trout rainbow cooked dry heat", 100, "fish", ("protein_g", "omega3_g", "vitamin_d_ug", "vitamin_b12_ug"), ("lunch", "dinner"), diet_tags=("pescatarian", "gluten_free"), allergens=("fish",)),
    _seed("tuna", "Tuna", "tuna light canned in water drained solids", 100, "fish", ("protein_g", "selenium_ug", "vitamin_b12_ug", "niacin_mg"), ("lunch", "dinner"), diet_tags=("pescatarian", "gluten_free"), allergens=("fish",)),
    _seed("cod", "Cod", "cod pacific cooked dry heat", 100, "fish", ("protein_g", "selenium_ug", "vitamin_b12_ug", "phosphorus_mg"), ("lunch", "dinner"), diet_tags=("pescatarian", "gluten_free"), allergens=("fish",)),
    _seed("herring", "Herring", "herring atlantic cooked dry heat", 100, "fish", ("omega3_g", "vitamin_d_ug", "vitamin_b12_ug", "protein_g"), ("lunch", "dinner"), diet_tags=("pescatarian", "gluten_free"), allergens=("fish",)),
    _seed("mackerel", "Mackerel", "mackerel atlantic cooked dry heat", 100, "fish", ("omega3_g", "vitamin_d_ug", "vitamin_b12_ug", "selenium_ug"), ("lunch", "dinner"), diet_tags=("pescatarian", "gluten_free"), allergens=("fish",)),
    _seed("shrimp", "Shrimp", "shrimp cooked", 100, "shellfish", ("protein_g", "selenium_ug", "vitamin_b12_ug"), ("lunch", "dinner"), diet_tags=("pescatarian", "gluten_free"), allergens=("shellfish",)),

    # Poultry / meat
    _seed("chicken_breast", "Chicken breast", "chicken broilers fryers breast meat only cooked roasted", 120, "meat", ("protein_g", "niacin_mg", "vitamin_b6_mg", "selenium_ug"), ("lunch", "dinner"), diet_tags=("gluten_free",)),
    _seed("turkey_breast", "Turkey breast", "turkey breast meat only cooked roasted", 120, "meat", ("protein_g", "niacin_mg", "vitamin_b6_mg", "selenium_ug"), ("lunch", "dinner"), diet_tags=("gluten_free",)),
    _seed("lean_beef", "Lean beef", "beef top sirloin steak separable lean only cooked grilled", 100, "meat", ("protein_g", "iron_mg", "zinc_mg", "vitamin_b12_ug"), ("lunch", "dinner"), diet_tags=("gluten_free",)),
    _seed("pork_tenderloin", "Pork tenderloin", "pork fresh loin tenderloin separable lean only cooked roasted", 100, "meat", ("protein_g", "thiamin_mg", "selenium_ug", "zinc_mg"), ("lunch", "dinner"), diet_tags=("gluten_free",)),
)

# Guard against accidental duplicate display identities in the maintained base.
assert len({item["id"] for item in RECOMMENDATION_FOOD_BASE}) == len(RECOMMENDATION_FOOD_BASE)
