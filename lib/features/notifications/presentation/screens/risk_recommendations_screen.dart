import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../history/models/analysis_history_record.dart';
import '../../../history/providers/analysis_history_provider.dart';
import '../../../profile/providers/profile_provider.dart';
import '../../../recommendation/models/post_analysis_recommendations.dart';
import '../../../recommendation/services/recommendation_service.dart';
import '../../models/health_risk_snapshot.dart';

class RiskRecommendationsScreen extends ConsumerStatefulWidget {
  const RiskRecommendationsScreen({
    super.key,
    required this.periodDays,
    this.notificationAsOf,
  });

  final int periodDays;
  final DateTime? notificationAsOf;

  @override
  ConsumerState<RiskRecommendationsScreen> createState() =>
      _RiskRecommendationsScreenState();
}

class _RiskRecommendationsScreenState
    extends ConsumerState<RiskRecommendationsScreen> {
  final _service = RecommendationService();
  PostAnalysisRecommendations? _recommendations;
  bool _loading = false;
  String? _error;

  Future<void> _loadRecommendations() async {
    final records = ref.read(analysisHistoryProvider);
    final riskSnapshot = _effectiveSnapshot(records);
    final latest = _latestRecord(
      records,
      widget.periodDays,
      riskSnapshot.asOf,
    );
    if (latest == null || latest.rawResult.isEmpty) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'Analyze and log a meal before requesting food options.';
        });
      }
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    if (ref.read(profileProvider).isLoading) {
      await ref.read(profileProvider.notifier).loadProfile();
    }
    if (!mounted) return;
    final sameDay = records
        .where((record) => record.analysisId != latest.analysisId)
        .where((record) => _sameLocalDay(record.createdAt, latest.createdAt))
        .where((record) => record.rawResult.isNotEmpty)
        .map((record) => Map<String, dynamic>.from(record.rawResult))
        .toList(growable: false);
    try {
      final result = await _service.afterAnalysis(
        currentResult: Map<String, dynamic>.from(latest.rawResult),
        todayResults: sameDay,
        profile: ref.read(profileProvider).backendPayload,
        localHour: DateTime.now().hour,
        maximumResults: 6,
        preferredDomainKeys: riskSnapshot.healthScores
            .map((item) => item.key)
            .toList(growable: false),
      );
      if (!mounted) return;
      setState(() {
        _recommendations = result;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = error.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final records = ref.watch(analysisHistoryProvider);
    final currentSnapshot = HealthRiskMonitor.evaluate(
      records,
      periodDays: widget.periodDays,
    );
    final snapshot = currentSnapshot.hasConcerns || widget.notificationAsOf == null
        ? currentSnapshot
        : HealthRiskMonitor.evaluate(
            records,
            periodDays: widget.periodDays,
            asOf: widget.notificationAsOf,
          );
    final addOptions = _recommendations?.items
            .where((item) => item.action == 'add')
            .toList(growable: false) ??
        const <FoodRecommendation>[];

    return Scaffold(
      appBar: AppBar(title: const Text('Nutrition recommendations')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 36),
        children: [
          _RiskSummary(snapshot: snapshot),
          const SizedBox(height: 20),
          Text(
            'Food options',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 6),
          Text(
            'Food options are calculated only when you ask, using your latest '
            'logged meal, personalized targets, dietary pattern, allergies, '
            'health profile, and USDA-verified nutrition data.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
          const SizedBox(height: 16),
          if (_loading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 28),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_recommendations == null && _error == null)
            FilledButton.icon(
              onPressed: _loadRecommendations,
              icon: const Icon(Icons.restaurant_menu_rounded),
              label: const Text('Find food options'),
            )
          else if (_error != null)
            _RecommendationError(
              message: _error!,
              onRetry: _loadRecommendations,
              onOpenRecipe: () => context.push('/recipe'),
            )
          else if (addOptions.isEmpty)
            _RecommendationError(
              message: _recommendations?.message.trim().isNotEmpty == true
                  ? _recommendations!.message
                  : 'No safe add-food option improved the affected score '
                      'without worsening another module.',
              onRetry: _loadRecommendations,
              onOpenRecipe: () => context.push('/recipe'),
            )
          else
            ...addOptions.map(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _FoodOptionCard(
                  item: item,
                  onAdd: () => context.push(
                    '/recipe',
                    extra: <String, dynamic>{
                      'recommendation_query': item.searchQuery,
                      'recommendation_name': item.foodName,
                      'recommendation_quantity': item.quantity,
                    },
                  ),
                ),
              ),
            ),
          if (addOptions.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              _recommendations?.disclaimer.trim().isNotEmpty == true
                  ? _recommendations!.disclaimer
                  : 'These are dietary-support suggestions based on logged '
                      'meals, not a diagnosis or treatment recommendation.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
        ],
      ),
    );
  }

  HealthRiskSnapshot _effectiveSnapshot(
    List<AnalysisHistoryRecord> records,
  ) {
    final current = HealthRiskMonitor.evaluate(
      records,
      periodDays: widget.periodDays,
    );
    if (current.hasConcerns || widget.notificationAsOf == null) return current;
    return HealthRiskMonitor.evaluate(
      records,
      periodDays: widget.periodDays,
      asOf: widget.notificationAsOf,
    );
  }
}

class _RiskSummary extends StatelessWidget {
  const _RiskSummary({required this.snapshot});

  final HealthRiskSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.monitor_heart_outlined,
                  color: theme.colorScheme.primary),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  snapshot.periodLabel,
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (!snapshot.hasConcerns)
            Text(
              snapshot.observedDays == 0
                  ? 'There is no logged meal data for this period yet.'
                  : 'Your latest logged pattern no longer meets the alert '
                      'threshold. Keep logging meals to maintain the trend.',
            )
          else ...[
            Text(
              'Based on ${snapshot.observedDays} logged '
              '${snapshot.observedDays == 1 ? 'day' : 'days'}.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 12),
            ...snapshot.healthScores.map(
              (risk) => _RiskLine(
                icon: Icons.favorite_border_rounded,
                title: '${risk.label} dietary-support score',
                detail:
                    '${risk.score.toStringAsFixed(0)}/100 · ${risk.level == RiskLevel.atRisk ? 'at risk' : 'monitor'}',
              ),
            ),
            ...snapshot.nutrients.map(
              (risk) => _RiskLine(
                icon: risk.direction == NutrientDirection.low
                    ? Icons.south_rounded
                    : Icons.north_rounded,
                title: risk.label,
                detail:
                    '${risk.averagePercent.toStringAsFixed(0)}% of target on average · ${risk.concernDays} of ${risk.trackedDays} tracked days ${risk.direction == NutrientDirection.low ? 'low' : 'high'}',
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _RiskLine extends StatelessWidget {
  const _RiskLine({
    required this.icon,
    required this.title,
    required this.detail,
  });

  final IconData icon;
  final String title;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 20, color: Theme.of(context).colorScheme.error),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                Text(detail, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _FoodOptionCard extends StatelessWidget {
  const _FoodOptionCard({required this.item, required this.onAdd});

  final FoodRecommendation item;
  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final target = item.targetDomain;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${_format(item.quantity)} ${item.unit} ${item.foodName}',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w900,
            ),
          ),
          if (target != null) ...[
            const SizedBox(height: 5),
            Text(
              '${target.label}: ${target.before.toStringAsFixed(0)} → '
              '${target.after.toStringAsFixed(0)} predicted',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.primary,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
          if (item.reason.trim().isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(item.reason),
          ],
          if (item.warnings.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              item.warnings.join(' · '),
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.error,
              ),
            ),
          ],
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton.icon(
              onPressed: onAdd,
              icon: const Icon(Icons.add_rounded),
              label: const Text('Add to recipe'),
            ),
          ),
        ],
      ),
    );
  }
}

class _RecommendationError extends StatelessWidget {
  const _RecommendationError({
    required this.message,
    required this.onRetry,
    required this.onOpenRecipe,
  });

  final String message;
  final VoidCallback onRetry;
  final VoidCallback onOpenRecipe;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(message),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            children: [
              OutlinedButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Retry'),
              ),
              FilledButton.icon(
                onPressed: onOpenRecipe,
                icon: const Icon(Icons.restaurant_menu_rounded),
                label: const Text('Open recipe builder'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

AnalysisHistoryRecord? _latestRecord(
  List<AnalysisHistoryRecord> records,
  int periodDays,
  DateTime asOf,
) {
  final localEnd = asOf.toLocal();
  final end = DateTime(
    localEnd.year,
    localEnd.month,
    localEnd.day,
    23,
    59,
    59,
    999,
  );
  final cutoff = DateTime(localEnd.year, localEnd.month, localEnd.day)
      .subtract(Duration(days: periodDays - 1));
  final eligible = records
      .where((record) {
        final local = record.createdAt.toLocal();
        return !local.isBefore(cutoff) && !local.isAfter(end);
      })
      .toList()
    ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
  return eligible.isEmpty ? null : eligible.first;
}

bool _sameLocalDay(DateTime first, DateTime second) {
  final a = first.toLocal();
  final b = second.toLocal();
  return a.year == b.year && a.month == b.month && a.day == b.day;
}

String _format(double value) => value == value.roundToDouble()
    ? value.toStringAsFixed(0)
    : value.toStringAsFixed(1);
