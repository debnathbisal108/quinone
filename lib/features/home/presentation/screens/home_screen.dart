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
    final protein = today.fold<double>(0, (sum, item) => sum + item.protein);
    final todayInsight = NutritionInsights.fromRecords(
      records,
      const Duration(days: 1),
    ).dailyInsights;
    final daily = todayInsight.isEmpty ? null : todayInsight.last;
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
                        child: _StatCard(
                          title: 'Protein',
                          value: today.isEmpty ? '--' : protein.toStringAsFixed(1),
                          suffix: today.isEmpty ? null : 'g',
                          icon: Icons.fitness_center_rounded,
                          color: Colors.green,
                          onTap: today.isEmpty
                              ? null
                              : () => _showTodaySummaryBreakdown(
                                    context,
                                    type: _TodaySummaryType.protein,
                                    records: today,
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
