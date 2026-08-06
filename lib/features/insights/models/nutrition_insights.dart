import '../../history/models/analysis_history_record.dart';

class NutritionInsights {
  const NutritionInsights({
    required this.mealCount,
    required this.daysWithMeals,
    required this.totalCalories,
    required this.averageDailyMacros,
    required this.targetAchievement,
    required this.averageHealthScores,
    required this.topFoodNames,
  });

  final int mealCount;
  final int daysWithMeals;
  final double totalCalories;
  final Map<String, double> averageDailyMacros;
  final Map<String, double> targetAchievement;
  final Map<String, double> averageHealthScores;
  final List<MapEntry<String, int>> topFoodNames;

  bool get isEmpty => mealCount == 0;

  factory NutritionInsights.fromRecords(
    List<AnalysisHistoryRecord> records,
    Duration period,
  ) {
    final cutoff = DateTime.now().subtract(period);
    final filtered = records.where((r) => !r.createdAt.isBefore(cutoff)).toList();
    if (filtered.isEmpty) {
      return const NutritionInsights(
        mealCount: 0,
        daysWithMeals: 0,
        totalCalories: 0,
        averageDailyMacros: {},
        targetAchievement: {},
        averageHealthScores: {},
        topFoodNames: [],
      );
    }

    final dates = <String>{};
    final dailyMacros = <String, Map<String, double>>{};
    final targetTotals = <String, double>{};
    final targetDays = <String, int>{};
    final scoreTotals = <String, double>{};
    final scoreCounts = <String, int>{};
    final foodCounts = <String, int>{};
    var totalCalories = 0.0;

    for (final record in filtered) {
      final day = '${record.createdAt.year.toString().padLeft(4, '0')}-'
          '${record.createdAt.month.toString().padLeft(2, '0')}-'
          '${record.createdAt.day.toString().padLeft(2, '0')}';
      dates.add(day);
      totalCalories += record.calories;
      final dayMacros = dailyMacros.putIfAbsent(day, () => <String, double>{});
      for (final entry in record.macronutrients.entries) {
        dayMacros.update(entry.key, (v) => v + entry.value,
            ifAbsent: () => entry.value);
      }
      for (final entry in record.healthScores.entries) {
        scoreTotals.update(entry.key, (v) => v + entry.value,
            ifAbsent: () => entry.value);
        scoreCounts.update(entry.key, (v) => v + 1, ifAbsent: () => 1);
      }
      for (final food in record.detectedFoods) {
        final key = food.trim();
        if (key.isNotEmpty) {
          foodCounts.update(key, (v) => v + 1, ifAbsent: () => 1);
        }
      }
    }

    final macroTotals = <String, double>{};
    for (final macros in dailyMacros.values) {
      for (final entry in macros.entries) {
        macroTotals.update(entry.key, (v) => v + entry.value,
            ifAbsent: () => entry.value);
      }
    }
    final dayCount = dates.length.clamp(1, 999999);
    final averages = <String, double>{
      for (final e in macroTotals.entries) e.key: e.value / dayCount,
    };

    // Use each day's saved target snapshot. This avoids rewriting old history
    // when the user later changes their profile.
    for (final day in dates) {
      final dayRecords = filtered.where((r) {
        final d = '${r.createdAt.year.toString().padLeft(4, '0')}-'
            '${r.createdAt.month.toString().padLeft(2, '0')}-'
            '${r.createdAt.day.toString().padLeft(2, '0')}';
        return d == day;
      });
      final dayNutrients = dailyMacros[day] ?? const <String, double>{};
      final dayTargets = <String, double>{};
      for (final record in dayRecords) {
        for (final entry in record.nutrientTargets.entries) {
          dayTargets[entry.key] = entry.value;
        }
      }
      for (final entry in dayTargets.entries) {
        final amount = _amountForTarget(dayNutrients, entry.key);
        if (amount == null || entry.value <= 0) continue;
        targetTotals.update(entry.key, (v) => v + amount / entry.value * 100,
            ifAbsent: () => amount / entry.value * 100);
        targetDays.update(entry.key, (v) => v + 1, ifAbsent: () => 1);
      }
    }

    final achievement = <String, double>{
      for (final e in targetTotals.entries)
        e.key: e.value / (targetDays[e.key] ?? 1),
    };
    final scoreAverages = <String, double>{
      for (final e in scoreTotals.entries)
        e.key: e.value / (scoreCounts[e.key] ?? 1),
    };
    final topFoods = foodCounts.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));

    return NutritionInsights(
      mealCount: filtered.length,
      daysWithMeals: dates.length,
      totalCalories: totalCalories,
      averageDailyMacros: averages,
      targetAchievement: achievement,
      averageHealthScores: scoreAverages,
      topFoodNames: topFoods.take(5).toList(growable: false),
    );
  }
}

double? _amountForTarget(Map<String, double> macros, String key) {
  const aliases = {
    'protein_g': ['protein_g', 'protein'],
    'carbohydrate_g': ['carbohydrate_g', 'carbohydrates_g', 'carbs_g', 'carbs'],
    'fat_g': ['fat_g', 'total_fat_g', 'fat'],
    'fiber_g': ['fiber_g', 'fibre_g', 'dietary_fiber_g'],
  };
  for (final candidate in aliases[key] ?? [key]) {
    final value = macros[candidate];
    if (value != null) return value;
  }
  return null;
}
