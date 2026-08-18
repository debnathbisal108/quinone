import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../history/providers/analysis_history_provider.dart';
import '../../../profile/providers/profile_provider.dart';

import '../../../upload/models/analysis_job_progress.dart';
import '../../models/draft_meal_guidance.dart';
import '../../services/serving_confirmation_service.dart';
import '../widgets/draft_meal_guidance_sheet.dart';

class ServingConfirmationScreen extends ConsumerStatefulWidget {
  const ServingConfirmationScreen({
    super.key,
    required this.payload,
  });

  final Map<String, dynamic> payload;

  @override
  ConsumerState<ServingConfirmationScreen> createState() =>
      _ServingConfirmationScreenState();
}

class _ServingConfirmationScreenState
    extends ConsumerState<ServingConfirmationScreen> {
  final _service = ServingConfirmationService();
  final List<TextEditingController> _controllers = [];
  late final List<Map<String, dynamic>> _items;
  bool _submitting = false;
  bool _guidanceEnabled = true;
  bool _checkingGuidance = false;
  int _revision = 0;
  int _acceptedGuidanceRevision = -1;
  AnalysisJobProgress? _progress;

  @override
  void initState() {
    super.initState();
    final raw = widget.payload['items'];
    _items = raw is List
        ? raw
            .whereType<Map>()
            .map((item) => Map<String, dynamic>.from(item))
            .toList()
        : <Map<String, dynamic>>[];

    for (final item in _items) {
      final value = (item['quantity'] as num?)?.toDouble() ?? 1;
      _controllers.add(
        TextEditingController(text: _format(value)),
      );
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _items.isNotEmpty) {
        _evaluateGuidance(analysisCheckpoint: false);
      }
    });
  }

  @override
  void dispose() {
    for (final controller in _controllers) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _confirm() async {
    if (_submitting || _checkingGuidance) return;

    final analysisId =
        widget.payload['analysis_id']?.toString().trim() ?? '';
    if (analysisId.isEmpty || _items.isEmpty) {
      _message('The serving information is incomplete.');
      return;
    }

    if (_confirmedItems() == null) {
      _message('Enter a valid amount for every packaged food.');
      return;
    }

    if (_guidanceEnabled && _acceptedGuidanceRevision != _revision) {
      final proceed = await _evaluateGuidance(analysisCheckpoint: true);
      if (!proceed || !mounted) return;
    }

    final confirmed = _confirmedItems();
    if (confirmed == null) return;

    setState(() {
      _submitting = true;
      _progress = null;
    });

    try {
      final result = await _service.confirm(
        analysisId: analysisId,
        items: confirmed,
        onProgress: (progress) {
          if (mounted) setState(() => _progress = progress);
        },
      );
      await ref.read(analysisHistoryProvider.notifier).saveResult(result);
      if (!mounted) return;
      context.pushReplacement('/result', extra: result);
    } catch (error) {
      if (!mounted) return;
      _message(
        error.toString()
            .replaceFirst('Bad state: ', '')
            .replaceFirst('StateError: ', ''),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  List<Map<String, dynamic>>? _confirmedItems() {
    final confirmed = <Map<String, dynamic>>[];
    for (var i = 0; i < _items.length; i++) {
      final quantity = double.tryParse(_controllers[i].text.trim());
      if (quantity == null || quantity <= 0) return null;
      confirmed.add({
        'food_id': _items[i]['food_id']?.toString() ?? '',
        'quantity': quantity,
        'unit': _items[i]['unit']?.toString() ?? 'serving',
      });
    }
    return confirmed;
  }

  List<DraftGuidanceAdjustableFood> _guidanceAdjustableFoods() {
    final foods = <DraftGuidanceAdjustableFood>[];
    for (var i = 0; i < _items.length; i++) {
      final quantity = double.tryParse(_controllers[i].text.trim());
      if (quantity == null || quantity <= 0) continue;
      foods.add(DraftGuidanceAdjustableFood(
        name: _items[i]['name']?.toString() ?? 'Packaged food',
        quantity: quantity,
        unit: _items[i]['unit']?.toString() ?? 'serving',
        backendFoodId: _items[i]['food_id']?.toString(),
      ));
    }
    return foods;
  }

  void _applyGuidanceQuantities(Map<String, double> quantities) {
    var changed = false;
    for (var i = 0; i < _items.length; i++) {
      final name = _items[i]['name']?.toString() ?? 'Packaged food';
      final foodId = _items[i]['food_id']?.toString().trim() ?? '';
      final quantity = (foodId.isEmpty ? null : quantities[_guidanceFoodKey(foodId)]) ??
          quantities[_guidanceFoodKey(name)];
      if (quantity == null || quantity <= 0) continue;
      final current = double.tryParse(_controllers[i].text.trim());
      if (current != null && (current - quantity).abs() < 0.0001) continue;
      _controllers[i].text = _format(quantity);
      changed = true;
    }
    if (changed) _revision += 1;
  }

  List<Map<String, dynamic>> _todayResultsForGuidance() {
    final now = DateTime.now();
    final currentAnalysisId =
        widget.payload['analysis_id']?.toString().trim() ?? '';
    return ref
        .read(analysisHistoryProvider)
        .where((record) => _sameLocalDay(record.createdAt, now))
        .where(
          (record) => currentAnalysisId.isEmpty ||
              record.analysisId != currentAnalysisId,
        )
        .where((record) => record.rawResult.isNotEmpty)
        .map((record) => Map<String, dynamic>.from(record.rawResult))
        .toList(growable: false);
  }

  Future<bool> _evaluateGuidance({
    required bool analysisCheckpoint,
  }) async {
    if (!_guidanceEnabled) return true;
    final analysisId = widget.payload['analysis_id']?.toString().trim() ?? '';
    final items = _confirmedItems();
    if (analysisId.isEmpty || items == null || _checkingGuidance) return false;
    final revision = _revision;
    setState(() => _checkingGuidance = true);
    try {
      // A saved personalization profile may still be loading when this screen
      // opens. Wait for it so condition/diet targets are never silently
      // replaced by the generic guidance path.
      if (ref.read(profileProvider).isLoading) {
        await ref.read(profileProvider.notifier).loadProfile();
        if (!mounted) return false;
      }
      final DraftMealGuidance guidance = await _service.evaluateGuidance(
        analysisId: analysisId,
        items: items,
        profile: ref.read(profileProvider).backendPayload,
        todayResults: _todayResultsForGuidance(),
        includeShortfalls: analysisCheckpoint,
        localHour: DateTime.now().hour,
      );
      if (!mounted || revision != _revision) return false;
      if (!guidance.hasAlerts) {
        if (analysisCheckpoint) {
          _acceptedGuidanceRevision = revision;
        }
        return true;
      }
      final result = await showDraftMealGuidanceSheet(
        context,
        guidance: guidance,
        analysisCheckpoint: analysisCheckpoint,
        adjustableFoods: _guidanceAdjustableFoods(),
        suggestionsLoader: guidance.suggestionsPending
            ? () => _service.evaluateGuidanceSuggestions(
                  analysisId: analysisId,
                  items: items,
                  profile: ref.read(profileProvider).backendPayload,
                  todayResults: _todayResultsForGuidance(),
                  includeShortfalls: analysisCheckpoint,
                  localHour: DateTime.now().hour,
                )
            : null,
      );
      if (!mounted) return false;
      if (result.action == DraftMealGuidanceAction.searchSuggestion) {
        _applyGuidanceQuantities(result.adjustedQuantities);
        _message('Use Add recipe to search and add this suggested food.');
        return false;
      }
      if (!result.accepted) return false;
      _applyGuidanceQuantities(result.adjustedQuantities);
      if (analysisCheckpoint) {
        _acceptedGuidanceRevision = _revision;
      }
      return true;
    } catch (_) {
      if (!mounted) return false;
      if (!analysisCheckpoint) {
        _message('Meal guidance is unavailable right now. You can continue.');
        return true;
      }
      return await showDialog<bool>(
            context: context,
            builder: (dialogContext) => AlertDialog(
              title: const Text('Guidance unavailable'),
              content: const Text(
                'The optional nutrient check could not be loaded. '
                'You can still continue with the normal analysis.',
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext, false),
                  child: const Text('Go back'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(dialogContext, true),
                  child: const Text('Continue anyway'),
                ),
              ],
            ),
          ) ??
          false;
    } finally {
      if (mounted) setState(() => _checkingGuidance = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Confirm serving')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 120),
        children: [
          Text(
            'How much did you consume?',
            style: theme.textTheme.headlineMedium?.copyWith(
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'We read the nutrition label. Confirm the amount you actually consumed before Quinone calculates nutrients and health scores.',
            style: theme.textTheme.bodyLarge?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 22),
          ...List.generate(
            _items.length,
            (index) => Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: _ServingCard(
                item: _items[index],
                controller: _controllers[index],
                onChanged: () => _revision += 1,
              ),
            ),
          ),
          SwitchListTile.adaptive(
            contentPadding: EdgeInsets.zero,
            value: _guidanceEnabled,
            onChanged: _submitting || _checkingGuidance
                ? null
                : (value) => setState(() => _guidanceEnabled = value),
            title: const Text('Optional nutrient guidance'),
            subtitle: const Text(
              'Check nutrient excesses or shortfalls before analysis. You can continue anyway.',
            ),
            secondary: const Icon(Icons.balance_outlined),
          ),
          if (_checkingGuidance) ...[
            const SizedBox(height: 8),
            const LinearProgressIndicator(),
            const SizedBox(height: 8),
            const Text('Checking this serving’s nutrient balance…'),
          ],
          if (_progress != null) ...[
            const SizedBox(height: 8),
            LinearProgressIndicator(
              value: _progress!.progress.clamp(0.0, 1.0),
            ),
            const SizedBox(height: 10),
            Text(
              _progress!.message,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ],
      ),
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.fromLTRB(20, 10, 20, 18),
        child: FilledButton.icon(
          onPressed: _submitting || _checkingGuidance ? null : _confirm,
          icon: _submitting || _checkingGuidance
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.check_circle_outline_rounded),
          label: Text(
            _checkingGuidance
                ? 'Checking…'
                : _submitting
                    ? 'Analyzing…'
                    : 'Confirm & analyze',
          ),
        ),
      ),
    );
  }

  void _message(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  String _format(double value) {
    if (value == value.roundToDouble()) {
      return value.toStringAsFixed(0);
    }
    return value.toStringAsFixed(2);
  }
}

String _guidanceFoodKey(String value) => value.trim().toLowerCase();

bool _sameLocalDay(DateTime a, DateTime b) {
  final left = a.toLocal();
  final right = b.toLocal();
  return left.year == right.year &&
      left.month == right.month &&
      left.day == right.day;
}

class _ServingCard extends StatelessWidget {
  const _ServingCard({
    required this.item,
    required this.controller,
    required this.onChanged,
  });

  final Map<String, dynamic> item;
  final TextEditingController controller;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final name = item['name']?.toString() ?? 'Packaged food';
    final brand = item['brand']?.toString().trim();
    final unit = item['unit']?.toString() ?? 'serving';
    final servingValue =
        (item['serving_size_value'] as num?)?.toDouble();
    final servingUnit = item['serving_size_unit']?.toString();
    final servingsPerContainer =
        (item['servings_per_container'] as num?)?.toDouble();

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
          Text(
            name,
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w900,
            ),
          ),
          if (brand != null && brand.isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(
              brand,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          if (servingValue != null && servingValue > 0) ...[
            const SizedBox(height: 12),
            Text(
              'Label serving: ${_number(servingValue)} ${servingUnit ?? ''}'
              '${servingsPerContainer != null && servingsPerContainer > 0 ? ' · ${_number(servingsPerContainer)} servings/container' : ''}',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          const SizedBox(height: 16),
          TextField(
            controller: controller,
            onChanged: (_) => onChanged(),
            keyboardType:
                const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(
              labelText: 'Amount consumed',
              suffixText: unit,
              border: const OutlineInputBorder(),
            ),
          ),
        ],
      ),
    );
  }

  String _number(double value) {
    return value == value.roundToDouble()
        ? value.toStringAsFixed(0)
        : value.toStringAsFixed(2);
  }
}
