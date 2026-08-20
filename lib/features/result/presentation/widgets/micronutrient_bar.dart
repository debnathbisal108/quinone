import 'package:flutter/material.dart';

import '../../models/analysis_result.dart';
import 'nutrient_target_view_data.dart';

class MicronutrientBar extends StatelessWidget {
  const MicronutrientBar({
    super.key,
    required this.nutrient,
    required this.target,
    required this.onTap,
  });

  final Micronutrient nutrient;
  final NutrientTargetViewData target;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final percent = target.percentFor(nutrient.amount);
    final over = target.isExcess(nutrient.amount);
    final aboveReference = !over && target.isAboveReference(nutrient.amount);
    final visualPercent = (over
            ? target.visualRatioFor(nutrient.amount)
            : aboveReference
                ? target.referenceOverflowRatioFor(nutrient.amount)
                : target.visualRatioFor(nutrient.amount)) *
        100;
    final overflowColor = over ? theme.colorScheme.error : Colors.orange;
    final valueColor = over
        ? theme.colorScheme.error
        : aboveReference
            ? Colors.orange
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
              const SizedBox(height: 5),
              Text(
                target.displayText,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 12),
              _MicronutrientProgress(
                percent: visualPercent,
                showOverflow: over || aboveReference,
                safeColor: theme.colorScheme.primary,
                overflowColor: overflowColor,
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
    required this.showOverflow,
    required this.safeColor,
    required this.overflowColor,
    required this.trackColor,
  });

  final double percent;
  final bool showOverflow;
  final Color safeColor;
  final Color overflowColor;
  final Color trackColor;

  @override
  Widget build(BuildContext context) {
    final clamped = percent < 0 ? 0.0 : percent;

    return ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: SizedBox(
        height: 9,
        child: !showOverflow || clamped <= 100
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
            : LayoutBuilder(
                builder: (context, constraints) {
                  // Target and excess share the same full-width bar. As the
                  // total rises beyond 100%, the green target share shrinks
                  // proportionally and the red excess share grows.
                  final targetShare = (100 / clamped)
                      .clamp(0.0, 1.0)
                      .toDouble();
                  final targetWidth = constraints.maxWidth * targetShare;

                  return Stack(
                    fit: StackFit.expand,
                    children: [
                      ColoredBox(color: overflowColor),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: SizedBox(
                          width: targetWidth,
                          height: double.infinity,
                          child: ColoredBox(color: safeColor),
                        ),
                      ),
                    ],
                  );
                },
              ),
      ),
    );
  }
}
