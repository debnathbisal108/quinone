import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../history/providers/analysis_history_provider.dart';

import '../../../upload/models/analysis_job_progress.dart';
import '../../services/serving_confirmation_service.dart';

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
  }

  @override
  void dispose() {
    for (final controller in _controllers) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _confirm() async {
    if (_submitting) return;

    final analysisId =
        widget.payload['analysis_id']?.toString().trim() ?? '';
    if (analysisId.isEmpty || _items.isEmpty) {
      _message('The serving information is incomplete.');
      return;
    }

    final confirmed = <Map<String, dynamic>>[];
    for (var i = 0; i < _items.length; i++) {
      final quantity =
          double.tryParse(_controllers[i].text.trim());
      if (quantity == null || quantity <= 0) {
        _message('Enter a valid amount for every packaged food.');
        return;
      }
      confirmed.add({
        'food_id': _items[i]['food_id']?.toString() ?? '',
        'quantity': quantity,
        'unit': _items[i]['unit']?.toString() ?? 'serving',
      });
    }

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
              ),
            ),
          ),
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
          onPressed: _submitting ? null : _confirm,
          icon: _submitting
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.check_circle_outline_rounded),
          label: Text(
            _submitting ? 'Analyzing…' : 'Confirm & analyze',
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

class _ServingCard extends StatelessWidget {
  const _ServingCard({
    required this.item,
    required this.controller,
  });

  final Map<String, dynamic> item;
  final TextEditingController controller;

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
