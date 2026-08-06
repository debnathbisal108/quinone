import 'package:flutter/material.dart';

class UploadProgressCard extends StatelessWidget {
  const UploadProgressCard({
    super.key,
    required this.progress,
    required this.message,
    required this.stage,
    this.canCancel = true,
    this.onCancel,
  });

  final double progress;
  final String message;
  final String stage;
  final bool canCancel;
  final VoidCallback? onCancel;

  static const _stages = <_StageView>[
    _StageView('analysis_engine', 'Food detection'),
    _StageView('food_resolution', 'Database matching'),
    _StageView('nutrient_calculation', 'Nutrient calculation'),
    _StageView('feature_engineering', 'Meal feature analysis'),
    _StageView('evidence_mapping', 'Evidence mapping'),
    _StageView('health_scoring', 'Health scoring'),
    _StageView('personalization', 'Personalisation'),
    _StageView('nutrient_targets', 'Daily target calculation'),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final normalized = progress.clamp(0.0, 1.0);
    final currentIndex = _stages.indexWhere((item) => item.id == stage);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const SizedBox(
                width: 42,
                height: 42,
                child: CircularProgressIndicator(strokeWidth: 4),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Analyzing meal',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      message,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              Text(
                '${(normalized * 100).round()}%',
                style: theme.textTheme.titleMedium?.copyWith(
                  color: theme.colorScheme.primary,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(value: normalized, minHeight: 8),
          ),
          const SizedBox(height: 18),
          ...List.generate(_stages.length, (index) {
            final item = _stages[index];
            final completed = currentIndex >= 0 && index < currentIndex;
            final active = currentIndex == index;
            return Padding(
              padding: const EdgeInsets.only(bottom: 9),
              child: Row(
                children: [
                  Icon(
                    completed
                        ? Icons.check_circle_rounded
                        : active
                            ? Icons.radio_button_checked_rounded
                            : Icons.radio_button_unchecked_rounded,
                    size: 20,
                    color: completed || active
                        ? theme.colorScheme.primary
                        : theme.colorScheme.outline,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      item.label,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontWeight: active ? FontWeight.w800 : FontWeight.w500,
                        color: active
                            ? theme.colorScheme.onSurface
                            : theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                ],
              ),
            );
          }),
          if (canCancel && onCancel != null)
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: onCancel,
                icon: const Icon(Icons.close_rounded, size: 19),
                label: const Text('Cancel'),
              ),
            ),
        ],
      ),
    );
  }
}

class _StageView {
  const _StageView(this.id, this.label);
  final String id;
  final String label;
}
