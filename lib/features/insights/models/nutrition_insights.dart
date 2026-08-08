import '../../history/models/analysis_history_record.dart';

class DailyNutritionInsight {
  const DailyNutritionInsight({
    required this.date,
    required this.mealCount,
    required this.calories,
    required this.macronutrients,
    required this.micronutrients,
    required this.healthScores,
    required this.overallHealthScore,
  });

  final DateTime date;
  final int mealCount;
  final double calories;
  final Map<String, double> macronutrients;
  final Map<String, double> micronutrients;
  final Map<String, double> healthScores;
  final double overallHealthScore;
}

class NutritionInsights {
  const NutritionInsights({
    required this.mealCount,
    required this.daysWithMeals,
    required this.totalCalories,
    required this.averageDailyMacros,
    required this.targetAchievement,
    required this.dailyInsights,
    required this.topFoodNames,
  });

  final int mealCount;
  final int daysWithMeals;
  final double totalCalories;
  final Map<String, double> averageDailyMacros;
  final Map<String, double> targetAchievement;
  final List<DailyNutritionInsight> dailyInsights;
  final List<MapEntry<String, int>> topFoodNames;

  bool get isEmpty => mealCount == 0;

  factory NutritionInsights.fromRecords(
    List<AnalysisHistoryRecord> records,
    Duration period,
  ) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final days = period.inDays <= 0 ? 1 : period.inDays;
    final cutoff = today.subtract(Duration(days: days - 1));

    final filtered = records.where((record) {
      final local = record.createdAt.toLocal();
      final day = DateTime(local.year, local.month, local.day);
      return !day.isBefore(cutoff) && !day.isAfter(today);
    }).toList();

    if (filtered.isEmpty) {
      return const NutritionInsights(
        mealCount: 0,
        daysWithMeals: 0,
        totalCalories: 0,
        averageDailyMacros: {},
        targetAchievement: {},
        dailyInsights: [],
        topFoodNames: [],
      );
    }

    final recordsByDay = <DateTime, List<AnalysisHistoryRecord>>{};
    final foodCounts = <String, int>{};
    var totalCalories = 0.0;

    for (final record in filtered) {
      final local = record.createdAt.toLocal();
      final day = DateTime(local.year, local.month, local.day);
      recordsByDay.putIfAbsent(day, () => []).add(record);
      totalCalories += record.calories;

      for (final food in record.detectedFoods.toSet()) {
        final key = food.trim();
        if (key.isNotEmpty) {
          foodCounts.update(key, (value) => value + 1, ifAbsent: () => 1);
        }
      }
    }

    final dailyInsights = <DailyNutritionInsight>[];
    final targetTotals = <String, double>{};
    final targetDays = <String, int>{};
    final macroTotalsAcrossDays = <String, double>{};

    final sortedDays = recordsByDay.keys.toList()..sort();
    for (final day in sortedDays) {
      final dayRecords = recordsByDay[day]!;
      final dayMacros = <String, double>{};
      final dayMicros = <String, double>{};
      final scoreTotals = <String, double>{};
      final scoreCounts = <String, int>{};
      final dayTargets = <String, double>{};
      var dayCalories = 0.0;

      for (final record in dayRecords) {
        dayCalories += record.calories;

        for (final entry in record.macronutrients.entries) {
          dayMacros.update(
            entry.key,
            (value) => value + entry.value,
            ifAbsent: () => entry.value,
          );
        }
        for (final entry in record.micronutrients.entries) {
          dayMicros.update(
            entry.key,
            (value) => value + entry.value,
            ifAbsent: () => entry.value,
          );
        }
        for (final entry in record.healthScores.entries) {
          scoreTotals.update(
            entry.key,
            (value) => value + entry.value,
            ifAbsent: () => entry.value,
          );
          scoreCounts.update(
            entry.key,
            (value) => value + 1,
            ifAbsent: () => 1,
          );
        }
        // Last saved snapshot for a target on that day wins. Since the target
        // is profile-derived, this also handles a profile edit between meals.
        dayTargets.addAll(record.nutrientTargets);
      }

      final dayScores = <String, double>{
        for (final entry in scoreTotals.entries)
          entry.key: entry.value / (scoreCounts[entry.key] ?? 1),
      };
      final overall = dayScores.isEmpty
          ? 0.0
          : dayScores.values.reduce((a, b) => a + b) / dayScores.length;

      dailyInsights.add(
        DailyNutritionInsight(
          date: day,
          mealCount: dayRecords.length,
          calories: dayCalories,
          macronutrients: Map.unmodifiable(dayMacros),
          micronutrients: Map.unmodifiable(dayMicros),
          healthScores: Map.unmodifiable(dayScores),
          overallHealthScore: overall,
        ),
      );

      for (final entry in dayMacros.entries) {
        macroTotalsAcrossDays.update(
          entry.key,
          (value) => value + entry.value,
          ifAbsent: () => entry.value,
        );
      }

      for (final entry in dayTargets.entries) {
        if (entry.value <= 0) continue;
        final amount = _amountForTarget(dayMacros, entry.key) ??
            dayMicros[entry.key];
        if (amount == null) continue;
        final achievement = amount / entry.value * 100;
        targetTotals.update(
          entry.key,
          (value) => value + achievement,
          ifAbsent: () => achievement,
        );
        targetDays.update(
          entry.key,
          (value) => value + 1,
          ifAbsent: () => 1,
        );
      }
    }

    final dayCount = dailyInsights.length;
    final averages = <String, double>{
      for (final entry in macroTotalsAcrossDays.entries)
        entry.key: entry.value / dayCount,
    };
    final achievement = <String, double>{
      for (final entry in targetTotals.entries)
        entry.key: entry.value / (targetDays[entry.key] ?? 1),
    };
    final topFoods = foodCounts.entries.toList()
      ..sort((a, b) {
        final count = b.value.compareTo(a.value);
        return count != 0 ? count : a.key.compareTo(b.key);
      });

    return NutritionInsights(
      mealCount: filtered.length,
      daysWithMeals: dayCount,
      totalCalories: totalCalories,
      averageDailyMacros: Map.unmodifiable(averages),
      targetAchievement: Map.unmodifiable(achievement),
      dailyInsights: List.unmodifiable(dailyInsights),
      topFoodNames: topFoods.take(5).toList(growable: false),
    );
  }
}

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
