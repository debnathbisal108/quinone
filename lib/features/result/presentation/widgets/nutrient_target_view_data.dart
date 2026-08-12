import '../../models/analysis_result.dart';

/// Range-aware target data shared by the macro and micronutrient cards.
class NutrientTargetViewData {
  const NutrientTargetViewData._({
    required this.lowerBound,
    required this.upperBound,
    required this.unit,
    required this.isPersonalized,
  });

  factory NutrientTargetViewData.generic({
    required double value,
    required String unit,
  }) {
    return NutrientTargetViewData._(
      lowerBound: value,
      upperBound: null,
      unit: _dailyUnit(unit),
      isPersonalized: false,
    );
  }

  factory NutrientTargetViewData.personalized(
    PersonalizedNutrientTarget target, {
    required double fallbackValue,
    required String fallbackUnit,
  }) {
    final hasRange = target.rangeLow != null && target.rangeHigh != null;

    return NutrientTargetViewData._(
      // A resolved range is the actual personalized target. Its old baseline
      // must never replace the range (for example, 56 g replacing 90–120 g).
      lowerBound: hasRange
          ? target.rangeLow!
          : target.resolvedValue ??
              target.baselineValue ??
              target.rangeLow ??
              fallbackValue,
      upperBound: hasRange ? target.rangeHigh : null,
      unit: target.unit.trim().isNotEmpty
          ? target.unit.trim()
          : _dailyUnit(fallbackUnit),
      isPersonalized: true,
    );
  }

  final double lowerBound;
  final double? upperBound;
  final String unit;
  final bool isPersonalized;

  bool get isRange => upperBound != null;
  bool get isAvailable => lowerBound > 0;

  /// Progress reaches 100% at the lower edge of a target range, stays at
  /// 100% while the value is inside the range, and shows excess only after
  /// the upper edge is exceeded.
  double ratioFor(double amount) {
    if (!isAvailable) return 0;

    final high = upperBound;
    if (high == null) return amount / lowerBound;
    if (amount < lowerBound) return amount / lowerBound;
    if (amount <= high) return 1;
    return high <= 0 ? 0 : amount / high;
  }

  String get displayText {
    if (!isAvailable) return 'No target available';
    final high = upperBound;
    final value = high == null
        ? _formatNumber(lowerBound)
        : '${_formatNumber(lowerBound)}–${_formatNumber(high)}';
    return 'Target $value $unit';
  }

  static String _dailyUnit(String unit) {
    final trimmed = unit.trim();
    if (trimmed.isEmpty || trimmed.contains('/')) return trimmed;
    return '$trimmed/day';
  }

  static String _formatNumber(double value) {
    if (value == value.roundToDouble()) return value.round().toString();
    if (value.abs() >= 10) return value.toStringAsFixed(1);
    return value.toStringAsFixed(2);
  }
}
