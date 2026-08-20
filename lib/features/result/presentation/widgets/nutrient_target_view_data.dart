import '../../models/analysis_result.dart';

/// Range/upper-limit-aware target data shared by macro and micronutrient cards.
///
/// A requirement such as an RDA/AI is an adequacy reference, not an upper
/// safety limit. Values above 100% of a minimum target therefore stay green
/// unless the target also supplies a real UL. Only a true range/maximum/UL can
/// create the red excess state.
class NutrientTargetViewData {
  const NutrientTargetViewData._({
    required this.lowerBound,
    required this.upperBound,
    required this.upperLimit,
    required this.unit,
    required this.isPersonalized,
    required this.targetType,
  });

  factory NutrientTargetViewData.generic({
    required double value,
    required String unit,
    double? upperBound,
    double? upperLimit,
    String targetType = 'minimum',
  }) {
    return NutrientTargetViewData._(
      lowerBound: value,
      upperBound: upperBound,
      upperLimit: upperLimit,
      unit: _dailyUnit(unit),
      isPersonalized: false,
      targetType: targetType,
    );
  }

  factory NutrientTargetViewData.personalized(
    PersonalizedNutrientTarget target, {
    required double fallbackValue,
    required String fallbackUnit,
  }) {
    final hasRange = target.rangeLow != null && target.rangeHigh != null;

    return NutrientTargetViewData._(
      lowerBound: hasRange
          ? target.rangeLow!
          : target.resolvedValue ??
              target.baselineValue ??
              target.rangeLow ??
              fallbackValue,
      upperBound: hasRange ? target.rangeHigh : null,
      upperLimit: _foodApplicableUpperLimit(target) ? target.upperLimit : null,
      unit: target.unit.trim().isNotEmpty
          ? target.unit.trim()
          : _dailyUnit(fallbackUnit),
      isPersonalized: true,
      targetType: (target.targetType ?? 'minimum').trim().toLowerCase(),
    );
  }

  final double lowerBound;
  final double? upperBound;
  final double? upperLimit;
  final String unit;
  final bool isPersonalized;
  final String targetType;

  bool get isRange => upperBound != null;
  bool get isAvailable => lowerBound > 0;
  bool get isMaximum =>
      targetType.contains('maximum') || targetType.contains('upper');

  /// The percentage displayed to the user. For a range, 100% means the value
  /// is inside the range; for a minimum target it remains the familiar
  /// amount/target percentage and may be >100 without implying excess.
  double percentFor(double amount) {
    if (!isAvailable) return 0;
    final high = upperBound;
    if (high != null) {
      if (amount < lowerBound) return amount / lowerBound * 100;
      if (amount <= high) return 100;
      return high <= 0 ? 0 : amount / high * 100;
    }
    return amount / lowerBound * 100;
  }

  bool isExcess(double amount) {
    final high = upperBound;
    if (high != null && high > 0) return amount > high;
    final ul = upperLimit;
    if (ul != null && ul > 0) return amount > ul;
    if (isMaximum && lowerBound > 0) return amount > lowerBound;
    return false;
  }

  /// Minimum/RDA/AI targets can exceed 100% without being a safety excess.
  /// Surface that as an informational overflow state, while ranges/maximums
  /// continue to use their actual upper boundary.
  bool isAboveReference(double amount) =>
      !isRange && !isMaximum && lowerBound > 0 && amount > lowerBound;

  double referenceOverflowRatioFor(double amount) =>
      lowerBound <= 0 ? 0 : amount / lowerBound;

  /// Ratio used only for the ring/bar drawing. A minimum target that is met
  /// stays fully green. Red overflow appears only against a real upper bound.
  double visualRatioFor(double amount) {
    if (!isAvailable) return 0;
    if (!isExcess(amount)) {
      if (isRange) return percentFor(amount).clamp(0.0, 100.0) / 100.0;
      return (amount / lowerBound).clamp(0.0, 1.0).toDouble();
    }

    final excessReference = upperBound ?? upperLimit ?? lowerBound;
    return excessReference <= 0 ? 0 : amount / excessReference;
  }

  /// Backward-compatible alias for callers that only need a progress ratio.
  double ratioFor(double amount) => visualRatioFor(amount);

  String get displayText {
    if (!isAvailable) return 'No target available';
    final high = upperBound;
    final base = high != null
        ? 'Target ${_formatNumber(lowerBound)}–${_formatNumber(high)} $unit'
        : isMaximum
            ? 'Limit ≤${_formatNumber(lowerBound)} $unit'
            : 'Target ≥${_formatNumber(lowerBound)} $unit';
    final ul = upperLimit;
    if (ul == null || ul <= 0 || high != null && (ul - high).abs() < 0.0001) {
      return base;
    }
    return '$base · UL ≤${_formatNumber(ul)} $unit';
  }


  static bool _foodApplicableUpperLimit(PersonalizedNutrientTarget target) {
    final scope = (target.upperLimitScope ?? '').trim().toLowerCase();
    if (scope.isEmpty) return true;
    if (scope.contains('added_') ||
        scope.contains('synthetic') ||
        scope.contains('preformed_retinol')) {
      return false;
    }
    if (scope == 'all_intake' ||
        scope == 'all_sources' ||
        scope.contains('food')) {
      return true;
    }
    if (scope.contains('supplement')) return false;
    return false;
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
