import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../history/models/analysis_history_record.dart';
import '../../../history/providers/analysis_history_provider.dart';
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
    final health = _averageDailyHealth(today);
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
                  _AnalyzeCard(onTap: () => context.push('/upload')),
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
            content: TextField(
              controller: controller,
              autofocus: true,
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
                  setDialogState(() => error = 'Enter at least 2 characters.');
                  return;
                }
                Navigator.of(dialogContext).pop(value);
              },
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
  const _AnalyzeCard({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Hero(
      tag: 'analyze_food',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(28),
          onTap: onTap,
          child: Ink(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(28),
              gradient: LinearGradient(
                colors: [Colors.teal.shade700, Colors.green.shade500],
              ),
            ),
            child: Padding(
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
                    child: const Icon(
                      Icons.restaurant_rounded,
                      color: Colors.white,
                      size: 34,
                    ),
                  ),
                  const SizedBox(height: 26),
                  Text(
                    'Analyze Food',
                    style: theme.textTheme.headlineMedium?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    'Capture your meal or upload multiple food images for complete nutritional analysis.',
                    style: TextStyle(color: Colors.white70, fontSize: 15),
                  ),
                  const SizedBox(height: 26),
                  FilledButton.icon(
                    style: FilledButton.styleFrom(
                      backgroundColor: Colors.white,
                      foregroundColor: Colors.teal.shade700,
                    ),
                    onPressed: onTap,
                    icon: const Icon(Icons.camera_alt_rounded),
                    label: const Text('Start'),
                  ),
                ],
              ),
            ),
          ),
        ),
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
  });

  final String title;
  final String value;
  final String? suffix;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
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

double? _averageDailyHealth(List<AnalysisHistoryRecord> records) {
  final values = <double>[];
  for (final record in records) {
    if (record.healthScores.isEmpty) continue;
    values.add(
      record.healthScores.values.reduce((a, b) => a + b) /
          record.healthScores.length,
    );
  }
  if (values.isEmpty) return null;
  return values.reduce((a, b) => a + b) / values.length;
}

String _greeting() {
  final hour = DateTime.now().hour;
  if (hour < 12) return 'Good Morning';
  if (hour < 17) return 'Good Afternoon';
  return 'Good Evening';
}
