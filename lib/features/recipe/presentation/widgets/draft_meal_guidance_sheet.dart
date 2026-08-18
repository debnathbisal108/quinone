import 'package:flutter/material.dart';

import '../../models/draft_meal_guidance.dart';

enum DraftMealGuidanceAction {
  review,
  continueAnyway,
  confirmQuantity,
  searchSuggestion,
}

class DraftGuidanceAdjustableFood {
  const DraftGuidanceAdjustableFood({
    required this.name,
    required this.quantity,
    this.unit = 'g',
  });

  final String name;
  final double quantity;
  final String unit;

  String get key => _foodKey(name);
}

class DraftMealGuidanceSheetResult {
  const DraftMealGuidanceSheetResult({
    required this.action,
    this.adjustedQuantities = const {},
    this.searchQuery,
  });

  final DraftMealGuidanceAction action;
  final Map<String, double> adjustedQuantities;
  final String? searchQuery;

  bool get accepted => action == DraftMealGuidanceAction.continueAnyway ||
      action == DraftMealGuidanceAction.confirmQuantity;
}

Future<DraftMealGuidanceSheetResult> showDraftMealGuidanceSheet(
  BuildContext context, {
  required DraftMealGuidance guidance,
  required bool analysisCheckpoint,
  List<DraftGuidanceAdjustableFood> adjustableFoods = const [],
  bool pendingFoodAddition = false,
}) async {
  return await showModalBottomSheet<DraftMealGuidanceSheetResult>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        showDragHandle: true,
        builder: (sheetContext) => _DraftMealGuidanceSheet(
          guidance: guidance,
          analysisCheckpoint: analysisCheckpoint,
          adjustableFoods: adjustableFoods,
          pendingFoodAddition: pendingFoodAddition,
        ),
      ) ??
      const DraftMealGuidanceSheetResult(
        action: DraftMealGuidanceAction.review,
      );
}

class _DraftMealGuidanceSheet extends StatefulWidget {
  const _DraftMealGuidanceSheet({
    required this.guidance,
    required this.analysisCheckpoint,
    required this.adjustableFoods,
    required this.pendingFoodAddition,
  });

  final DraftMealGuidance guidance;
  final bool analysisCheckpoint;
  final List<DraftGuidanceAdjustableFood> adjustableFoods;
  final bool pendingFoodAddition;

  @override
  State<_DraftMealGuidanceSheet> createState() =>
      _DraftMealGuidanceSheetState();
}

class _DraftMealGuidanceSheetState
    extends State<_DraftMealGuidanceSheet> {
  late final Map<String, DraftGuidanceAdjustableFood> _foodsByKey;
  late final Map<String, double> _quantities;
  String? _selectedSuggestionQuery;

  @override
  void initState() {
    super.initState();
    _foodsByKey = {
      for (final food in widget.adjustableFoods) food.key: food,
    };
    _quantities = {
      for (final food in widget.adjustableFoods) food.key: food.quantity,
    };
  }

  void _changeQuantity(DraftGuidanceAdjustableFood food, double multiplier) {
    final current = _quantities[food.key] ?? food.quantity;
    final changed = (current * multiplier * 10).roundToDouble() / 10;
    setState(() {
      _quantities[food.key] = changed.clamp(0.1, 1000000).toDouble();
    });
  }

  DraftGuidanceAdjustableFood? _adjustableContributor(
    DraftNutrientAlert alert,
  ) {
    for (final contributor in alert.contributors) {
      final food = _foodsByKey[_foodKey(contributor.name)];
      if (food != null) return food;
    }
    return null;
  }

  double _adjustedAmount(DraftNutrientAlert alert) {
    var amount = alert.amount;
    for (final contributor in alert.contributors) {
      final food = _foodsByKey[_foodKey(contributor.name)];
      if (food == null || food.quantity <= 0) continue;
      final adjustedQuantity = _quantities[food.key] ?? food.quantity;
      amount += contributor.amount *
          ((adjustedQuantity / food.quantity) - 1.0);
    }
    return amount.clamp(0.0, double.infinity).toDouble();
  }

  double _adjustedPercentage(DraftNutrientAlert alert) {
    if (alert.reference <= 0) return alert.percentage;
    return _adjustedAmount(alert) / alert.reference * 100.0;
  }

  bool _resolvedAtCurrentQuantity(DraftNutrientAlert alert) {
    if (!alert.isExcess || alert.requiresClinicalInput) return false;
    return _adjustedPercentage(alert) <= 100.0001;
  }

  DraftMealGuidanceSheetResult _result(
    DraftMealGuidanceAction action, {
    String? searchQuery,
  }) {
    return DraftMealGuidanceSheetResult(
      action: action,
      adjustedQuantities: Map<String, double>.unmodifiable(_quantities),
      searchQuery: searchQuery,
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final hasActiveAlerts = widget.guidance.alerts.any(
      (alert) => !_resolvedAtCurrentQuantity(alert),
    );
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.82,
      minChildSize: 0.52,
      maxChildSize: 0.96,
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
                        'Meal guidance',
                        style: theme.textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        widget.pendingFoodAddition
                            ? 'Review nutrient changes before adding this food.'
                            : !hasActiveAlerts
                                ? 'The flagged excesses are now within their displayed references.'
                                : widget.guidance.message,
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
              itemCount: widget.guidance.alerts.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, index) {
                final alert = widget.guidance.alerts[index];
                final adjustable = alert.isExcess
                    ? _adjustableContributor(alert)
                    : null;
                return _NutrientAlertCard(
                  alert: alert,
                  adjustedAmount: _adjustedAmount(alert),
                  adjustedPercentage: _adjustedPercentage(alert),
                  resolved: _resolvedAtCurrentQuantity(alert),
                  adjustableFood: adjustable,
                  adjustedQuantity:
                      adjustable == null ? null : _quantities[adjustable.key],
                  onDecrease: adjustable == null
                      ? null
                      : () => _changeQuantity(adjustable, 0.90),
                  onIncrease: adjustable == null
                      ? null
                      : () => _changeQuantity(adjustable, 1.10),
                  onSearchSuggestion: (query) => Navigator.pop(
                    context,
                    _result(
                      DraftMealGuidanceAction.searchSuggestion,
                      searchQuery: query,
                    ),
                  ),
                  pendingFoodAddition: widget.pendingFoodAddition,
                  selectedSuggestionQuery: _selectedSuggestionQuery,
                  onSelectPendingSuggestion: (query) => setState(() {
                    _selectedSuggestionQuery = query;
                  }),
                );
              },
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
                  widget.guidance.disclaimer,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.pop(
                          context,
                          _result(DraftMealGuidanceAction.review),
                        ),
                        child: Text(
                          widget.pendingFoodAddition
                              ? 'Cancel'
                              : widget.analysisCheckpoint
                                  ? 'Review meal'
                                  : 'Back to edit',
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: FilledButton(
                        onPressed: () => Navigator.pop(
                          context,
                          _result(
                            widget.pendingFoodAddition
                                ? DraftMealGuidanceAction.confirmQuantity
                                : DraftMealGuidanceAction.continueAnyway,
                            searchQuery: widget.pendingFoodAddition
                                ? _selectedSuggestionQuery
                                : null,
                          ),
                        ),
                        child: Text(
                          widget.pendingFoodAddition
                              ? 'Confirm & add'
                              : widget.analysisCheckpoint
                                  ? hasActiveAlerts
                                      ? 'Continue & analyze anyway'
                                      : 'Confirm & analyze'
                                  : 'Confirm changes',
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
  const _NutrientAlertCard({
    required this.alert,
    required this.adjustedAmount,
    required this.adjustedPercentage,
    required this.resolved,
    required this.adjustableFood,
    required this.adjustedQuantity,
    required this.onDecrease,
    required this.onIncrease,
    required this.onSearchSuggestion,
    required this.pendingFoodAddition,
    required this.selectedSuggestionQuery,
    required this.onSelectPendingSuggestion,
  });

  final DraftNutrientAlert alert;
  final double adjustedAmount;
  final double adjustedPercentage;
  final bool resolved;
  final DraftGuidanceAdjustableFood? adjustableFood;
  final double? adjustedQuantity;
  final VoidCallback? onDecrease;
  final VoidCallback? onIncrease;
  final ValueChanged<String> onSearchSuggestion;
  final bool pendingFoodAddition;
  final String? selectedSuggestionQuery;
  final ValueChanged<String> onSelectPendingSuggestion;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final critical = alert.severity == 'critical';
    final color = alert.requiresClinicalInput
        ? scheme.tertiary
        : resolved
            ? scheme.primary
            : alert.isExcess
                ? (critical ? scheme.error : Colors.orange.shade700)
                : scheme.primary;
    final displayedMessage = resolved
        ? '${alert.label} is now within the displayed reference at this quantity.'
        : !alert.isExcess &&
                !alert.requiresClinicalInput &&
                adjustedPercentage >= 55
            ? '${alert.label} has improved for this meal at the adjusted quantity.'
            : alert.message;
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
                resolved
                    ? Icons.check_circle_rounded
                    : alert.isExcess
                        ? Icons.warning_amber_rounded
                        : alert.requiresClinicalInput
                            ? Icons.medical_information_outlined
                            : Icons.add_chart_rounded,
                color: color,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${alert.label}: ${_format(adjustedAmount)} ${alert.unit}',
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              if (!alert.requiresClinicalInput)
                Text(
                  '${adjustedPercentage.toStringAsFixed(0)}%',
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w900,
                  ),
                ),
            ],
          ),
          if (resolved) ...[
            const SizedBox(height: 7),
            Align(
              alignment: Alignment.centerLeft,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                decoration: BoxDecoration(
                  color: scheme.primary.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  'Resolved',
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: scheme.primary,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ),
          ],
          const SizedBox(height: 7),
          Text(displayedMessage, style: theme.textTheme.bodyMedium),
          if (alert.contributors.isNotEmpty) ...[
            const SizedBox(height: 7),
            Text(
              'Main contributors: ${alert.contributors.take(3).map((item) => item.name).join(', ')}',
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ],
          if (alert.isExcess && adjustableFood != null) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Text(
                    adjustableFood!.name,
                    style: theme.textTheme.labelLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                IconButton.filledTonal(
                  tooltip: 'Decrease quantity by 10%',
                  onPressed: onDecrease,
                  icon: const Icon(Icons.remove_rounded),
                ),
                SizedBox(
                  width: 72,
                  child: Text(
                    '${_format(adjustedQuantity ?? adjustableFood!.quantity)} ${adjustableFood!.unit}',
                    textAlign: TextAlign.center,
                    style: theme.textTheme.labelLarge?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                IconButton.filledTonal(
                  tooltip: 'Increase quantity by 10%',
                  onPressed: onIncrease,
                  icon: const Icon(Icons.add_rounded),
                ),
              ],
            ),
            Text(
              'Each tap changes this food by 10%. Nutrient values above update immediately.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ],
          if (!alert.isExcess && alert.suggestions.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              'Foods to add (choose one)',
              style: theme.textTheme.labelLarge?.copyWith(
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 5),
            if (pendingFoodAddition) ...[
              Text(
                'Select one now; it will open after you confirm this food.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 5),
            ],
            Wrap(
              spacing: 7,
              runSpacing: 7,
              children: alert.suggestions.map((suggestion) {
                return FilterChip(
                  avatar: const Icon(Icons.add_rounded, size: 18),
                  selected:
                      selectedSuggestionQuery == suggestion.searchQuery,
                  label: Text(
                    '${suggestion.name} · ${_format(suggestion.quantity)} ${suggestion.unit}',
                  ),
                  onSelected: suggestion.searchQuery.isEmpty
                      ? null
                      : (_) {
                          if (pendingFoodAddition) {
                            onSelectPendingSuggestion(
                              suggestion.searchQuery,
                            );
                          } else {
                            onSearchSuggestion(suggestion.searchQuery);
                          }
                        },
                );
              }).toList(growable: false),
            ),
          ],
        ],
      ),
    );
  }
}

String _foodKey(String value) => value.trim().toLowerCase();

String _format(double value) => value == value.roundToDouble()
    ? value.toStringAsFixed(0)
    : value.toStringAsFixed(1);
