import 'usda_food_suggestion.dart';

class ManualRecipeIngredient {
  const ManualRecipeIngredient({
    required this.food,
    required this.grams,
  });

  final UsdaFoodSuggestion food;
  final double grams;

  ManualRecipeIngredient copyWith({double? grams}) => ManualRecipeIngredient(
        food: food,
        grams: grams ?? this.grams,
      );

  factory ManualRecipeIngredient.fromJson(Map<String, dynamic> json) {
    return ManualRecipeIngredient(
      food: UsdaFoodSuggestion.fromJson(
        Map<String, dynamic>.from(json['food'] as Map),
      ),
      grams: (json['grams'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'food': food.toJson(),
        'grams': grams,
      };

  Map<String, dynamic> toBackendJson() => {
        'fdc_id': food.fdcId,
        'name': food.displayName,
        'description': food.description,
        'data_type': food.dataType,
        if (food.foodCategory != null) 'food_category': food.foodCategory,
        'grams': grams,
      };
}

class ManualRecipe {
  const ManualRecipe({
    required this.id,
    required this.name,
    required this.ingredients,
    this.servingsMade = 1,
    this.servingsEaten = 1,
    this.source = 'manual',
  });

  final String id;
  final String name;
  final List<ManualRecipeIngredient> ingredients;
  final double servingsMade;
  final double servingsEaten;
  final String source;

  double get portionFraction =>
      servingsMade <= 0 ? 1 : (servingsEaten / servingsMade).clamp(0.0, 1.0);

  factory ManualRecipe.fromJson(Map<String, dynamic> json) {
    final rawIngredients = json['ingredients'];
    return ManualRecipe(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? 'My recipe',
      ingredients: rawIngredients is List
          ? rawIngredients
              .whereType<Map>()
              .map((item) => ManualRecipeIngredient.fromJson(Map<String, dynamic>.from(item)))
              .toList(growable: false)
          : const [],
      servingsMade: (json['servings_made'] as num?)?.toDouble() ?? 1,
      servingsEaten: (json['servings_eaten'] as num?)?.toDouble() ?? 1,
      source: json['source']?.toString() ?? 'manual',
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'ingredients': ingredients.map((item) => item.toJson()).toList(),
        'servings_made': servingsMade,
        'servings_eaten': servingsEaten,
        'source': source,
      };

  Map<String, dynamic> toBackendJson({Map<String, dynamic>? profile}) => {
        'recipe_name': name.trim().isEmpty ? 'Manual recipe' : name.trim(),
        'ingredients': ingredients.map((item) => item.toBackendJson()).toList(),
        'servings_made': servingsMade,
        'servings_eaten': servingsEaten,
        'source': source,
        if (profile != null && profile.isNotEmpty) 'profile': profile,
      };
}
