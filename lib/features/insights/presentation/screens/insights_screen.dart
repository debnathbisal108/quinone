import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../history/providers/analysis_history_provider.dart';
import '../../models/nutrition_insights.dart';

class InsightsScreen extends ConsumerStatefulWidget {
  const InsightsScreen({super.key});

  @override
  ConsumerState<InsightsScreen> createState() => _InsightsScreenState();
}

class _InsightsScreenState extends ConsumerState<InsightsScreen> {
  int _days = 7;

  @override
  Widget build(BuildContext context) {
    final records = ref.watch(analysisHistoryProvider);
    final insights = NutritionInsights.fromRecords(
      records,
      Duration(days: _days),
    );
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Insights')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 110),
        children: [
          SegmentedButton<int>(
            segments: const [
              ButtonSegment(value: 7, label: Text('7 days')),
              ButtonSegment(value: 30, label: Text('30 days')),
            ],
            selected: {_days},
            onSelectionChanged: (selection) {
              setState(() => _days = selection.first);
            },
          ),
          const SizedBox(height: 18),
          if (insights.isEmpty)
            _EmptyInsights(theme: theme)
          else ...[
            Row(
              children: [
                Expanded(
                  child: _StatCard(
                    label: 'Meals logged',
                    value: '${insights.mealCount}',
                    icon: Icons.restaurant_menu_rounded,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _StatCard(
                    label: 'Days tracked',
                    value: '${insights.daysWithMeals}',
                    icon: Icons.calendar_month_rounded,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            const _SectionTitle('Average daily macros'),
            const SizedBox(height: 10),
            _MacroSummary(insights: insights),
            if (insights.targetAchievement.isNotEmpty) ...[
              const SizedBox(height: 24),
              const _SectionTitle('Personal target achievement'),
              const SizedBox(height: 10),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: insights.targetAchievement.entries
                        .where((e) => const {
                              'protein_g',
                              'carbohydrate_g',
                              'fat_g',
                              'fiber_g',
                            }.contains(e.key))
                        .map((entry) => _ProgressRow(
                              label: _friendlyName(entry.key),
                              percent: entry.value,
                            ))
                        .toList(growable: false),
                  ),
                ),
              ),
            ],
            if (insights.averageHealthScores.isNotEmpty) ...[
              const SizedBox(height: 24),
              const _SectionTitle('Average health scores'),
              const SizedBox(height: 10),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: (insights.averageHealthScores.entries.toList()
                          ..sort((a, b) => b.value.compareTo(a.value)))
                        .take(6)
                        .map((entry) => _ProgressRow(
                              label: _friendlyName(entry.key),
                              percent: entry.value,
                              isScore: true,
                            ))
                        .toList(growable: false),
                  ),
                ),
              ),
            ],
            if (insights.topFoodNames.isNotEmpty) ...[
              const SizedBox(height: 24),
              const _SectionTitle('Most frequent foods'),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: insights.topFoodNames
                    .map((e) => Chip(label: Text('${e.key} · ${e.value}')))
                    .toList(growable: false),
              ),
            ],
            const SizedBox(height: 12),
            Text(
              'Insights use analyses saved on this device. Daily target percentages use the personal target snapshot stored with each meal.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                height: 1.4,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _MacroSummary extends StatelessWidget {
  const _MacroSummary({required this.insights});
  final NutritionInsights insights;

  @override
  Widget build(BuildContext context) {
    final values = [
      ('Protein', _macro(insights, ['protein_g', 'protein'])),
      ('Carbohydrates', _macro(insights,
          ['carbohydrate_g', 'carbohydrates_g', 'carbs_g', 'carbs'])),
      ('Fat', _macro(insights, ['fat_g', 'total_fat_g', 'fat'])),
      ('Fiber', _macro(insights, ['fiber_g', 'fibre_g', 'dietary_fiber_g'])),
    ];
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 10,
      crossAxisSpacing: 10,
      childAspectRatio: 1.7,
      children: values
          .map((e) => Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(e.$1),
                      const SizedBox(height: 4),
                      Text(
                        '${e.$2.toStringAsFixed(1)} g',
                        style: Theme.of(context)
                            .textTheme
                            .titleLarge
                            ?.copyWith(fontWeight: FontWeight.w800),
                      ),
                    ],
                  ),
                ),
              ))
          .toList(growable: false),
    );
  }
}

class _ProgressRow extends StatelessWidget {
  const _ProgressRow({
    required this.label,
    required this.percent,
    this.isScore = false,
  });
  final String label;
  final double percent;
  final bool isScore;

  @override
  Widget build(BuildContext context) {
    final normalized = (percent / 100).clamp(0.0, 1.0);
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(label)),
              Text('${percent.round()}%'),
            ],
          ),
          const SizedBox(height: 6),
          LinearProgressIndicator(value: normalized),
          if (!isScore && percent > 130) ...[
            const SizedBox(height: 4),
            Text(
              'Above the saved daily target',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({required this.label, required this.value, required this.icon});
  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon),
              const SizedBox(height: 14),
              Text(value,
                  style: Theme.of(context)
                      .textTheme
                      .headlineSmall
                      ?.copyWith(fontWeight: FontWeight.w900)),
              Text(label),
            ],
          ),
        ),
      );
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Text(
        text,
        style: Theme.of(context)
            .textTheme
            .titleLarge
            ?.copyWith(fontWeight: FontWeight.w800),
      );
}

class _EmptyInsights extends StatelessWidget {
  const _EmptyInsights({required this.theme});
  final ThemeData theme;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 70),
        child: Column(
          children: [
            Icon(Icons.insights_rounded,
                size: 64, color: theme.colorScheme.primary),
            const SizedBox(height: 18),
            Text('Not enough data yet',
                style: theme.textTheme.titleLarge
                    ?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            Text(
              'Complete meal analyses to build your personal nutrition trends.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyLarge
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ],
        ),
      );
}

double _macro(NutritionInsights insights, List<String> keys) {
  for (final key in keys) {
    final value = insights.averageDailyMacros[key];
    if (value != null) return value;
  }
  return 0;
}

String _friendlyName(String key) => key
    .replaceAll(RegExp(r'_(g|mg|ug|mcg)$'), '')
    .replaceAll('_', ' ')
    .split(' ')
    .where((e) => e.isNotEmpty)
    .map((e) => '${e[0].toUpperCase()}${e.substring(1)}')
    .join(' ');
