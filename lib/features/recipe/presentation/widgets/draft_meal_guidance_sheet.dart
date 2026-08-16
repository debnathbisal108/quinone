import 'package:flutter/material.dart';

import '../../models/draft_meal_guidance.dart';

Future<bool> showDraftMealGuidanceSheet(
  BuildContext context, {
  required DraftMealGuidance guidance,
  required bool analysisCheckpoint,
  required ValueChanged<String> onSearchSuggestion,
}) async {
  final result = await showModalBottomSheet<String>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (sheetContext) => _DraftMealGuidanceSheet(
      guidance: guidance,
      analysisCheckpoint: analysisCheckpoint,
    ),
  );
  if (result != null && result.startsWith('search:')) {
    final query = result.substring('search:'.length).trim();
    if (query.isNotEmpty) onSearchSuggestion(query);
    return false;
  }
  return result == 'continue';
}

class _DraftMealGuidanceSheet extends StatelessWidget {
  const _DraftMealGuidanceSheet({
    required this.guidance,
    required this.analysisCheckpoint,
  });

  final DraftMealGuidance guidance;
  final bool analysisCheckpoint;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.78,
      minChildSize: 0.48,
      maxChildSize: 0.94,
      builder: (context, controller) => Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 4, 20, 12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CircleAvatar(
                  backgroundColor: scheme.primaryContainer,
                  child: Icon(
                    Icons.balance_rounded,
                    color: scheme.onPrimaryContainer,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Optional meal guidance',
                        style: theme.textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        guidance.message,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView.separated(
              controller: controller,
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 16),
              itemCount: guidance.alerts.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, index) => _NutrientAlertCard(
                alert: guidance.alerts[index],
              ),
            ),
          ),
          Container(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 18),
            decoration: BoxDecoration(
              color: scheme.surface,
              border: Border(top: BorderSide(color: scheme.outlineVariant)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  guidance.disclaimer,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.pop(context, 'review'),
                        child: Text(
                          analysisCheckpoint ? 'Review meal' : 'Back to edit',
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: FilledButton(
                        onPressed: () => Navigator.pop(context, 'continue'),
                        child: Text(
                          analysisCheckpoint
                              ? 'Continue & analyze anyway'
                              : 'Dismiss for this draft',
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _NutrientAlertCard extends StatelessWidget {
  const _NutrientAlertCard({required this.alert});

  final DraftNutrientAlert alert;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final critical = alert.severity == 'critical';
    final color = alert.requiresClinicalInput
        ? scheme.tertiary
        : alert.isExcess
        ? (critical ? scheme.error : Colors.orange.shade700)
        : scheme.primary;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: color.withOpacity(0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                alert.isExcess
                    ? Icons.warning_amber_rounded
                    : alert.requiresClinicalInput
                        ? Icons.medical_information_outlined
                        : Icons.add_chart_rounded,
                color: color,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${alert.label}: ${_format(alert.amount)} ${alert.unit}',
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              if (!alert.requiresClinicalInput)
                Text(
                  '${alert.percentage.toStringAsFixed(0)}%',
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w900,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 7),
          Text(alert.message, style: theme.textTheme.bodyMedium),
          if (alert.contributors.isNotEmpty) ...[
            const SizedBox(height: 7),
            Text(
              'Main contributors: ${alert.contributors.join(', ')}',
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ],
          if (alert.suggestions.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              alert.isExcess
                  ? 'Lower-${alert.label.toLowerCase()} alternatives'
                  : 'Foods to add (choose one)',
              style: theme.textTheme.labelLarge?.copyWith(
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 5),
            Wrap(
              spacing: 7,
              runSpacing: 7,
              children: alert.suggestions.map((suggestion) {
                return ActionChip(
                  avatar: Icon(
                    alert.isExcess
                        ? Icons.swap_horiz_rounded
                        : Icons.add_rounded,
                    size: 18,
                  ),
                  label: Text(
                    '${suggestion.name} · ${_format(suggestion.quantity)} ${suggestion.unit}',
                  ),
                  onPressed: suggestion.searchQuery.isEmpty
                      ? null
                      : () => Navigator.pop(
                            context,
                            'search:${suggestion.searchQuery}',
                          ),
                );
              }).toList(growable: false),
            ),
          ],
        ],
      ),
    );
  }
}

String _format(double value) => value == value.roundToDouble()
    ? value.toStringAsFixed(0)
    : value.toStringAsFixed(1);
