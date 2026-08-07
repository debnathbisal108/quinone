import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../models/analysis_result.dart';
import '../widgets/food_card.dart';
import '../widgets/health_score_card.dart';
import '../widgets/macro_circle.dart';
import '../widgets/micronutrient_bar.dart';
import '../widgets/score_gauge.dart';

// import 'package:flutter/material.dart';
// import 'package:go_router/go_router.dart';
// import 'package:quinone/features/result/models/analysis_result.dart';

// import '../widgets/food_card.dart';
// import '../widgets/health_score_card.dart';
// import '../widgets/macro_circle.dart';
// import '../widgets/micronutrient_bar.dart';
// import '../widgets/score_gauge.dart';

class ResultScreen extends StatelessWidget {
  const ResultScreen({
    super.key,
    required this.result,
  });

  final AnalysisResult result;

  void _showNutrientDetails(
    BuildContext context, {
    required String title,
    required String nutrientKey,
    required double amount,
    required String unit,
    List<_NutrientDetailItem> relatedValues = const [],
  }) {
    final contributions = result.contributionsFor(nutrientKey);

    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) {
        final theme = Theme.of(sheetContext);

        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: 0.52,
          minChildSize: 0.35,
          maxChildSize: 0.88,
          builder: (context, scrollController) {
            return ListView(
              controller: scrollController,
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
              children: [
                Text(
                  title,
                  style: theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  '${_formatNumber(amount)} $unit total',
                  style: theme.textTheme.bodyLarge?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                if (relatedValues.isNotEmpty) ...[
                  const SizedBox(height: 20),
                  Text(
                    'Breakdown',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Container(
                    decoration: BoxDecoration(
                      color: theme.colorScheme.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(
                        color: theme.colorScheme.outlineVariant,
                      ),
                    ),
                    child: Column(
                      children: [
                        for (
                          var index = 0;
                          index < relatedValues.length;
                          index++
                        ) ...[
                          Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 14,
                            ),
                            child: Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    relatedValues[index].label,
                                    style:
                                        theme.textTheme.bodyLarge?.copyWith(
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Text(
                                  relatedValues[index].available
                                      ? '${_formatNumber(relatedValues[index].value)} '
                                          '${relatedValues[index].unit}'
                                      : 'Not available',
                                  style:
                                      theme.textTheme.titleSmall?.copyWith(
                                    fontWeight: FontWeight.w800,
                                    color: relatedValues[index].available
                                        ? null
                                        : theme
                                            .colorScheme
                                            .onSurfaceVariant,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          if (index < relatedValues.length - 1)
                            Divider(
                              height: 1,
                              color: theme.colorScheme.outlineVariant,
                            ),
                        ],
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 20),
                Text(
                  'Food contributors',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 10),
                if (contributions.isEmpty)
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: const Text(
                      'Food-level contribution data is not available for this nutrient.',
                    ),
                  )
                else
                  ...contributions.map(
                    (item) => Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 14,
                        ),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.surfaceContainerLow,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: theme.colorScheme.outlineVariant,
                          ),
                        ),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                item.foodName,
                                style: theme.textTheme.titleSmall?.copyWith(
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Text(
                              '${_formatNumber(item.amount)} $unit',
                              style: theme.textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            );
          },
        );
      },
    );
  }

  void _showHealthScoreDetails(
    BuildContext context,
    HealthScore score,
  ) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) {
        final theme = Theme.of(sheetContext);

        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: 0.72,
          minChildSize: 0.45,
          maxChildSize: 0.92,
          builder: (context, scrollController) {
            return ListView(
              controller: scrollController,
              padding: const EdgeInsets.fromLTRB(
                20,
                4,
                20,
                30,
              ),
              children: [
                Text(
                  score.label,
                  style:
                      theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  '${score.score.toStringAsFixed(0)} / 100',
                  style:
                      theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _ScoreMetricChip(
                      label: 'Confidence',
                      value:
                          '${(score.confidence * 100).round()}%',
                    ),
                    _ScoreMetricChip(
                      label: 'Coverage',
                      value:
                          '${(score.coverage * 100).round()}%',
                    ),
                    _ScoreMetricChip(
                      label: 'Reliability',
                      value:
                          '${(score.reliability * 100).round()}%',
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                _HealthContributorSection(
                  title: 'Positive contributors',
                  emptyText:
                      'No positive contributor was identified.',
                  contributors:
                      score.positiveContributors,
                  positive: true,
                ),
                const SizedBox(height: 22),
                _HealthContributorSection(
                  title: 'Negative contributors',
                  emptyText:
                      'No negative contributor was identified.',
                  contributors:
                      score.negativeContributors,
                  positive: false,
                ),
              ],
            );
          },
        );
      },
    );
  }

  double _resolvedMacroTarget(
    String nutrientKey,
    double fallback,
  ) {
    final target = result.nutrientTargets[nutrientKey];
    if (target == null || !target.isResolved) return fallback;

    return target.resolvedValue ??
        target.baselineValue ??
        target.rangeLow ??
        fallback;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final macros = <_MacroItem>[
      _MacroItem(
        label: 'Protein',
        value: result.protein,
        target: _resolvedMacroTarget('protein_g', 50),
        nutrientKey: 'protein_g',
        icon: Icons.fitness_center_rounded,
      ),
      _MacroItem(
        label: 'Carbohydrates',
        value: result.carbohydrates,
        target: _resolvedMacroTarget('carbohydrate_g', 275),
        nutrientKey: 'carbohydrate_g',
        icon: Icons.grain_rounded,
      ),
      _MacroItem(
        label: 'Fat',
        value: result.fat,
        target: _resolvedMacroTarget('fat_g', 78),
        nutrientKey: 'fat_g',
        icon: Icons.water_drop_outlined,
      ),
      _MacroItem(
        label: 'Fiber',
        value: result.fiber,
        target: _resolvedMacroTarget('fiber_g', 28),
        nutrientKey: 'fiber_g',
        icon: Icons.eco_outlined,
      ),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Meal analysis'),
        leading: IconButton(
          onPressed: () => context.canPop()
              ? context.pop()
              : context.go('/home'),
          icon: const Icon(Icons.arrow_back_rounded),
        ),
      ),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final horizontalPadding = constraints.maxWidth >= 700 ? 32.0 : 20.0;
            final contentWidth = constraints.maxWidth >= 900 ? 820.0 : double.infinity;

            return SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(
                horizontalPadding,
                12,
                horizontalPadding,
                36,
              ),
              child: Align(
                alignment: Alignment.topCenter,
                child: ConstrainedBox(
                  constraints: BoxConstraints(maxWidth: contentWidth),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        result.mealName,
                        style: theme.textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      if (result.summary != null && result.summary!.trim().isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Text(
                          result.summary!,
                          style: theme.textTheme.bodyLarge?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                            height: 1.45,
                          ),
                        ),
                      ],
                      const SizedBox(height: 24),
                      _OverviewCard(result: result),
                      if (result.foods.isNotEmpty) ...[
                        const SizedBox(height: 28),
                        const _SectionTitle('Detected foods'),
                        const SizedBox(height: 14),
                        ...result.foods.map(
                          (food) => Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: FoodCard(food: food),
                          ),
                        ),
                      ],
                      const SizedBox(height: 28),
                      const _SectionTitle('Macronutrients'),
                      const SizedBox(height: 14),
                      LayoutBuilder(
                        builder: (context, gridConstraints) {
                          final width = gridConstraints.maxWidth;
                          final columns = width >= 720 ? 4 : 2;
                          const spacing = 12.0;
                          final itemWidth =
                              (width - spacing * (columns - 1)) / columns;

                          return Wrap(
                            spacing: spacing,
                            runSpacing: spacing,
                            children: [
                              for (final macro in macros)
                                SizedBox(
                                  width: itemWidth,
                                  child: MacroCircle(
                                    label: macro.label,
                                    value: macro.value,
                                    target: macro.target,
                                    icon: macro.icon,
                                    onTap: () {
                                    if (macro.nutrientKey == 'fat_g') {
                                      _showNutrientDetails(
                                        context,
                                        title: 'Fat',
                                        nutrientKey: 'fat_g',
                                        amount: result.fat,
                                        unit: 'g',
                                        relatedValues: [
                                          _NutrientDetailItem(
                                            label: 'Total fat',
                                            value: result.fat,
                                            unit: 'g',
                                            available: true,
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Saturated fat',
                                            value: result.saturatedFat ?? 0,
                                            unit: 'g',
                                            available: result.saturatedFat != null,
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Monounsaturated fat',
                                            value: result.monounsaturatedFat ?? 0,
                                            unit: 'g',
                                            available: result.monounsaturatedFat != null,
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Polyunsaturated fat',
                                            value: result.polyunsaturatedFat ?? 0,
                                            unit: 'g',
                                            available: result.polyunsaturatedFat != null,
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Trans fat',
                                            value: result.transFat ?? 0,
                                            unit: 'g',
                                            available: result.transFat != null,
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Omega-3',
                                            value: result.omega3 ?? 0,
                                            unit: 'g',
                                            available: result.omega3 != null,
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Omega-6',
                                            value: result.omega6 ?? 0,
                                            unit: 'g',
                                            available: result.omega6 != null,
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Cholesterol',
                                            value: result.cholesterol ?? 0,
                                            unit: 'mg',
                                            available: result.cholesterol != null,
                                          ),
                                        ],
                                      );

                                      return;
                                    }

                                    if (macro.nutrientKey == 'carbohydrate_g') {
                                      _showNutrientDetails(
                                        context,
                                        title: macro.label,
                                        nutrientKey: macro.nutrientKey,
                                        amount: macro.value,
                                        unit: 'g',
                                        relatedValues: [
                                          _NutrientDetailItem(
                                            label: 'Total carbohydrates',
                                            value: result.carbohydrates,
                                            unit: 'g',
                                            available: true,
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Total sugars',
                                            value: result.sugars ?? 0,
                                            unit: 'g',
                                            available: result.sugars != null,
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Added sugars',
                                            value: result.addedSugars ?? 0,
                                            unit: 'g',
                                            available: result.addedSugars != null,
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Dietary fiber',
                                            value: result.fiber,
                                            unit: 'g',
                                            available: result.fiber > 0,
                                          ),
                                        ],
                                      );

                                      return;
                                    }

                                    _showNutrientDetails(
                                      context,
                                      title: macro.label,
                                      nutrientKey: macro.nutrientKey,
                                      amount: macro.value,
                                      unit: 'g',
                                    );
                                  },
                                  ),
                                ),
                            ],
                          );
                        },
                      ),
                      if (result.healthScores.isNotEmpty) ...[
                        const SizedBox(height: 32),
                        const _SectionTitle('Health scores'),
                        const SizedBox(height: 14),
                        ...result.healthScores.map(
                          (score) => Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            // child: HealthScoreCard(item: score),
                            child: HealthScoreCard(
                              item: score,
                                onTap: () => _showHealthScoreDetails(
                                  context,
                                  score,
                                ),
                              ),
                          ),
                        ),
                      ],
                      if (result.micronutrients.isNotEmpty) ...[
                        const SizedBox(height: 32),
                        const _SectionTitle('Micronutrients'),
                        const SizedBox(height: 14),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 8,
                          ),
                          decoration: BoxDecoration(
                            color: theme.colorScheme.surfaceContainerLow,
                            borderRadius: BorderRadius.circular(22),
                            border: Border.all(
                              color: theme.colorScheme.outlineVariant,
                            ),
                          ),
                          child: Column(
                            children: [
                              for (var index = 0;
                                  index < result.micronutrients.length;
                                  index++) ...[
                                MicronutrientBar(
                                  nutrient: result.micronutrients[index],
                                  onTap: () {
                                    final nutrient = result.micronutrients[index];
                                    _showNutrientDetails(
                                      context,
                                      title: nutrient.label,
                                      nutrientKey: nutrient.key,
                                      amount: nutrient.amount,
                                      unit: nutrient.unit,
                                    );
                                  },
                                ),
                                if (index < result.micronutrients.length - 1)
                                  Divider(
                                    height: 1,
                                    color: theme.colorScheme.outlineVariant,
                                  ),
                              ],
                            ],
                          ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          'Tap a nutrient to see which foods contributed to it. Percentages use general daily values.',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                            height: 1.4,
                          ),
                        ),
                      ],
                      if (result.nutrientTargets.isNotEmpty) ...[
                        const SizedBox(height: 32),
                        const _SectionTitle('Personalized daily targets'),
                        const SizedBox(height: 14),
                        ...result.nutrientTargets.values
                            .where((target) =>
                                target.isResolved ||
                                target.status == 'requires_clinical_input')
                            .map(
                              (target) => Padding(
                                padding: const EdgeInsets.only(bottom: 10),
                                child: _PersonalizedTargetCard(
                                  target: target,
                                ),
                              ),
                            ),
                      ],
                      if (result.nutrientRiskFlags.isNotEmpty) ...[
                        const SizedBox(height: 22),
                        const _SectionTitle('Personalization notes'),
                        const SizedBox(height: 12),
                        ...result.nutrientRiskFlags.map(
                          (flag) => Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: _RiskFlagCard(flag: flag),
                          ),
                        ),
                      ],
                      const SizedBox(height: 28),
                      SizedBox(
                        height: 52,
                        child: FilledButton.icon(
                          onPressed: () => context.go('/upload'),
                          icon: const Icon(Icons.add_a_photo_outlined),
                          label: const Text('Analyze another meal'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  String _formatNumber(double value) {
    return value >= 10 ? value.toStringAsFixed(1) : value.toStringAsFixed(2);
  }
}

String _displayFeatureName(String value) {
  return value
      .replaceAll('_', ' ')
      .split(RegExp(r'\s+'))
      .where((word) => word.isNotEmpty)
      .map(
        (word) =>
            '${word[0].toUpperCase()}'
            '${word.substring(1).toLowerCase()}',
      )
      .join(' ');
}

class _OverviewCard extends StatelessWidget {
  const _OverviewCard({required this.result});

  final AnalysisResult result;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(26),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 460;
          final score = ScoreGauge(score: result.overallScore, size: compact ? 140 : 154);
          final calories = _CaloriesCard(calories: result.calories);

          if (compact) {
            return Column(
              children: [
                score,
                const SizedBox(height: 18),
                calories,
              ],
            );
          }

          return Row(
            children: [
              score,
              const SizedBox(width: 24),
              Expanded(child: calories),
            ],
          );
        },
      ),
    );
  }
}

class _CaloriesCard extends StatelessWidget {
  const _CaloriesCard({required this.calories});

  final double calories;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          Icon(
            Icons.local_fire_department_rounded,
            size: 34,
            color: theme.colorScheme.onPrimaryContainer,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Energy',
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: theme.colorScheme.onPrimaryContainer,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${calories.round()} kcal',
                  style: theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                    color: theme.colorScheme.onPrimaryContainer,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PersonalizedTargetCard extends StatelessWidget {
  const _PersonalizedTargetCard({required this.target});

  final PersonalizedNutrientTarget target;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    String valueText;
    if (target.status == 'requires_clinical_input') {
      valueText = 'Clinical input required';
    } else if (target.isRange) {
      valueText = '${_formatTarget(target.rangeLow!)}–${_formatTarget(target.rangeHigh!)} ${target.unit}';
    } else if (target.resolvedValue != null) {
      valueText = '${_formatTarget(target.resolvedValue!)} ${target.unit}';
    } else {
      valueText = 'Not resolved';
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            target.status == 'requires_clinical_input'
                ? Icons.medical_information_outlined
                : Icons.track_changes_rounded,
            color: theme.colorScheme.primary,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  target.name,
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  valueText,
                  style: theme.textTheme.bodyLarge?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (target.targetType != null) ...[
                  const SizedBox(height: 3),
                  Text(
                    _displayTargetType(target.targetType!),
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RiskFlagCard extends StatelessWidget {
  const _RiskFlagCard({required this.flag});

  final NutrientRiskFlag flag;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.tertiaryContainer,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.info_outline_rounded,
            color: theme.colorScheme.onTertiaryContainer,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              flag.message ?? flag.id.replaceAll('_', ' '),
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onTertiaryContainer,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

String _formatTarget(double value) {
  if (value == value.roundToDouble()) return value.round().toString();
  if (value.abs() >= 10) return value.toStringAsFixed(1);
  return value.toStringAsFixed(2);
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: Theme.of(context).textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.w800,
          ),
    );
  }
}

class _MacroItem {
  const _MacroItem({
    required this.label,
    required this.value,
    required this.target,
    required this.nutrientKey,
    required this.icon,
  });

  final String label;
  final double value;
  final double target;
  final String nutrientKey;
  final IconData icon;
}

class _NutrientDetailItem {
  const _NutrientDetailItem({
    required this.label,
    required this.value,
    required this.unit,
    required this.available,
  });

  final String label;
  final double value;
  final String unit;
  final bool available;
}

class _ScoreMetricChip extends StatelessWidget {
  const _ScoreMetricChip({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 12,
        vertical: 8,
      ),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
        ),
      ),
      child: Text(
        '$label: $value',
        style: theme.textTheme.labelLarge?.copyWith(
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _HealthContributorSection
    extends StatelessWidget {
  const _HealthContributorSection({
    required this.title,
    required this.emptyText,
    required this.contributors,
    required this.positive,
  });

  final String title;
  final String emptyText;
  final List<HealthContributor> contributors;
  final bool positive;

  List<HealthContributor> get _uniqueContributors {
    final unique = <String, HealthContributor>{};

    for (final contributor in contributors) {
      final key = [
        contributor.ruleName.trim().toLowerCase(),
        contributor.feature.trim().toLowerCase(),
        (contributor.mechanism ?? '').trim().toLowerCase(),
        positive ? 'positive' : 'negative',
      ].join('|');

      final existing = unique[key];
      if (existing == null ||
          contributor.effectiveWeight.abs() >
              existing.effectiveWeight.abs()) {
        unique[key] = contributor;
      }
    }

    return unique.values.toList(growable: false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          title,
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 10),
        if (_uniqueContributors.isEmpty)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color:
                  theme.colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Text(emptyText),
          )
        else
          ..._uniqueContributors.map(
            (contributor) =>
                _HealthContributorTile(
              contributor: contributor,
              positive: positive,
            ),
          ),
      ],
    );
  }
}

class _HealthContributorTile
    extends StatelessWidget {
  const _HealthContributorTile({
    required this.contributor,
    required this.positive,
  });

  final HealthContributor contributor;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            positive
                ? Icons.add_circle_outline_rounded
                : Icons.remove_circle_outline_rounded,
            color: positive
                ? theme.colorScheme.primary
                : theme.colorScheme.error,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment:
                  CrossAxisAlignment.start,
              children: [
                Text(
                  contributor.ruleName,
                  style:
                      theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  _displayFeatureName(
                    contributor.feature,
                  ),
                  style: theme.textTheme.bodyMedium,
                ),
                if (contributor.mechanism != null &&
                    contributor
                        .mechanism!
                        .isNotEmpty) ...[
                  const SizedBox(height: 5),
                  Text(
                    contributor.mechanism!,
                    style:
                        theme.textTheme.bodySmall?.copyWith(
                      color: theme
                          .colorScheme
                          .onSurfaceVariant,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 10),
          _ImpactBadge(
            label: _impactLabel(
              contributor.effectiveWeight,
              positive: positive,
            ),
            positive: positive,
          ),
        ],
      ),
    );
  }
}

String _displayTargetType(String rawValue) {
  final normalized = rawValue.trim().toLowerCase();

  const exactLabels = <String, String>{
    'rda': 'Recommended Dietary Allowance',
    'ai': 'Adequate Intake',
    'eer': 'Estimated Energy Requirement',
    'amdr': 'Acceptable Macronutrient Distribution Range',
    'clinical_target_range': 'Clinical target range',
    'clinical_goal_range': 'Clinical goal range',
    'clinical_goal': 'Clinical goal',
    'maximum': 'Recommended maximum',
    'minimum': 'Recommended minimum',
  };

  final exact = exactLabels[normalized];
  if (exact != null) return exact;

  return normalized
      .replaceAll('_', ' ')
      .split(RegExp(r'\s+'))
      .where((word) => word.isNotEmpty)
      .map(
        (word) =>
            '${word[0].toUpperCase()}${word.substring(1).toLowerCase()}',
      )
      .join(' ');
}

String _impactLabel(
  double effectiveWeight, {
  required bool positive,
}) {
  final magnitude = effectiveWeight.abs();

  String strength;
  if (magnitude >= 0.75) {
    strength = 'Very strong';
  } else if (magnitude >= 0.45) {
    strength = 'Strong';
  } else if (magnitude >= 0.20) {
    strength = 'Moderate';
  } else {
    strength = 'Small';
  }

  return '$strength ${positive ? 'benefit' : 'concern'}';
}

class _ImpactBadge extends StatelessWidget {
  const _ImpactBadge({
    required this.label,
    required this.positive,
  });

  final String label;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final foreground = positive
        ? theme.colorScheme.primary
        : theme.colorScheme.error;
    final background = foreground.withAlpha(31);

    return Container(
      constraints: const BoxConstraints(maxWidth: 96),
      padding: const EdgeInsets.symmetric(
        horizontal: 9,
        vertical: 6,
      ),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        textAlign: TextAlign.center,
        style: theme.textTheme.labelSmall?.copyWith(
          color: foreground,
          fontWeight: FontWeight.w800,
          height: 1.15,
        ),
      ),
    );
  }
}

