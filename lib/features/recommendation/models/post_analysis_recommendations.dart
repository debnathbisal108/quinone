class PostAnalysisRecommendations {
  const PostAnalysisRecommendations({
    required this.currentDayScore,
    required this.nutritionBalanceScore,
    required this.mealsIncluded,
    required this.context,
    required this.items,
    required this.message,
    required this.disclaimer,
  });

  final double currentDayScore;
  final double nutritionBalanceScore;
  final int mealsIncluded;
  final String context;
  final List<FoodRecommendation> items;
  final String message;
  final String disclaimer;

  factory PostAnalysisRecommendations.fromJson(Map<String, dynamic> json) {
    final baseline = _asMap(json['baseline']);
    final timing = _asMap(json['timing']);
    final rawItems = json['recommendations'];
    return PostAnalysisRecommendations(
      currentDayScore: _number(baseline['current_day_score']),
      nutritionBalanceScore: _number(baseline['nutrition_balance_score']),
      mealsIncluded: _integer(baseline['meals_included']),
      context: timing['context']?.toString() ?? 'the rest of today',
      items: rawItems is List
          ? rawItems
              .whereType<Map>()
              .map((item) => FoodRecommendation.fromJson(
                    Map<String, dynamic>.from(item),
                  ))
              .toList(growable: false)
          : const [],
      message: json['message']?.toString() ?? '',
      disclaimer: json['disclaimer']?.toString() ?? '',
    );
  }
}

class FoodRecommendation {
  const FoodRecommendation({
    required this.id,
    required this.action,
    required this.scope,
    required this.foodName,
    required this.searchQuery,
    required this.quantity,
    required this.unit,
    required this.originalFoodName,
    required this.originalQuantity,
    required this.baselineScore,
    required this.predictedScore,
    required this.predictedScoreLow,
    required this.predictedScoreHigh,
    required this.scoreDelta,
    required this.reason,
    required this.confidence,
    required this.nutrientEffects,
    required this.warnings,
  });

  final String id;
  final String action;
  final String scope;
  final String foodName;
  final String searchQuery;
  final double quantity;
  final String unit;
  final String? originalFoodName;
  final double? originalQuantity;
  final double baselineScore;
  final double predictedScore;
  final double predictedScoreLow;
  final double predictedScoreHigh;
  final double scoreDelta;
  final String reason;
  final double confidence;
  final List<RecommendationNutrientEffect> nutrientEffects;
  final List<String> warnings;

  String get actionLabel {
    switch (action) {
      case 'replace':
        return 'Replace';
      case 'adjust_portion':
        return 'Adjust portion';
      default:
        return scope == 'next_meal' ? 'For next meal' : 'Add';
    }
  }

  String get title {
    if (action == 'replace' && originalFoodName != null) {
      return 'Replace $originalFoodName with $foodName';
    }
    if (action == 'adjust_portion') {
      return 'Reduce $foodName to ${_format(quantity)} $unit';
    }
    return 'Add ${_format(quantity)} $unit $foodName';
  }

  factory FoodRecommendation.fromJson(Map<String, dynamic> json) {
    final food = _asMap(json['food']);
    final replaces = _asMap(json['replaces']);
    final effects = json['nutrient_effects'];
    final warnings = json['warnings'];
    return FoodRecommendation(
      id: json['id']?.toString() ?? '',
      action: json['action']?.toString() ?? 'add',
      scope: json['scope']?.toString() ?? 'current_meal',
      foodName: food['name']?.toString() ?? 'Food',
      searchQuery: food['search_query']?.toString() ?? food['name']?.toString() ?? '',
      quantity: _number(food['quantity']),
      unit: food['unit']?.toString() ?? 'g',
      originalFoodName: replaces['name']?.toString(),
      originalQuantity: _nullableNumber(
        replaces['quantity'] ?? food['original_quantity'],
      ),
      baselineScore: _number(json['baseline_score']),
      predictedScore: _number(json['predicted_score']),
      predictedScoreLow: _number(json['predicted_score_low']),
      predictedScoreHigh: _number(json['predicted_score_high']),
      scoreDelta: _number(json['score_delta']),
      reason: json['reason']?.toString() ?? '',
      confidence: _number(json['confidence']),
      nutrientEffects: effects is List
          ? effects
              .whereType<Map>()
              .map((item) => RecommendationNutrientEffect.fromJson(
                    Map<String, dynamic>.from(item),
                  ))
              .toList(growable: false)
          : const [],
      warnings: warnings is List
          ? warnings.map((item) => item.toString()).toList(growable: false)
          : const [],
    );
  }
}

class RecommendationNutrientEffect {
  const RecommendationNutrientEffect({
    required this.nutrient,
    required this.label,
    required this.before,
    required this.after,
    required this.target,
  });

  final String nutrient;
  final String label;
  final double before;
  final double after;
  final double target;

  factory RecommendationNutrientEffect.fromJson(Map<String, dynamic> json) {
    return RecommendationNutrientEffect(
      nutrient: json['nutrient']?.toString() ?? '',
      label: json['label']?.toString() ?? '',
      before: _number(json['before']),
      after: _number(json['after']),
      target: _number(json['target']),
    );
  }
}

Map<String, dynamic> _asMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return Map<String, dynamic>.from(value);
  return const {};
}

double _number(dynamic value) => _nullableNumber(value) ?? 0;

double? _nullableNumber(dynamic value) {
  if (value == null || value is bool) return null;
  final parsed = value is num ? value.toDouble() : double.tryParse(value.toString());
  return parsed?.isFinite == true ? parsed : null;
}

int _integer(dynamic value) {
  if (value is int) return value;
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

String _format(double value) => value == value.roundToDouble()
    ? value.toStringAsFixed(0)
    : value.toStringAsFixed(1);

