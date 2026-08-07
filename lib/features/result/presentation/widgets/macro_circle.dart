import 'package:flutter/material.dart';

class MacroCircle extends StatelessWidget {
  const MacroCircle({
    super.key,
    required this.label,
    required this.value,
    required this.target,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final double value;
  final double target;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final percentage = target <= 0 ? 0.0 : value / target;
    final isOverTarget = percentage > 1;
    final progressColor = isOverTarget
        ? theme.colorScheme.error
        : theme.colorScheme.primary;

    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          constraints: const BoxConstraints(minHeight: 205),
          padding: const EdgeInsets.fromLTRB(12, 16, 12, 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: theme.colorScheme.outlineVariant,
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              SizedBox.square(
                dimension: 96,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    CircularProgressIndicator(
                      value: 1,
                      strokeWidth: 8,
                      color: theme
                          .colorScheme
                          .surfaceContainerHighest,
                    ),
                    CircularProgressIndicator(
                      value: percentage.clamp(0, 1),
                      strokeWidth: 8,
                      strokeCap: StrokeCap.round,
                      color: progressColor,
                    ),
                    if (isOverTarget)
                      SizedBox.square(
                        dimension: 76,
                        child: CircularProgressIndicator(
                          value: (percentage - 1).clamp(0, 1),
                          strokeWidth: 4,
                          strokeCap: StrokeCap.round,
                          color: theme.colorScheme.tertiary,
                        ),
                      ),
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          icon,
                          size: 17,
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                        const SizedBox(height: 3),
                        FittedBox(
                          fit: BoxFit.scaleDown,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            crossAxisAlignment: CrossAxisAlignment.baseline,
                            textBaseline: TextBaseline.alphabetic,
                            children: [
                              Text(
                                _formatNumber(value),
                                style: theme.textTheme.titleLarge?.copyWith(
                                  fontWeight: FontWeight.w900,
                                  height: 1,
                                ),
                              ),
                              const SizedBox(width: 2),
                              Text(
                                'g',
                                style: theme.textTheme.labelMedium?.copyWith(
                                  color: theme.colorScheme.onSurfaceVariant,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 9),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: progressColor.withAlpha(31),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  '${(percentage * 100).round()}% of target',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: progressColor,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              const SizedBox(height: 10),
              Text(
                label,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.labelLarge?.copyWith(
                  fontWeight: FontWeight.w800,
                  height: 1.15,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static String _formatNumber(double value) {
    return value >= 10
        ? value.toStringAsFixed(1)
        : value.toStringAsFixed(2);
  }
}
