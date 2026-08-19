import 'package:flutter/material.dart';

import '../../models/draft_meal_guidance.dart';

typedef DraftMealGuidanceSuggestionsLoader = Future<DraftMealGuidance> Function();

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
    this.backendFoodId,
  });

  final String name;
  final double quantity;
  final String unit;
  final String? backendFoodId;

  String get key {
    final id = backendFoodId?.trim() ?? '';
    return id.isNotEmpty ? _foodKey(id) : _foodKey(name);
  }
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
  DraftMealGuidanceSuggestionsLoader? suggestionsLoader,
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
          suggestionsLoader: suggestionsLoader,
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
    required this.suggestionsLoader,
  });

  final DraftMealGuidance guidance;
  final bool analysisCheckpoint;
  final List<DraftGuidanceAdjustableFood> adjustableFoods;
  final bool pendingFoodAddition;
  final DraftMealGuidanceSuggestionsLoader? suggestionsLoader;

  @override
  State<_DraftMealGuidanceSheet> createState() =>
      _DraftMealGuidanceSheetState();
}

class _DraftMealGuidanceSheetState
    extends State<_DraftMealGuidanceSheet> {
  late final Map<String, DraftGuidanceAdjustableFood> _foodsByKey;
  late final Map<String, double> _quantities;
  late DraftMealGuidance _guidance;
  bool _loadingSuggestions = false;
  bool _suggestionsLoadFailed = false;
  bool _suggestionsRequested = false;
  String? _selectedSuggestionQuery;

  @override
  void initState() {
    super.initState();
    _guidance = widget.guidance;
    _foodsByKey = {
      for (final food in widget.adjustableFoods) food.key: food,
    };
    _quantities = {
      for (final food in widget.adjustableFoods) food.key: food.quantity,
    };
  }

  Future<void> _loadSuggestions() async {
    if (!mounted) return;
    final loader = widget.suggestionsLoader;
    if (loader == null || _loadingSuggestions) return;
    setState(() {
      _loadingSuggestions = true;
      _suggestionsLoadFailed = false;
      _suggestionsRequested = true;
    });
    try {
      final enriched = await loader().timeout(const Duration(seconds: 35));
      if (!mounted) return;
      setState(() {
        _guidance = enriched;
        _loadingSuggestions = false;
        _suggestionsLoadFailed = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingSuggestions = false;
        _suggestionsLoadFailed = true;
      });
    }
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
      final byId = contributor.foodId.trim().isEmpty
          ? null
          : _foodsByKey[_foodKey(contributor.foodId)];
      if (byId != null) return byId;
      final byName = _foodsByKey[_foodKey(contributor.name)];
      if (byName != null) return byName;
    }
    return null;
  }

  double _adjustedAmount(DraftNutrientAlert alert) {
    var amount = alert.amount;
    for (final contributor in alert.contributors) {
      final food = contributor.foodId.trim().isNotEmpty
          ? _foodsByKey[_foodKey(contributor.foodId)] ??
              _foodsByKey[_foodKey(contributor.name)]
          : _foodsByKey[_foodKey(contributor.name)];
      if (food == null || food.quantity <= 0) continue;
      final adjustedQuantity = _quantities[food.key] ?? food.quantity;
      amount += contributor.amount *
          ((adjustedQuantity / food.quantity) - 1.0);
    }
    return amount.clamp(0.0, double.infinity).toDouble();
  }

  double? _adjustedContributorAmount(
    DraftNutrientAlert alert,
    DraftGuidanceAdjustableFood food,
  ) {
    for (final contributor in alert.contributors) {
      final idMatches = contributor.foodId.trim().isNotEmpty &&
          _foodKey(contributor.foodId) == food.key;
      final nameMatches = _foodKey(contributor.name) == _foodKey(food.name);
      if (!idMatches && !nameMatches) continue;
      if (food.quantity <= 0) return contributor.amount;
      final quantity = _quantities[food.key] ?? food.quantity;
      return contributor.amount * quantity / food.quantity;
    }
    return null;
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
    final hasActiveAlerts = _guidance.alerts.any(
      (alert) => !alert.isAboveReference && !_resolvedAtCurrentQuantity(alert),
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
                                : _guidance.message,
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
              itemCount: _guidance.alerts.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, index) {
                final alert = _guidance.alerts[index];
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
                  adjustedFoodContribution: adjustable == null
                      ? null
                      : _adjustedContributorAmount(alert, adjustable),
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
                  suggestionsLoading: _loadingSuggestions &&
                      alert.isLow &&
                      alert.suggestions.isEmpty,
                  suggestionsLoadFailed: _suggestionsLoadFailed &&
                      alert.isLow &&
                      alert.suggestions.isEmpty,
                  suggestionsRequested: _suggestionsRequested,
                  onFindSuggestions: alert.isLow &&
                          alert.suggestions.isEmpty &&
                          widget.suggestionsLoader != null &&
                          (!_suggestionsRequested || _suggestionsLoadFailed)
                      ? _loadSuggestions
                      : null,
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
                if (_guidance.disclaimer.trim().isNotEmpty) ...[
                  Text(
                    _guidance.disclaimer,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 10),
                ],
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
    required this.adjustedFoodContribution,
    required this.onDecrease,
    required this.onIncrease,
    required this.onSearchSuggestion,
    required this.pendingFoodAddition,
    required this.selectedSuggestionQuery,
    required this.suggestionsLoading,
    required this.suggestionsLoadFailed,
    required this.suggestionsRequested,
    required this.onFindSuggestions,
    required this.onSelectPendingSuggestion,
  });

  final DraftNutrientAlert alert;
  final double adjustedAmount;
  final double adjustedPercentage;
  final bool resolved;
  final DraftGuidanceAdjustableFood? adjustableFood;
  final double? adjustedQuantity;
  final double? adjustedFoodContribution;
  final VoidCallback? onDecrease;
  final VoidCallback? onIncrease;
  final ValueChanged<String> onSearchSuggestion;
  final bool pendingFoodAddition;
  final String? selectedSuggestionQuery;
  final bool suggestionsLoading;
  final bool suggestionsLoadFailed;
  final bool suggestionsRequested;
  final VoidCallback? onFindSuggestions;
  final ValueChanged<String> onSelectPendingSuggestion;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final critical = alert.severity == 'critical';
    final color = alert.requiresClinicalInput
        ? scheme.tertiary
        : alert.isAboveReference
            ? scheme.tertiary
            : resolved
                ? scheme.primary
                : alert.isExcess
                    ? (critical ? scheme.error : Colors.orange.shade700)
                    : scheme.primary;
    final displayedMessage = resolved
        ? '${alert.label} is now within the displayed reference at this quantity.'
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
                        : alert.isAboveReference
                            ? Icons.info_outline_rounded
                            : alert.requiresClinicalInput
                                ? Icons.medical_information_outlined
                                : Icons.add_chart_rounded,
                color: color,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${alert.isExcess || alert.isAboveReference ? 'Projected today · ' : 'This meal · '}${alert.label}: ${_format(adjustedAmount)} ${alert.unit}',
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
          if (alert.isAboveReference) ...[
            const SizedBox(height: 7),
            Align(
              alignment: Alignment.centerLeft,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                decoration: BoxDecoration(
                  color: scheme.tertiary.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  'Above daily reference · informational',
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: scheme.tertiary,
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
            if (adjustedFoodContribution != null) ...[
              const SizedBox(height: 2),
              Text(
                '${adjustableFood!.name} contributes ${_format(adjustedFoodContribution!)} ${alert.unit} at this quantity.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
            Text(
              'Each tap changes this food by 10%. The projected nutrient total above updates immediately.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ],
          if (alert.isLow && alert.suggestions.isEmpty && suggestionsLoading) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Finding safe, suitable foods…',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
          ],
          if (alert.isLow && alert.suggestions.isEmpty && suggestionsLoadFailed) ...[
            const SizedBox(height: 10),
            Text(
              'Food suggestions are temporarily unavailable. This does not block analysis.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
            if (onFindSuggestions != null) ...[
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: onFindSuggestions,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Try food suggestions again'),
              ),
            ],
          ],
          if (alert.isLow &&
              alert.suggestions.isEmpty &&
              !suggestionsLoading &&
              !suggestionsLoadFailed &&
              !alert.requiresClinicalInput &&
              onFindSuggestions != null) ...[
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: onFindSuggestions,
              icon: const Icon(Icons.restaurant_menu_rounded),
              label: const Text('Find foods for low nutrients'),
            ),
          ],
          if (alert.isLow &&
              alert.suggestions.isEmpty &&
              suggestionsRequested &&
              !suggestionsLoading &&
              !suggestionsLoadFailed &&
              !alert.requiresClinicalInput) ...[
            const SizedBox(height: 10),
            Text(
              'No safe, compatible food suggestion was found for this shortfall.',
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
