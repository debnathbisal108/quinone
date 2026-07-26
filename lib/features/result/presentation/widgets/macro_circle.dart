// import 'dart:math' as math;
import 'package:flutter/material.dart';

class MacroCircle extends StatelessWidget {
  const MacroCircle({super.key, required this.label, required this.value, required this.target, required this.icon});
  final String label;
  final double value;
  final double target;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final progress = target <= 0 ? 0.0 : (value / target).clamp(0.0, 1.0);
    return Expanded(
      child: Column(
        children: [
          SizedBox.square(
            dimension: 92,
            child: Stack(
              alignment: Alignment.center,
              children: [
                CircularProgressIndicator(value: 1, strokeWidth: 8, color: theme.colorScheme.surfaceContainerHighest),
                CircularProgressIndicator(value: progress, strokeWidth: 8, strokeCap: StrokeCap.round),
                Column(mainAxisSize: MainAxisSize.min, children: [
                  Icon(icon, size: 18),
                  const SizedBox(height: 2),
                  Text('${_format(value)} g', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                ]),
              ],
            ),
          ),
          const SizedBox(height: 9),
          Text(label, style: theme.textTheme.labelLarge, textAlign: TextAlign.center),
        ],
      ),
    );
  }

  String _format(double value) => value >= 10 ? value.round().toString() : value.toStringAsFixed(1);
}
