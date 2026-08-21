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
    required this.minimumStyle,
    required this.personalized,
  });

  final double? low;
  final double? high;
  final double? reference;
  final String unit;
  final bool isUpperLimit;
  final bool minimumStyle;
  final bool personalized;

  bool isAboveReference(double value) {
    final ref = reference;
    return ref != null && ref > 0 && value > ref;
  }

  bool isSafetyExcess(double value) {
    if (isUpperLimit) {
      final ceiling = high ?? reference;
      return ceiling != null && ceiling >= 0 && value > ceiling;
    }
    final ceiling = high;
    return ceiling != null && ceiling >= 0 && value > ceiling;
  }

  BalanceState classify(double value) {
    if (isUpperLimit) {
      final ceiling = high ?? reference;
      if (ceiling == null || ceiling < 0) {
        return BalanceState.unknown;
      }
      return value <= ceiling ? BalanceState.balanced : BalanceState.high;
    }

    final lower = low;
    final upper = high;

    // Minimum/RDA/AI targets remain adequate once the lower threshold is
    // reached. Above-100% reference intake is surfaced separately by the UI
    // and is not automatically treated as a harmful/high balance state.
    if (minimumStyle) {
      if (lower == null || lower <= 0) return BalanceState.unknown;
      if (value < lower) return BalanceState.low;
      if (isSafetyExcess(value)) return BalanceState.high;
      return BalanceState.balanced;
    }

    if (lower == null || upper == null || lower <= 0 || upper <= 0) {
      return BalanceState.unknown;
    }
    if (value < lower) return BalanceState.low;
    if (value > upper) return BalanceState.high;
    return BalanceState.balanced;
  }
}

class FoodMetricContribution {
  const FoodMetricContribution({
    required this.foodName,
    required this.percentage,
    this.amount,
  });

  final String foodName;
  final double percentage;
  final double? amount;
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
    required this.nutrientContributions,
    required this.healthContributions,
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
  final Map<String, List<FoodMetricContribution>> nutrientContributions;
  final Map<String, List<FoodMetricContribution>> healthContributions;

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

  NutrientTargetBand? targetFor(String key) =>
      targets[_canonicalMetricKey(key)];

  List<FoodMetricContribution> contributorsFor(
    InsightCategory category,
    String key,
  ) {
    if (category == InsightCategory.health) {
      return healthContributions[key] ?? const [];
    }
    return nutrientContributions[_canonicalMetricKey(key)] ?? const [];
  }
}

class NutrientBalanceSummary {
  const NutrientBalanceSummary({
    required this.key,
    required this.label,
    required this.unit,
    required this.lowDays,
    required this.balancedDays,
    required this.highDays,
    required this.unknownDays,
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
  final int unknownDays;
  final int trackedDays;
  final double averageValue;
  final double? averagePercent;

  int get classifiedDays => lowDays + balancedDays + highDays;

  BalanceState get dominantState {
    if (classifiedDays == 0) return BalanceState.unknown;
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
      day.targetFor(_canonicalMetricKey(nutrientKey)) ??
      _genericTargetFor(_canonicalMetricKey(nutrientKey));

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
    // Calories are shown separately and are not a macronutrient balance row.
    keys.remove('energy_kcal');
    keys.remove('calories');
    keys.remove('calories_kcal');
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

    for (final rawKey in keys) {
      final key = _canonicalMetricKey(rawKey);
      var low = 0;
      var balanced = 0;
      var high = 0;
      var unknown = 0;
      var observed = 0;
      var amountSum = 0.0;
      var percentSum = 0.0;
      var percentCount = 0;
      String unit = unitForMetric(key);

      for (final day in dailyInsights) {
        final amount = day.metricValue(category, key);
        if (amount == null) continue;

        observed += 1;
        amountSum += amount;

        final target = targetForDay(day, key);
        if (target == null) {
          unknown += 1;
          continue;
        }

        unit = target.unit.isNotEmpty ? target.unit : unit;
        final state = target.classify(amount);
        if (state == BalanceState.unknown) {
          unknown += 1;
          continue;
        }

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
            unknown += 1;
            break;
        }
      }

      // User-facing balance lists contain only nutrients that can actually be
      // classified. A measured nutrient with no defensible numeric reference
      // remains available in the detailed meal breakdown, but is not shown as
      // a misleading "Reference unavailable" balance row.
      if (observed == 0 || low + balanced + high == 0) continue;

      summaries.add(
        NutrientBalanceSummary(
          key: key,
          label: friendlyMetricName(key),
          unit: unit,
          lowDays: low,
          balancedDays: balanced,
          highDays: high,
          unknownDays: unknown,
          trackedDays: observed,
          averageValue: amountSum / observed,
          averagePercent: percentCount == 0 ? null : percentSum / percentCount,
        ),
      );
    }

    summaries.sort((a, b) {
      // Actionable classified nutrients first, then unclassified rows. Within
      // each group, surface the nutrients most often outside their range.
      final aUnknown = a.dominantState == BalanceState.unknown ? 1 : 0;
      final bUnknown = b.dominantState == BalanceState.unknown ? 1 : 0;
      final unknownOrder = aUnknown.compareTo(bUnknown);
      if (unknownOrder != 0) return unknownOrder;

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
  final nutrientContributionAmounts =
      <String, Map<String, _NamedAmount>>{};
  final healthContributionWeights =
      <String, Map<String, _NamedAmount>>{};

  var calories = 0.0;
  var weightedOverall = 0.0;
  var overallWeight = 0.0;

  for (final record in records) {
    calories += record.calories;

    final canonicalMacros = _canonicalMetricEntries(record.macronutrients);
    final canonicalMicros = _canonicalMetricEntries(record.micronutrients);

    for (final entry in canonicalMacros) {
      macros.update(
        entry.canonicalKey,
        (value) => value + entry.value,
        ifAbsent: () => entry.value,
      );
    }
    for (final entry in canonicalMicros) {
      micros.update(
        entry.canonicalKey,
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
          targets[_canonicalMetricKey(targetEntry.key)] = band;
        }
      }

      final canonicalNutrients = <_CanonicalMetricEntry>[
        ...canonicalMacros,
        ...canonicalMicros,
      ];
      for (final nutrient in canonicalNutrients) {
        for (final contribution in parsed.contributionsFor(nutrient.sourceKey)) {
          _addNamedAmount(
            nutrientContributionAmounts,
            nutrient.canonicalKey,
            contribution.foodName,
            contribution.amount * nutrient.conversionFactor,
          );
        }
      }

      final healthWeights = _healthEvidenceWeightsByFood(record.rawResult);
      for (final domainEntry in healthWeights.entries) {
        for (final foodEntry in domainEntry.value.entries) {
          // Daily health scores are meal-energy weighted, so food influence
          // uses the same meal weight before percentages are calculated.
          _addNamedAmount(
            healthContributionWeights,
            domainEntry.key,
            foodEntry.value.name,
            foodEntry.value.amount * weight,
          );
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
      final canonicalKey = _canonicalMetricKey(entry.key);
      final convertedValue =
          entry.value * _metricConversionFactor(entry.key, canonicalKey);
      targets.putIfAbsent(
        canonicalKey,
        () => _bandAroundReference(
          convertedValue,
          unitForMetric(canonicalKey),
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

  final nutrientContributions = <String, List<FoodMetricContribution>>{};
  for (final entry in nutrientContributionAmounts.entries) {
    final total = macros[entry.key] ?? micros[entry.key] ?? 0.0;
    if (total <= 0) continue;
    final items = entry.value.values
        .where((item) => item.amount > 0)
        .map(
          (item) => FoodMetricContribution(
            foodName: item.name,
            amount: item.amount,
            percentage: (item.amount / total * 100).clamp(0.0, 100.0).toDouble(),
          ),
        )
        .toList(growable: false)
      ..sort((a, b) => b.percentage.compareTo(a.percentage));
    if (items.isNotEmpty) {
      nutrientContributions[entry.key] = List.unmodifiable(items);
    }
  }

  final healthContributions = <String, List<FoodMetricContribution>>{};
  for (final entry in healthContributionWeights.entries) {
    final totalWeight = entry.value.values.fold<double>(
      0,
      (sum, item) => sum + item.amount,
    );
    if (totalWeight <= 0) continue;
    final items = entry.value.values
        .where((item) => item.amount > 0)
        .map(
          (item) => FoodMetricContribution(
            foodName: item.name,
            percentage: item.amount / totalWeight * 100,
          ),
        )
        .toList(growable: false)
      ..sort((a, b) => b.percentage.compareTo(a.percentage));
    if (items.isNotEmpty) {
      healthContributions[entry.key] = List.unmodifiable(items);
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
    nutrientContributions: Map.unmodifiable(nutrientContributions),
    healthContributions: Map.unmodifiable(healthContributions),
  );
}

class _NamedAmount {
  _NamedAmount(this.name, this.amount);

  final String name;
  double amount;
}

void _addNamedAmount(
  Map<String, Map<String, _NamedAmount>> destination,
  String metricKey,
  String foodName,
  double amount,
) {
  if (!amount.isFinite || amount <= 0) return;
  final cleanName = foodName.trim();
  if (cleanName.isEmpty) return;
  final normalized = cleanName.toLowerCase().replaceAll(RegExp(r'\s+'), ' ');
  final byFood = destination.putIfAbsent(metricKey, () => {});
  final existing = byFood[normalized];
  if (existing == null) {
    byFood[normalized] = _NamedAmount(cleanName, amount);
  } else {
    existing.amount += amount;
  }
}

Map<String, Map<String, _NamedAmount>> _healthEvidenceWeightsByFood(
  Map<String, dynamic> rawResult,
) {
  final root = _unwrapInsightResult(rawResult);
  final meal = _asMapLocal(root['meal']) ?? root;
  final result = <String, Map<String, _NamedAmount>>{};

  for (final rawFood in _asListLocal(meal['foods'])) {
    final food = _asMapLocal(rawFood);
    if (food == null) continue;
    final foodName = _foodDisplayName(food);
    if (foodName == null) continue;
    _collectFoodHealthEvidence(food, foodName, result);
  }
  return result;
}

void _collectFoodHealthEvidence(
  Map<String, dynamic> food,
  String rootFoodName,
  Map<String, Map<String, _NamedAmount>> destination,
) {
  final evidence = _asMapLocal(food['evidence']);
  for (final rawItem in _asListLocal(evidence?['items'])) {
    final item = _asMapLocal(rawItem);
    if (item == null) continue;
    final domain = item['domain']?.toString().trim();
    if (domain == null || domain.isEmpty) continue;
    final weight = _finiteDouble(item['effective_weight']).abs();
    if (weight <= 0) continue;
    _addNamedAmount(destination, domain, rootFoodName, weight);
  }

  // Match the backend scoring traversal: an aggregated DECOMPOSE parent
  // already contains its components' evidence and must not be counted twice.
  final route = food['analysis_route']?.toString().toUpperCase();
  final nutrientStatus = food['nutrient_status']?.toString();
  if (route == 'DECOMPOSE' && nutrientStatus == 'aggregated_from_components') {
    return;
  }

  for (final childKey in const ['ingredients', 'spices']) {
    for (final rawChild in _asListLocal(food[childKey])) {
      final child = _asMapLocal(rawChild);
      if (child == null) continue;
      _collectFoodHealthEvidence(child, rootFoodName, destination);
    }
  }
}

Map<String, dynamic> _unwrapInsightResult(Map<String, dynamic> json) {
  for (final key in const ['final_result', 'meal_analysis', 'data']) {
    final nested = _asMapLocal(json[key]);
    if (nested != null && nested.isNotEmpty) return nested;
  }
  return json;
}

Map<String, dynamic>? _asMapLocal(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return Map<String, dynamic>.from(value);
  return null;
}

List<dynamic> _asListLocal(dynamic value) => value is List ? value : const [];

String? _foodDisplayName(Map<String, dynamic> food) {
  for (final key in const ['display_name', 'name', 'canonical_name']) {
    final value = food[key]?.toString().trim();
    if (value != null && value.isNotEmpty) return value;
  }
  return null;
}

double _finiteDouble(dynamic value) {
  if (value == null || value is bool) return 0;
  final parsed = value is num
      ? value.toDouble()
      : double.tryParse(value.toString());
  return parsed?.isFinite == true ? parsed! : 0;
}

NutrientTargetBand? _bandFromPersonalizedTarget(
  PersonalizedNutrientTarget target,
) {
  final type = (target.targetType ?? '').toLowerCase();
  final unit = target.unit.isNotEmpty ? target.unit : unitForMetric(target.key);

  // Explicit clinical/AMDR ranges are true two-sided ranges.
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
      minimumStyle: false,
      personalized: true,
    );
  }

  final upper = target.upperLimit;
  final resolved = target.resolvedValue ?? target.baselineValue;

  // Maximum-style nutrients such as sodium/saturated fat have no "too low"
  // state in this balance UI.
  if (type.contains('upper') ||
      type.contains('limit') ||
      type.contains('maximum')) {
    final ceiling = target.rangeHigh ?? upper ?? resolved;
    if (ceiling != null && ceiling >= 0) {
      return NutrientTargetBand(
        low: null,
        high: ceiling,
        reference: ceiling,
        unit: unit,
        isUpperLimit: true,
        minimumStyle: false,
        personalized: true,
      );
    }
  }

  if (resolved != null && resolved > 0) {
    // RDA/AI/reference targets are minimum-style for balance purposes. Keep a
    // small 20% tolerance below the reference. If the target engine supplied
    // a real tolerable upper limit, use that as the only "high" boundary.
    final high = upper != null && upper > resolved ? upper : null;
    return NutrientTargetBand(
      low: resolved * 0.8,
      high: high,
      reference: resolved,
      unit: unit,
      isUpperLimit: false,
      minimumStyle: true,
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
    minimumStyle: false,
    personalized: personalized,
  );
}

NutrientTargetBand _minimumAroundReference(
  double reference,
  String unit, {
  required bool personalized,
}) {
  return NutrientTargetBand(
    low: reference * 0.8,
    high: null,
    reference: reference,
    unit: unit,
    isUpperLimit: false,
    minimumStyle: true,
    personalized: personalized,
  );
}

NutrientTargetBand? _genericTargetFor(String rawKey) {
  final key = _canonicalMetricKey(rawKey);

  // General adult Nutrition Facts / daily-reference fallbacks. They are used
  // only when the backend did not provide a personalized target. Personalized
  // targets always win in _buildDay().
  const balancedReferences = <String, double>{
    'protein_g': 50,
    'carbohydrate_g': 275,
    'fat_g': 78,
  };

  const minimumReferences = <String, double>{
    'fiber_g': 28,
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
    'biotin_ug': 30,
    'calcium_mg': 1300,
    'iron_mg': 18,
    'magnesium_mg': 420,
    'phosphorus_mg': 1250,
    'potassium_mg': 4700,
    'zinc_mg': 11,
    'copper_mg': 0.9,
    'manganese_mg': 2.3,
    'selenium_ug': 55,
    'iodine_ug': 150,
    'chromium_ug': 35,
    'molybdenum_ug': 45,
    'chloride_mg': 2300,
  };

  // Upper-reference nutrients must not be treated like "needs more" targets.
  const upperLimits = <String, double>{
    'sodium_mg': 2300,
    'saturated_fat_g': 20,
    'added_sugars_g': 50,
    'cholesterol_mg': 300,
    // Public-health guidance treats trans fat as an as-low-as-possible target.
    // In the app this is represented as a zero maximum: 0 g is in range and
    // any reported positive amount is above target.
    'trans_fat_g': 0,
  };

  final upper = upperLimits[key];
  if (upper != null) {
    return NutrientTargetBand(
      low: null,
      high: upper,
      reference: upper,
      unit: unitForMetric(key),
      isUpperLimit: true,
      minimumStyle: false,
      personalized: false,
    );
  }

  final balancedReference = balancedReferences[key];
  if (balancedReference != null) {
    return _bandAroundReference(
      balancedReference,
      unitForMetric(key),
      personalized: false,
    );
  }

  final minimumReference = minimumReferences[key];
  if (minimumReference == null) return null;
  return _minimumAroundReference(
    minimumReference,
    unitForMetric(key),
    personalized: false,
  );
}

class _CanonicalMetricEntry {
  const _CanonicalMetricEntry({
    required this.canonicalKey,
    required this.sourceKey,
    required this.value,
    required this.conversionFactor,
  });

  final String canonicalKey;
  final String sourceKey;
  final double value;
  final double conversionFactor;
}

const _metricAliasGroups = <String, List<String>>{
  'energy_kcal': ['energy_kcal', 'calories_kcal', 'calories'],
  'protein_g': ['protein_g', 'protein'],
  'carbohydrate_g': [
    'carbohydrate_g',
    'carbohydrates_g',
    'carbs_g',
    'carbs',
  ],
  'fat_g': ['fat_g', 'total_fat_g', 'fat'],
  'fiber_g': ['fiber_g', 'fibre_g', 'dietary_fiber_g'],
  'saturated_fat_g': ['saturated_fat_g', 'total_saturated_fat_g'],
  'monounsaturated_fat_g': [
    'monounsaturated_fat_g',
    'total_monounsaturated_fat_g',
  ],
  'polyunsaturated_fat_g': [
    'polyunsaturated_fat_g',
    'total_polyunsaturated_fat_g',
  ],
  'trans_fat_g': ['trans_fat_g', 'total_trans_fat_g'],
  'omega_3_g': ['omega_3_g', 'omega3_g'],
  'omega_6_g': ['omega_6_g', 'omega6_g'],
  'alpha_linolenic_acid_g': [
    'alpha_linolenic_acid_g',
    'ala_g',
    '18_3_n_3_g',
  ],
  'linoleic_acid_g': ['linoleic_acid_g', '18_2_n_6_g'],
  'cholesterol_mg': ['cholesterol_mg', 'cholesterol'],
  'sugars_g': ['sugars_g', 'total_sugars_g', 'sugar_g', 'sugars'],
  'added_sugars_g': ['added_sugars_g', 'added_sugar_g', 'added_sugars'],
  'vitamin_a_ug': ['vitamin_a_ug_rae', 'vitamin_a_ug'],
  'vitamin_c_mg': ['vitamin_c_mg'],
  'vitamin_d_ug': ['vitamin_d_ug', 'vitamin_d_mcg', 'vitamin_d_iu'],
  'vitamin_e_mg': [
    'vitamin_e_mg_alpha_tocopherol',
    'alpha_tocopherol_mg',
    'vitamin_e_mg',
  ],
  'vitamin_k_ug': ['vitamin_k_ug', 'vitamin_k_mcg'],
  'thiamin_mg': ['thiamin_mg', 'vitamin_b1_mg'],
  'riboflavin_mg': ['riboflavin_mg', 'vitamin_b2_mg'],
  'niacin_mg': ['niacin_mg_ne', 'niacin_mg'],
  'pantothenic_acid_mg': ['pantothenic_acid_mg', 'vitamin_b5_mg'],
  'vitamin_b6_mg': ['vitamin_b6_mg'],
  'folate_ug': ['folate_ug_dfe', 'folate_ug'],
  'vitamin_b12_ug': ['vitamin_b12_ug', 'vitamin_b12_mcg'],
  'choline_mg': ['choline_mg'],
  'biotin_ug': ['biotin_ug', 'biotin_mcg', 'vitamin_b7_ug', 'vitamin_b7_mcg'],
  'calcium_mg': ['calcium_mg'],
  'iron_mg': ['iron_mg'],
  'magnesium_mg': ['magnesium_mg'],
  'phosphorus_mg': ['phosphorus_mg'],
  'potassium_mg': ['potassium_mg'],
  'sodium_mg': ['sodium_mg'],
  'zinc_mg': ['zinc_mg'],
  'copper_mg': ['copper_mg', 'copper_ug', 'copper_mcg'],
  'manganese_mg': ['manganese_mg'],
  'selenium_ug': ['selenium_ug', 'selenium_mcg'],
  'iodine_ug': ['iodine_ug', 'iodine_mcg'],
  'chromium_ug': ['chromium_ug', 'chromium_mcg'],
  'molybdenum_ug': ['molybdenum_ug', 'molybdenum_mcg'],
  'fluoride_mg': ['fluoride_mg'],
  'chloride_mg': ['chloride_mg'],
};

final Map<String, String> _canonicalMetricByAlias = {
  for (final group in _metricAliasGroups.entries)
    for (final alias in group.value) alias: group.key,
};

String _canonicalMetricKey(String rawKey) {
  final key = rawKey.trim().toLowerCase();
  return _canonicalMetricByAlias[key] ?? key;
}

double _metricConversionFactor(String sourceKey, String canonicalKey) {
  final source = sourceKey.trim().toLowerCase();
  if (canonicalKey == 'vitamin_d_ug' && source == 'vitamin_d_iu') {
    return 0.025;
  }
  if (canonicalKey == 'copper_mg' &&
      (source == 'copper_ug' || source == 'copper_mcg')) {
    return 0.001;
  }
  return 1.0;
}

List<_CanonicalMetricEntry> _canonicalMetricEntries(
  Map<String, double> source,
) {
  if (source.isEmpty) return const [];

  final normalizedSource = <String, MapEntry<String, double>>{};
  for (final entry in source.entries) {
    normalizedSource[entry.key.trim().toLowerCase()] = entry;
  }

  final result = <_CanonicalMetricEntry>[];
  final consumed = <String>{};

  // Pick one preferred representation for each nutrient so payloads carrying
  // both canonical and alias forms are not double-counted.
  for (final group in _metricAliasGroups.entries) {
    MapEntry<String, double>? selected;
    String? selectedAlias;
    for (final alias in group.value) {
      final candidate = normalizedSource[alias];
      if (candidate != null) {
        selected = candidate;
        selectedAlias = alias;
        break;
      }
    }
    if (selected == null || selectedAlias == null) continue;

    for (final alias in group.value) {
      if (normalizedSource.containsKey(alias)) consumed.add(alias);
    }

    final factor = _metricConversionFactor(selectedAlias, group.key);
    result.add(
      _CanonicalMetricEntry(
        canonicalKey: group.key,
        sourceKey: selected.key,
        value: selected.value * factor,
        conversionFactor: factor,
      ),
    );
  }

  // Preserve measured nutrients internally even when they are not yet in the
  // alias registry. User-facing balance lists omit them unless a defensible
  // numeric target/reference can classify them.
  for (final normalized in normalizedSource.entries) {
    if (consumed.contains(normalized.key)) continue;
    final original = normalized.value;
    result.add(
      _CanonicalMetricEntry(
        canonicalKey: normalized.key,
        sourceKey: original.key,
        value: original.value,
        conversionFactor: 1.0,
      ),
    );
  }

  return result;
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

bool _isMacroKey(String rawKey) {
  final key = _canonicalMetricKey(rawKey);
  return const <String>{
    'energy_kcal',
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
    'alpha_linolenic_acid_g',
    'linoleic_acid_g',
    'cholesterol_mg',
    'sugars_g',
    'added_sugars_g',
  }.contains(key);
}

double? amountForMetric(
  DailyNutritionInsight day,
  InsightCategory category,
  String key,
) =>
    day.metricValue(category, key);

double? _amountForTarget(Map<String, double> macros, String rawKey) {
  final key = _canonicalMetricKey(rawKey);
  final direct = macros[key];
  if (direct != null) return direct;

  for (final alias in _metricAliasGroups[key] ?? [key]) {
    final value = macros[alias];
    if (value != null) {
      return value * _metricConversionFactor(alias, key);
    }
  }
  return null;
}

String friendlyMetricName(String value) {
  final canonical = _canonicalMetricKey(value);
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
    'alpha_linolenic_acid_g': 'Alpha-linolenic acid (ALA)',
    'linoleic_acid_g': 'Linoleic acid (LA)',
    'cholesterol_mg': 'Cholesterol',
    'sugars_g': 'Total sugars',
    'added_sugars_g': 'Added sugars',
    'vitamin_a_ug': 'Vitamin A',
    'vitamin_c_mg': 'Vitamin C',
    'vitamin_d_ug': 'Vitamin D',
    'vitamin_e_mg': 'Vitamin E',
    'vitamin_k_ug': 'Vitamin K',
    'thiamin_mg': 'Thiamin (B1)',
    'riboflavin_mg': 'Riboflavin (B2)',
    'niacin_mg': 'Niacin (B3)',
    'pantothenic_acid_mg': 'Pantothenic acid (B5)',
    'vitamin_b6_mg': 'Vitamin B6',
    'folate_ug': 'Folate',
    'vitamin_b12_ug': 'Vitamin B12',
    'biotin_ug': 'Biotin (B7)',
    'iodine_ug': 'Iodine',
    'chromium_ug': 'Chromium',
    'molybdenum_ug': 'Molybdenum',
    'chloride_mg': 'Chloride',
    'renal_health': 'Renal health',
    'kidney_health': 'Renal health',
    'cardiovascular_health': 'Cardiovascular health',
    'metabolic_health': 'Metabolic health',
    'digestive_health': 'Digestive health',
    'bone_health': 'Bone health',
  };
  final direct = aliases[canonical];
  if (direct != null) return direct;
  return canonical
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

String unitForMetric(String rawKey) {
  final key = _canonicalMetricKey(rawKey);
  if (key.endsWith('_ug') || key.endsWith('_mcg')) return 'µg';
  if (key.endsWith('_mg')) return 'mg';
  if (key.endsWith('_g')) return 'g';
  if (key.endsWith('_kcal')) return 'kcal';
  return '';
}

String healthStatusLabel(double score) {
  if (score >= 85) return 'Excellent';
  if (score >= 70) return 'Good';
  if (score >= 55) return 'Monitor';
  if (score >= 40) return 'Needs attention';
  return 'Significant dietary concern';
}
