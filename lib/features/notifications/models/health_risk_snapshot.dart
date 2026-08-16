import '../../history/models/analysis_history_record.dart';
import '../../insights/models/nutrition_insights.dart';

enum RiskLevel { monitor, atRisk }

enum NutrientDirection { low, high }

class HealthScoreRisk {
  const HealthScoreRisk({
    required this.key,
    required this.label,
    required this.score,
    required this.level,
    this.change,
  });

  final String key;
  final String label;
  final double score;
  final RiskLevel level;
  final double? change;
}

class NutrientRisk {
  const NutrientRisk({
    required this.key,
    required this.label,
    required this.direction,
    required this.level,
    required this.averagePercent,
    required this.concernDays,
    required this.trackedDays,
  });

  final String key;
  final String label;
  final NutrientDirection direction;
  final RiskLevel level;
  final double averagePercent;
  final int concernDays;
  final int trackedDays;
}

class HealthRiskSnapshot {
  const HealthRiskSnapshot({
    required this.periodDays,
    required this.observedDays,
    required this.asOf,
    required this.healthScores,
    required this.nutrients,
  });

  final int periodDays;
  final int observedDays;
  final DateTime asOf;
  final List<HealthScoreRisk> healthScores;
  final List<NutrientRisk> nutrients;

  bool get hasConcerns => healthScores.isNotEmpty || nutrients.isNotEmpty;

  String get periodLabel {
    switch (periodDays) {
      case 1:
        return 'Today';
      case 7:
        return '7-day pattern';
      case 30:
        return '30-day pattern';
      default:
        return '$periodDays-day pattern';
    }
  }

  String get signature {
    final scorePart = healthScores
        .map((item) =>
            '${item.key}:${item.level.name}:${item.score.round()}')
        .join(',');
    final nutrientPart = nutrients
        .map((item) =>
            '${item.key}:${item.direction.name}:${item.level.name}:${(item.averagePercent / 5).round() * 5}')
        .join(',');
    return '$periodDays|$scorePart|$nutrientPart';
  }

  String get notificationTitle {
    if (periodDays == 1) return 'Today’s nutrition needs attention';
    return 'Your $periodDays-day nutrition pattern needs attention';
  }

  String get notificationBody {
    final parts = <String>[];
    if (healthScores.isNotEmpty) {
      final atRisk = healthScores
          .where((item) => item.level == RiskLevel.atRisk)
          .take(4)
          .map((item) => _shortHealthLabel(item.label))
          .toList(growable: false);
      final monitor = healthScores
          .where((item) => item.level == RiskLevel.monitor)
          .take(4 - atRisk.length)
          .map((item) => _shortHealthLabel(item.label))
          .toList(growable: false);
      if (atRisk.isNotEmpty) {
        parts.add(
          '${_joined(atRisk)} dietary-support ${atRisk.length == 1 ? 'score is' : 'scores are'} at risk',
        );
      }
      if (monitor.isNotEmpty) {
        parts.add(
          '${_joined(monitor)} dietary-support ${monitor.length == 1 ? 'score needs' : 'scores need'} monitoring',
        );
      }
    }
    if (nutrients.isNotEmpty) {
      final low = nutrients
          .where((item) => item.direction == NutrientDirection.low)
          .take(4)
          .map((item) => item.label)
          .toList(growable: false);
      final high = nutrients
          .where((item) => item.direction == NutrientDirection.high)
          .take(3)
          .map((item) => item.label)
          .toList(growable: false);
      if (low.isNotEmpty) parts.add('${_joined(low)} are below target');
      if (high.isNotEmpty) parts.add('${_joined(high)} are above target');
    }
    return '${parts.join('. ')}. Tap for personalized food options.';
  }

  static String _joined(List<String> values) {
    if (values.isEmpty) return '';
    if (values.length == 1) return values.first;
    return '${values.take(values.length - 1).join(', ')} and ${values.last}';
  }

  static String _shortHealthLabel(String label) => label
      .replaceAll(RegExp(r'\s+health$', caseSensitive: false), '')
      .trim();
}

class HealthRiskMonitor {
  const HealthRiskMonitor._();

  static const List<int> supportedPeriods = [1, 7, 30];
  static const Set<String> _upperOnlyNutrients = {
    'sodium_mg',
    'added_sugars_g',
    'saturated_fat_g',
    'trans_fat_g',
    'cholesterol_mg',
  };

  static HealthRiskSnapshot evaluate(
    List<AnalysisHistoryRecord> records, {
    required int periodDays,
    DateTime? asOf,
  }) {
    final normalizedDays = supportedPeriods.contains(periodDays)
        ? periodDays
        : 1;
    final referenceDate = asOf ?? DateTime.now();
    final insights = NutritionInsights.fromRecords(
      records,
      Duration(days: normalizedDays),
      referenceDate: referenceDate,
    );
    final minimumObservedDays = switch (normalizedDays) {
      7 => 4,
      30 => 10,
      _ => 1,
    };
    if (insights.daysWithMeals < minimumObservedDays) {
      return HealthRiskSnapshot(
        periodDays: normalizedDays,
        observedDays: insights.daysWithMeals,
        asOf: referenceDate,
        healthScores: const [],
        nutrients: const [],
      );
    }

    final scores = <HealthScoreRisk>[];
    for (final trend in insights.healthDomainTrends()) {
      final declined = (trend.delta ?? 0) <= -8 && trend.averageScore < 75;
      if (trend.averageScore >= 60 && !declined) continue;
      scores.add(
        HealthScoreRisk(
          key: trend.key,
          label: friendlyMetricName(trend.key),
          score: trend.averageScore,
          level: trend.averageScore < 45 ? RiskLevel.atRisk : RiskLevel.monitor,
          change: trend.delta,
        ),
      );
    }
    scores.sort((a, b) => a.score.compareTo(b.score));

    final accumulators = <String, _NutrientAccumulator>{};
    for (final day in insights.dailyInsights) {
      for (final entry in day.targets.entries) {
        final target = entry.value;
        // Generic fallback references are useful in Insights, but are not
        // strong enough evidence to trigger a personalized notification.
        if (!target.personalized) continue;
        final amount = day.metricValue(InsightCategory.macros, entry.key) ??
            day.metricValue(InsightCategory.micronutrients, entry.key);
        final reference = target.reference ?? target.high ?? target.low;
        if (amount == null || reference == null || reference <= 0) continue;
        final state = _upperOnlyNutrients.contains(entry.key)
            ? (amount > reference
                ? BalanceState.high
                : BalanceState.balanced)
            : target.classify(amount);
        if (state == BalanceState.unknown) continue;
        final accumulator = accumulators.putIfAbsent(
          entry.key,
          () => _NutrientAccumulator(
            key: entry.key,
            label: friendlyMetricName(entry.key),
          ),
        );
        accumulator.add(state, amount / reference * 100);
      }
    }

    final minimumTracked = switch (normalizedDays) {
      7 => 3,
      30 => 7,
      _ => 1,
    };
    final nutrients = <NutrientRisk>[];
    for (final item in accumulators.values) {
      if (item.trackedDays < minimumTracked) continue;
      final lowRate = item.lowDays / item.trackedDays;
      final highRate = item.highDays / item.trackedDays;
      final requiredRate = normalizedDays == 1 ? 1.0 : 0.6;
      if (lowRate >= requiredRate) {
        nutrients.add(
          item.toRisk(
            direction: NutrientDirection.low,
            level: item.averagePercent < 50
                ? RiskLevel.atRisk
                : RiskLevel.monitor,
          ),
        );
      } else if (highRate >= requiredRate) {
        nutrients.add(
          item.toRisk(
            direction: NutrientDirection.high,
            level: item.averagePercent > 150
                ? RiskLevel.atRisk
                : RiskLevel.monitor,
          ),
        );
      }
    }
    nutrients.sort((a, b) {
      final level = b.level.index.compareTo(a.level.index);
      if (level != 0) return level;
      final aDistance = (a.averagePercent - 100).abs();
      final bDistance = (b.averagePercent - 100).abs();
      return bDistance.compareTo(aDistance);
    });

    return HealthRiskSnapshot(
      periodDays: normalizedDays,
      observedDays: insights.daysWithMeals,
      asOf: referenceDate,
      healthScores: List.unmodifiable(scores.take(4)),
      nutrients: List.unmodifiable(nutrients.take(4)),
    );
  }
}

class _NutrientAccumulator {
  _NutrientAccumulator({required this.key, required this.label});

  final String key;
  final String label;
  int trackedDays = 0;
  int lowDays = 0;
  int highDays = 0;
  double percentTotal = 0;

  double get averagePercent =>
      trackedDays == 0 ? 0 : percentTotal / trackedDays;

  void add(BalanceState state, double percent) {
    trackedDays += 1;
    percentTotal += percent;
    if (state == BalanceState.low) lowDays += 1;
    if (state == BalanceState.high) highDays += 1;
  }

  NutrientRisk toRisk({
    required NutrientDirection direction,
    required RiskLevel level,
  }) {
    return NutrientRisk(
      key: key,
      label: label,
      direction: direction,
      level: level,
      averagePercent: averagePercent,
      concernDays: direction == NutrientDirection.low ? lowDays : highDays,
      trackedDays: trackedDays,
    );
  }
}
