class DraftMealGuidance {
  const DraftMealGuidance({
    required this.alerts,
    required this.message,
    required this.disclaimer,
    required this.canContinue,
  });

  final List<DraftNutrientAlert> alerts;
  final String message;
  final String disclaimer;
  final bool canContinue;

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
  });

  final String type;
  final String name;
  final String searchQuery;
  final double quantity;
  final String unit;
  final String reason;

  factory DraftFoodSuggestion.fromJson(Map<String, dynamic> json) {
    return DraftFoodSuggestion(
      type: json['type']?.toString() ?? 'add',
      name: json['name']?.toString() ?? 'Food',
      searchQuery: json['search_query']?.toString() ?? '',
      quantity: _number(json['quantity']),
      unit: json['unit']?.toString() ?? 'g',
      reason: json['reason']?.toString() ?? '',
    );
  }
}

double _number(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? 0;
}
