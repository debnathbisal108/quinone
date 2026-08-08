import 'dart:math' as math;

/// Parsed result displayed by the result screen.
///
/// Meal-level totals returned by the backend are always authoritative. Food-level
/// values are retained only for contribution details and are never allowed to
/// overwrite an available backend total.
class AnalysisResult {
  const AnalysisResult({
    required this.mealName,
    required this.summary,
    required this.calories,
    required this.protein,
    required this.carbohydrates,
    required this.fat,
    required this.saturatedFat,
    required this.monounsaturatedFat,
    required this.polyunsaturatedFat,
    required this.transFat,
    required this.omega3,
    required this.omega6,
    required this.cholesterol,
    required this.fiber,
    required this.sugars,
    required this.addedSugars,
    required this.healthScores,
    required this.micronutrients,
    required this.foods,
    required this.nutrientTargets,
    required this.nutrientRiskFlags,
    required this.personalizationApplied,
    required this.usedAuthoritativeNutritionTotals,
  });

  final String mealName;
  final String? summary;
  final double calories;
  final double protein;
  final double carbohydrates;
  final double fat;
  final double? saturatedFat;
  final double? monounsaturatedFat;
  final double? polyunsaturatedFat;
  final double? transFat;
  final double? omega3;
  final double? omega6;
  final double? cholesterol;
  final double fiber;
  final double? sugars;
  final double? addedSugars;
  final List<HealthScore> healthScores;
  final List<Micronutrient> micronutrients;
  final List<FoodSummary> foods;
  final Map<String, PersonalizedNutrientTarget> nutrientTargets;
  final List<NutrientRiskFlag> nutrientRiskFlags;
  final bool personalizationApplied;

  /// A display-only de-duplicated food list. It never changes authoritative
  /// meal totals. Enrichment pipelines can carry both the visible portion and
  /// a database reference row for the same food; the best portion row wins.
  List<FoodSummary> get displayFoods {
    final bestByName = <String, FoodSummary>{};

    for (final food in foods) {
      final key = _normalizedDisplayFoodName(food.name);
      final existing = bestByName[key];
      if (existing == null ||
          _foodDisplayQuality(food) > _foodDisplayQuality(existing)) {
        bestByName[key] = food;
      }
    }

    return List.unmodifiable(bestByName.values);
  }

  /// False only for legacy responses that contain no meal-level totals and
  /// therefore require a deduplicated food-level fallback.
  final bool usedAuthoritativeNutritionTotals;

  double get overallScore {
    if (healthScores.isEmpty) return 0;

    final weightedTotal = healthScores.fold<double>(
      0,
      (sum, item) => sum + item.score * math.max(item.confidence, 0.25),
    );
    final totalWeight = healthScores.fold<double>(
      0,
      (sum, item) => sum + math.max(item.confidence, 0.25),
    );

    return totalWeight == 0 ? 0 : weightedTotal / totalWeight;
  }

  /// Returns a deduplicated food-level breakdown for the requested nutrient.
  /// These amounts explain the backend total; they do not replace it.
  List<NutrientContribution> contributionsFor(String key) {
    final totalsByFood = <String, NutrientContribution>{};

    for (final food in foods) {
      final amount = food.nutrients[key] ?? 0;
      if (amount <= 0) continue;

      final identity = _normalizedDisplayFoodName(food.name);
      final existing = totalsByFood[identity];
      if (existing == null) {
        totalsByFood[identity] = NutrientContribution(
          foodName: food.name,
          amount: amount,
        );
      } else {
        // Exact duplicate entities can occur in enriched payloads. Keep the
        // larger identical representation instead of adding it twice.
        totalsByFood[identity] = NutrientContribution(
          foodName: existing.foodName,
          amount: math.max(existing.amount, amount),
        );
      }
    }

    final result = totalsByFood.values.toList()
      ..sort((a, b) => b.amount.compareTo(a.amount));
    return result;
  }

  factory AnalysisResult.fromJson(Map<String, dynamic> json) {
    final root = _unwrapResult(json);
    final meal = _asMap(root['meal']) ?? root;

    final foods = _asList(meal['foods'])
        .map((item) => FoodSummary.fromJson(_asMap(item) ?? const {}))
        .toList(growable: false);

    final authoritativeNutrition = _findAuthoritativeNutrition(root, meal);
    final usedAuthoritativeTotals = authoritativeNutrition != null;

    // The current backend may return nutrients only inside each detected food.
    // In that valid response shape, build the meal totals from the unique foods
    // instead of rejecting the completed response.
    final nutrition = authoritativeNutrition ?? _aggregateFoodNutrition(foods);

    final macros = _extractMacroMap(nutrition);
    final vitamins = _extractSection(nutrition, const ['vitamins']);
    final minerals = _extractSection(nutrition, const ['minerals']);
    final micronutrientValues = <String, double>{
      ...vitamins,
      ...minerals,
    };

    final personalization =
        _asMap(meal['personalization']) ?? _asMap(root['personalization']);

    final rawTargets = _asMap(
          personalization?['nutrient_targets'],
        ) ??
        const <String, dynamic>{};

    final nutrientTargets = <String, PersonalizedNutrientTarget>{};
    for (final entry in rawTargets.entries) {
      final map = _asMap(entry.value);
      if (map == null) continue;
      nutrientTargets[entry.key] = PersonalizedNutrientTarget.fromJson(
        entry.key,
        map,
      );
    }

    final nutrientRiskFlags = _asList(
      personalization?['nutrient_risk_flags'],
    )
        .map(_asMap)
        .whereType<Map<String, dynamic>>()
        .map(NutrientRiskFlag.fromJson)
        .toList(growable: false);

    final personalizedScores = _asMap(
      personalization?['personalized_domain_scores'],
    );
    final scoreMap = personalizedScores ??
        _asMap(meal['health_domain_scores']) ??
        _asMap(root['health_domain_scores']) ??
        _asMap(root['health_scores']) ??
        const <String, dynamic>{};

    final scores = scoreMap.entries
        .map((entry) => HealthScore.fromEntry(entry.key, entry.value))
        .toList()
      ..sort((a, b) => b.score.compareTo(a.score));

    final micronutrients = micronutrientValues.entries
        .where((entry) => entry.value > 0)
        .map((entry) => Micronutrient.fromKeyValue(entry.key, entry.value))
        .where((nutrient) => nutrient.dailyValue > 0)
        .toList()
      ..sort(
        (a, b) => b.percentDailyValue.compareTo(a.percentDailyValue),
      );

    return AnalysisResult(
      mealName: _firstText(
            meal,
            const ['meal_name', 'name', 'title', 'meal_type'],
          ) ??
          'Meal analysis',
      summary: _firstText(meal, const ['summary', 'description']) ??
          _firstText(root, const ['summary', 'message']),
      calories: _firstNumber(
        macros,
        const ['energy_kcal', 'calories', 'calories_kcal'],
      ),
      protein: _firstNumber(macros, const ['protein_g', 'protein']),
      carbohydrates: _firstNumber(
        macros,
        const ['carbohydrate_g', 'carbohydrates_g', 'carbs_g', 'carbs'],
      ),
      fat: _firstNumber(macros, const ['fat_g', 'total_fat_g', 'fat']),
      saturatedFat: _firstNullableNumber(
        macros,
        const [
          'saturated_fat_g',
          'total_saturated_fat_g',
        ],
      ),
      monounsaturatedFat: _firstNullableNumber(
        macros,
        const [
          'monounsaturated_fat_g',
          'total_monounsaturated_fat_g',
        ],
      ),
      polyunsaturatedFat: _firstNullableNumber(
        macros,
        const [
          'polyunsaturated_fat_g',
          'total_polyunsaturated_fat_g',
        ],
      ),
      transFat: _firstNullableNumber(
        macros,
        const [
          'trans_fat_g',
          'total_trans_fat_g',
        ],
      ),
      omega3: _firstNullableNumber(
        macros,
        const [
          'omega3_g',
          'omega_3_g',
        ],
      ),
      omega6: _firstNullableNumber(
        macros,
        const [
          'omega6_g',
          'omega_6_g',
        ],
      ),
      cholesterol: _firstNullableNumber(
        macros,
        const [
          'cholesterol_mg',
          'cholesterol',
        ],
      ),
      fiber: _firstNumber(
        macros,
        const [
          'fiber_g',
          'fibre_g',
          'dietary_fiber_g',
        ],
      ),
      sugars: _firstNullableNumber(
        macros,
        const [
          'sugars_g',
          'total_sugars_g',
          'sugar_g',
          'sugars',
        ],
      ),
      addedSugars: _firstNullableNumber(
        macros,
        const [
          'added_sugars_g',
          'added_sugar_g',
          'added_sugars',
        ],
      ),
      healthScores: List.unmodifiable(scores),
      micronutrients: List.unmodifiable(micronutrients),
      foods: List.unmodifiable(foods),
      nutrientTargets: Map.unmodifiable(nutrientTargets),
      nutrientRiskFlags: List.unmodifiable(nutrientRiskFlags),
      personalizationApplied: personalization?['profile_applied'] == true,
      usedAuthoritativeNutritionTotals: usedAuthoritativeTotals,
    );
  }

  static Map<String, dynamic> _unwrapResult(Map<String, dynamic> json) {
    for (final key in const ['final_result', 'meal_analysis', 'data']) {
      final nested = _asMap(json[key]);
      if (nested != null && nested.isNotEmpty) return nested;
    }
    return json;
  }
}

class PersonalizedNutrientTarget {
  const PersonalizedNutrientTarget({
    required this.key,
    required this.name,
    required this.targetType,
    required this.unit,
    required this.status,
    required this.baselineValue,
    required this.resolvedValue,
    required this.rangeLow,
    required this.rangeHigh,
    required this.upperLimit,
    required this.requiredInputs,
    required this.warnings,
    required this.overrideChain,
  });

  final String key;
  final String name;
  final String? targetType;
  final String unit;
  final String status;
  final double? baselineValue;
  final double? resolvedValue;
  final double? rangeLow;
  final double? rangeHigh;
  final double? upperLimit;
  final List<String> requiredInputs;
  final List<String> warnings;
  final List<String> overrideChain;

  bool get isResolved =>
      status == 'resolved' || status == 'resolved_range';

  bool get isRange => rangeLow != null && rangeHigh != null;

  factory PersonalizedNutrientTarget.fromJson(
    String key,
    Map<String, dynamic> json,
  ) {
    return PersonalizedNutrientTarget(
      key: key,
      name: json['nutrient_name']?.toString().trim().isNotEmpty == true
          ? json['nutrient_name'].toString().trim()
          : _titleCase(key),
      targetType: json['target_type']?.toString(),
      unit: json['resolved_unit']?.toString() ?? '',
      status: json['status']?.toString() ?? 'unresolved',
      baselineValue: _nullableNumber(json['baseline_value']),
      resolvedValue: _nullableNumber(json['resolved_value']),
      rangeLow: _nullableNumber(json['range_low']),
      rangeHigh: _nullableNumber(json['range_high']),
      upperLimit: _nullableNumber(json['upper_limit']),
      requiredInputs: _stringList(json['required_inputs']),
      warnings: _stringList(json['warnings']),
      overrideChain: _stringList(json['override_chain']),
    );
  }
}

class NutrientRiskFlag {
  const NutrientRiskFlag({
    required this.id,
    required this.type,
    required this.message,
    required this.affectedNutrients,
  });

  final String id;
  final String type;
  final String? message;
  final List<String> affectedNutrients;

  factory NutrientRiskFlag.fromJson(Map<String, dynamic> json) {
    return NutrientRiskFlag(
      id: json['id']?.toString() ?? 'nutrient_risk',
      type: json['type']?.toString() ?? 'risk_flag',
      message: json['message']?.toString(),
      affectedNutrients: _stringList(json['affected_nutrients']),
    );
  }
}

class NutrientContribution {
  const NutrientContribution({
    required this.foodName,
    required this.amount,
  });

  final String foodName;
  final double amount;
}

class HealthScore {
  const HealthScore({
    required this.key,
    required this.label,
    required this.score,
    required this.directionalScore,
    required this.confidence,
    required this.coverage,
    required this.reliability,
    required this.positiveContributors,
    required this.negativeContributors,
  });

  final String key;
  final String label;
  final double score;
  final double directionalScore;
  final double confidence;
  final double coverage;
  final double reliability;
  final List<HealthContributor> positiveContributors;
  final List<HealthContributor> negativeContributors;

  factory HealthScore.fromEntry(
    String key,
    dynamic value,
  ) {
    final map = _asMap(value);

    return HealthScore(
      key: key,
      label: _titleCase(
        map?['health_domain']?.toString() ?? key,
      ),
      score: _number(
        map?['score'] ?? value,
      ).clamp(0, 100).toDouble(),
      directionalScore: _number(
        map?['directional_score'] ??
            map?['score'] ??
            value,
      ).clamp(0, 100).toDouble(),
      confidence: _fraction(
        _number(map?['confidence']),
      ),
      coverage: _fraction(
        _number(map?['coverage']),
      ),
      reliability: _fraction(
        _number(map?['reliability']),
      ),
      positiveContributors: List.unmodifiable(
        _asList(
          map?['positive_contributors'],
        )
            .map(
              (item) => HealthContributor.fromJson(
                _asMap(item) ?? const {},
              ),
            )
            .toList(),
      ),
      negativeContributors: List.unmodifiable(
        _asList(
          map?['negative_contributors'],
        )
            .map(
              (item) => HealthContributor.fromJson(
                _asMap(item) ?? const {},
              ),
            )
            .toList(),
      ),
    );
  }
}

class HealthContributor {
  const HealthContributor({
    required this.ruleName,
    required this.feature,
    required this.featureValue,
    required this.effectiveWeight,
    required this.confidence,
    required this.mechanism,
    required this.pathway,
  });

  final String ruleName;
  final String feature;
  final String? featureValue;
  final double effectiveWeight;
  final double confidence;
  final String? mechanism;
  final String? pathway;

  factory HealthContributor.fromJson(
    Map<String, dynamic> json,
  ) {
    final rawFeatureValue = json['feature_value'];

    return HealthContributor(
      ruleName: _firstText(
            json,
            const [
              'rule_name',
              'display_name',
              'rule_id',
            ],
          ) ??
          'Nutrition factor',
      feature: _firstText(
            json,
            const ['feature'],
          ) ??
          'Unknown feature',
      // featureValue: rawFeatureValue == null
      //     ? null
      //     : rawFeatureValue.toString(),
      featureValue: rawFeatureValue?.toString(),
      effectiveWeight: _number(
        json['effective_weight'],
      ),
      confidence: _fraction(
        _number(json['confidence']),
      ),
      mechanism: _firstText(
        json,
        const ['mechanism'],
      ),
      pathway: _firstText(
        json,
        const ['pathway'],
      ),
    );
  }
}

class Micronutrient {
  const Micronutrient({
    required this.key,
    required this.label,
    required this.amount,
    required this.unit,
    required this.dailyValue,
  });

  final String key;
  final String label;
  final double amount;
  final String unit;
  final double dailyValue;

  double get percentDailyValue =>
      dailyValue <= 0 ? 0 : amount / dailyValue * 100;

  factory Micronutrient.fromKeyValue(String key, double amount) {
    final definition = _definitions[key];
    return Micronutrient(
      key: key,
      label: definition?.label ??
          _titleCase(key.replaceAll(RegExp(r'_(mg|ug|mcg)$'), '')),
      amount: amount,
      unit: definition?.unit ?? _unitFromKey(key),
      dailyValue: definition?.dailyValue ?? 0,
    );
  }
}

class FoodSummary {
  const FoodSummary({
    required this.id,
    required this.name,
    required this.weightGrams,
    required this.calories,
    required this.protein,
    required this.macronutrients,
    required this.vitamins,
    required this.minerals,
  });

  final String? id;
  final String name;
  final double weightGrams;
  final double calories;
  final double protein;
  final Map<String, double> macronutrients;
  final Map<String, double> vitamins;
  final Map<String, double> minerals;

  String get identity {
    final normalizedId = id?.trim();
    if (normalizedId != null && normalizedId.isNotEmpty) return normalizedId;
    return '${name.trim().toLowerCase()}|${weightGrams.toStringAsFixed(3)}';
  }

  Map<String, double> get nutrients => {
        ...macronutrients,
        ...vitamins,
        ...minerals,
      };

  factory FoodSummary.fromJson(Map<String, dynamic> json) {
    final features =
    _asMap(json['features']) ?? const {};

    // final macros = <String, double>{
    //   ..._doubleMap(
    //     _asMap(json['nutrients']),
    //   ),
    //   ..._doubleMap(
    //     _asMap(features['macronutrients']),
    //   ),
    // };

    final macros = <String, double>{
      ..._doubleMap(
        _asMap(json['nutrients']),
      ),
      ..._doubleMap(
        _asMap(features['macronutrients']),
      ),
      ..._doubleMap(
        _asMap(features['fat_profile']),
      ),
    };

    return FoodSummary(
      id: _firstText(json, const ['id', 'food_id', 'entity_id']),
      name: _firstText(
            json,
            const ['display_name', 'name', 'canonical_name'],
          ) ??
          'Detected food',
      weightGrams: _number(
        json['estimated_weight_g'] ??
            json['weight_g'] ??
            _asMap(features['physical'])?['serving_size_g'],
      ),
      calories: _firstNumber(
        macros,
        const ['energy_kcal', 'calories', 'calories_kcal'],
      ),
      protein: _firstNumber(macros, const ['protein_g', 'protein']),
      macronutrients: Map.unmodifiable(macros),
      vitamins: Map.unmodifiable(
        _doubleMap(_asMap(features['vitamins'])),
      ),
      minerals: Map.unmodifiable(
        _doubleMap(_asMap(features['minerals'])),
      ),
    );
  }
}

double _foodDisplayQuality(FoodSummary food) {
  // A row with an actual portion weight is much more likely to be the visible
  // food than a USDA/reference row containing only per-100-g nutrition.
  if (food.weightGrams > 0) {
    return 1000000 + food.weightGrams * 100 + food.calories;
  }
  return food.calories * 10 + food.protein;
}

String _normalizedDisplayFoodName(String value) {
  var normalized = value
      .trim()
      .toLowerCase()
      .replaceAll(RegExp(r'[^a-z0-9\s]'), ' ')
      .replaceAll(RegExp(r'\s+'), ' ');

  const removableWords = <String>{
    'slice',
    'slices',
    'sliced',
    'piece',
    'pieces',
    'chopped',
    'diced',
    'slivered',
  };

  final tokens = normalized
      .split(' ')
      .where((token) => token.isNotEmpty && !removableWords.contains(token))
      .toList();
  normalized = tokens.join(' ');

  // Keep this conservative: only normalize the plural forms that commonly
  // appear as duplicate vision/database labels.
  const aliases = <String, String>{
    'bananas': 'banana',
    'blueberry': 'blueberries',
    'chia seed': 'chia seeds',
    'rolled oat': 'rolled oats',
    'almond': 'almonds',
  };
  return aliases[normalized] ?? normalized;
}

class _NutrientDefinition {
  const _NutrientDefinition(this.label, this.dailyValue, this.unit);

  final String label;
  final double dailyValue;
  final String unit;
}

// General adult label Daily Values. These are not personalized RDAs.
const _definitions = <String, _NutrientDefinition>{
  'vitamin_a_ug': _NutrientDefinition('Vitamin A', 900, 'µg'),
  'vitamin_c_mg': _NutrientDefinition('Vitamin C', 90, 'mg'),
  'vitamin_d_ug': _NutrientDefinition('Vitamin D', 20, 'µg'),
  'vitamin_e_mg': _NutrientDefinition('Vitamin E', 15, 'mg'),
  'vitamin_k_ug': _NutrientDefinition('Vitamin K', 120, 'µg'),
  'thiamin_mg': _NutrientDefinition('Thiamin (B1)', 1.2, 'mg'),
  'riboflavin_mg': _NutrientDefinition('Riboflavin (B2)', 1.3, 'mg'),
  'niacin_mg': _NutrientDefinition('Niacin (B3)', 16, 'mg'),
  'pantothenic_acid_mg':
      _NutrientDefinition('Pantothenic acid', 5, 'mg'),
  'vitamin_b6_mg': _NutrientDefinition('Vitamin B6', 1.7, 'mg'),
  'folate_ug': _NutrientDefinition('Folate', 400, 'µg'),
  'vitamin_b12_ug': _NutrientDefinition('Vitamin B12', 2.4, 'µg'),
  'choline_mg': _NutrientDefinition('Choline', 550, 'mg'),
  'calcium_mg': _NutrientDefinition('Calcium', 1300, 'mg'),
  'iron_mg': _NutrientDefinition('Iron', 18, 'mg'),
  'magnesium_mg': _NutrientDefinition('Magnesium', 420, 'mg'),
  'phosphorus_mg': _NutrientDefinition('Phosphorus', 1250, 'mg'),
  'potassium_mg': _NutrientDefinition('Potassium', 4700, 'mg'),
  'sodium_mg': _NutrientDefinition('Sodium', 2300, 'mg'),
  'zinc_mg': _NutrientDefinition('Zinc', 11, 'mg'),
  'copper_mg': _NutrientDefinition('Copper', 0.9, 'mg'),
  'manganese_mg': _NutrientDefinition('Manganese', 2.3, 'mg'),
  'selenium_ug': _NutrientDefinition('Selenium', 55, 'µg'),
};


Map<String, dynamic> _aggregateFoodNutrition(List<FoodSummary> foods) {
  final uniqueFoods = <String, FoodSummary>{};

  for (final food in foods) {
    final key = _normalizedDisplayFoodName(food.name);
    final existing = uniqueFoods[key];
    if (existing == null ||
        _foodDisplayQuality(food) > _foodDisplayQuality(existing)) {
      uniqueFoods[key] = food;
    }
  }

  final macros = <String, double>{};
  final vitamins = <String, double>{};
  final minerals = <String, double>{};

  void addValues(Map<String, double> target, Map<String, double> source) {
    for (final entry in source.entries) {
      target.update(
        entry.key,
        (value) => value + entry.value,
        ifAbsent: () => entry.value,
      );
    }
  }

  for (final food in uniqueFoods.values) {
    addValues(macros, food.macronutrients);
    addValues(vitamins, food.vitamins);
    addValues(minerals, food.minerals);
  }

  return <String, dynamic>{
    'macronutrients': macros,
    'vitamins': vitamins,
    'minerals': minerals,
  };
}

Map<String, dynamic>? _findAuthoritativeNutrition(
  Map<String, dynamic> root,
  Map<String, dynamic> meal,
) {
  final candidates = <dynamic>[
    meal['nutrition'],
    meal['nutrition_totals'],
    meal['total_nutrition'],
    meal['nutrition_summary'],
    root['nutrition'],
    root['nutrition_totals'],
    root['total_nutrition'],
    root['nutrition_summary'],
  ];

  for (final candidate in candidates) {
    final map = _asMap(candidate);
    if (map == null || map.isEmpty) continue;

    final macros = _extractMacroMap(map);
    if (_containsAnyNutritionValue(macros)) return map;
  }
  return null;
}

Map<String, double> _extractMacroMap(Map<String, dynamic> nutrition) {
  final result = <String, double>{};

  // Some APIs put macros directly in nutrition; others nest them.
  _mergeNumericValues(result, nutrition);
  for (final key in const [
    'macronutrients',
    'macros',
    'totals',
    'total',
    'per_serving',
    'nutrition_per_serving',
  ]) {
    _mergeNumericValues(result, _asMap(nutrition[key]));
  }

  return result;
}

Map<String, double> _extractSection(
  Map<String, dynamic> nutrition,
  List<String> keys,
) {
  final result = <String, double>{};
  for (final key in keys) {
    _mergeNumericValues(result, _asMap(nutrition[key]));
  }

  // Also retain known micronutrients if the backend returns a flat map.
  for (final entry in nutrition.entries) {
    if (_definitions.containsKey(entry.key)) {
      final value = _nullableNumber(entry.value);
      if (value != null) result[entry.key] = value;
    }
  }
  return result;
}

bool _containsAnyNutritionValue(Map<String, double> values) {
  const keys = {
    'energy_kcal',
    'calories',
    'calories_kcal',
    'protein_g',
    'protein',
    'carbohydrate_g',
    'carbohydrates_g',
    'carbs_g',
    'fat_g',
    'total_fat_g',
    'fiber_g',
    'fibre_g',
    'sugars_g',
    'total_sugars_g',
    'added_sugars_g',
  };
  return values.entries.any((entry) => keys.contains(entry.key));
}

void _mergeNumericValues(
  Map<String, double> target,
  Map<String, dynamic>? source,
) {
  if (source == null) return;
  for (final entry in source.entries) {
    final value = _nullableNumber(entry.value);
    if (value != null) target[entry.key] = value;
  }
}

Map<String, double> _doubleMap(Map<String, dynamic>? map) {
  final result = <String, double>{};
  for (final entry in (map ?? const <String, dynamic>{}).entries) {
    final value = _nullableNumber(entry.value);
    if (value != null) result[entry.key] = value;
  }
  return result;
}

List<String> _stringList(dynamic value) {
  if (value is! Iterable) return const <String>[];
  return value
      .map((item) => item.toString().trim())
      .where((item) => item.isNotEmpty)
      .toList(growable: false);
}

Map<String, dynamic>? _asMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return Map<String, dynamic>.from(value);
  return null;
}

List<dynamic> _asList(dynamic value) => value is List ? value : const [];

double? _nullableNumber(dynamic value) {
  if (value == null || value is bool) return null;
  final parsed = value is num
      ? value.toDouble()
      : double.tryParse(value.toString().trim());
  if (parsed == null || !parsed.isFinite || parsed < 0) return null;
  return parsed;
}

double _number(dynamic value) => _nullableNumber(value) ?? 0;

double _firstNumber(Map<String, double> source, List<String> keys) {
  for (final key in keys) {
    final value = source[key];
    if (value != null) return value;
  }
  return 0;
}

double? _firstNullableNumber(
  Map<String, double> source,
  List<String> keys,
) {
  for (final key in keys) {
    final value = source[key];

    if (value != null) {
      return value;
    }
  }

  return null;
}

double _fraction(double value) {
  return value > 1
      ? (value / 100).clamp(0, 1).toDouble()
      : value.clamp(0, 1).toDouble();
}

String? _firstText(Map<String, dynamic> source, List<String> keys) {
  for (final key in keys) {
    final text = source[key]?.toString().trim();
    if (text != null &&
        text.isNotEmpty &&
        text.toLowerCase() != 'null') {
      return text;
    }
  }
  return null;
}

String _unitFromKey(String key) {
  if (key.endsWith('_ug') || key.endsWith('_mcg')) return 'µg';
  if (key.endsWith('_mg')) return 'mg';
  if (key.endsWith('_g')) return 'g';
  return '';
}

String _titleCase(String value) {
  return value
      .replaceAll('_', ' ')
      .split(RegExp(r'\s+'))
      .where((word) => word.isNotEmpty)
      .map(
        (word) =>
            '${word[0].toUpperCase()}${word.substring(1).toLowerCase()}',
      )
      .join(' ');
}
