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
    final ratio = target <= 0 ? 0.0 : value / target;
    final percent = ratio * 100;
    final over = ratio > 1;
    final color = over
        ? theme.colorScheme.error
        : theme.colorScheme.primary;

    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(22),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(22),
        child: Container(
          constraints: const BoxConstraints(minHeight: 220),
          padding: const EdgeInsets.fromLTRB(14, 18, 14, 16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            border: Border.all(
              color: theme.colorScheme.outlineVariant,
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              SizedBox.square(
                dimension: 92,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    CircularProgressIndicator(
                      value: 1,
                      strokeWidth: 9,
                      color: theme.colorScheme.surfaceContainerHighest,
                    ),
                    CircularProgressIndicator(
                      value: ratio.clamp(0.0, 1.0).toDouble(),
                      strokeWidth: 9,
                      strokeCap: StrokeCap.round,
                      color: color,
                    ),
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          icon,
                          size: 17,
                          color: color,
                        ),
                        const SizedBox(height: 3),
                        Text(
                          '${percent.round()}%',
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w900,
                            color: color,
                            height: 1,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 13),
              FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  '${_formatNumber(value)} g',
                  style: theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w900,
                    height: 1,
                  ),
                ),
              ),
              const SizedBox(height: 5),
              Text(
                target > 0
                    ? 'Target ${_formatNumber(target)} g'
                    : 'No target available',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.labelSmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                label,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w800,
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
