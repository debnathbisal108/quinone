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

    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          constraints: const BoxConstraints(minHeight: 184),
          padding: const EdgeInsets.fromLTRB(10, 16, 10, 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: theme.colorScheme.outlineVariant),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              SizedBox.square(
                dimension: 112,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    CircularProgressIndicator(
                      value: 1,
                      strokeWidth: 9,
                      color: theme.colorScheme.surfaceContainerHighest,
                    ),
                    CircularProgressIndicator(
                      value: percentage.clamp(0, 1),
                      strokeWidth: 9,
                      strokeCap: StrokeCap.round,
                      color: isOverTarget
                          ? theme.colorScheme.error
                          : theme.colorScheme.primary,
                    ),
                    if (isOverTarget)
                      SizedBox.square(
                        dimension: 90,
                        child: CircularProgressIndicator(
                          value: (percentage - 1).clamp(0, 1),
                          strokeWidth: 5,
                          strokeCap: StrokeCap.round,
                          color: theme.colorScheme.tertiary,
                        ),
                      ),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(icon, size: 18),
                          const SizedBox(height: 4),
                          FittedBox(
                            fit: BoxFit.scaleDown,
                            child: Text(
                              '${_formatNumber(value)} g',
                              maxLines: 1,
                              style: theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          const SizedBox(height: 1),
                          Text(
                            '${(percentage * 100).round()}%',
                            style: theme.textTheme.labelSmall?.copyWith(
                              color: isOverTarget
                                  ? theme.colorScheme.error
                                  : theme.colorScheme.onSurfaceVariant,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 10),
              Text(
                label,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.labelLarge?.copyWith(
                  fontWeight: FontWeight.w700,
                  height: 1.15,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _formatNumber(double value) {
    return value >= 10 ? value.toStringAsFixed(1) : value.toStringAsFixed(2);
  }
}
