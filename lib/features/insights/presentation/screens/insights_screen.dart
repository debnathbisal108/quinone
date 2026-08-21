import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../history/models/analysis_history_record.dart';
import '../../../history/providers/analysis_history_provider.dart';
import '../../../profile/providers/profile_provider.dart';
import '../../../recommendation/models/post_analysis_recommendations.dart';
import '../../../recommendation/services/recommendation_service.dart';
import '../../models/nutrition_insights.dart';

class InsightsScreen extends ConsumerStatefulWidget {
  const InsightsScreen({super.key});

  @override
  ConsumerState<InsightsScreen> createState() => _InsightsScreenState();
}

class _InsightsScreenState extends ConsumerState<InsightsScreen> {
  int _days = 7;
  InsightCategory _category = InsightCategory.health;
  String _metricKey = 'overall';
  DailyNutritionInsight? _selectedDay;
  final RecommendationService _recommendationService = RecommendationService();
  PostAnalysisRecommendations? _recommendations;
  bool _recommendationsLoading = false;
  String? _recommendationsError;
  String? _recommendationsForAnalysisId;

  Future<void> _loadRecommendations(List<AnalysisHistoryRecord> records) async {
    if (records.isEmpty || _recommendationsLoading) return;
    final sorted = [...records]..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    final latest = sorted.first;
    if (_recommendationsForAnalysisId == latest.analysisId &&
        _recommendations != null) {
      return;
    }
    if (mounted) {
      setState(() {
        _recommendationsLoading = true;
        _recommendationsError = null;
      });
    }
    try {
      if (ref.read(profileProvider).isLoading) {
        await ref.read(profileProvider.notifier).loadProfile();
      }
      final sameDay = sorted
          .where((record) => _sameInsightDay(record.createdAt, latest.createdAt))
          .where((record) => record.analysisId != latest.analysisId)
          .map((record) => Map<String, dynamic>.from(record.rawResult))
          .toList(growable: false);
      final preferredDomains = _category == InsightCategory.health &&
              _metricKey.isNotEmpty &&
              _metricKey != 'overall'
          ? <String>[_metricKey]
          : const <String>[];
      final preferredNutrients = _category != InsightCategory.health &&
              _metricKey.isNotEmpty &&
              _metricKey != 'overall'
          ? <String>[_metricKey]
          : const <String>[];
      final value = await _recommendationService.afterAnalysis(
        currentResult: Map<String, dynamic>.from(latest.rawResult),
        todayResults: sameDay,
        profile: ref.read(profileProvider).backendPayload,
        localHour: latest.createdAt.toLocal().hour,
        maximumResults: 8,
        preferredDomainKeys: preferredDomains,
        preferredNutrientKeys: preferredNutrients,
      );
      if (!mounted) return;
      setState(() {
        _recommendations = value;
        _recommendationsForAnalysisId = latest.analysisId;
        _recommendationsLoading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _recommendationsLoading = false;
        _recommendationsError = error.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final records = ref.watch(analysisHistoryProvider);
    final insights = NutritionInsights.fromRecords(
      records,
      Duration(days: _days),
    );
    final theme = Theme.of(context);
    final availableMetrics = _metricsFor(insights, _category);
    if (!availableMetrics.any((item) => item.$1 == _metricKey)) {
      _metricKey = availableMetrics.isEmpty ? '' : availableMetrics.first.$1;
      _selectedDay = null;
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Insights')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 110),
        children: [
          SegmentedButton<int>(
            segments: const [
              ButtonSegment(value: 7, label: Text('7 days')),
              ButtonSegment(value: 30, label: Text('30 days')),
              ButtonSegment(value: 90, label: Text('90 days')),
            ],
            selected: {_days},
            onSelectionChanged: (selection) {
              setState(() {
                _days = selection.first;
                _selectedDay = null;
              });
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
            const SizedBox(height: 26),
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Trend explorer',
                    style: theme.textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                Icon(
                  Icons.auto_graph_rounded,
                  color: theme.colorScheme.primary,
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'Switch between health domains, macronutrients, and micronutrients. Tap any point to inspect that day.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 14),
            _MetricSelectors(
              category: _category,
              metricKey: _metricKey,
              metrics: availableMetrics,
              onCategoryChanged: (category) {
                setState(() {
                  _category = category;
                  final next = _metricsFor(insights, category);
                  _metricKey = next.isEmpty ? '' : next.first.$1;
                  _selectedDay = null;
                });
              },
              onMetricChanged: (key) {
                setState(() {
                  _metricKey = key;
                  _selectedDay = null;
                });
              },
            ),
            const SizedBox(height: 12),
            if (_metricKey.isNotEmpty)
              _MetricChart(
                days: insights.dailyInsights,
                category: _category,
                metricKey: _metricKey,
                selectedDate: _selectedDay?.date,
                onDaySelected: (day) {
                  setState(() => _selectedDay = day);
                },
              ),
            if (_selectedDay != null && _metricKey.isNotEmpty) ...[
              const SizedBox(height: 12),
              _SelectedDayCard(
                day: _selectedDay!,
                category: _category,
                metricKey: _metricKey,
              ),
            ],
            const SizedBox(height: 28),
            if (_category == InsightCategory.health)
              _HealthDomainOverview(
                insights: insights,
                onTap: (key) {
                  setState(() {
                    _metricKey = key;
                    _selectedDay = null;
                  });
                  _showHealthDomainDailyBreakdown(
                    context,
                    insights: insights,
                    domainKey: key,
                  );
                },
              )
            else
              _NutritionBalanceSection(
                insights: insights,
                category: _category,
                onTap: (key) {
                  setState(() {
                    _metricKey = key;
                    _selectedDay = null;
                  });
                  _showNutrientDailyBreakdown(
                    context,
                    insights: insights,
                    category: _category,
                    nutrientKey: key,
                  );
                },
              ),
            const SizedBox(height: 28),
            _WhatChangedSection(
              insights: insights,
              category: _category,
            ),
            const SizedBox(height: 28),
            _InsightRecommendationSection(
              loading: _recommendationsLoading,
              error: _recommendationsError,
              recommendations: _recommendations,
              category: _category,
              metricKey: _metricKey,
              onRequest: records.isEmpty
                  ? null
                  : () => _loadRecommendations(records),
              onAdd: (item) {
                context.push('/recipe', extra: {
                  'recommendation_query': item.searchQuery,
                  'recommendation_name': item.foodName,
                  'recommendation_quantity': item.quantity,
                });
              },
            ),
            if (insights.topFoodNames.isNotEmpty) ...[
              const SizedBox(height: 28),
              const _SectionTitle('Most frequent foods'),
              const SizedBox(height: 6),
              Text(
                'Foods that appeared most often during this period.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: insights.topFoodNames
                    .map(
                      (entry) => Chip(
                        avatar: const Icon(
                          Icons.restaurant_rounded,
                          size: 17,
                        ),
                        label: Text('${entry.key} · ${entry.value}'),
                      ),
                    )
                    .toList(growable: false),
              ),
            ],
          ],
        ],
      ),
    );
  }
}


bool _sameInsightDay(DateTime a, DateTime b) {
  final x = a.toLocal();
  final y = b.toLocal();
  return x.year == y.year && x.month == y.month && x.day == y.day;
}

class _InsightRecommendationSection extends StatelessWidget {
  const _InsightRecommendationSection({
    required this.loading,
    required this.error,
    required this.recommendations,
    required this.category,
    required this.metricKey,
    required this.onRequest,
    required this.onAdd,
  });

  final bool loading;
  final String? error;
  final PostAnalysisRecommendations? recommendations;
  final InsightCategory category;
  final String metricKey;
  final VoidCallback? onRequest;
  final ValueChanged<FoodRecommendation> onAdd;

  bool _matches(FoodRecommendation item) {
    if (metricKey.isEmpty || metricKey == 'overall') return true;
    if (category == InsightCategory.health) {
      return item.targetDomain?.key == metricKey;
    }
    return item.nutrientEffects.any((effect) => effect.nutrient == metricKey);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final all = recommendations?.items ?? const <FoodRecommendation>[];
    final relevant = all.where(_matches).toList(growable: false);
    final source = relevant.isNotEmpty ? relevant : all;
    final add = source.where((item) => item.action == 'add').take(4).toList();
    final reduce = source.where((item) => item.action == 'adjust_portion').take(4).toList();

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('What to change', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
          const SizedBox(height: 5),
          Text(
            'Food changes are calculated only when you ask. Switching metrics reuses the same result.',
            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
          if (loading) ...[
            const SizedBox(height: 14),
            const LinearProgressIndicator(),
          ] else if (recommendations == null && error == null) ...[
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: onRequest,
              icon: const Icon(Icons.restaurant_menu_rounded),
              label: const Text('Find food recommendations'),
            ),
          ] else if (error != null) ...[
            const SizedBox(height: 12),
            Text(error!, style: TextStyle(color: theme.colorScheme.error)),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: onRequest,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Try again'),
            ),
          ] else ...[
            const SizedBox(height: 16),
            Text('To add', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900)),
            const SizedBox(height: 8),
            if (add.isEmpty)
              Text('No verified addition is currently available for this selection.', style: theme.textTheme.bodyMedium)
            else
              ...add.map((item) => ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const CircleAvatar(child: Icon(Icons.add_rounded)),
                    title: Text(item.foodName, style: const TextStyle(fontWeight: FontWeight.w800)),
                    subtitle: Text('${item.quantity.toStringAsFixed(item.quantity == item.quantity.roundToDouble() ? 0 : 1)} ${item.unit} · ${item.reason}'),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    onTap: () => onAdd(item),
                  )),
            const SizedBox(height: 12),
            Text('To reduce', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900)),
            const SizedBox(height: 8),
            if (reduce.isEmpty)
              Text('No food needs a verified reduction for this selection.', style: theme.textTheme.bodyMedium)
            else
              ...reduce.map((item) => ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const CircleAvatar(child: Icon(Icons.remove_rounded)),
                    title: Text(item.foodName, style: const TextStyle(fontWeight: FontWeight.w800)),
                    subtitle: Text(item.reason),
                  )),
          ],
        ],
      ),
    );
  }
}

void _showHealthDomainDailyBreakdown(
  BuildContext context, {
  required NutritionInsights insights,
  required String domainKey,
}) {
  final days = insights.dailyInsights
      .where((day) => day.healthScores[domainKey] != null)
      .toList(growable: false)
    ..sort((a, b) => b.date.compareTo(a.date));
  if (days.isEmpty) return;

  final average = days.fold<double>(
        0,
        (sum, day) => sum + day.healthScores[domainKey]!,
      ) /
      days.length;

  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    useSafeArea: true,
    isScrollControlled: true,
    builder: (sheetContext) {
      final theme = Theme.of(sheetContext);

      return DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.78,
        minChildSize: 0.48,
        maxChildSize: 0.94,
        builder: (context, controller) => ListView(
          controller: controller,
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 30),
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        friendlyMetricName(domainKey),
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${days.length} ${days.length == 1 ? 'tracked day' : 'tracked days'} in this period',
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: _healthColor(average).withOpacity(0.12),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    '${average.round()}/100 avg',
                    style: TextStyle(
                      color: _healthColor(average),
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              'Each daily score combines that day’s meal scores, weighted by meal energy. Meal rows show what raised or lowered the daily result.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 18),
            ...days.map(
              (day) {
                final dailyScore = day.healthScores[domainKey]!;
                final meals = day.mealImpacts
                    .where((meal) => meal.healthScores[domainKey] != null)
                    .toList(growable: false)
                  ..sort(
                    (a, b) => b.healthScores[domainKey]!
                        .compareTo(a.healthScores[domainKey]!),
                  );

                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: theme.colorScheme.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(
                        color: theme.colorScheme.outlineVariant,
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                _fullDate(day.date),
                                style: theme.textTheme.titleSmall?.copyWith(
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ),
                            Text(
                              '${dailyScore.round()}/100',
                              style: theme.textTheme.titleMedium?.copyWith(
                                color: _healthColor(dailyScore),
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 3),
                        Text(
                          '${day.mealCount} ${day.mealCount == 1 ? 'meal' : 'meals'} · ${day.calories.round()} kcal · ${healthStatusLabel(dailyScore)}',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                        _FoodContributorExtremes(
                          contributors: day.contributorsFor(
                            InsightCategory.health,
                            domainKey,
                          ),
                          percentageLabel: 'share of score influence',
                        ),
                        if (meals.isNotEmpty) ...[
                          const SizedBox(height: 10),
                          Divider(color: theme.colorScheme.outlineVariant),
                          ...meals.map(
                            (meal) => _MealImpactRow(
                              mealName: meal.mealName,
                              score: meal.healthScores[domainKey]!,
                              dailyScore: dailyScore,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                );
              },
            ),
          ],
        ),
      );
    },
  );
}

void _showNutrientDailyBreakdown(
  BuildContext context, {
  required NutritionInsights insights,
  required InsightCategory category,
  required String nutrientKey,
}) {
  final days = insights.dailyInsights
      .where((day) {
        final value = day.metricValue(category, nutrientKey);
        final target = insights.targetForDay(day, nutrientKey);
        return value != null &&
            target != null &&
            target.classify(value) != BalanceState.unknown;
      })
      .toList(growable: false)
    ..sort((a, b) => b.date.compareTo(a.date));
  if (days.isEmpty) return;

  final average = days.fold<double>(
        0,
        (sum, day) => sum + day.metricValue(category, nutrientKey)!,
      ) /
      days.length;
  final unit = insights.targetForDay(days.first, nutrientKey)?.unit ??
      unitForMetric(nutrientKey);

  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    useSafeArea: true,
    isScrollControlled: true,
    builder: (sheetContext) {
      final theme = Theme.of(sheetContext);

      return DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.72,
        minChildSize: 0.42,
        maxChildSize: 0.94,
        builder: (context, controller) => ListView(
          controller: controller,
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 30),
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        friendlyMetricName(nutrientKey),
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${days.length} ${days.length == 1 ? 'tracked day' : 'tracked days'} in this period',
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.primaryContainer,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    '${_compactNumber(average)}${unit.isEmpty ? '' : ' $unit'} avg',
                    style: TextStyle(
                      color: theme.colorScheme.onPrimaryContainer,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              'Daily amounts are compared with the target or reference used for that day.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 18),
            ...days.map((day) {
              final value = day.metricValue(category, nutrientKey)!;
              final target = insights.targetForDay(day, nutrientKey)!;
              final state = target.classify(value);
              final (status, color) = switch (state) {
                BalanceState.low => ('Below target', Colors.orange),
                BalanceState.balanced => ('In target range', Colors.green),
                BalanceState.high =>
                  ('Above target', theme.colorScheme.error),
                BalanceState.unknown =>
                  ('Target unavailable', theme.colorScheme.onSurfaceVariant),
              };

              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.surfaceContainerLow,
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(
                      color: theme.colorScheme.outlineVariant,
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              _fullDate(day.date),
                              style: theme.textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          Text(
                            _metricDisplayValue(
                              category,
                              nutrientKey,
                              value,
                            ),
                            style: theme.textTheme.titleMedium?.copyWith(
                              color: color,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 5),
                      Text(
                        '$status · ${_targetDescription(target)}',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: color,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        '${day.mealCount} ${day.mealCount == 1 ? 'meal' : 'meals'} · ${day.calories.round()} kcal logged',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                      _FoodContributorExtremes(
                        contributors: day.contributorsFor(
                          category,
                          nutrientKey,
                        ),
                        percentageLabel: 'of this day’s ${friendlyMetricName(nutrientKey).toLowerCase()}',
                      ),
                    ],
                  ),
                ),
              );
            }),
          ],
        ),
      );
    },
  );
}

class _FoodContributorExtremes extends StatelessWidget {
  const _FoodContributorExtremes({
    required this.contributors,
    required this.percentageLabel,
  });

  final List<FoodMetricContribution> contributors;
  final String percentageLabel;

  @override
  Widget build(BuildContext context) {
    if (contributors.isEmpty) return const SizedBox.shrink();

    final theme = Theme.of(context);
    final highest = contributors.first;
    final lowest = contributors.last;
    final single = contributors.length == 1;

    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHighest.withOpacity(0.42),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              single ? 'Food contributor' : 'Food contributors',
              style: theme.textTheme.labelLarge?.copyWith(
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 8),
            _FoodContributorRow(
              label: single ? 'Only' : 'Highest',
              contribution: highest,
              percentageLabel: percentageLabel,
            ),
            if (!single) ...[
              const SizedBox(height: 7),
              _FoodContributorRow(
                label: 'Lowest',
                contribution: lowest,
                percentageLabel: percentageLabel,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _FoodContributorRow extends StatelessWidget {
  const _FoodContributorRow({
    required this.label,
    required this.contribution,
    required this.percentageLabel,
  });

  final String label;
  final FoodMetricContribution contribution;
  final String percentageLabel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final percentage = _insightContributionPercent(
      contribution.percentage,
    );

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
          decoration: BoxDecoration(
            color: theme.colorScheme.primary.withOpacity(0.10),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Text(
            label,
            style: theme.textTheme.labelSmall?.copyWith(
              color: theme.colorScheme.primary,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text.rich(
            TextSpan(
              children: [
                TextSpan(
                  text: contribution.foodName,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                TextSpan(
                  text: ' · $percentage $percentageLabel',
                  style: TextStyle(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
            style: theme.textTheme.bodySmall,
          ),
        ),
      ],
    );
  }
}

class _MetricSelectors extends StatelessWidget {
  const _MetricSelectors({
    required this.category,
    required this.metricKey,
    required this.metrics,
    required this.onCategoryChanged,
    required this.onMetricChanged,
  });

  final InsightCategory category;
  final String metricKey;
  final List<(String, String)> metrics;
  final ValueChanged<InsightCategory> onCategoryChanged;
  final ValueChanged<String> onMetricChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: DropdownButtonFormField<InsightCategory>(
            value: category,
            decoration: const InputDecoration(
              labelText: 'Category',
              border: OutlineInputBorder(),
              isDense: true,
            ),
            items: const [
              DropdownMenuItem(
                value: InsightCategory.health,
                child: Text('Health'),
              ),
              DropdownMenuItem(
                value: InsightCategory.macros,
                child: Text('Macros'),
              ),
              DropdownMenuItem(
                value: InsightCategory.micronutrients,
                child: Text('Micronutrients'),
              ),
            ],
            onChanged: (value) {
              if (value != null) onCategoryChanged(value);
            },
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: DropdownButtonFormField<String>(
            value: metrics.any((item) => item.$1 == metricKey)
                ? metricKey
                : null,
            decoration: const InputDecoration(
              labelText: 'Metric',
              border: OutlineInputBorder(),
              isDense: true,
            ),
            items: [
              for (final item in metrics)
                DropdownMenuItem(
                  value: item.$1,
                  child: Text(
                    item.$2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
            ],
            onChanged: (value) {
              if (value != null) onMetricChanged(value);
            },
          ),
        ),
      ],
    );
  }
}

class _MetricChart extends StatelessWidget {
  const _MetricChart({
    required this.days,
    required this.category,
    required this.metricKey,
    required this.selectedDate,
    required this.onDaySelected,
  });

  final List<DailyNutritionInsight> days;
  final InsightCategory category;
  final String metricKey;
  final DateTime? selectedDate;
  final ValueChanged<DailyNutritionInsight> onDaySelected;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final available = days
        .where((day) => day.metricValue(category, metricKey) != null)
        .toList(growable: false);

    if (available.isEmpty) {
      return _MessageCard(
        icon: Icons.query_stats_rounded,
        text: 'There is not enough data for this metric yet.',
      );
    }

    final last = available.last;
    final latestValue = last.metricValue(category, metricKey)!;
    final target = category == InsightCategory.health
        ? null
        : last.targetFor(metricKey);

    return Container(
      padding: const EdgeInsets.fromLTRB(14, 16, 14, 12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  friendlyMetricName(metricKey),
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              Text(
                _metricDisplayValue(
                  category,
                  metricKey,
                  latestValue,
                ),
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                  color: theme.colorScheme.primary,
                ),
              ),
            ],
          ),
          if (target != null) ...[
            const SizedBox(height: 4),
            Text(
              _targetDescription(target),
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          const SizedBox(height: 12),
          SizedBox(
            height: 225,
            child: LayoutBuilder(
              builder: (context, constraints) => GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTapDown: (details) {
                  const left = 42.0;
                  const right = 12.0;
                  final usable = math
                      .max(
                        1.0,
                        constraints.maxWidth - left - right,
                      )
                      .toDouble();
                  final normalized =
                      ((details.localPosition.dx - left) / usable)
                          .clamp(0.0, 1.0);
                  final index = available.length == 1
                      ? 0
                      : (normalized * (available.length - 1)).round();
                  onDaySelected(available[index]);
                },
                child: CustomPaint(
                  painter: _MetricChartPainter(
                    days: available,
                    category: category,
                    metricKey: metricKey,
                    selectedDate: selectedDate,
                    lineColor: theme.colorScheme.primary,
                    gridColor: theme.colorScheme.outlineVariant,
                    textColor: theme.colorScheme.onSurfaceVariant,
                    targetColor: theme.colorScheme.tertiary,
                    goodColor: Colors.green,
                    warningColor: Colors.orange,
                    dangerColor: theme.colorScheme.error,
                  ),
                  child: const SizedBox.expand(),
                ),
              ),
            ),
          ),
          const SizedBox(height: 2),
          Row(
            children: [
              Icon(
                Icons.touch_app_outlined,
                size: 16,
                color: theme.colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 6),
              Text(
                'Tap a point for that day',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MetricChartPainter extends CustomPainter {
  const _MetricChartPainter({
    required this.days,
    required this.category,
    required this.metricKey,
    required this.selectedDate,
    required this.lineColor,
    required this.gridColor,
    required this.textColor,
    required this.targetColor,
    required this.goodColor,
    required this.warningColor,
    required this.dangerColor,
  });

  final List<DailyNutritionInsight> days;
  final InsightCategory category;
  final String metricKey;
  final DateTime? selectedDate;
  final Color lineColor;
  final Color gridColor;
  final Color textColor;
  final Color targetColor;
  final Color goodColor;
  final Color warningColor;
  final Color dangerColor;

  @override
  void paint(Canvas canvas, Size size) {
    if (days.isEmpty) {
      return;
    }

    const left = 42.0;
    const right = 12.0;
    const top = 10.0;
    const bottom = 34.0;
    final width = math.max(1.0, size.width - left - right).toDouble();
    final height = math.max(1.0, size.height - top - bottom).toDouble();

    final values = <double>[
      for (final day in days)
        day.metricValue(category, metricKey) ?? 0,
    ];

    double minValue;
    double maxValue;

    if (category == InsightCategory.health) {
      minValue = 0;
      maxValue = 100;

      _paintHealthBand(
        canvas,
        Rect.fromLTWH(
          left,
          top,
          width,
          height * 0.15,
        ),
        goodColor.withOpacity(0.08),
      );
      _paintHealthBand(
        canvas,
        Rect.fromLTWH(
          left,
          top + height * 0.15,
          width,
          height * 0.15,
        ),
        goodColor.withOpacity(0.04),
      );
      _paintHealthBand(
        canvas,
        Rect.fromLTWH(
          left,
          top + height * 0.30,
          width,
          height * 0.15,
        ),
        warningColor.withOpacity(0.05),
      );
      _paintHealthBand(
        canvas,
        Rect.fromLTWH(
          left,
          top + height * 0.45,
          width,
          height * 0.55,
        ),
        dangerColor.withOpacity(0.045),
      );
    } else {
      minValue = 0;
      final valueMax = values.fold<double>(
        0,
        (a, b) => math.max(a, b).toDouble(),
      );
      final targetHighs = days
          .map((day) => day.targetFor(metricKey)?.high)
          .whereType<double>()
          .toList();
      final targetMax = targetHighs.isEmpty
          ? 0.0
          : targetHighs.fold<double>(
              0,
              (a, b) => math.max(a, b).toDouble(),
            );
      maxValue = math
          .max(
            1.0,
            math.max(valueMax, targetMax).toDouble() * 1.18,
          )
          .toDouble();
    }

    final gridPaint = Paint()
      ..color = gridColor.withOpacity(0.55)
      ..strokeWidth = 1;

    for (var i = 0; i <= 4; i++) {
      final y = top + height * i / 4;
      canvas.drawLine(Offset(left, y), Offset(left + width, y), gridPaint);
      final labelValue = maxValue - (maxValue - minValue) * i / 4;
      _paintText(
        canvas,
        _axisLabel(labelValue),
        Offset(0, y - 7),
        textColor,
        10,
      );
    }

    if (category != InsightCategory.health) {
      final target = days.last.targetFor(metricKey);
      if (target != null) {
        final low = target.low;
        final high = target.high;
        if (low != null && high != null && high > low) {
          final yHigh = _yFor(high, minValue, maxValue, top, height);
          final yLow = _yFor(low, minValue, maxValue, top, height);
          canvas.drawRect(
            Rect.fromLTRB(left, yHigh, left + width, yLow),
            Paint()..color = targetColor.withOpacity(0.10),
          );
        } else {
          final reference = target.high ?? target.reference;
          if (reference != null) {
            final y = _yFor(reference, minValue, maxValue, top, height);
            canvas.drawLine(
              Offset(left, y),
              Offset(left + width, y),
              Paint()
                ..color = targetColor.withOpacity(0.65)
                ..strokeWidth = 1.4,
            );
          }
        }
      }
    }

    final points = <Offset>[];
    for (var index = 0; index < values.length; index++) {
      final x = days.length == 1
          ? left + width / 2
          : left + width * index / (days.length - 1);
      final y = _yFor(
        values[index],
        minValue,
        maxValue,
        top,
        height,
      );
      points.add(Offset(x, y));
    }

    if (points.length > 1) {
      final path = Path()..moveTo(points.first.dx, points.first.dy);
      for (final point in points.skip(1)) {
        path.lineTo(point.dx, point.dy);
      }
      canvas.drawPath(
        path,
        Paint()
          ..color = lineColor
          ..strokeWidth = 3
          ..style = PaintingStyle.stroke
          ..strokeCap = StrokeCap.round
          ..strokeJoin = StrokeJoin.round,
      );
    }

    for (var index = 0; index < points.length; index++) {
      final selected = selectedDate != null &&
          _sameDay(days[index].date, selectedDate!);
      canvas.drawCircle(
        points[index],
        selected ? 7 : 5,
        Paint()..color = selected ? targetColor : lineColor,
      );
      canvas.drawCircle(
        points[index],
        selected ? 3 : 2,
        Paint()..color = Colors.white,
      );

      final showLabel = days.length <= 7 ||
          index == 0 ||
          index == days.length - 1 ||
          index % math.max(1, (days.length / 5).round()).toInt() == 0;
      if (showLabel) {
        final date = days[index].date;
        _paintText(
          canvas,
          '${date.day}/${date.month}',
          Offset(points[index].dx - 13, size.height - 22),
          textColor,
          10,
        );
      }
    }
  }

  double _yFor(
    double value,
    double min,
    double max,
    double top,
    double height,
  ) {
    if ((max - min).abs() < 0.000001) return top + height / 2;
    final normalized = ((value - min) / (max - min)).clamp(0.0, 1.0);
    return top + height * (1 - normalized);
  }

  void _paintHealthBand(Canvas canvas, Rect rect, Color color) {
    canvas.drawRect(rect, Paint()..color = color);
  }

  void _paintText(
    Canvas canvas,
    String text,
    Offset offset,
    Color color,
    double fontSize,
  ) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(color: color, fontSize: fontSize),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(canvas, offset);
  }

  String _axisLabel(double value) {
    if (category == InsightCategory.health) {
      return value.round().toString();
    }
    if (value >= 1000) return '${(value / 1000).toStringAsFixed(1)}k';
    if (value >= 100) return value.round().toString();
    if (value >= 10) return value.toStringAsFixed(0);
    return value.toStringAsFixed(1);
  }

  @override
  bool shouldRepaint(covariant _MetricChartPainter oldDelegate) {
    return oldDelegate.days != days ||
        oldDelegate.category != category ||
        oldDelegate.metricKey != metricKey ||
        oldDelegate.selectedDate != selectedDate ||
        oldDelegate.lineColor != lineColor;
  }
}

class _SelectedDayCard extends StatelessWidget {
  const _SelectedDayCard({
    required this.day,
    required this.category,
    required this.metricKey,
  });

  final DailyNutritionInsight day;
  final InsightCategory category;
  final String metricKey;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final value = day.metricValue(category, metricKey);
    final target = category == InsightCategory.health
        ? null
        : day.targetFor(metricKey);
    if (value == null) {
      return const SizedBox.shrink();
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer.withOpacity(0.32),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: theme.colorScheme.primary.withOpacity(0.22),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _fullDate(day.date),
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            '${day.mealCount} ${day.mealCount == 1 ? 'meal' : 'meals'} · ${day.calories.round()} kcal',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: Text(
                  friendlyMetricName(metricKey),
                  style: theme.textTheme.bodyLarge,
                ),
              ),
              Text(
                _metricDisplayValue(category, metricKey, value),
                style: theme.textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          if (category == InsightCategory.health) ...[
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerRight,
              child: Text(
                healthStatusLabel(value),
                style: theme.textTheme.labelLarge?.copyWith(
                  color: _healthColor(value),
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            if (metricKey != 'overall') ...[
              const SizedBox(height: 14),
              ...day.mealImpacts
                  .where((meal) => meal.healthScores[metricKey] != null)
                  .map(
                    (meal) => _MealImpactRow(
                      mealName: meal.mealName,
                      score: meal.healthScores[metricKey]!,
                      dailyScore: value,
                    ),
                  ),
            ],
          ] else if (target != null) ...[
            const SizedBox(height: 8),
            _TargetStatus(
              value: value,
              target: target,
            ),
          ],
        ],
      ),
    );
  }
}

class _MealImpactRow extends StatelessWidget {
  const _MealImpactRow({
    required this.mealName,
    required this.score,
    required this.dailyScore,
  });

  final String mealName;
  final double score;
  final double dailyScore;

  @override
  Widget build(BuildContext context) {
    final difference = score - dailyScore;
    final icon = difference.abs() < 2
        ? Icons.remove_rounded
        : difference > 0
            ? Icons.arrow_upward_rounded
            : Icons.arrow_downward_rounded;
    final color = difference.abs() < 2
        ? Theme.of(context).colorScheme.onSurfaceVariant
        : difference > 0
            ? Colors.green
            : Theme.of(context).colorScheme.error;

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              mealName,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 5),
          Text(
            score.round().toString(),
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _TargetStatus extends StatelessWidget {
  const _TargetStatus({
    required this.value,
    required this.target,
  });

  final double value;
  final NutrientTargetBand target;

  @override
  Widget build(BuildContext context) {
    final state = target.classify(value);
    final theme = Theme.of(context);
    final (label, color) = switch (state) {
      BalanceState.low => ('Below target', Colors.orange),
      BalanceState.balanced => ('In target range', Colors.green),
      BalanceState.high => ('Above target', theme.colorScheme.error),
      BalanceState.unknown => (
          'Target unavailable',
          theme.colorScheme.onSurfaceVariant,
        ),
    };

    return Row(
      children: [
        Icon(Icons.circle, size: 10, color: color),
        const SizedBox(width: 7),
        Expanded(
          child: Text(
            '$label · ${_targetDescription(target)}',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      ],
    );
  }
}

class _HealthDomainOverview extends StatelessWidget {
  const _HealthDomainOverview({
    required this.insights,
    required this.onTap,
  });

  final NutritionInsights insights;
  final ValueChanged<String> onTap;

  @override
  Widget build(BuildContext context) {
    final trends = insights.healthDomainTrends();
    if (trends.isEmpty) {
      return const _MessageCard(
        icon: Icons.favorite_border_rounded,
        text: 'Health-domain scores will appear after scored meals are logged.',
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _SectionTitle('Health domains'),
        const SizedBox(height: 6),
        Text(
          'A dietary score, not a diagnosis. Lower-scoring domains are shown first so changes are easier to monitor.',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
        const SizedBox(height: 12),
        ...trends.map(
          (trend) => Padding(
            padding: const EdgeInsets.only(bottom: 9),
            child: _DomainTrendCard(
              trend: trend,
              onTap: () => onTap(trend.key),
            ),
          ),
        ),
      ],
    );
  }
}

class _DomainTrendCard extends StatelessWidget {
  const _DomainTrendCard({
    required this.trend,
    required this.onTap,
  });

  final HealthDomainTrend trend;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final delta = trend.delta;
    final scoreColor = _healthColor(trend.averageScore);

    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: Padding(
          padding: const EdgeInsets.all(15),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: scoreColor.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Text(
                  trend.averageScore.round().toString(),
                  style: TextStyle(
                    color: scoreColor,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      trend.label,
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      healthStatusLabel(trend.averageScore),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scoreColor,
                      ),
                    ),
                  ],
                ),
              ),
              if (delta != null)
                _DeltaBadge(
                  value: delta,
                  suffix: ' pts',
                  positiveIsGood: true,
                ),
              const SizedBox(width: 4),
              const Icon(Icons.chevron_right_rounded),
            ],
          ),
        ),
      ),
    );
  }
}

String _insightContributionPercent(double percentage) {
  if (percentage <= 0) return '';
  if (percentage < 1) return '<1%';
  return percentage >= 10
      ? '${percentage.toStringAsFixed(0)}%'
      : '${percentage.toStringAsFixed(1)}%';
}

class _NutritionBalanceSection extends StatelessWidget {
  const _NutritionBalanceSection({
    required this.insights,
    required this.category,
    required this.onTap,
  });

  final NutritionInsights insights;
  final InsightCategory category;
  final ValueChanged<String> onTap;

  @override
  Widget build(BuildContext context) {
    final summaries = insights.balanceSummaries(category);
    final theme = Theme.of(context);

    if (summaries.isEmpty) {
      return const _MessageCard(
        icon: Icons.balance_rounded,
        text: 'No usable daily target/reference data is available for this category yet.',
      );
    }

    final low = summaries
        .where((item) => item.dominantState == BalanceState.low)
        .toList();
    final balanced = summaries
        .where((item) => item.dominantState == BalanceState.balanced)
        .toList();
    final high = summaries
        .where((item) => item.dominantState == BalanceState.high)
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _SectionTitle('Nutrition balance'),
        const SizedBox(height: 6),
        Text(
          'Quinone uses the personalized target when available, otherwise a standard daily reference. Only nutrients with a usable numeric reference are listed here.',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 12),
        if (low.isNotEmpty)
          _BalanceGroup(
            title: 'Needs more',
            color: Colors.orange,
            items: low,
            onTap: onTap,
          ),
        if (balanced.isNotEmpty)
          _BalanceGroup(
            title: 'Well balanced',
            color: Colors.green,
            items: balanced,
            onTap: onTap,
          ),
        if (high.isNotEmpty)
          _BalanceGroup(
            title: 'Frequently above target',
            color: theme.colorScheme.error,
            items: high,
            onTap: onTap,
          ),
      ],
    );
  }
}

class _BalanceGroup extends StatelessWidget {
  const _BalanceGroup({
    required this.title,
    required this.color,
    required this.items,
    required this.onTap,
  });

  final String title;
  final Color color;
  final List<NutrientBalanceSummary> items;
  final ValueChanged<String> onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.06),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: color.withOpacity(0.16)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: theme.textTheme.titleSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 8),
          ...items.map(
            (item) {
              final hasReference =
                  item.dominantState != BalanceState.unknown;
              return InkWell(
                onTap: hasReference ? () => onTap(item.key) : null,
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 7),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          item.label,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                      ),
                      Flexible(
                        child: Text(
                          _balanceFrequency(item),
                          textAlign: TextAlign.end,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ),
                      const SizedBox(width: 4),
                      Icon(
                        hasReference
                            ? Icons.chevron_right_rounded
                            : Icons.info_outline_rounded,
                        size: 18,
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _WhatChangedSection extends StatelessWidget {
  const _WhatChangedSection({
    required this.insights,
    required this.category,
  });

  final NutritionInsights insights;
  final InsightCategory category;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (insights.previousDailyInsights.isEmpty) {
      return const _MessageCard(
        icon: Icons.compare_arrows_rounded,
        text: 'Keep logging meals. Quinone will compare this period with the previous one when enough history is available.',
      );
    }

    if (category == InsightCategory.health) {
      final changes = insights
          .healthDomainTrends()
          .where((item) => item.delta != null)
          .toList()
        ..sort(
          (a, b) => b.delta!.abs().compareTo(a.delta!.abs()),
        );
      if (changes.isEmpty) return const SizedBox.shrink();

      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('What changed'),
          const SizedBox(height: 6),
          Text(
            'Compared with the previous ${insights.daysWithMeals == 1 ? 'tracked period' : 'period'}.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 10),
          ...changes.take(4).map(
            (item) => _ChangeRow(
              label: item.label,
              detail: '${item.averageScore.round()}/100',
              delta: item.delta!,
              suffix: ' pts',
              positiveIsGood: true,
            ),
          ),
        ],
      );
    }

    final changes = insights.metricChanges(category);
    if (changes.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _SectionTitle('What changed'),
        const SizedBox(height: 6),
        Text(
          'Largest changes in average daily intake versus the previous period.',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 10),
        ...changes.take(4).map(
          (item) => _ChangeRow(
            label: item.label,
            detail:
                '${_compactNumber(item.currentAverage)}${item.unit.isEmpty ? '' : ' ${item.unit}'} / day',
            delta: item.percentChange,
            suffix: '%',
            positiveIsGood: null,
          ),
        ),
      ],
    );
  }
}

class _ChangeRow extends StatelessWidget {
  const _ChangeRow({
    required this.label,
    required this.detail,
    required this.delta,
    required this.suffix,
    required this.positiveIsGood,
  });

  final String label;
  final String detail;
  final double delta;
  final String suffix;
  final bool? positiveIsGood;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 2),
                Text(
                  detail,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          _DeltaBadge(
            value: delta,
            suffix: suffix,
            positiveIsGood: positiveIsGood,
          ),
        ],
      ),
    );
  }
}

class _DeltaBadge extends StatelessWidget {
  const _DeltaBadge({
    required this.value,
    required this.suffix,
    required this.positiveIsGood,
  });

  final double value;
  final String suffix;
  final bool? positiveIsGood;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final positive = value >= 0;
    Color color;
    if (positiveIsGood == null) {
      color = theme.colorScheme.primary;
    } else {
      final good = positiveIsGood! ? positive : !positive;
      color = good ? Colors.green : theme.colorScheme.error;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        '${positive ? '+' : ''}${value.toStringAsFixed(value.abs() >= 10 ? 0 : 1)}$suffix',
        style: theme.textTheme.labelMedium?.copyWith(
          color: color,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.label,
    required this.value,
    required this.icon,
  });

  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      elevation: 0,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: theme.colorScheme.primary),
            const SizedBox(height: 14),
            Text(
              value,
              style: theme.textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 3),
            Text(label),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w900,
          ),
    );
  }
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({
    required this.icon,
    required this.text,
  });

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: theme.colorScheme.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyInsights extends StatelessWidget {
  const _EmptyInsights({required this.theme});

  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 70),
      child: Column(
        children: [
          Icon(
            Icons.insights_rounded,
            size: 68,
            color: theme.colorScheme.primary,
          ),
          const SizedBox(height: 18),
          Text(
            'No insights yet',
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Analyze meals to build daily nutrition and health trends.',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyLarge?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

List<(String, String)> _metricsFor(
  NutritionInsights insights,
  InsightCategory category,
) {
  switch (category) {
    case InsightCategory.health:
      return [
        ('overall', 'Overall score'),
        for (final key in insights.healthDomainKeys)
          (key, friendlyMetricName(key)),
      ];
    case InsightCategory.macros:
      return [
        for (final key in insights.macroKeys)
          (key, friendlyMetricName(key)),
      ];
    case InsightCategory.micronutrients:
      return [
        for (final key in insights.micronutrientKeys)
          (key, friendlyMetricName(key)),
      ];
  }
}

String _metricDisplayValue(
  InsightCategory category,
  String key,
  double value,
) {
  if (category == InsightCategory.health) {
    return '${value.round()}/100';
  }
  final unit = unitForMetric(key);
  return '${_compactNumber(value)}${unit.isEmpty ? '' : ' $unit'}';
}

String _compactNumber(double value) {
  if (value.abs() >= 100) return value.toStringAsFixed(0);
  if (value.abs() >= 10) return value.toStringAsFixed(1);
  return value.toStringAsFixed(2);
}

String _targetDescription(NutrientTargetBand target) {
  final unit = target.unit.isEmpty ? '' : ' ${target.unit}';
  if (target.isUpperLimit) {
    final ceiling = target.high ?? target.reference;
    if (ceiling == null) return 'Daily reference';
    return 'Daily upper reference: ${_compactNumber(ceiling)}$unit';
  }
  if (target.low != null && target.high != null) {
    return 'Target range: ${_compactNumber(target.low!)}–${_compactNumber(target.high!)}$unit';
  }
  if (target.reference != null) {
    return 'Daily reference: ${_compactNumber(target.reference!)}$unit';
  }
  return 'Daily target';
}

String _balanceFrequency(NutrientBalanceSummary item) {
  switch (item.dominantState) {
    case BalanceState.low:
      return '${item.lowDays} of ${item.trackedDays} days low';
    case BalanceState.balanced:
      return '${item.balancedDays} of ${item.trackedDays} days in range';
    case BalanceState.high:
      return '${item.highDays} of ${item.trackedDays} days high';
    case BalanceState.unknown:
      return item.trackedDays == 1
          ? 'No daily reference'
          : '${item.trackedDays} days · no daily reference';
  }
}

Color _healthColor(double score) {
  if (score >= 85) return Colors.green;
  if (score >= 70) return Colors.lightGreen.shade700;
  if (score >= 55) return Colors.orange;
  return Colors.red;
}

String _fullDate(DateTime date) {
  const months = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ];
  return '${date.day} ${months[date.month - 1]} ${date.year}';
}

bool _sameDay(DateTime a, DateTime b) =>
    a.year == b.year && a.month == b.month && a.day == b.day;
