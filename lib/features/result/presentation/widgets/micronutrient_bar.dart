import 'package:flutter/material.dart';

import '../../models/analysis_result.dart';

class MicronutrientBar extends StatelessWidget {
  const MicronutrientBar({
    super.key,
    required this.nutrient,
    required this.onTap,
    this.targetOverride,
  });

  final Micronutrient nutrient;
  final VoidCallback onTap;
  final double? targetOverride;

  double get _target {
    final override = targetOverride;
    if (override != null && override > 0) return override;
    return nutrient.dailyValue;
  }

  double get _percent =>
      _target <= 0 ? 0 : nutrient.amount / _target * 100;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final percent = _percent;
    final over = percent > 100;
    final valueColor = over
        ? theme.colorScheme.error
        : theme.colorScheme.primary;

    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: Container(
          padding: const EdgeInsets.fromLTRB(16, 15, 16, 15),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: theme.colorScheme.outlineVariant,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      nutrient.label,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  Icon(
                    Icons.chevron_right_rounded,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      '${_number(nutrient.amount)} ${nutrient.unit}',
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  Text(
                    '${percent.round()}%',
                    style: theme.textTheme.titleSmall?.copyWith(
                      color: valueColor,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              _MicronutrientProgress(
                percent: percent,
                safeColor: theme.colorScheme.primary,
                excessColor: theme.colorScheme.error,
                trackColor: theme.colorScheme.surfaceContainerHighest,
              ),
            ],
          ),
        ),
      ),
    );
  }

  static String _number(double value) {
    if (value >= 100) return value.toStringAsFixed(0);
    if (value >= 10) return value.toStringAsFixed(1);
    return value.toStringAsFixed(2);
  }
}

class _MicronutrientProgress extends StatelessWidget {
  const _MicronutrientProgress({
    required this.percent,
    required this.safeColor,
    required this.excessColor,
    required this.trackColor,
  });

  final double percent;
  final Color safeColor;
  final Color excessColor;
  final Color trackColor;

  @override
  Widget build(BuildContext context) {
    final clamped = percent < 0 ? 0.0 : percent;

    return ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: SizedBox(
        height: 9,
        child: clamped <= 100
            ? Stack(
                fit: StackFit.expand,
                children: [
                  ColoredBox(color: trackColor),
                  FractionallySizedBox(
                    alignment: Alignment.centerLeft,
                    widthFactor: (clamped / 100).clamp(0.0, 1.0).toDouble(),
                    child: ColoredBox(color: safeColor),
                  ),
                ],
              )
            : Row(
                children: [
                  // For values over 100%, the green part always represents
                  // exactly the first 100%. Only the red excess grows.
                  Expanded(
                    flex: 100,
                    child: ColoredBox(color: safeColor),
                  ),
                  Expanded(
                    flex: (clamped - 100).round().clamp(1, 900).toInt(),
                    child: ColoredBox(color: excessColor),
                  ),
                ],
              ),
      ),
    );
  }
}
