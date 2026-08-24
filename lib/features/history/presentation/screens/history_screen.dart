import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../providers/analysis_history_provider.dart';
import '../../../result/models/analysis_result.dart';
import '../../../share/services/meal_share_service.dart';

class HistoryScreen extends ConsumerWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final records = ref.watch(analysisHistoryProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('History'),
        actions: [
          if (records.isNotEmpty)
            PopupMenuButton<String>(
              onSelected: (value) async {
                if (value != 'clear') return;
                final confirmed = await showDialog<bool>(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Clear meal history?'),
                    content: const Text(
                      'This permanently removes all locally saved analyses.',
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context, false),
                        child: const Text('Cancel'),
                      ),
                      FilledButton(
                        onPressed: () => Navigator.pop(context, true),
                        child: const Text('Clear'),
                      ),
                    ],
                  ),
                );
                if (confirmed == true) {
                  await ref.read(analysisHistoryProvider.notifier).clear();
                }
              },
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'clear', child: Text('Clear history')),
              ],
            ),
        ],
      ),
      body: records.isEmpty
          ? _EmptyHistory(theme: theme)
          : RefreshIndicator(
              onRefresh: () async =>
                  ref.read(analysisHistoryProvider.notifier).refresh(),
              child: ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 110),
                itemCount: records.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (context, index) {
                  final record = records[index];
                  final protein = record.macronutrients['protein_g'] ??
                      record.macronutrients['protein'] ??
                      0;
                  return Dismissible(
                    key: ValueKey(record.analysisId),
                    direction: DismissDirection.endToStart,
                    background: Container(
                      alignment: Alignment.centerRight,
                      padding: const EdgeInsets.only(right: 24),
                      decoration: BoxDecoration(
                        color: theme.colorScheme.errorContainer,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Icon(
                        Icons.delete_outline_rounded,
                        color: theme.colorScheme.onErrorContainer,
                      ),
                    ),
                    onDismissed: (_) => ref
                        .read(analysisHistoryProvider.notifier)
                        .delete(record.analysisId),
                    child: Card(
                      clipBehavior: Clip.antiAlias,
                      child: InkWell(
                        onTap: () => context.push(
                          '/result',
                          extra: record.rawResult,
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Row(
                            children: [
                              ClipRRect(
                                borderRadius: BorderRadius.circular(14),
                                child: SizedBox(width: 58, height: 58, child: _HistoryThumbnail(paths: record.mealImagePaths, theme: theme)),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      record.mealName,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: theme.textTheme.titleMedium
                                          ?.copyWith(fontWeight: FontWeight.w800),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      _formatDate(record.createdAt),
                                      style: theme.textTheme.bodySmall?.copyWith(
                                        color: theme.colorScheme.onSurfaceVariant,
                                      ),
                                    ),
                                    if (record.detectedFoods.isNotEmpty) ...[
                                      const SizedBox(height: 5),
                                      Text(
                                        record.detectedFoods.take(3).join(', '),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: theme.textTheme.bodySmall,
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                              const SizedBox(width: 10),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text('${record.calories.round()} kcal', style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800)),
                                  const SizedBox(height: 2),
                                  Text('${protein.toStringAsFixed(1)} g protein', style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
                                  const SizedBox(height: 2),
                                  IconButton(
                                    tooltip: 'Share meal',
                                    visualDensity: VisualDensity.compact,
                                    onPressed: record.rawResult.isEmpty ? null : () async {
                                      try {
                                        await MealShareService.instance.shareMeal(context: context, result: AnalysisResult.fromJson(record.rawResult), imagePaths: record.mealImagePaths);
                                      } catch (error) {
                                        if (!context.mounted) return;
                                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not create the share card: $error')));
                                      }
                                    },
                                    icon: const Icon(Icons.ios_share_rounded, size: 20),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
    );
  }
}

class _HistoryThumbnail extends StatelessWidget {
  const _HistoryThumbnail({required this.paths, required this.theme});
  final List<String> paths;
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    final path = paths.firstWhere((item) => item.trim().isNotEmpty && File(item).existsSync(), orElse: () => '');
    if (path.isEmpty) {
      return ColoredBox(color: theme.colorScheme.primaryContainer, child: Icon(Icons.restaurant_rounded, color: theme.colorScheme.onPrimaryContainer));
    }
    return Image.file(File(path), fit: BoxFit.cover, errorBuilder: (_, __, ___) => ColoredBox(color: theme.colorScheme.primaryContainer, child: Icon(Icons.restaurant_rounded, color: theme.colorScheme.onPrimaryContainer)));
  }
}

class _EmptyHistory extends StatelessWidget {
  const _EmptyHistory({required this.theme});
  final ThemeData theme;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.history_rounded,
                  size: 64, color: theme.colorScheme.primary),
              const SizedBox(height: 18),
              Text(
                'No saved meals yet',
                style: theme.textTheme.titleLarge
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              Text(
                'Completed analyses are saved automatically on this device.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyLarge?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      );
}

String _formatDate(DateTime date) {
  final now = DateTime.now();
  final local = date.toLocal();
  final sameDay = now.year == local.year &&
      now.month == local.month &&
      now.day == local.day;
  final time =
      '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
  if (sameDay) return 'Today, $time';
  return '${local.day.toString().padLeft(2, '0')}/'
      '${local.month.toString().padLeft(2, '0')}/${local.year}, $time';
}
