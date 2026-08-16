import '../../history/models/analysis_history_record.dart';
import '../../result/models/analysis_result.dart';

enum InsightCategory {
  health,
  macros,
  micronutrients,
}

enum BalanceState {
  low,
  balanced,
  high,
  unknown,
}

class NutrientTargetBand {
  const NutrientTargetBand({
    required this.low,
    required this.high,
    required this.reference,
    required this.unit,
    required this.isUpperLimit,
    required this.personalized,
  });

  final double? low;
  final double? high;
  final double? reference;
  final String unit;
  final bool isUpperLimit;
  final bool personalized;

  BalanceState classify(double value) {
    if (isUpperLimit) {
      final ceiling = high ?? reference;
      if (ceiling == null || ceiling <= 0) {
        return BalanceState.unknown;
      }
      return value <= ceiling ? BalanceState.balanced : BalanceState.high;
    }

    final lower = low;
    final upper = high;
    if (lower == null || upper == null || lower <= 0 || upper <= 0) {
      return BalanceState.unknown;
    }
    if (value < lower) return BalanceState.low;
    if (value > upper) return BalanceState.high;
    return BalanceState.balanced;
  }
}

class MealHealthImpact {
  const MealHealthImpact({
    required this.analysisId,
    required this.mealName,
    required this.calories,
    required this.overallScore,
    required this.healthScores,
  });

  final String analysisId;
  final String mealName;
  final double calories;
  final double overallScore;
  final Map<String, double> healthScores;
}

class DailyNutritionInsight {
  const DailyNutritionInsight({
    required this.date,
    required this.mealCount,
    required this.calories,
    required this.macronutrients,
    required this.micronutrients,
    required this.healthScores,
    required this.overallHealthScore,
    required this.targets,
    required this.mealImpacts,
  });

  final DateTime date;
  final int mealCount;
  final double calories;
  final Map<String, double> macronutrients;
  final Map<String, double> micronutrients;
  final Map<String, double> healthScores;
  final double overallHealthScore;
  final Map<String, NutrientTargetBand> targets;
  final List<MealHealthImpact> mealImpacts;

  double? metricValue(InsightCategory category, String key) {
    switch (category) {
      case InsightCategory.health:
        if (key == 'overall') return overallHealthScore;
        return healthScores[key];
      case InsightCategory.macros:
        return _amountForTarget(macronutrients, key);
      case InsightCategory.micronutrients:
        return micronutrients[key];
    }
  }

  NutrientTargetBand? targetFor(String key) => targets[key];
}

class NutrientBalanceSummary {
  const NutrientBalanceSummary({
    required this.key,
    required this.label,
    required this.unit,
    required this.lowDays,
    required this.balancedDays,
    required this.highDays,
    required this.trackedDays,
    required this.averageValue,
    required this.averagePercent,
  });

  final String key;
  final String label;
  final String unit;
  final int lowDays;
  final int balancedDays;
  final int highDays;
  final int trackedDays;
  final double averageValue;
  final double? averagePercent;

  BalanceState get dominantState {
    if (trackedDays == 0) return BalanceState.unknown;
    final counts = <BalanceState, int>{
      BalanceState.low: lowDays,
      BalanceState.balanced: balancedDays,
      BalanceState.high: highDays,
    };
    return counts.entries.reduce((a, b) => a.value >= b.value ? a : b).key;
  }
}

class HealthDomainTrend {
  const HealthDomainTrend({
    required this.key,
    required this.label,
    required this.averageScore,
    required this.latestScore,
    required this.previousAverageScore,
  });

  final String key;
  final String label;
  final double averageScore;
  final double latestScore;
  final double? previousAverageScore;

  double? get delta =>
      previousAverageScore == null ? null : averageScore - previousAverageScore!;
}

class MetricChange {
  const MetricChange({
    required this.key,
    required this.label,
    required this.currentAverage,
    required this.previousAverage,
    required this.unit,
  });

  final String key;
  final String label;
  final double currentAverage;
  final double previousAverage;
  final String unit;

  double get percentChange {
    if (previousAverage.abs() < 0.000001) return 0;
    return (currentAverage - previousAverage) / previousAverage * 100;
  }
}

class NutritionInsights {
  const NutritionInsights({
    required this.mealCount,
    required this.daysWithMeals,
    required this.totalCalories,
    required this.averageDailyMacros,
    required this.averageDailyMicros,
    required this.targetAchievement,
    required this.dailyInsights,
    required this.previousDailyInsights,
    required this.topFoodNames,
  });

  final int mealCount;
  final int daysWithMeals;
  final double totalCalories;
  final Map<String, double> averageDailyMacros;
  final Map<String, double> averageDailyMicros;
  final Map<String, double> targetAchievement;
  final List<DailyNutritionInsight> dailyInsights;
  final List<DailyNutritionInsight> previousDailyInsights;
  final List<MapEntry<String, int>> topFoodNames;

  bool get isEmpty => mealCount == 0;

  NutrientTargetBand? targetForDay(
    DailyNutritionInsight day,
    String nutrientKey,
  ) =>
      day.targetFor(nutrientKey) ?? _genericTargetFor(nutrientKey);

  List<String> get healthDomainKeys {
    final keys = <String>{};
    for (final day in dailyInsights) {
      keys.addAll(day.healthScores.keys);
    }
    final result = keys.toList()
      ..sort((a, b) => friendlyMetricName(a).compareTo(friendlyMetricName(b)));
    return result;
  }

  List<String> get macroKeys {
    final keys = <String>{};
    for (final day in dailyInsights) {
      keys.addAll(day.macronutrients.keys);
    }
    const priority = [
      'protein_g',
      'carbohydrate_g',
      'fat_g',
      'fiber_g',
      'saturated_fat_g',
      'monounsaturated_fat_g',
      'polyunsaturated_fat_g',
      'trans_fat_g',
      'omega_3_g',
      'omega_6_g',
      'cholesterol_mg',
      'sugars_g',
      'added_sugars_g',
    ];
    final ordered = <String>[];
    for (final key in priority) {
      if (keys.remove(key)) ordered.add(key);
    }
    ordered.addAll(keys.toList()..sort());
    return ordered;
  }

  List<String> get micronutrientKeys {
    final keys = <String>{};
    for (final day in dailyInsights) {
      keys.addAll(day.micronutrients.keys);
    }
    return keys.toList()
      ..sort((a, b) => friendlyMetricName(a).compareTo(friendlyMetricName(b)));
  }

  factory NutritionInsights.fromRecords(
    List<AnalysisHistoryRecord> records,
    Duration period, {
    DateTime? referenceDate,
  }) {
    final now = referenceDate ?? DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final days = period.inDays <= 0 ? 1 : period.inDays;
    final currentStart = today.subtract(Duration(days: days - 1));
    final previousEnd = currentStart.subtract(const Duration(days: 1));
    final previousStart = previousEnd.subtract(Duration(days: days - 1));

    final currentRecords = _recordsWithin(records, currentStart, today);
    final previousRecords = _recordsWithin(records, previousStart, previousEnd);

    if (currentRecords.isEmpty) {
      return const NutritionInsights(
        mealCount: 0,
        daysWithMeals: 0,
        totalCalories: 0,
        averageDailyMacros: {},
        averageDailyMicros: {},
        targetAchievement: {},
        dailyInsights: [],
        previousDailyInsights: [],
        topFoodNames: [],
      );
    }

    final currentDays = _buildDays(currentRecords);
    final previousDays = _buildDays(previousRecords);

    final foodCounts = <String, int>{};
    var totalCalories = 0.0;
    for (final record in currentRecords) {
      totalCalories += record.calories;
      for (final food in record.detectedFoods.toSet()) {
        final key = food.trim();
        if (key.isEmpty) {
          continue;
        }
        foodCounts.update(key, (value) => value + 1, ifAbsent: () => 1);
      }
    }

    final averageMacros = _averageMaps(
      currentDays.map((day) => day.macronutrients),
    );
    final averageMicros = _averageMaps(
      currentDays.map((day) => day.micronutrients),
    );

    final achievementTotals = <String, double>{};
    final achievementCounts = <String, int>{};
    for (final day in currentDays) {
      for (final entry in day.targets.entries) {
        final amount = day.metricValue(
          _isMacroKey(entry.key)
              ? InsightCategory.macros
              : InsightCategory.micronutrients,
          entry.key,
        );
        final target = entry.value.reference ??
            entry.value.high ??
            entry.value.low;
        if (amount == null || target == null || target <= 0) continue;
        achievementTotals.update(
          entry.key,
          (value) => value + (amount / target * 100),
          ifAbsent: () => amount / target * 100,
        );
        achievementCounts.update(
          entry.key,
          (value) => value + 1,
          ifAbsent: () => 1,
        );
      }
    }

    final achievement = <String, double>{
      for (final entry in achievementTotals.entries)
        entry.key: entry.value / (achievementCounts[entry.key] ?? 1),
    };

    final topFoods = foodCounts.entries.toList()
      ..sort((a, b) {
        final count = b.value.compareTo(a.value);
        return count != 0 ? count : a.key.compareTo(b.key);
      });

    return NutritionInsights(
      mealCount: currentRecords.length,
      daysWithMeals: currentDays.length,
      totalCalories: totalCalories,
      averageDailyMacros: Map.unmodifiable(averageMacros),
      averageDailyMicros: Map.unmodifiable(averageMicros),
      targetAchievement: Map.unmodifiable(achievement),
      dailyInsights: List.unmodifiable(currentDays),
      previousDailyInsights: List.unmodifiable(previousDays),
      topFoodNames: topFoods.take(6).toList(growable: false),
    );
  }

  List<NutrientBalanceSummary> balanceSummaries(
    InsightCategory category,
  ) {
    if (category == InsightCategory.health) return const [];

    final keys =
        category == InsightCategory.macros ? macroKeys : micronutrientKeys;
    final summaries = <NutrientBalanceSummary>[];

    for (final key in keys) {
      var low = 0;
      var balanced = 0;
      var high = 0;
      var tracked = 0;
      var amountSum = 0.0;
      var percentSum = 0.0;
      var percentCount = 0;
      String unit = unitForMetric(key);

      for (final day in dailyInsights) {
        final amount = day.metricValue(category, key);
        if (amount == null) continue;
        final target = day.targetFor(key) ?? _genericTargetFor(key);
        if (target == null) continue;

        final state = target.classify(amount);
        if (state == BalanceState.unknown) continue;

        tracked += 1;
        amountSum += amount;
        unit = target.unit.isNotEmpty ? target.unit : unit;

        final reference = target.reference ?? target.high ?? target.low;
        if (reference != null && reference > 0) {
          percentSum += amount / reference * 100;
          percentCount += 1;
        }

        switch (state) {
          case BalanceState.low:
            low += 1;
            break;
          case BalanceState.balanced:
            balanced += 1;
            break;
          case BalanceState.high:
            high += 1;
            break;
          case BalanceState.unknown:
            break;
        }
      }

      if (tracked == 0) {
        continue;
      }
      summaries.add(
        NutrientBalanceSummary(
          key: key,
          label: friendlyMetricName(key),
          unit: unit,
          lowDays: low,
          balancedDays: balanced,
          highDays: high,
          trackedDays: tracked,
          averageValue: amountSum / tracked,
          averagePercent: percentCount == 0 ? null : percentSum / percentCount,
        ),
      );
    }

    summaries.sort((a, b) {
      final aConcern = a.lowDays + a.highDays;
      final bConcern = b.lowDays + b.highDays;
      final concern = bConcern.compareTo(aConcern);
      if (concern != 0) return concern;
      return a.label.compareTo(b.label);
    });
    return summaries;
  }

  List<HealthDomainTrend> healthDomainTrends() {
    final current = _averageHealthScores(dailyInsights);
    final previous = _averageHealthScores(previousDailyInsights);
    final latest = dailyInsights.isEmpty
        ? const <String, double>{}
        : dailyInsights.last.healthScores;

    final result = <HealthDomainTrend>[
      for (final entry in current.entries)
        HealthDomainTrend(
          key: entry.key,
          label: friendlyMetricName(entry.key),
          averageScore: entry.value,
          latestScore: latest[entry.key] ?? entry.value,
          previousAverageScore: previous[entry.key],
        ),
    ];

    result.sort((a, b) => a.averageScore.compareTo(b.averageScore));
    return result;
  }

  List<MetricChange> metricChanges(InsightCategory category) {
    if (category == InsightCategory.health) return const [];

    final current = category == InsightCategory.macros
        ? averageDailyMacros
        : averageDailyMicros;
    final previous = _averageMaps(
      previousDailyInsights.map(
        (day) => category == InsightCategory.macros
            ? day.macronutrients
            : day.micronutrients,
      ),
    );

    final changes = <MetricChange>[];
    for (final entry in current.entries) {
      final previousValue = previous[entry.key];
      if (previousValue == null || previousValue <= 0) continue;
      changes.add(
        MetricChange(
          key: entry.key,
          label: friendlyMetricName(entry.key),
          currentAverage: entry.value,
          previousAverage: previousValue,
          unit: unitForMetric(entry.key),
        ),
      );
    }
    changes.sort(
      (a, b) => b.percentChange.abs().compareTo(a.percentChange.abs()),
    );
    return changes;
  }
}

List<AnalysisHistoryRecord> _recordsWithin(
  List<AnalysisHistoryRecord> records,
  DateTime start,
  DateTime end,
) {
  return records.where((record) {
    final local = record.createdAt.toLocal();
    final day = DateTime(local.year, local.month, local.day);
    return !day.isBefore(start) && !day.isAfter(end);
  }).toList(growable: false);
}

List<DailyNutritionInsight> _buildDays(
  List<AnalysisHistoryRecord> records,
) {
  final byDay = <DateTime, List<AnalysisHistoryRecord>>{};
  for (final record in records) {
    final local = record.createdAt.toLocal();
    final day = DateTime(local.year, local.month, local.day);
    byDay.putIfAbsent(day, () => []).add(record);
  }

  final days = byDay.keys.toList()..sort();
  return [
    for (final day in days)
      _buildDay(day, byDay[day]!..sort((a, b) => a.createdAt.compareTo(b.createdAt))),
  ];
}

DailyNutritionInsight _buildDay(
  DateTime day,
  List<AnalysisHistoryRecord> records,
) {
  final macros = <String, double>{};
  final micros = <String, double>{};
  final weightedDomainTotals = <String, double>{};
  final domainWeights = <String, double>{};
  final mealImpacts = <MealHealthImpact>[];
  final targets = <String, NutrientTargetBand>{};

  var calories = 0.0;
  var weightedOverall = 0.0;
  var overallWeight = 0.0;

  for (final record in records) {
    calories += record.calories;

    for (final entry in record.macronutrients.entries) {
      macros.update(
        entry.key,
        (value) => value + entry.value,
        ifAbsent: () => entry.value,
      );
    }
    for (final entry in record.micronutrients.entries) {
      micros.update(
        entry.key,
        (value) => value + entry.value,
        ifAbsent: () => entry.value,
      );
    }

    final weight = record.calories > 0 ? record.calories : 1.0;
    for (final entry in record.healthScores.entries) {
      weightedDomainTotals.update(
        entry.key,
        (value) => value + entry.value * weight,
        ifAbsent: () => entry.value * weight,
      );
      domainWeights.update(
        entry.key,
        (value) => value + weight,
        ifAbsent: () => weight,
      );
    }

    var mealOverall = 0.0;
    try {
      final parsed = AnalysisResult.fromJson(record.rawResult);
      mealOverall = parsed.overallScore;
      for (final targetEntry in parsed.nutrientTargets.entries) {
        final band = _bandFromPersonalizedTarget(targetEntry.value);
        if (band != null) {
          targets[targetEntry.key] = band;
        }
      }
    } catch (_) {
      if (record.healthScores.isNotEmpty) {
        mealOverall = record.healthScores.values.reduce((a, b) => a + b) /
            record.healthScores.length;
      }
    }

    if (mealOverall > 0) {
      weightedOverall += mealOverall * weight;
      overallWeight += weight;
    }

    mealImpacts.add(
      MealHealthImpact(
        analysisId: record.analysisId,
        mealName: record.mealName,
        calories: record.calories,
        overallScore: mealOverall,
        healthScores: Map.unmodifiable(record.healthScores),
      ),
    );

    // Older records may have only the simplified locally stored targets.
    for (final entry in record.nutrientTargets.entries) {
      targets.putIfAbsent(
        entry.key,
        () => _bandAroundReference(
          entry.value,
          unitForMetric(entry.key),
          personalized: true,
        ),
      );
    }
  }

  final healthScores = <String, double>{
    for (final entry in weightedDomainTotals.entries)
      entry.key: entry.value / (domainWeights[entry.key] ?? 1),
  };

  final overall = overallWeight > 0
      ? weightedOverall / overallWeight
      : healthScores.isEmpty
          ? 0.0
          : healthScores.values.reduce((a, b) => a + b) /
              healthScores.length;

  // Generic reference targets are only fallbacks for nutrients where the app
  // already has a standard daily reference. Personalized targets always win.
  for (final key in {...macros.keys, ...micros.keys}) {
    final generic = _genericTargetFor(key);
    if (generic != null) {
      targets.putIfAbsent(key, () => generic);
    }
  }

  return DailyNutritionInsight(
    date: day,
    mealCount: records.length,
    calories: calories,
    macronutrients: Map.unmodifiable(macros),
    micronutrients: Map.unmodifiable(micros),
    healthScores: Map.unmodifiable(healthScores),
    overallHealthScore: overall,
    targets: Map.unmodifiable(targets),
    mealImpacts: List.unmodifiable(mealImpacts),
  );
}

NutrientTargetBand? _bandFromPersonalizedTarget(
  PersonalizedNutrientTarget target,
) {
  final type = (target.targetType ?? '').toLowerCase();
  final unit = target.unit.isNotEmpty ? target.unit : unitForMetric(target.key);

  if (target.rangeLow != null &&
      target.rangeHigh != null &&
      target.rangeLow! > 0 &&
      target.rangeHigh! > 0) {
    return NutrientTargetBand(
      low: target.rangeLow,
      high: target.rangeHigh,
      reference: target.resolvedValue ??
          ((target.rangeLow! + target.rangeHigh!) / 2),
      unit: unit,
      isUpperLimit: false,
      personalized: true,
    );
  }

  final upper = target.upperLimit;
  if ((type.contains('upper') || type.contains('limit')) &&
      upper != null &&
      upper > 0) {
    return NutrientTargetBand(
      low: null,
      high: upper,
      reference: upper,
      unit: unit,
      isUpperLimit: true,
      personalized: true,
    );
  }

  final resolved = target.resolvedValue ?? target.baselineValue;
  if (resolved != null && resolved > 0) {
    if (type.contains('upper') || type.contains('limit')) {
      return NutrientTargetBand(
        low: null,
        high: resolved,
        reference: resolved,
        unit: unit,
        isUpperLimit: true,
        personalized: true,
      );
    }
    return _bandAroundReference(
      resolved,
      unit,
      personalized: true,
    );
  }
  return null;
}

NutrientTargetBand _bandAroundReference(
  double reference,
  String unit, {
  required bool personalized,
}) {
  return NutrientTargetBand(
    low: reference * 0.8,
    high: reference * 1.2,
    reference: reference,
    unit: unit,
    isUpperLimit: false,
    personalized: personalized,
  );
}

NutrientTargetBand? _genericTargetFor(String key) {
  const references = <String, double>{
    'fiber_g': 28,
    'saturated_fat_g': 20,
    'added_sugars_g': 50,
    'vitamin_a_ug': 900,
    'vitamin_c_mg': 90,
    'vitamin_d_ug': 20,
    'vitamin_e_mg': 15,
    'vitamin_k_ug': 120,
    'thiamin_mg': 1.2,
    'riboflavin_mg': 1.3,
    'niacin_mg': 16,
    'pantothenic_acid_mg': 5,
    'vitamin_b6_mg': 1.7,
    'folate_ug': 400,
    'vitamin_b12_ug': 2.4,
    'choline_mg': 550,
    'calcium_mg': 1300,
    'iron_mg': 18,
    'magnesium_mg': 420,
    'phosphorus_mg': 1250,
    'potassium_mg': 4700,
    'zinc_mg': 11,
    'copper_mg': 0.9,
    'manganese_mg': 2.3,
    'selenium_ug': 55,
  };
  const upperLimits = <String, double>{
    'sodium_mg': 2300,
    'saturated_fat_g': 20,
    'added_sugars_g': 50,
  };

  final upper = upperLimits[key];
  if (upper != null) {
    return NutrientTargetBand(
      low: null,
      high: upper,
      reference: upper,
      unit: unitForMetric(key),
      isUpperLimit: true,
      personalized: false,
    );
  }

  final reference = references[key];
  if (reference == null) return null;
  return _bandAroundReference(
    reference,
    unitForMetric(key),
    personalized: false,
  );
}

Map<String, double> _averageMaps(
  Iterable<Map<String, double>> maps,
) {
  final totals = <String, double>{};
  final counts = <String, int>{};
  for (final map in maps) {
    for (final entry in map.entries) {
      totals.update(
        entry.key,
        (value) => value + entry.value,
        ifAbsent: () => entry.value,
      );
      counts.update(
        entry.key,
        (value) => value + 1,
        ifAbsent: () => 1,
      );
    }
  }
  return {
    for (final entry in totals.entries)
      entry.key: entry.value / (counts[entry.key] ?? 1),
  };
}

Map<String, double> _averageHealthScores(
  List<DailyNutritionInsight> days,
) {
  final totals = <String, double>{};
  final counts = <String, int>{};
  for (final day in days) {
    for (final entry in day.healthScores.entries) {
      totals.update(
        entry.key,
        (value) => value + entry.value,
        ifAbsent: () => entry.value,
      );
      counts.update(
        entry.key,
        (value) => value + 1,
        ifAbsent: () => 1,
      );
    }
  }
  return {
    for (final entry in totals.entries)
      entry.key: entry.value / (counts[entry.key] ?? 1),
  };
}

bool _isMacroKey(String key) {
  return key.endsWith('_g') ||
      key == 'protein' ||
      key == 'carbs' ||
      key == 'fat';
}

double? amountForMetric(
  DailyNutritionInsight day,
  InsightCategory category,
  String key,
) =>
    day.metricValue(category, key);

double? _amountForTarget(Map<String, double> macros, String key) {
  const aliases = <String, List<String>>{
    'protein_g': ['protein_g', 'protein'],
    'carbohydrate_g': [
      'carbohydrate_g',
      'carbohydrates_g',
      'carbs_g',
      'carbs',
    ],
    'fat_g': ['fat_g', 'total_fat_g', 'fat'],
    'fiber_g': ['fiber_g', 'fibre_g', 'dietary_fiber_g'],
  };
  for (final candidate in aliases[key] ?? [key]) {
    final value = macros[candidate];
    if (value != null) return value;
  }
  return null;
}

String friendlyMetricName(String value) {
  const aliases = <String, String>{
    'overall': 'Overall health score',
    'protein_g': 'Protein',
    'carbohydrate_g': 'Carbohydrates',
    'carbohydrates_g': 'Carbohydrates',
    'fat_g': 'Fat',
    'fiber_g': 'Fiber',
    'saturated_fat_g': 'Saturated fat',
    'monounsaturated_fat_g': 'Monounsaturated fat',
    'polyunsaturated_fat_g': 'Polyunsaturated fat',
    'trans_fat_g': 'Trans fat',
    'omega_3_g': 'Omega-3',
    'omega_6_g': 'Omega-6',
    'cholesterol_mg': 'Cholesterol',
    'sugars_g': 'Total sugars',
    'added_sugars_g': 'Added sugars',
    'renal_health': 'Renal health',
    'kidney_health': 'Renal health',
    'cardiovascular_health': 'Cardiovascular health',
    'metabolic_health': 'Metabolic health',
    'digestive_health': 'Digestive health',
    'bone_health': 'Bone health',
  };
  final direct = aliases[value];
  if (direct != null) return direct;
  return value
      .replaceAll(RegExp(r'_(mg|ug|mcg|g)$'), '')
      .replaceAll('_', ' ')
      .split(RegExp(r'\s+'))
      .where((word) => word.isNotEmpty)
      .map(
        (word) =>
            '${word[0].toUpperCase()}${word.substring(1).toLowerCase()}',
      )
      .join(' ');
}

String unitForMetric(String key) {
  if (key.endsWith('_ug') || key.endsWith('_mcg')) return 'µg';
  if (key.endsWith('_mg')) return 'mg';
  if (key.endsWith('_g')) return 'g';
  return '';
}

String healthStatusLabel(double score) {
  if (score >= 85) return 'Excellent';
  if (score >= 70) return 'Good';
  if (score >= 55) return 'Monitor';
  if (score >= 40) return 'Needs attention';
  return 'Significant dietary concern';
}
