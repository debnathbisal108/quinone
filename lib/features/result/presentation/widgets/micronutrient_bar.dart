import 'package:flutter/material.dart';
import '../../models/analysis_result.dart';

// import 'package:flutter/material.dart';
// import 'package:quinone/features/result/models/analysis_result.dart';

class MicronutrientBar extends StatelessWidget {
  const MicronutrientBar({
    super.key,
    required this.nutrient,
    required this.onTap,
  });

  final Micronutrient nutrient;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final percentage = nutrient.percentDailyValue;
    final isOverDailyValue = percentage > 100;
    final progress = (percentage / 100).clamp(0.0, 1.0);

    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(14, 13, 10, 13),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: theme.colorScheme.outlineVariant),
          ),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final compact = constraints.maxWidth < 320;

              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (compact)
                    _CompactHeader(
                      nutrient: nutrient,
                      isOverDailyValue: isOverDailyValue,
                    )
                  else
                    _WideHeader(
                      nutrient: nutrient,
                      isOverDailyValue: isOverDailyValue,
                    ),
                  const SizedBox(height: 11),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(99),
                    child: SizedBox(
                      height: 9,
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          ColoredBox(
                            color: theme.colorScheme.surfaceContainerHighest,
                          ),
                          Align(
                            alignment: Alignment.centerLeft,
                            child: FractionallySizedBox(
                              widthFactor: progress,
                              child: ColoredBox(
                                color: isOverDailyValue
                                    ? theme.colorScheme.error
                                    : theme.colorScheme.primary,
                              ),
                            ),
                          ),
                          if (isOverDailyValue)
                            Align(
                              alignment: Alignment.centerRight,
                              child: FractionallySizedBox(
                                widthFactor: 0.08,
                                child: ColoredBox(
                                  color: theme.colorScheme.tertiary,
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

class _WideHeader extends StatelessWidget {
  const _WideHeader({
    required this.nutrient,
    required this.isOverDailyValue,
  });

  final Micronutrient nutrient;
  final bool isOverDailyValue;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(
          child: Text(
            nutrient.label,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w700,
              height: 1.2,
            ),
          ),
        ),
        const SizedBox(width: 12),
        ConstrainedBox(
          constraints: const BoxConstraints(minWidth: 78),
          child: Text(
            _formatAmount(nutrient),
            maxLines: 1,
            overflow: TextOverflow.fade,
            softWrap: false,
            textAlign: TextAlign.right,
            style: theme.textTheme.bodyMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        const SizedBox(width: 12),
        SizedBox(
          width: 48,
          child: Text(
            '${nutrient.percentDailyValue.round()}%',
            maxLines: 1,
            textAlign: TextAlign.right,
            style: theme.textTheme.labelLarge?.copyWith(
              color: isOverDailyValue
                  ? theme.colorScheme.error
                  : theme.colorScheme.primary,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        const SizedBox(width: 2),
        Icon(
          Icons.chevron_right_rounded,
          size: 22,
          color: theme.colorScheme.onSurfaceVariant,
        ),
      ],
    );
  }
}

class _CompactHeader extends StatelessWidget {
  const _CompactHeader({
    required this.nutrient,
    required this.isOverDailyValue,
  });

  final Micronutrient nutrient;
  final bool isOverDailyValue;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                nutrient.label,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                  height: 1.2,
                ),
              ),
            ),
            const SizedBox(width: 8),
            Icon(
              Icons.chevron_right_rounded,
              size: 22,
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ],
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            Expanded(
              child: Text(
                _formatAmount(nutrient),
                maxLines: 1,
                overflow: TextOverflow.fade,
                softWrap: false,
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Text(
              '${nutrient.percentDailyValue.round()}%',
              style: theme.textTheme.labelLarge?.copyWith(
                color: isOverDailyValue
                    ? theme.colorScheme.error
                    : theme.colorScheme.primary,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

String _formatAmount(Micronutrient nutrient) {
  final amount = nutrient.amount;
  final formatted = amount >= 100
      ? amount.round().toString()
      : amount >= 10
          ? amount.toStringAsFixed(1)
          : amount.toStringAsFixed(2);
  final unit = nutrient.unit.trim();
  return unit.isEmpty ? formatted : '$formatted $unit';
}
