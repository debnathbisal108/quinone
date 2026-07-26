import 'package:flutter/material.dart';
import '../../models/analysis_result.dart';

class FoodCard extends StatelessWidget {
  const FoodCard({super.key, required this.food});
  final FoodSummary food;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Row(children: [
        CircleAvatar(backgroundColor: theme.colorScheme.primaryContainer, child: const Icon(Icons.restaurant_rounded)),
        const SizedBox(width: 14),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(food.name, style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text(_details(), style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
        ])),
      ]),
    );
  }

  String _details() {
    final parts = <String>[];
    if (food.weightGrams > 0) parts.add('${food.weightGrams.round()} g');
    if (food.calories > 0) parts.add('${food.calories.round()} kcal');
    if (food.protein > 0) parts.add('${food.protein.toStringAsFixed(1)} g protein');
    return parts.isEmpty ? 'Detected in this meal' : parts.join(' • ');
  }
}
