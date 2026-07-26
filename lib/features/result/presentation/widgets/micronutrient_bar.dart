import 'package:flutter/material.dart';
import '../../models/analysis_result.dart';

class MicronutrientBar extends StatelessWidget {
  const MicronutrientBar({super.key, required this.nutrient});
  final Micronutrient nutrient;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final percent = nutrient.percentDailyValue;
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(child: Text(nutrient.label, style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700))),
            Text('${_format(nutrient.amount)} ${nutrient.unit}', style: theme.textTheme.bodyMedium),
            const SizedBox(width: 10),
            SizedBox(width: 46, child: Text('${percent.round()}%', textAlign: TextAlign.end, style: theme.textTheme.labelLarge?.copyWith(color: theme.colorScheme.primary))),
          ]),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(99),
            child: LinearProgressIndicator(value: (percent / 100).clamp(0, 1), minHeight: 10, backgroundColor: theme.colorScheme.surfaceContainerHighest),
          ),
        ],
      ),
    );
  }

  String _format(double value) => value >= 10 ? value.round().toString() : value.toStringAsFixed(1);
}
