class DraftMealGuidance {
  const DraftMealGuidance({
    required this.alerts,
    required this.message,
    required this.disclaimer,
    required this.canContinue,
    required this.suggestionsPending,
  });

  final List<DraftNutrientAlert> alerts;
  final String message;
  final String disclaimer;
  final bool canContinue;
  final bool suggestionsPending;

  bool get hasAlerts => alerts.isNotEmpty;

  factory DraftMealGuidance.fromJson(Map<String, dynamic> json) {
    final rawAlerts = json['alerts'];
    return DraftMealGuidance(
      alerts: rawAlerts is List
          ? rawAlerts
              .whereType<Map>()
              .map((item) => DraftNutrientAlert.fromJson(
                    Map<String, dynamic>.from(item),
                  ))
              .toList(growable: false)
          : const [],
      message: json['message']?.toString() ?? '',
      disclaimer: json['disclaimer']?.toString() ?? '',
      canContinue: json['can_continue'] != false,
      suggestionsPending: json['suggestions_pending'] == true,
    );
  }
}

class DraftNutrientAlert {
  const DraftNutrientAlert({
    required this.direction,
    required this.severity,
    required this.nutrient,
    required this.label,
    required this.amount,
    required this.unit,
    required this.reference,
    required this.percentage,
    required this.message,
    required this.contributors,
    required this.suggestions,
  });

  final String direction;
  final String severity;
  final String nutrient;
  final String label;
  final double amount;
  final String unit;
  final double reference;
  final double percentage;
  final String message;
  final List<DraftNutrientContributor> contributors;
  final List<DraftFoodSuggestion> suggestions;

  bool get isExcess => direction == 'excess';
  bool get isLow => direction == 'low';
  bool get isAboveReference => direction == 'above_reference';
  bool get requiresClinicalInput => direction == 'clinical';

  factory DraftNutrientAlert.fromJson(Map<String, dynamic> json) {
    final rawContributors = json['contributors'];
    final rawSuggestions = json['suggestions'];
    return DraftNutrientAlert(
      direction: json['direction']?.toString() ?? 'low',
      severity: json['severity']?.toString() ?? 'notice',
      nutrient: json['nutrient']?.toString() ?? '',
      label: json['label']?.toString() ?? 'Nutrient',
      amount: _number(json['amount']),
      unit: json['unit']?.toString() ?? '',
      reference: _number(json['reference']),
      percentage: _number(json['percentage']),
      message: json['message']?.toString() ?? '',
      contributors: rawContributors is List
          ? rawContributors
              .whereType<Map>()
              .map((item) => DraftNutrientContributor.fromJson(
                    Map<String, dynamic>.from(item),
                  ))
              .where((item) => item.name.isNotEmpty)
              .toList(growable: false)
          : const [],
      suggestions: rawSuggestions is List
          ? rawSuggestions
              .whereType<Map>()
              .map((item) => DraftFoodSuggestion.fromJson(
                    Map<String, dynamic>.from(item),
                  ))
              .toList(growable: false)
          : const [],
    );
  }
}

class DraftNutrientContributor {
  const DraftNutrientContributor({
    required this.foodId,
    required this.name,
    required this.amount,
    required this.quantity,
    required this.quantityUnit,
  });

  final String foodId;
  final String name;
  final double amount;
  final double quantity;
  final String quantityUnit;

  factory DraftNutrientContributor.fromJson(Map<String, dynamic> json) {
    return DraftNutrientContributor(
      foodId: json['food_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      amount: _number(json['amount']),
      quantity: _number(json['quantity']),
      quantityUnit: json['quantity_unit']?.toString() ?? 'g',
    );
  }
}

class DraftFoodSuggestion {
  const DraftFoodSuggestion({
    required this.type,
    required this.name,
    required this.searchQuery,
    required this.quantity,
    required this.unit,
    required this.reason,
    this.fdcId,
    this.description,
    this.dataType,
    this.foodCategory,
    this.targetNutrient,
    this.targetNutrientPer100g,
  });

  final String type;
  final String name;
  final String searchQuery;
  final double quantity;
  final String unit;
  final String reason;
  final int? fdcId;
  final String? description;
  final String? dataType;
  final String? foodCategory;
  final String? targetNutrient;
  final double? targetNutrientPer100g;

  factory DraftFoodSuggestion.fromJson(Map<String, dynamic> json) {
    return DraftFoodSuggestion(
      type: json['type']?.toString() ?? 'add',
      name: json['name']?.toString() ?? 'Food',
      searchQuery: json['search_query']?.toString() ?? '',
      quantity: _number(json['quantity']),
      unit: json['unit']?.toString() ?? 'g',
      reason: json['reason']?.toString() ?? '',
      fdcId: _nullableInt(json['fdc_id']),
      description: json['description']?.toString(),
      dataType: json['data_type']?.toString(),
      foodCategory: json['food_category']?.toString(),
      targetNutrient: json['target_nutrient']?.toString(),
      targetNutrientPer100g: _nullableNumber(json['target_nutrient_per_100g']),
    );
  }
}

int? _nullableInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '');
}

double? _nullableNumber(dynamic value) {
  if (value == null) return null;
  if (value is num) return value.toDouble();
  return double.tryParse(value.toString());
}

double _number(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? 0;
}
