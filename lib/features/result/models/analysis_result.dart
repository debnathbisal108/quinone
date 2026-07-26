import 'dart:math' as math;

class AnalysisResult {
  const AnalysisResult({
    required this.mealName,
    required this.summary,
    required this.calories,
    required this.protein,
    required this.carbohydrates,
    required this.fat,
    required this.fiber,
    required this.healthScores,
    required this.micronutrients,
    required this.foods,
  });

  final String mealName;
  final String? summary;
  final double calories;
  final double protein;
  final double carbohydrates;
  final double fat;
  final double fiber;
  final List<HealthScore> healthScores;
  final List<Micronutrient> micronutrients;
  final List<FoodSummary> foods;

  double get overallScore {
    if (healthScores.isEmpty) return 0;
    final weightedTotal = healthScores.fold<double>(
      0,
      (sum, item) => sum + (item.score * math.max(item.confidence, 0.25)),
    );
    final weights = healthScores.fold<double>(
      0,
      (sum, item) => sum + math.max(item.confidence, 0.25),
    );
    return weights == 0 ? 0 : weightedTotal / weights;
  }

  factory AnalysisResult.fromJson(Map<String, dynamic> json) {
    final root = _unwrapResult(json);
    final meal = _asMap(root['meal']) ?? root;
    final foodsJson = _asList(meal['foods']);
    final foods = foodsJson
        .map((item) => FoodSummary.fromJson(_asMap(item) ?? const {}))
        .toList();

    final macroTotals = <String, double>{};
    final microTotals = <String, double>{};

    for (final food in foodsJson) {
      final foodMap = _asMap(food) ?? const <String, dynamic>{};
      final features = _asMap(foodMap['features']) ?? const <String, dynamic>{};
      _addValues(macroTotals, _asMap(features['macronutrients']));
      _addValues(microTotals, _asMap(features['vitamins']));
      _addValues(microTotals, _asMap(features['minerals']));
    }

    final directNutrition = _asMap(root['nutrition']);
    if (macroTotals.isEmpty && directNutrition != null) {
      _addValues(macroTotals, directNutrition);
      _addValues(microTotals, _asMap(directNutrition['vitamins']));
      _addValues(microTotals, _asMap(directNutrition['minerals']));
    }

    final scoreMap = _asMap(meal['health_domain_scores']) ??
        _asMap(root['health_scores']) ??
        const <String, dynamic>{};

    final scores = scoreMap.entries
        .map((entry) => HealthScore.fromEntry(entry.key, entry.value))
        .where((item) => item.score.isFinite)
        .toList()
      ..sort((a, b) => b.score.compareTo(a.score));

    final micronutrients = microTotals.entries
        .where((entry) => entry.value > 0)
        .map((entry) => Micronutrient.fromKeyValue(entry.key, entry.value))
        .where((item) => item.dailyValue > 0)
        .toList()
      ..sort((a, b) => b.percentDailyValue.compareTo(a.percentDailyValue));

    return AnalysisResult(
      mealName: _firstText(meal, const ['meal_name', 'name', 'title', 'meal_type']) ??
          'Meal analysis',
      summary: _firstText(meal, const ['summary', 'description']) ??
          _firstText(root, const ['summary', 'message']),
      calories: _number(macroTotals['energy_kcal']),
      protein: _number(macroTotals['protein_g']),
      carbohydrates: _number(macroTotals['carbohydrate_g'] ?? macroTotals['carbs_g']),
      fat: _number(macroTotals['fat_g']),
      fiber: _number(macroTotals['fiber_g']),
      healthScores: scores,
      micronutrients: micronutrients,
      foods: foods,
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

class HealthScore {
  const HealthScore({
    required this.key,
    required this.label,
    required this.score,
    required this.confidence,
  });

  final String key;
  final String label;
  final double score;
  final double confidence;

  factory HealthScore.fromEntry(String key, dynamic value) {
    final map = _asMap(value);
    return HealthScore(
      key: key,
      label: _titleCase(map?['health_domain']?.toString() ?? key),
      score: _number(map?['score'] ?? value).clamp(0, 100),
      confidence: _normaliseFraction(_number(map?['confidence'] ?? 1)),
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

  double get percentDailyValue => dailyValue <= 0 ? 0 : (amount / dailyValue) * 100;

  factory Micronutrient.fromKeyValue(String key, double amount) {
    final definition = _micronutrientDefinitions[key];
    final unit = key.endsWith('_ug') ? 'µg' : 'mg';
    return Micronutrient(
      key: key,
      label: definition?.label ?? _titleCase(key.replaceAll(RegExp(r'_(mg|ug)$'), '')),
      amount: amount,
      unit: definition?.unit ?? unit,
      dailyValue: definition?.dailyValue ?? 0,
    );
  }
}

class FoodSummary {
  const FoodSummary({
    required this.name,
    required this.weightGrams,
    required this.calories,
    required this.protein,
  });

  final String name;
  final double weightGrams;
  final double calories;
  final double protein;

  factory FoodSummary.fromJson(Map<String, dynamic> json) {
    final features = _asMap(json['features']) ?? const <String, dynamic>{};
    final macros = _asMap(features['macronutrients']) ?? const <String, dynamic>{};
    final physical = _asMap(features['physical']) ?? const <String, dynamic>{};
    return FoodSummary(
      name: _firstText(json, const ['display_name', 'name', 'canonical_name']) ?? 'Detected food',
      weightGrams: _number(
        json['estimated_weight_g'] ??
            json['weight_g'] ??
            physical['serving_size_g'],
      ),
      calories: _number(macros['energy_kcal']),
      protein: _number(macros['protein_g']),
    );
  }
}

class _MicronutrientDefinition {
  const _MicronutrientDefinition(this.label, this.dailyValue, this.unit);
  final String label;
  final double dailyValue;
  final String unit;
}

const _micronutrientDefinitions = <String, _MicronutrientDefinition>{
  'vitamin_a_ug': _MicronutrientDefinition('Vitamin A', 900, 'µg'),
  'vitamin_c_mg': _MicronutrientDefinition('Vitamin C', 90, 'mg'),
  'vitamin_d_ug': _MicronutrientDefinition('Vitamin D', 20, 'µg'),
  'vitamin_e_mg': _MicronutrientDefinition('Vitamin E', 15, 'mg'),
  'vitamin_k_ug': _MicronutrientDefinition('Vitamin K', 120, 'µg'),
  'thiamin_mg': _MicronutrientDefinition('Thiamin (B1)', 1.2, 'mg'),
  'riboflavin_mg': _MicronutrientDefinition('Riboflavin (B2)', 1.3, 'mg'),
  'niacin_mg': _MicronutrientDefinition('Niacin (B3)', 16, 'mg'),
  'pantothenic_acid_mg': _MicronutrientDefinition('Pantothenic acid', 5, 'mg'),
  'vitamin_b6_mg': _MicronutrientDefinition('Vitamin B6', 1.7, 'mg'),
  'folate_ug': _MicronutrientDefinition('Folate', 400, 'µg'),
  'vitamin_b12_ug': _MicronutrientDefinition('Vitamin B12', 2.4, 'µg'),
  'choline_mg': _MicronutrientDefinition('Choline', 550, 'mg'),
  'calcium_mg': _MicronutrientDefinition('Calcium', 1300, 'mg'),
  'iron_mg': _MicronutrientDefinition('Iron', 18, 'mg'),
  'magnesium_mg': _MicronutrientDefinition('Magnesium', 420, 'mg'),
  'phosphorus_mg': _MicronutrientDefinition('Phosphorus', 1250, 'mg'),
  'potassium_mg': _MicronutrientDefinition('Potassium', 4700, 'mg'),
  'sodium_mg': _MicronutrientDefinition('Sodium', 2300, 'mg'),
  'zinc_mg': _MicronutrientDefinition('Zinc', 11, 'mg'),
  'copper_mg': _MicronutrientDefinition('Copper', 0.9, 'mg'),
  'manganese_mg': _MicronutrientDefinition('Manganese', 2.3, 'mg'),
  'selenium_ug': _MicronutrientDefinition('Selenium', 55, 'µg'),
};

void _addValues(Map<String, double> target, Map<String, dynamic>? source) {
  if (source == null) return;
  for (final entry in source.entries) {
    final value = _number(entry.value);
    if (value.isFinite && value > 0) {
      target.update(entry.key, (current) => current + value, ifAbsent: () => value);
    }
  }
}

Map<String, dynamic>? _asMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return Map<String, dynamic>.from(value);
  return null;
}

List<dynamic> _asList(dynamic value) => value is List ? value : const [];

double _number(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? 0;
}

double _normaliseFraction(double value) => value > 1 ? (value / 100).clamp(0, 1) : value.clamp(0, 1);

String? _firstText(Map<String, dynamic> source, List<String> keys) {
  for (final key in keys) {
    final text = source[key]?.toString().trim();
    if (text != null && text.isNotEmpty && text.toLowerCase() != 'null') return text;
  }
  return null;
}

String _titleCase(String input) => input
    .replaceAll('_', ' ')
    .split(RegExp(r'\s+'))
    .where((word) => word.isNotEmpty)
    .map((word) => '${word[0].toUpperCase()}${word.substring(1).toLowerCase()}')
    .join(' ');
