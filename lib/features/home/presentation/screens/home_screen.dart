import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../history/models/analysis_history_record.dart';
import '../../../history/providers/analysis_history_provider.dart';
import '../../../insights/models/nutrition_insights.dart';
import '../../../profile/providers/profile_provider.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  bool _namePromptScheduled = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final profileState = ref.watch(profileProvider);
    final records = ref.watch(analysisHistoryProvider);

    if (!profileState.isLoading &&
        (profileState.profile.displayName == null ||
            profileState.profile.displayName!.trim().isEmpty) &&
        !_namePromptScheduled) {
      _namePromptScheduled = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _askForName();
      });
    }
    final today = _todayRecords(records);
    final calories = today.fold<double>(0, (sum, item) => sum + item.calories);
    final todayNutrition = NutritionInsights.fromRecords(
      records,
      const Duration(days: 1),
    );
    final todayInsight = todayNutrition.dailyInsights;
    final daily = todayInsight.isEmpty ? null : todayInsight.last;
    final todayNutrients = daily == null
        ? const <_TodayNutrientItem>[]
        : _todayNutrientItems(todayNutrition, daily);
    final balancedNutrients = todayNutrients
        .where((item) => item.state == BalanceState.balanced)
        .length;
    final highNutrients = todayNutrients
        .where((item) => item.state == BalanceState.high)
        .length;
    final lowNutrients = todayNutrients
        .where((item) => item.state == BalanceState.low)
        .length;
    final health = daily == null || daily.overallHealthScore <= 0
        ? null
        : daily.overallHealthScore;
    final name = profileState.profile.displayName?.trim();

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            pinned: true,
            expandedHeight: 132,
            elevation: 0,
            backgroundColor: scheme.surface,
            flexibleSpace: FlexibleSpaceBar(
              titlePadding: const EdgeInsets.only(left: 20, bottom: 16),
              title: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _greeting(),
                    style: theme.textTheme.labelLarge,
                  ),
                  Text(
                    name == null || name.isEmpty ? 'Quinone' : name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ],
              ),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.all(20),
            sliver: SliverList(
              delegate: SliverChildListDelegate(
                [
                  _AnalyzeCard(
                    onPhotoTap: () => context.push('/upload'),
                    onRecipeTap: () => context.push('/recipe'),
                  ),
                  const SizedBox(height: 30),
                  Text(
                    "Today's Summary",
                    style: theme.textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: _StatCard(
                          title: 'Calories',
                          value: today.isEmpty ? '--' : '${calories.round()}',
                          suffix: today.isEmpty ? null : 'kcal',
                          icon: Icons.local_fire_department_rounded,
                          color: Colors.orange,
                          onTap: today.isEmpty
                              ? null
                              : () => _showTodaySummaryBreakdown(
                                    context,
                                    type: _TodaySummaryType.calories,
                                    records: today,
                                  ),
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: _NutrientSummaryCard(
                          balanced: balancedNutrients,
                          high: highNutrients,
                          low: lowNutrients,
                          enabled: daily != null,
                          onTap: daily == null
                              ? null
                              : () => _showTodayNutrients(
                                    context,
                                    insights: todayNutrition,
                                    day: daily,
                                  ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      Expanded(
                        child: _StatCard(
                          title: 'Meals',
                          value: '${today.length}',
                          icon: Icons.restaurant_menu_rounded,
                          color: Colors.teal,
                          onTap: today.isEmpty
                              ? null
                              : () => _showTodaySummaryBreakdown(
                                    context,
                                    type: _TodaySummaryType.meals,
                                    records: today,
                                  ),
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: _StatCard(
                          title: 'Health',
                          value: health == null ? '--' : health.round().toString(),
                          suffix: health == null ? null : '/100',
                          icon: Icons.favorite_rounded,
                          color: Colors.red,
                          onTap: daily == null
                              ? null
                              : () => _showTodayHealthProfile(
                                    context,
                                    daily,
                                  ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 34),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Recent Analyses',
                          style: theme.textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  if (records.isEmpty)
                    Card(
                      elevation: 0,
                      child: const Padding(
                        padding: EdgeInsets.all(26),
                        child: Center(
                          child: Text(
                            'No analyses yet.\nAnalyze your first meal.',
                            textAlign: TextAlign.center,
                          ),
                        ),
                      ),
                    )
                  else
                    ...records.take(3).map(
                          (record) => Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: _RecentMealCard(
                              record: record,
                              onTap: () => context.push(
                                '/result',
                                extra: record.rawResult,
                              ),
                            ),
                          ),
                        ),
                  const SizedBox(height: 100),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _askForName() async {
    final controller = TextEditingController();
    String? error;

    final name = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: const Text('What should Quinone call you?'),
            scrollable: true,
            content: SingleChildScrollView(
              child: TextField(
                controller: controller,
                autofocus: true,
                scrollPadding: const EdgeInsets.only(bottom: 120),
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.done,
                decoration: InputDecoration(
                  labelText: 'Your name',
                  hintText: 'Enter your name',
                  errorText: error,
                ),
                onSubmitted: (_) {
                  final value = controller.text.trim();
                  if (value.length < 2) {
                    setDialogState(
                      () => error = 'Enter at least 2 characters.',
                    );
                    return;
                  }
                  Navigator.of(dialogContext).pop(value);
                },
              ),
            ),
            actions: [
              FilledButton(
                onPressed: () {
                  final value = controller.text.trim();
                  if (value.length < 2) {
                    setDialogState(() => error = 'Enter at least 2 characters.');
                    return;
                  }
                  Navigator.of(dialogContext).pop(value);
                },
                child: const Text('Continue'),
              ),
            ],
          ),
        );
      },
    );

    controller.dispose();
    if (!mounted || name == null) return;
    final notifier = ref.read(profileProvider.notifier);
    notifier.setDisplayName(name);
    await notifier.saveProfile();
  }
}

class _AnalyzeCard extends StatelessWidget {
  const _AnalyzeCard({
    required this.onPhotoTap,
    required this.onRecipeTap,
  });

  final VoidCallback onPhotoTap;
  final VoidCallback onRecipeTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(28),
        gradient: LinearGradient(
          colors: [Colors.teal.shade700, Colors.green.shade500],
        ),
      ),
      padding: const EdgeInsets.all(26),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.white24,
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Icon(Icons.restaurant_rounded, color: Colors.white, size: 34),
          ),
          const SizedBox(height: 24),
          Text(
            'Analyze Food',
            style: theme.textTheme.headlineMedium?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 9),
          const Text(
            'Use a photo for speed, or build the exact recipe when ingredients are hidden.',
            style: TextStyle(color: Colors.white70, fontSize: 15, height: 1.4),
          ),
          const SizedBox(height: 22),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  style: FilledButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: Colors.teal.shade800,
                  ),
                  onPressed: onPhotoTap,
                  icon: const Icon(Icons.camera_alt_rounded),
                  label: const Text('Photo'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.white,
                    side: const BorderSide(color: Colors.white70),
                  ),
                  onPressed: onRecipeTap,
                  icon: const Icon(Icons.soup_kitchen_outlined),
                  label: const Text('Add recipe'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
    this.suffix,
    this.onTap,
  });

  final String title;
  final String value;
  final String? suffix;
  final IconData icon;
  final Color color;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(22),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(22),
        child: Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: theme.colorScheme.outlineVariant),
          ),
          child: Column(
            children: [
              CircleAvatar(
                backgroundColor: color.withOpacity(0.12),
                child: Icon(icon, color: color),
              ),
              const SizedBox(height: 16),
              FittedBox(
                fit: BoxFit.scaleDown,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(
                      value,
                      style: theme.textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    if (suffix != null) ...[
                      const SizedBox(width: 3),
                      Text(suffix!, style: theme.textTheme.labelMedium),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 5),
              Text(title),
            ],
          ),
        ),
      ),
    );
  }
}


class _NutrientSummaryCard extends StatelessWidget {
  const _NutrientSummaryCard({
    required this.balanced,
    required this.high,
    required this.low,
    required this.enabled,
    this.onTap,
  });

  final int balanced;
  final int high;
  final int low;
  final bool enabled;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(22),
      child: InkWell(
        onTap: enabled ? onTap : null,
        borderRadius: BorderRadius.circular(22),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: theme.colorScheme.outlineVariant),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                backgroundColor: Colors.teal.withOpacity(0.12),
                child: const Icon(Icons.balance_rounded, color: Colors.teal),
              ),
              const SizedBox(height: 12),
              if (!enabled)
                Text('--', style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900))
              else ...[
                _NutrientCountLine(count: balanced, label: 'well balanced'),
                const SizedBox(height: 3),
                _NutrientCountLine(count: high, label: 'above target'),
                const SizedBox(height: 3),
                _NutrientCountLine(count: low, label: 'needs more'),
              ],
            ],
          ),
        ),
      ),
    );
  }
}


class _NutrientCountLine extends StatelessWidget {
  const _NutrientCountLine({required this.count, required this.label});

  final int count;
  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return RichText(
      text: TextSpan(
        style: theme.textTheme.labelLarge,
        children: [
          TextSpan(
            text: '$count',
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w900,
            ),
          ),
          TextSpan(text: ' $label'),
        ],
      ),
    );
  }
}

class _TodayNutrientItem {
  const _TodayNutrientItem({
    required this.category,
    required this.key,
    required this.label,
    required this.value,
    required this.unit,
    required this.state,
    required this.target,
    required this.contributors,
  });

  final InsightCategory category;
  final String key;
  final String label;
  final double value;
  final String unit;
  final BalanceState state;
  final NutrientTargetBand? target;
  final List<FoodMetricContribution> contributors;
}

List<_TodayNutrientItem> _todayNutrientItems(
  NutritionInsights insights,
  DailyNutritionInsight day,
) {
  final result = <_TodayNutrientItem>[];
  for (final category in const [
    InsightCategory.macros,
    InsightCategory.micronutrients,
  ]) {
    final keys = category == InsightCategory.macros
        ? insights.macroKeys
        : insights.micronutrientKeys;
    for (final key in keys) {
      final normalizedKey = key.trim().toLowerCase();
      // Sugars stay available in meal-level carbohydrate details, but the
      // Home nutrient-balance list intentionally excludes sugar rows.
      if (normalizedKey == 'sugars_g' ||
          normalizedKey == 'total_sugars_g' ||
          normalizedKey == 'sugar_g' ||
          normalizedKey == 'added_sugars_g' ||
          normalizedKey == 'added_sugar_g') {
        continue;
      }

      final value = day.metricValue(category, key);
      final target = insights.targetForDay(day, key);
      // A nutrient without a defensible numeric target is omitted rather than
      // shown as an unavailable/unknown balance row.
      if (value == null || target == null) continue;
      final classified = target.classify(value);
      if (classified == BalanceState.unknown) continue;
      final state = target.minimumStyle && target.isAboveReference(value)
          ? BalanceState.high
          : classified;
      result.add(
        _TodayNutrientItem(
          category: category,
          key: key,
          label: friendlyMetricName(key),
          value: value,
          unit: target.unit.isEmpty ? unitForMetric(key) : target.unit,
          state: state,
          target: target,
          contributors: day.contributorsFor(category, key),
        ),
      );
    }
  }
  result.sort((a, b) => a.label.compareTo(b.label));
  return result;
}

void _showTodayNutrients(
  BuildContext context, {
  required NutritionInsights insights,
  required DailyNutritionInsight day,
}) {
  final items = _todayNutrientItems(insights, day);
  final groups = <BalanceState, List<_TodayNutrientItem>>{
    BalanceState.low: items.where((i) => i.state == BalanceState.low).toList(),
    BalanceState.balanced: items.where((i) => i.state == BalanceState.balanced).toList(),
    BalanceState.high: items.where((i) => i.state == BalanceState.high).toList(),
  };

  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    useSafeArea: true,
    isScrollControlled: true,
    builder: (sheetContext) {
      final theme = Theme.of(sheetContext);
      return DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.82,
        minChildSize: 0.50,
        maxChildSize: 0.95,
        builder: (context, controller) => ListView(
          controller: controller,
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 30),
          children: [
            Text(
              "Today's nutrients",
              style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 5),
            Text(
              '${groups[BalanceState.balanced]!.length} well balanced · '
              '${groups[BalanceState.high]!.length} above target · '
              '${groups[BalanceState.low]!.length} needs more',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 20),
            _TodayNutrientGroup(
              title: 'Needs more',
              items: groups[BalanceState.low]!,
            ),
            const SizedBox(height: 20),
            _TodayNutrientGroup(
              title: 'Well balanced',
              items: groups[BalanceState.balanced]!,
            ),
            const SizedBox(height: 20),
            _TodayNutrientGroup(
              title: 'Above target',
              items: groups[BalanceState.high]!,
            ),
          ],
        ),
      );
    },
  );
}

class _TodayNutrientGroup extends StatelessWidget {
  const _TodayNutrientGroup({required this.title, required this.items});

  final String title;
  final List<_TodayNutrientItem> items;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
        const SizedBox(height: 10),
        if (items.isEmpty)
          Text('None', style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant))
        else
          ...items.map((item) {
            final reference = item.target?.reference ?? item.target?.high ?? item.target?.low;
            final highest = item.contributors.isEmpty ? null : item.contributors.first;
            final lowest = item.contributors.isEmpty ? null : item.contributors.last;
            return Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerLow,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: theme.colorScheme.outlineVariant),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: Text(item.label, style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800))),
                      Text('${_homeCompact(item.value)} ${item.unit}', style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900)),
                    ],
                  ),
                  if (reference != null && reference >= 0) ...[
                    const SizedBox(height: 3),
                    Text(
                      reference == 0
                          ? 'Reference 0 ${item.unit}'
                          : 'Reference ${_homeCompact(reference)} ${item.unit} · ${(item.value / reference * 100).round()}%',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 10),
                    _TodayNutrientProgress(
                      value: item.value,
                      target: item.target!,
                      state: item.state,
                    ),
                  ],
                  if (highest != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      highest == lowest
                          ? 'Only contributor: ${highest.foodName} · ${_homeContributionPercent(highest.percentage)}'
                          : 'Highest: ${highest.foodName} · ${_homeContributionPercent(highest.percentage)}',
                      style: theme.textTheme.bodySmall,
                    ),
                    if (lowest != null && lowest != highest)
                      Text(
                        'Lowest: ${lowest.foodName} · ${_homeContributionPercent(lowest.percentage)}',
                        style: theme.textTheme.bodySmall,
                      ),
                  ],
                ],
              ),
            );
          }),
      ],
    );
  }
}

class _TodayNutrientProgress extends StatelessWidget {
  const _TodayNutrientProgress({
    required this.value,
    required this.target,
    required this.state,
  });

  final double value;
  final NutrientTargetBand target;
  final BalanceState state;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final track = theme.colorScheme.surfaceContainerHighest;
    final green = theme.colorScheme.primary;
    final orange = Colors.orange;
    final red = theme.colorScheme.error;

    final safetyExcess = target.isSafetyExcess(value);
    final referenceGoal = target.minimumStyle
        ? target.reference ?? target.low
        : target.isUpperLimit
            ? target.high ?? target.reference
            : target.high ?? target.low ?? target.reference;
    final safetyGoal = target.isUpperLimit
        ? target.high ?? target.reference
        : target.high;
    final goal = safetyExcess ? safetyGoal ?? referenceGoal : referenceGoal;
    if (goal == null) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(999),
        child: SizedBox(height: 9, child: ColoredBox(color: track)),
      );
    }
    // Zero is a meaningful maximum for trans fat: zero intake is in range,
    // while any positive reported amount is above target.
    if (goal == 0) {
      final fill = value > 0 ? red : green;
      return ClipRRect(
        borderRadius: BorderRadius.circular(999),
        child: SizedBox(height: 9, child: ColoredBox(color: fill)),
      );
    }
    if (goal < 0) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(999),
        child: SizedBox(height: 9, child: ColoredBox(color: track)),
      );
    }

    final percent = (value / goal * 100).clamp(0.0, 100000.0).toDouble();
    final highColor = safetyExcess ? red : orange;
    if (state != BalanceState.high || percent <= 100) {
      final fill = switch (state) {
        BalanceState.low => orange,
        BalanceState.balanced => green,
        BalanceState.high => highColor,
        BalanceState.unknown => theme.colorScheme.onSurfaceVariant,
      };
      return ClipRRect(
        borderRadius: BorderRadius.circular(999),
        child: SizedBox(
          height: 9,
          child: Stack(
            fit: StackFit.expand,
            children: [
              ColoredBox(color: track),
              FractionallySizedBox(
                alignment: Alignment.centerLeft,
                widthFactor: (percent / 100).clamp(0.0, 1.0).toDouble(),
                child: ColoredBox(color: fill),
              ),
            ],
          ),
        ),
      );
    }

    // Above a minimum/reference target, use amber for informational overflow.
    // Red is reserved for a real range/maximum/food-applicable upper-limit
    // breach.  Both states keep the same single-bar overflow treatment.
    return ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: SizedBox(
        height: 9,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final targetShare = (100 / percent).clamp(0.0, 1.0).toDouble();
            return Stack(
              fit: StackFit.expand,
              children: [
                ColoredBox(color: highColor),
                Align(
                  alignment: Alignment.centerLeft,
                  child: SizedBox(
                    width: constraints.maxWidth * targetShare,
                    height: double.infinity,
                    child: ColoredBox(color: green),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

String _homeCompact(double value) => value == value.roundToDouble()
    ? value.toStringAsFixed(0)
    : value.toStringAsFixed(value.abs() < 10 ? 2 : 1);

String _homeContributionPercent(double percentage) {
  if (percentage <= 0) return '';
  if (percentage < 1) return '<1%';
  return '${percentage.toStringAsFixed(0)}%';
}

class _RecentMealCard extends StatelessWidget {
  const _RecentMealCard({required this.record, required this.onTap});
  final AnalysisHistoryRecord record;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              CircleAvatar(
                backgroundColor: theme.colorScheme.primaryContainer,
                child: Icon(
                  Icons.restaurant_rounded,
                  color: theme.colorScheme.onPrimaryContainer,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      record.mealName,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '${record.calories.round()} kcal · '
                      '${record.protein.toStringAsFixed(1)} g protein',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded),
            ],
          ),
        ),
      ),
    );
  }
}

List<AnalysisHistoryRecord> _todayRecords(List<AnalysisHistoryRecord> records) {
  final now = DateTime.now();
  return records.where((record) {
    final local = record.createdAt.toLocal();
    return local.year == now.year &&
        local.month == now.month &&
        local.day == now.day;
  }).toList(growable: false);
}

enum _TodaySummaryType { calories, protein, meals }

void _showTodaySummaryBreakdown(
  BuildContext context, {
  required _TodaySummaryType type,
  required List<AnalysisHistoryRecord> records,
}) {
  final pageContext = context;
  final totalCalories = records.fold<double>(
    0,
    (sum, record) => sum + record.calories,
  );
  final totalProtein = records.fold<double>(
    0,
    (sum, record) => sum + record.protein,
  );
  final title = switch (type) {
    _TodaySummaryType.calories => 'Calories by meal',
    _TodaySummaryType.protein => 'Protein by meal',
    _TodaySummaryType.meals => "Today's meals",
  };
  final totalText = switch (type) {
    _TodaySummaryType.calories => '${totalCalories.round()} kcal today',
    _TodaySummaryType.protein =>
      '${totalProtein.toStringAsFixed(1)} g protein today',
    _TodaySummaryType.meals =>
      '${records.length} ${records.length == 1 ? 'meal' : 'meals'} analysed today',
  };
  final sorted = [...records]
    ..sort((a, b) => b.createdAt.compareTo(a.createdAt));

  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    useSafeArea: true,
    isScrollControlled: true,
    builder: (sheetContext) {
      final theme = Theme.of(sheetContext);

      return DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.62,
        minChildSize: 0.38,
        maxChildSize: 0.90,
        builder: (context, controller) => ListView(
          controller: controller,
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 30),
          children: [
            Text(
              title,
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 5),
            Text(
              totalText,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 18),
            ...sorted.map(
              (record) {
                final value = type == _TodaySummaryType.protein
                    ? record.protein
                    : record.calories;
                final total = type == _TodaySummaryType.protein
                    ? totalProtein
                    : totalCalories;
                final fraction = total <= 0
                    ? 0.0
                    : (value / total).clamp(0.0, 1.0).toDouble();
                final localTime = TimeOfDay.fromDateTime(
                  record.createdAt.toLocal(),
                );

                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Material(
                    color: theme.colorScheme.surfaceContainerLow,
                    borderRadius: BorderRadius.circular(18),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(18),
                      onTap: () {
                        Navigator.of(sheetContext).pop();
                        pageContext.push('/result', extra: record.rawResult);
                      },
                      child: Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
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
                                    record.mealName,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: theme.textTheme.titleSmall?.copyWith(
                                      fontWeight: FontWeight.w800,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Text(
                                  MaterialLocalizations.of(sheetContext)
                                      .formatTimeOfDay(localTime),
                                  style: theme.textTheme.bodySmall?.copyWith(
                                    color: theme.colorScheme.onSurfaceVariant,
                                  ),
                                ),
                                const SizedBox(width: 4),
                                const Icon(Icons.chevron_right_rounded),
                              ],
                            ),
                            const SizedBox(height: 7),
                            Text(
                              '${record.calories.round()} kcal · '
                              '${record.protein.toStringAsFixed(1)} g protein',
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                            ),
                            if (type != _TodaySummaryType.meals) ...[
                              const SizedBox(height: 11),
                              ClipRRect(
                                borderRadius: BorderRadius.circular(999),
                                child: LinearProgressIndicator(
                                  minHeight: 7,
                                  value: fraction,
                                  backgroundColor:
                                      theme.colorScheme.surfaceContainerHighest,
                                ),
                              ),
                              const SizedBox(height: 5),
                              Text(
                                '${(fraction * 100).round()}% of today’s '
                                '${type == _TodaySummaryType.protein ? 'protein' : 'calories'}',
                                style: theme.textTheme.labelSmall?.copyWith(
                                  color: theme.colorScheme.onSurfaceVariant,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
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


void _showTodayHealthProfile(
  BuildContext context,
  DailyNutritionInsight day,
) {
  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    useSafeArea: true,
    isScrollControlled: true,
    builder: (context) {
      final theme = Theme.of(context);
      final scores = day.healthScores.entries.toList()
        ..sort((a, b) => a.value.compareTo(b.value));

      return DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.78,
        minChildSize: 0.50,
        maxChildSize: 0.94,
        builder: (context, controller) => ListView(
          controller: controller,
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 30),
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    "Today's Health Profile",
                    style: theme.textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                _HomeScorePill(score: day.overallHealthScore),
              ],
            ),
            const SizedBox(height: 5),
            Text(
              '${day.mealCount} ${day.mealCount == 1 ? 'meal' : 'meals'} analysed today',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'These are dietary health-domain scores, not medical diagnoses. Tap a domain to see how individual meals compared with today’s combined score.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 20),
            if (scores.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 30),
                child: Center(
                  child: Text('No health-domain scores are available today.'),
                ),
              )
            else
              ...scores.map(
                (entry) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _HomeDomainTile(
                    domainKey: entry.key,
                    score: entry.value,
                    meals: day.mealImpacts,
                  ),
                ),
              ),
          ],
        ),
      );
    },
  );
}

class _HomeScorePill extends StatelessWidget {
  const _HomeScorePill({required this.score});

  final double score;

  @override
  Widget build(BuildContext context) {
    final color = _homeHealthColor(score);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        '${score.round()}/100',
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _HomeDomainTile extends StatelessWidget {
  const _HomeDomainTile({
    required this.domainKey,
    required this.score,
    required this.meals,
  });

  final String domainKey;
  final double score;
  final List<MealHealthImpact> meals;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = _homeHealthColor(score);
    final relevantMeals = meals
        .where((meal) => meal.healthScores[domainKey] != null)
        .toList(growable: false);

    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(18),
      child: ExpansionTile(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
        ),
        collapsedShape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
        ),
        leading: Container(
          width: 42,
          height: 42,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: color.withOpacity(0.12),
            borderRadius: BorderRadius.circular(13),
          ),
          child: Text(
            score.round().toString(),
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
        title: Text(
          friendlyMetricName(domainKey),
          style: const TextStyle(fontWeight: FontWeight.w800),
        ),
        subtitle: Text(
          healthStatusLabel(score),
          style: TextStyle(color: color),
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
        children: [
          if (relevantMeals.isEmpty)
            Text(
              'No meal-level breakdown is available.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            )
          else
            ...relevantMeals.map(
              (meal) {
                final mealScore = meal.healthScores[domainKey]!;
                final delta = mealScore - score;
                final near = delta.abs() < 2;
                final deltaColor = near
                    ? theme.colorScheme.onSurfaceVariant
                    : delta > 0
                        ? Colors.green
                        : theme.colorScheme.error;
                final icon = near
                    ? Icons.remove_rounded
                    : delta > 0
                        ? Icons.arrow_upward_rounded
                        : Icons.arrow_downward_rounded;

                return Padding(
                  padding: const EdgeInsets.only(top: 9),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          meal.mealName,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      Icon(icon, size: 16, color: deltaColor),
                      const SizedBox(width: 5),
                      Text(
                        '${mealScore.round()}/100',
                        style: TextStyle(
                          color: deltaColor,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
        ],
      ),
    );
  }
}

Color _homeHealthColor(double score) {
  if (score >= 85) return Colors.green;
  if (score >= 70) return Colors.lightGreen.shade700;
  if (score >= 55) return Colors.orange;
  return Colors.red;
}


String _greeting() {
  final hour = DateTime.now().hour;
  if (hour < 12) return 'Good Morning';
  if (hour < 17) return 'Good Afternoon';
  return 'Good Evening';
}
