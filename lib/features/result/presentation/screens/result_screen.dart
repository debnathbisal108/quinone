import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class ResultScreen extends StatelessWidget {
  final Map<String, dynamic> result;

  const ResultScreen({
    super.key,
    required this.result,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    final mealName = _firstText(
      result,
      const [
        'meal_name',
        'food_name',
        'name',
        'title',
      ],
      fallback: 'Meal analysis',
    );

    final summary = _firstText(
      result,
      const [
        'summary',
        'meal_summary',
        'description',
        'message',
      ],
    );

    final healthScores = _readMap(
      result['health_scores'],
    );

    final nutrition = _readMap(
      result['nutrition'],
    );

    final mealAnalysis = _readMap(
      result['meal_analysis'],
    );

    final finalResult = _readMap(
      result['final_result'],
    );

    final foods = _readList(
      result['foods'] ??
          mealAnalysis?['foods'] ??
          finalResult?['foods'],
    );

    final recommendations = _readStringList(
      result['recommendations'] ??
          result['suggestions'] ??
          mealAnalysis?['recommendations'] ??
          finalResult?['recommendations'],
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Analysis result'),
        leading: IconButton(
          tooltip: 'Back',
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            }
          },
          icon: const Icon(
            Icons.arrow_back_rounded,
          ),
        ),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(
            20,
            16,
            20,
            36,
          ),
          children: [
            _ResultHeader(
              mealName: mealName,
              summary: summary,
            ),

            if (healthScores != null &&
                healthScores.isNotEmpty) ...[
              const SizedBox(height: 24),
              _SectionTitle(
                title: 'Health scores',
                icon: Icons.monitor_heart_outlined,
              ),
              const SizedBox(height: 12),
              _ScoreGrid(
                scores: healthScores,
              ),
            ],

            if (nutrition != null &&
                nutrition.isNotEmpty) ...[
              const SizedBox(height: 28),
              _SectionTitle(
                title: 'Nutrition',
                icon: Icons.pie_chart_outline_rounded,
              ),
              const SizedBox(height: 12),
              _InformationCard(
                data: nutrition,
              ),
            ],

            if (foods.isNotEmpty) ...[
              const SizedBox(height: 28),
              _SectionTitle(
                title: 'Detected foods',
                icon: Icons.restaurant_rounded,
              ),
              const SizedBox(height: 12),
              for (var index = 0;
                  index < foods.length;
                  index++) ...[
                _FoodCard(
                  index: index,
                  food: foods[index],
                ),
                if (index < foods.length - 1)
                  const SizedBox(height: 12),
              ],
            ],

            if (mealAnalysis != null &&
                mealAnalysis.isNotEmpty) ...[
              const SizedBox(height: 28),
              _SectionTitle(
                title: 'Meal details',
                icon: Icons.analytics_outlined,
              ),
              const SizedBox(height: 12),
              _InformationCard(
                data: mealAnalysis,
                excludedKeys: const {
                  'foods',
                  'recommendations',
                },
              ),
            ],

            if (finalResult != null &&
                finalResult.isNotEmpty) ...[
              const SizedBox(height: 28),
              _SectionTitle(
                title: 'Detailed analysis',
                icon: Icons.fact_check_outlined,
              ),
              const SizedBox(height: 12),
              _InformationCard(
                data: finalResult,
                excludedKeys: const {
                  'foods',
                  'recommendations',
                },
              ),
            ],

            if (recommendations.isNotEmpty) ...[
              const SizedBox(height: 28),
              _SectionTitle(
                title: 'Recommendations',
                icon: Icons.lightbulb_outline_rounded,
              ),
              const SizedBox(height: 12),
              _RecommendationCard(
                recommendations: recommendations,
              ),
            ],

            if (!_hasVisibleResultContent(
              healthScores: healthScores,
              nutrition: nutrition,
              mealAnalysis: mealAnalysis,
              finalResult: finalResult,
              foods: foods,
              recommendations: recommendations,
            )) ...[
              const SizedBox(height: 24),
              _InformationCard(
                data: result,
              ),
            ],

            const SizedBox(height: 30),
            FilledButton.icon(
              onPressed: () {
                context.go('/upload');
              },
              icon: const Icon(
                Icons.add_a_photo_outlined,
              ),
              label: const Text(
                'Analyze another meal',
              ),
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(56),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static bool _hasVisibleResultContent({
    required Map<String, dynamic>? healthScores,
    required Map<String, dynamic>? nutrition,
    required Map<String, dynamic>? mealAnalysis,
    required Map<String, dynamic>? finalResult,
    required List<dynamic> foods,
    required List<String> recommendations,
  }) {
    return (healthScores?.isNotEmpty ?? false) ||
        (nutrition?.isNotEmpty ?? false) ||
        (mealAnalysis?.isNotEmpty ?? false) ||
        (finalResult?.isNotEmpty ?? false) ||
        foods.isNotEmpty ||
        recommendations.isNotEmpty;
  }
}

class _ResultHeader extends StatelessWidget {
  final String mealName;
  final String? summary;

  const _ResultHeader({
    required this.mealName,
    required this.summary,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(26),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.auto_awesome_rounded,
            color: theme.colorScheme.onPrimaryContainer,
            size: 30,
          ),
          const SizedBox(height: 18),
          Text(
            mealName,
            style: theme.textTheme.headlineSmall?.copyWith(
              color:
                  theme.colorScheme.onPrimaryContainer,
              fontWeight: FontWeight.w800,
            ),
          ),
          if (summary != null &&
              summary!.trim().isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              summary!,
              style: theme.textTheme.bodyLarge?.copyWith(
                color: theme
                    .colorScheme.onPrimaryContainer
                    .withValues(alpha: 0.82),
                height: 1.45,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  final IconData icon;

  const _SectionTitle({
    required this.title,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Row(
      children: [
        Icon(
          icon,
          color: theme.colorScheme.primary,
        ),
        const SizedBox(width: 10),
        Text(
          title,
          style: theme.textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

class _ScoreGrid extends StatelessWidget {
  final Map<String, dynamic> scores;

  const _ScoreGrid({
    required this.scores,
  });

  @override
  Widget build(BuildContext context) {
    final entries = scores.entries
        .where(
          (entry) =>
              entry.value != null &&
              entry.value is! Map &&
              entry.value is! List,
        )
        .toList();

    if (entries.isEmpty) {
      return _InformationCard(
        data: scores,
      );
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        final itemWidth =
            (constraints.maxWidth - 12) / 2;

        return Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            for (final entry in entries)
              SizedBox(
                width: itemWidth,
                child: _ScoreCard(
                  label: _formatKey(entry.key),
                  value: entry.value,
                ),
              ),
          ],
        );
      },
    );
  }
}

class _ScoreCard extends StatelessWidget {
  final String label;
  final dynamic value;

  const _ScoreCard({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final numericValue = _readNumber(value);

    final normalizedScore = numericValue == null
        ? null
        : numericValue > 1
            ? (numericValue / 100).clamp(0.0, 1.0)
            : numericValue.clamp(0.0, 1.0);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.labelLarge?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            _displayValue(value),
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w800,
            ),
          ),
          if (normalizedScore != null) ...[
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: normalizedScore,
                minHeight: 7,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _FoodCard extends StatelessWidget {
  final int index;
  final dynamic food;

  const _FoodCard({
    required this.index,
    required this.food,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final foodData = _readMap(food);

    final name = foodData == null
        ? food.toString()
        : _firstText(
            foodData,
            const [
              'name',
              'food_name',
              'item',
              'label',
            ],
            fallback: 'Food ${index + 1}',
          );

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 18,
                backgroundColor:
                    theme.colorScheme.secondaryContainer,
                child: Text(
                  '${index + 1}',
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: theme
                        .colorScheme.onSecondaryContainer,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  name,
                  style:
                      theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          if (foodData != null &&
              foodData.isNotEmpty) ...[
            const SizedBox(height: 14),
            _InformationRows(
              data: foodData,
              excludedKeys: const {
                'name',
                'food_name',
                'item',
                'label',
              },
            ),
          ],
        ],
      ),
    );
  }
}

class _InformationCard extends StatelessWidget {
  final Map<String, dynamic> data;
  final Set<String> excludedKeys;

  const _InformationCard({
    required this.data,
    this.excludedKeys = const {},
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
        ),
      ),
      child: _InformationRows(
        data: data,
        excludedKeys: excludedKeys,
      ),
    );
  }
}

class _InformationRows extends StatelessWidget {
  final Map<String, dynamic> data;
  final Set<String> excludedKeys;

  const _InformationRows({
    required this.data,
    this.excludedKeys = const {},
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    final entries = data.entries
        .where(
          (entry) =>
              !excludedKeys.contains(entry.key) &&
              entry.value != null,
        )
        .toList();

    if (entries.isEmpty) {
      return Text(
        'No additional information was returned.',
        style: theme.textTheme.bodyMedium?.copyWith(
          color: theme.colorScheme.onSurfaceVariant,
        ),
      );
    }

    return Column(
      children: [
        for (var index = 0;
            index < entries.length;
            index++) ...[
          _ResultEntry(
            label: _formatKey(entries[index].key),
            value: entries[index].value,
          ),
          if (index < entries.length - 1)
            const Divider(height: 24),
        ],
      ],
    );
  }
}

class _ResultEntry extends StatelessWidget {
  final String label;
  final dynamic value;

  const _ResultEntry({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    final nestedMap = _readMap(value);
    final nestedList = _readList(value);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: theme.textTheme.labelLarge?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 6),
        if (nestedMap != null)
          _InformationRows(
            data: nestedMap,
          )
        else if (nestedList.isNotEmpty)
          Column(
            children: [
              for (final item in nestedList)
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    crossAxisAlignment:
                        CrossAxisAlignment.start,
                    children: [
                      const Padding(
                        padding: EdgeInsets.only(top: 7),
                        child: Icon(
                          Icons.circle,
                          size: 6,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          _displayValue(item),
                          style: theme.textTheme.bodyLarge,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          )
        else
          Text(
            _displayValue(value),
            style: theme.textTheme.bodyLarge?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
      ],
    );
  }
}

class _RecommendationCard extends StatelessWidget {
  final List<String> recommendations;

  const _RecommendationCard({
    required this.recommendations,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: theme.colorScheme.tertiaryContainer,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        children: [
          for (var index = 0;
              index < recommendations.length;
              index++) ...[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.check_circle_outline_rounded,
                  size: 21,
                  color:
                      theme.colorScheme.onTertiaryContainer,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    recommendations[index],
                    style: theme.textTheme.bodyLarge?.copyWith(
                      color: theme
                          .colorScheme.onTertiaryContainer,
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
            if (index < recommendations.length - 1)
              const SizedBox(height: 14),
          ],
        ],
      ),
    );
  }
}

Map<String, dynamic>? _readMap(dynamic value) {
  if (value is Map<String, dynamic>) {
    return value;
  }

  if (value is Map) {
    return Map<String, dynamic>.from(value);
  }

  return null;
}

List<dynamic> _readList(dynamic value) {
  if (value is List) {
    return value;
  }

  return const [];
}

List<String> _readStringList(dynamic value) {
  if (value is List) {
    return value
        .where((item) => item != null)
        .map((item) => item.toString())
        .where((item) => item.trim().isNotEmpty)
        .toList();
  }

  if (value is String && value.trim().isNotEmpty) {
    return [value];
  }

  return const [];
}

String _firstText(
  Map<String, dynamic> data,
  List<String> keys, {
  String fallback = '',
}) {
  for (final key in keys) {
    final value = data[key];

    if (value != null &&
        value.toString().trim().isNotEmpty) {
      return value.toString().trim();
    }
  }

  return fallback;
}

double? _readNumber(dynamic value) {
  if (value is num) {
    return value.toDouble();
  }

  return double.tryParse(
    value?.toString() ?? '',
  );
}

String _displayValue(dynamic value) {
  if (value == null) {
    return 'Not available';
  }

  if (value is bool) {
    return value ? 'Yes' : 'No';
  }

  if (value is num) {
    if (value is double &&
        value == value.roundToDouble()) {
      return value.round().toString();
    }

    return value.toString();
  }

  if (value is Map) {
    return value.entries
        .map(
          (entry) =>
              '${_formatKey(entry.key.toString())}: '
              '${_displayValue(entry.value)}',
        )
        .join('\n');
  }

  if (value is List) {
    return value.map(_displayValue).join(', ');
  }

  final text = value.toString();

  return text
      .replaceAll('_', ' ')
      .trim();
}

String _formatKey(String key) {
  final words = key
      .replaceAllMapped(
        RegExp(r'([a-z])([A-Z])'),
        (match) => '${match.group(1)} ${match.group(2)}',
      )
      .replaceAll('_', ' ')
      .replaceAll('-', ' ')
      .trim()
      .split(RegExp(r'\s+'));

  return words
      .where((word) => word.isNotEmpty)
      .map(
        (word) =>
            '${word[0].toUpperCase()}'
            '${word.substring(1).toLowerCase()}',
      )
      .join(' ');
}