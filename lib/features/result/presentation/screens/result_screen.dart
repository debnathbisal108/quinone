import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../models/analysis_result.dart';
import '../widgets/food_card.dart';
import '../widgets/health_score_card.dart';
import '../widgets/macro_circle.dart';
import '../widgets/micronutrient_bar.dart';
import '../widgets/score_gauge.dart';

class ResultScreen extends StatelessWidget {
  const ResultScreen({super.key, required this.result});
  final AnalysisResult result;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Meal analysis'),
        leading: IconButton(onPressed: () => context.canPop() ? context.pop() : context.go('/upload'), icon: const Icon(Icons.arrow_back_rounded)),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 36),
          children: [
            Text(result.mealName, style: theme.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
            if (result.summary != null) ...[
              const SizedBox(height: 8),
              Text(result.summary!, style: theme.textTheme.bodyLarge?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            ],
            const SizedBox(height: 24),
            Center(child: ScoreGauge(score: result.overallScore)),
            const SizedBox(height: 24),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(color: theme.colorScheme.primaryContainer, borderRadius: BorderRadius.circular(24)),
              child: Row(children: [
                Icon(Icons.local_fire_department_rounded, size: 34, color: theme.colorScheme.onPrimaryContainer),
                const SizedBox(width: 14),
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Energy', style: theme.textTheme.labelLarge?.copyWith(color: theme.colorScheme.onPrimaryContainer)),
                  Text('${result.calories.round()} kcal', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800, color: theme.colorScheme.onPrimaryContainer)),
                ]),
              ]),
            ),
            const SizedBox(height: 28),
            const _SectionTitle('Macronutrients'),
            const SizedBox(height: 16),
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              MacroCircle(label: 'Protein', value: result.protein, target: 50, icon: Icons.fitness_center_rounded),
              const SizedBox(width: 10),
              MacroCircle(label: 'Carbs', value: result.carbohydrates, target: 100, icon: Icons.grain_rounded),
              const SizedBox(width: 10),
              MacroCircle(label: 'Fat', value: result.fat, target: 35, icon: Icons.water_drop_outlined),
            ]),
            if (result.fiber > 0) ...[
              const SizedBox(height: 14),
              Text('Fiber ${result.fiber.toStringAsFixed(1)} g', textAlign: TextAlign.center, style: theme.textTheme.labelLarge?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            ],
            if (result.healthScores.isNotEmpty) ...[
              const SizedBox(height: 32),
              const _SectionTitle('Health scores'),
              const SizedBox(height: 14),
              for (var i = 0; i < result.healthScores.length; i++) ...[
                HealthScoreCard(item: result.healthScores[i]),
                if (i < result.healthScores.length - 1) const SizedBox(height: 10),
              ],
            ],
            if (result.micronutrients.isNotEmpty) ...[
              const SizedBox(height: 32),
              const _SectionTitle('Micronutrients'),
              const SizedBox(height: 14),
              Container(
                padding: const EdgeInsets.fromLTRB(18, 18, 18, 2),
                decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerLow, borderRadius: BorderRadius.circular(22), border: Border.all(color: theme.colorScheme.outlineVariant)),
                child: Column(children: [for (final nutrient in result.micronutrients) MicronutrientBar(nutrient: nutrient)]),
              ),
              const SizedBox(height: 8),
              Text('Daily-value percentages are general reference values, not personalised medical targets.', style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            ],
            if (result.foods.isNotEmpty) ...[
              const SizedBox(height: 32),
              const _SectionTitle('Detected foods'),
              const SizedBox(height: 14),
              for (var i = 0; i < result.foods.length; i++) ...[
                FoodCard(food: result.foods[i]),
                if (i < result.foods.length - 1) const SizedBox(height: 10),
              ],
            ],
            const SizedBox(height: 32),
            FilledButton.icon(
              onPressed: () => context.go('/upload'),
              icon: const Icon(Icons.add_a_photo_outlined),
              label: const Text('Analyze another meal'),
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18))),
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);
  final String title;
  @override
  Widget build(BuildContext context) => Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800));
}
