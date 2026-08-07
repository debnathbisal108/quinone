import 'dart:convert';

class AnalysisHistoryRecord {
  const AnalysisHistoryRecord({
    required this.analysisId,
    required this.createdAt,
    required this.mealName,
    required this.calories,
    required this.macronutrients,
    required this.micronutrients,
    required this.healthScores,
    required this.nutrientTargets,
    required this.detectedFoods,
    required this.rawResult,
  });

  final String analysisId;
  final DateTime createdAt;
  final String mealName;
  final double calories;
  final Map<String, double> macronutrients;
  final Map<String, double> micronutrients;
  final Map<String, double> healthScores;
  final Map<String, double> nutrientTargets;
  final List<String> detectedFoods;
  final Map<String, dynamic> rawResult;

  factory AnalysisHistoryRecord.fromAnalysisJson(
    Map<String, dynamic> json, {
    DateTime? createdAt,
  }) {
    final root = _unwrap(json);
    final meal = _asMap(root['meal']) ?? root;
    final nutrition = _findNutrition(root, meal);
    final macros = _extractNumericSection(
      nutrition,
      const ['macronutrients', 'macros', 'totals', 'total'],
    );

    final personalization =
        _asMap(meal['personalization']) ?? _asMap(root['personalization']);
    final targetMap = _asMap(personalization?['nutrient_targets']);
    final targets = <String, double>{};
    for (final entry in (targetMap ?? const <String, dynamic>{}).entries) {
      final target = _asMap(entry.value);
      final value = _numberOrNull(
        target?['resolved_value'] ??
            target?['value'] ??
            target?['range_low'] ??
            target?['baseline_value'],
      );
      if (value != null && value > 0) targets[entry.key] = value;
    }

    final scoreSource =
        _asMap(personalization?['personalized_domain_scores']) ??
            _asMap(meal['health_domain_scores']) ??
            _asMap(root['health_domain_scores']) ??
            _asMap(root['health_scores']) ??
            const <String, dynamic>{};
    final scores = <String, double>{};
    for (final entry in scoreSource.entries) {
      final map = _asMap(entry.value);
      final score = _numberOrNull(map?['score'] ?? entry.value);
      if (score != null) scores[entry.key] = score;
    }

    final micros = <String, double>{
      ..._extractNumericSection(nutrition, const ['vitamins']),
      ..._extractNumericSection(nutrition, const ['minerals']),
    };

    final foods = <String>[];
    for (final item in _asList(meal['foods'])) {
      final food = _asMap(item);
      final name = _firstText(food ?? const {}, const [
        'display_name',
        'name',
        'canonical_name',
      ]);
      if (name != null && !foods.contains(name)) foods.add(name);
    }

    final id = _firstText(json, const ['analysis_id']) ??
        _firstText(root, const ['analysis_id']) ??
        'local_${DateTime.now().microsecondsSinceEpoch}';

    return AnalysisHistoryRecord(
      analysisId: id,
      createdAt: createdAt ?? DateTime.now(),
      mealName: _firstText(
            meal,
            const ['meal_name', 'name', 'title', 'meal_type'],
          ) ??
          'Meal analysis',
      calories: _firstNumber(
        macros,
        const ['energy_kcal', 'calories', 'calories_kcal'],
      ),
      macronutrients: Map.unmodifiable(macros),
      micronutrients: Map.unmodifiable(micros),
      healthScores: Map.unmodifiable(scores),
      nutrientTargets: Map.unmodifiable(targets),
      detectedFoods: List.unmodifiable(foods),
      rawResult: Map<String, dynamic>.from(json),
    );
  }

  Map<String, dynamic> toJson() => {
        'analysis_id': analysisId,
        'created_at': createdAt.toIso8601String(),
        'meal_name': mealName,
        'calories': calories,
        'macronutrients': macronutrients,
        'micronutrients': micronutrients,
        'health_scores': healthScores,
        'nutrient_targets': nutrientTargets,
        'detected_foods': detectedFoods,
        'raw_result_json': jsonEncode(rawResult),
      };

  factory AnalysisHistoryRecord.fromJson(Map<String, dynamic> json) {
    Map<String, dynamic> raw = const {};
    final encoded = json['raw_result_json'];
    if (encoded is String && encoded.isNotEmpty) {
      final decoded = jsonDecode(encoded);
      if (decoded is Map) raw = Map<String, dynamic>.from(decoded);
    }
    return AnalysisHistoryRecord(
      analysisId: json['analysis_id']?.toString() ?? '',
      createdAt: DateTime.tryParse(json['created_at']?.toString() ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
      mealName: json['meal_name']?.toString() ?? 'Meal analysis',
      calories: _numberOrNull(json['calories']) ?? 0,
      macronutrients: _doubleMap(_asMap(json['macronutrients'])),
      micronutrients: _doubleMap(_asMap(json['micronutrients'])),
      healthScores: _doubleMap(_asMap(json['health_scores'])),
      nutrientTargets: _doubleMap(_asMap(json['nutrient_targets'])),
      detectedFoods: _asList(json['detected_foods'])
          .map((e) => e.toString())
          .toList(growable: false),
      rawResult: raw,
    );
  }
}

Map<String, dynamic> _unwrap(Map<String, dynamic> json) {
  for (final key in const ['final_result', 'meal_analysis', 'data']) {
    final nested = _asMap(json[key]);
    if (nested != null && nested.isNotEmpty) return nested;
  }
  return json;
}

Map<String, dynamic> _findNutrition(
  Map<String, dynamic> root,
  Map<String, dynamic> meal,
) {
  for (final value in [
    meal['nutrition'],
    meal['nutrition_totals'],
    meal['total_nutrition'],
    meal['nutrition_summary'],
    root['nutrition'],
    root['nutrition_totals'],
    root['total_nutrition'],
    root['nutrition_summary'],
  ]) {
    final map = _asMap(value);
    if (map != null && map.isNotEmpty) return map;
  }
  return const {};
}

Map<String, double> _extractNumericSection(
  Map<String, dynamic> source,
  List<String> sectionKeys,
) {
  final result = <String, double>{};
  void merge(Map<String, dynamic>? map) {
    for (final entry in (map ?? const <String, dynamic>{}).entries) {
      final value = _numberOrNull(entry.value);
      if (value != null) result[entry.key] = value;
    }
  }

  merge(source);
  // for (final key in sectionKeys) merge(_asMap(source[key]));
  for (final key in sectionKeys) {
    merge(_asMap(source[key]));
  }
  return result;
}

Map<String, double> _doubleMap(Map<String, dynamic>? source) {
  final result = <String, double>{};
  for (final entry in (source ?? const <String, dynamic>{}).entries) {
    final value = _numberOrNull(entry.value);
    if (value != null) result[entry.key] = value;
  }
  return result;
}

Map<String, dynamic>? _asMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return Map<String, dynamic>.from(value);
  return null;
}

List<dynamic> _asList(dynamic value) => value is List ? value : const [];

double? _numberOrNull(dynamic value) {
  if (value == null || value is bool) return null;
  final parsed = value is num ? value.toDouble() : double.tryParse(value.toString());
  return parsed?.isFinite == true ? parsed : null;
}

double _firstNumber(Map<String, double> source, List<String> keys) {
  for (final key in keys) {
    final value = source[key];
    if (value != null) return value;
  }
  return 0;
}

String? _firstText(Map<String, dynamic> source, List<String> keys) {
  for (final key in keys) {
    final value = source[key]?.toString().trim();
    if (value != null && value.isNotEmpty && value.toLowerCase() != 'null') {
      return value;
    }
  }
  return null;
}
