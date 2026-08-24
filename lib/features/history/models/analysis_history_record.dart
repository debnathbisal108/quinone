import 'dart:convert';

import '../../result/models/analysis_result.dart';

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
    this.mealImagePaths = const [],
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
  final List<String> mealImagePaths;

  double get protein => _firstNumber(
        macronutrients,
        const ['protein_g', 'protein'],
      );

  double get carbohydrates => _firstNumber(
        macronutrients,
        const [
          'carbohydrate_g',
          'carbohydrates_g',
          'carbs_g',
          'carbs',
        ],
      );

  double get fat => _firstNumber(
        macronutrients,
        const ['fat_g', 'total_fat_g', 'fat'],
      );

  double get fiber => _firstNumber(
        macronutrients,
        const ['fiber_g', 'fibre_g', 'dietary_fiber_g'],
      );

  factory AnalysisHistoryRecord.fromAnalysisJson(
    Map<String, dynamic> json, {
    DateTime? createdAt,
    String? analysisId,
  }) {
    // IMPORTANT: use the exact same parser as ResultScreen. This prevents
    // History/Insights from showing zero while the opened report is correct.
    final parsed = AnalysisResult.fromJson(json);

    final macros = <String, double>{
      'energy_kcal': parsed.calories,
      'protein_g': parsed.protein,
      'carbohydrate_g': parsed.carbohydrates,
      'fat_g': parsed.fat,
      'fiber_g': parsed.fiber,
      if (parsed.saturatedFat != null)
        'saturated_fat_g': parsed.saturatedFat!,
      if (parsed.monounsaturatedFat != null)
        'monounsaturated_fat_g': parsed.monounsaturatedFat!,
      if (parsed.polyunsaturatedFat != null)
        'polyunsaturated_fat_g': parsed.polyunsaturatedFat!,
      if (parsed.transFat != null) 'trans_fat_g': parsed.transFat!,
      if (parsed.omega3 != null) 'omega_3_g': parsed.omega3!,
      if (parsed.omega6 != null) 'omega_6_g': parsed.omega6!,
      if (parsed.cholesterol != null)
        'cholesterol_mg': parsed.cholesterol!,
      if (parsed.sugars != null) 'sugars_g': parsed.sugars!,
      if (parsed.addedSugars != null)
        'added_sugars_g': parsed.addedSugars!,
    };

    final micros = <String, double>{
      for (final nutrient in parsed.micronutrients)
        nutrient.key: nutrient.amount,
    };

    final scores = <String, double>{
      for (final score in parsed.healthScores) score.key: score.score,
    };

    final targets = <String, double>{};
    if (parsed.personalizationApplied) {
      for (final entry in parsed.nutrientTargets.entries) {
        final target = entry.value;
        final value = target.resolvedValue ??
            target.baselineValue ??
            target.rangeLow;
        if (value != null && value > 0) {
          targets[entry.key] = value;
        }
      }
    }

    final foods = <String>[];
    final seen = <String>{};
    for (final food in parsed.displayFoods) {
      final key = food.name.trim().toLowerCase();
      if (key.isEmpty || !seen.add(key)) continue;
      foods.add(food.name);
    }

    final id = analysisId ??
        _firstText(json, const ['analysis_id']) ??
        _firstText(_unwrap(json), const ['analysis_id']) ??
        'local_${DateTime.now().microsecondsSinceEpoch}';

    return AnalysisHistoryRecord(
      analysisId: id,
      createdAt: createdAt ?? DateTime.now(),
      mealName: parsed.mealName,
      calories: parsed.calories,
      macronutrients: Map.unmodifiable(macros),
      micronutrients: Map.unmodifiable(micros),
      healthScores: Map.unmodifiable(scores),
      nutrientTargets: Map.unmodifiable(targets),
      detectedFoods: List.unmodifiable(foods),
      rawResult: Map<String, dynamic>.from(json),
      mealImagePaths: List.unmodifiable(parsed.mealImagePaths),
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
        'meal_image_paths': mealImagePaths,
      };

  factory AnalysisHistoryRecord.fromJson(Map<String, dynamic> json) {
    Map<String, dynamic> raw = const {};
    final encoded = json['raw_result_json'];
    if (encoded is String && encoded.isNotEmpty) {
      try {
        final decoded = jsonDecode(encoded);
        if (decoded is Map) {
          raw = Map<String, dynamic>.from(decoded);
        }
      } catch (_) {
        raw = const {};
      }
    }

    // Migrate old locally saved records that were written with the broken
    // History parser. The complete raw response was preserved, so we can
    // reconstruct the correct calories/macros without deleting history.
    if (raw.isNotEmpty) {
      try {
        return AnalysisHistoryRecord.fromAnalysisJson(
          raw,
          createdAt: DateTime.tryParse(
            json['created_at']?.toString() ?? '',
          ),
          analysisId: json['analysis_id']?.toString(),
        );
      } catch (_) {
        // Fall through to the stored fields if one legacy raw row is damaged.
      }
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
      mealImagePaths: _asList(json['meal_image_paths']).map((e) => e.toString().trim()).where((e) => e.isNotEmpty).toList(growable: false),
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
  final parsed = value is num
      ? value.toDouble()
      : double.tryParse(value.toString());
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
