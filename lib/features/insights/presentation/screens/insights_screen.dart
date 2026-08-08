import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../history/providers/analysis_history_provider.dart';
import '../../models/nutrition_insights.dart';

class InsightsScreen extends ConsumerStatefulWidget {
  const InsightsScreen({super.key});

  @override
  ConsumerState<InsightsScreen> createState() => _InsightsScreenState();
}

class _InsightsScreenState extends ConsumerState<InsightsScreen> {
  int _days = 7;

  @override
  Widget build(BuildContext context) {
    final records = ref.watch(analysisHistoryProvider);
    final insights = NutritionInsights.fromRecords(
      records,
      Duration(days: _days),
    );
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Insights')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 110),
        children: [
          SegmentedButton<int>(
            segments: const [
              ButtonSegment(value: 7, label: Text('7 days')),
              ButtonSegment(value: 30, label: Text('30 days')),
            ],
            selected: {_days},
            onSelectionChanged: (selection) {
              setState(() => _days = selection.first);
            },
          ),
          const SizedBox(height: 18),
          if (insights.isEmpty)
            _EmptyInsights(theme: theme)
          else ...[
            Row(
              children: [
                Expanded(
                  child: _StatCard(
                    label: 'Meals logged',
                    value: '${insights.mealCount}',
                    icon: Icons.restaurant_menu_rounded,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _StatCard(
                    label: 'Days tracked',
                    value: '${insights.daysWithMeals}',
                    icon: Icons.calendar_month_rounded,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 26),
            const _SectionTitle('Average daily macros'),
            const SizedBox(height: 12),
            _MacroSummary(insights: insights),
            if (insights.targetAchievement.isNotEmpty) ...[
              const SizedBox(height: 26),
              const _SectionTitle('Personal target achievement'),
              const SizedBox(height: 12),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: insights.targetAchievement.entries
                        .where(
                          (entry) => const {
                            'protein_g',
                            'carbohydrate_g',
                            'fat_g',
                            'fiber_g',
                          }.contains(entry.key),
                        )
                        .map(
                          (entry) => _ProgressRow(
                            label: _friendlyName(entry.key),
                            percent: entry.value,
                          ),
                        )
                        .toList(growable: false),
                  ),
                ),
              ),
            ],
            if (insights.dailyInsights.isNotEmpty) ...[
              const SizedBox(height: 26),
              const _SectionTitle('Daily health trend'),
              const SizedBox(height: 6),
              Text(
                'Tap a day to inspect that day’s macros, micronutrients, and health scores.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 12),
              _DailyHealthChart(
                days: insights.dailyInsights,
                onDaySelected: (day) => _showDayDetails(context, day),
              ),
            ],
            if (insights.topFoodNames.isNotEmpty) ...[
              const SizedBox(height: 26),
              const _SectionTitle('Most frequent foods'),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: insights.topFoodNames
                    .map(
                      (entry) => Chip(
                        label: Text('${entry.key} · ${entry.value}'),
                      ),
                    )
                    .toList(growable: false),
              ),
            ],
          ],
        ],
      ),
    );
  }

  void _showDayDetails(
    BuildContext context,
    DailyNutritionInsight day,
  ) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (context) {
        final theme = Theme.of(context);
        final scores = day.healthScores.entries.toList()
          ..sort((a, b) => b.value.compareTo(a.value));
        final micros = day.micronutrients.entries.toList()
          ..sort((a, b) => b.value.compareTo(a.value));

        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: 0.78,
          minChildSize: 0.48,
          maxChildSize: 0.94,
          builder: (context, controller) => ListView(
            controller: controller,
            padding: const EdgeInsets.fromLTRB(20, 4, 20, 30),
            children: [
              Text(
                _fullDate(day.date),
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                '${day.mealCount} ${day.mealCount == 1 ? 'meal' : 'meals'} · '
                '${day.calories.round()} kcal · '
                'Health ${day.overallHealthScore.round()}/100',
                style: theme.textTheme.bodyLarge?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 24),
              const _SectionTitle('Macronutrients'),
              const SizedBox(height: 10),
              _DayMacroGrid(macros: day.macronutrients),
              if (micros.isNotEmpty) ...[
                const SizedBox(height: 24),
                const _SectionTitle('Micronutrients'),
                const SizedBox(height: 10),
                ...micros.take(12).map(
                      (entry) => _DetailRow(
                        label: _friendlyName(entry.key),
                        value: _formatNutrient(entry.key, entry.value),
                      ),
                    ),
              ],
              if (scores.isNotEmpty) ...[
                const SizedBox(height: 24),
                const _SectionTitle('Health scores'),
                const SizedBox(height: 10),
                ...scores.map(
                  (entry) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: _ScoreRow(
                      label: _friendlyName(entry.key),
                      score: entry.value,
                    ),
                  ),
                ),
              ],
            ],
          ),
        );
      },
    );
  }
}

class _DailyHealthChart extends StatelessWidget {
  const _DailyHealthChart({
    required this.days,
    required this.onDaySelected,
  });

  final List<DailyNutritionInsight> days;
  final ValueChanged<DailyNutritionInsight> onDaySelected;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final chartDays = days;

    return Container(
      padding: const EdgeInsets.fromLTRB(14, 18, 14, 12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        children: [
          SizedBox(
            height: 210,
            child: LayoutBuilder(
              builder: (context, constraints) {
                return GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTapDown: (details) {
                    if (chartDays.isEmpty) return;
                    const left = 34.0;
                    const right = 10.0;
                    final usable = math.max(
                      1.0,
                      constraints.maxWidth - left - right,
                    );
                    final normalized =
                        ((details.localPosition.dx - left) / usable)
                            .clamp(0.0, 1.0);
                    final index = chartDays.length == 1
                        ? 0
                        : (normalized * (chartDays.length - 1)).round();
                    onDaySelected(chartDays[index]);
                  },
                  child: CustomPaint(
                    painter: _HealthChartPainter(
                      days: chartDays,
                      lineColor: theme.colorScheme.primary,
                      gridColor: theme.colorScheme.outlineVariant,
                      textColor: theme.colorScheme.onSurfaceVariant,
                      pointColor: theme.colorScheme.primary,
                    ),
                    child: const SizedBox.expand(),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              Icon(
                Icons.touch_app_outlined,
                size: 16,
                color: theme.colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'Each point is the average of that day’s health-domain scores.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _HealthChartPainter extends CustomPainter {
  _HealthChartPainter({
    required this.days,
    required this.lineColor,
    required this.gridColor,
    required this.textColor,
    required this.pointColor,
  });

  final List<DailyNutritionInsight> days;
  final Color lineColor;
  final Color gridColor;
  final Color textColor;
  final Color pointColor;

  @override
  void paint(Canvas canvas, Size size) {
    const left = 34.0;
    const right = 10.0;
    const top = 12.0;
    const bottom = 32.0;
    final width = math.max(1.0, size.width - left - right);
    final height = math.max(1.0, size.height - top - bottom);

    final gridPaint = Paint()
      ..color = gridColor
      ..strokeWidth = 1;
    final linePaint = Paint()
      ..color = lineColor
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    final pointPaint = Paint()
      ..color = pointColor
      ..style = PaintingStyle.fill;

    for (final score in const [0, 25, 50, 75, 100]) {
      final y = top + height * (1 - score / 100);
      canvas.drawLine(
        Offset(left, y),
        Offset(left + width, y),
        gridPaint,
      );
      _paintText(
        canvas,
        '$score',
        Offset(0, y - 7),
        textColor,
        10,
      );
    }

    if (days.isEmpty) return;

    final points = <Offset>[];
    for (var index = 0; index < days.length; index++) {
      final x = days.length == 1
          ? left + width / 2
          : left + width * index / (days.length - 1);
      final score = days[index].overallHealthScore
          .clamp(0.0, 100.0)
          .toDouble();
      final y = top + height * (1 - score / 100);
      points.add(Offset(x, y));
    }

    if (points.length > 1) {
      final path = Path()..moveTo(points.first.dx, points.first.dy);
      for (final point in points.skip(1)) {
        path.lineTo(point.dx, point.dy);
      }
      canvas.drawPath(path, linePaint);
    }

    for (var index = 0; index < points.length; index++) {
      canvas.drawCircle(points[index], 5, pointPaint);
      canvas.drawCircle(
        points[index],
        2,
        Paint()..color = Colors.white,
      );

      final showLabel = days.length <= 7 ||
          index == 0 ||
          index == days.length - 1 ||
          index % math.max(1, (days.length / 5).round()) == 0;
      if (showLabel) {
        final date = days[index].date;
        _paintText(
          canvas,
          '${date.day}/${date.month}',
          Offset(points[index].dx - 13, size.height - 22),
          textColor,
          10,
        );
      }
    }
  }

  void _paintText(
    Canvas canvas,
    String text,
    Offset offset,
    Color color,
    double size,
  ) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(color: color, fontSize: size),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(canvas, offset);
  }

  @override
  bool shouldRepaint(covariant _HealthChartPainter oldDelegate) {
    return oldDelegate.days != days ||
        oldDelegate.lineColor != lineColor ||
        oldDelegate.gridColor != gridColor;
  }
}

class _MacroSummary extends StatelessWidget {
  const _MacroSummary({required this.insights});

  final NutritionInsights insights;

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 10,
      mainAxisSpacing: 10,
      childAspectRatio: 1.55,
      children: [
        _MacroTile(
          label: 'Protein',
          value: _macro(insights.averageDailyMacros, const ['protein_g', 'protein']),
        ),
        _MacroTile(
          label: 'Carbohydrates',
          value: _macro(
            insights.averageDailyMacros,
            const ['carbohydrate_g', 'carbohydrates_g', 'carbs_g', 'carbs'],
          ),
        ),
        _MacroTile(
          label: 'Fat',
          value: _macro(insights.averageDailyMacros, const ['fat_g', 'total_fat_g', 'fat']),
        ),
        _MacroTile(
          label: 'Fiber',
          value: _macro(
            insights.averageDailyMacros,
            const ['fiber_g', 'fibre_g', 'dietary_fiber_g'],
          ),
        ),
      ],
    );
  }
}

class _DayMacroGrid extends StatelessWidget {
  const _DayMacroGrid({required this.macros});
  final Map<String, double> macros;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        _SmallValueChip(label: 'Protein', value: _macro(macros, const ['protein_g', 'protein'])),
        _SmallValueChip(label: 'Carbs', value: _macro(macros, const ['carbohydrate_g', 'carbohydrates_g', 'carbs_g', 'carbs'])),
        _SmallValueChip(label: 'Fat', value: _macro(macros, const ['fat_g', 'total_fat_g', 'fat'])),
        _SmallValueChip(label: 'Fiber', value: _macro(macros, const ['fiber_g', 'fibre_g', 'dietary_fiber_g'])),
      ],
    );
  }
}

class _SmallValueChip extends StatelessWidget {
  const _SmallValueChip({required this.label, required this.value});
  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    return Chip(label: Text('$label ${value.toStringAsFixed(1)} g'));
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({required this.label, required this.value, required this.icon});
  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon),
            const SizedBox(height: 16),
            Text(
              value,
              style: theme.textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 4),
            Text(label),
          ],
        ),
      ),
    );
  }
}

class _MacroTile extends StatelessWidget {
  const _MacroTile({required this.label, required this.value});
  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(label, style: theme.textTheme.bodyLarge),
          const SizedBox(height: 4),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              '${value.toStringAsFixed(1)} g',
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProgressRow extends StatelessWidget {
  const _ProgressRow({required this.label, required this.percent});
  final String label;
  final double percent;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(child: Text(label)),
              Text('${percent.round()}%'),
            ],
          ),
          const SizedBox(height: 7),
          LinearProgressIndicator(
            value: (percent / 100).clamp(0.0, 1.0).toDouble(),
            borderRadius: BorderRadius.circular(999),
            minHeight: 7,
            color: percent > 100
                ? theme.colorScheme.error
                : theme.colorScheme.primary,
          ),
        ],
      ),
    );
  }
}

class _ScoreRow extends StatelessWidget {
  const _ScoreRow({required this.label, required this.score});
  final String label;
  final double score;

  @override
  Widget build(BuildContext context) {
    return _ProgressRow(label: label, percent: score);
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          const SizedBox(width: 12),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w900,
          ),
    );
  }
}

class _EmptyInsights extends StatelessWidget {
  const _EmptyInsights({required this.theme});
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 70),
      child: Column(
        children: [
          Icon(
            Icons.insights_rounded,
            size: 68,
            color: theme.colorScheme.primary,
          ),
          const SizedBox(height: 18),
          Text(
            'No insights yet',
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Analyze meals to build daily nutrition and health trends.',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyLarge?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

double _macro(Map<String, double> source, List<String> keys) {
  for (final key in keys) {
    final value = source[key];
    if (value != null) return value;
  }
  return 0;
}

String _friendlyName(String value) {
  const aliases = <String, String>{
    'protein_g': 'Protein',
    'carbohydrate_g': 'Carbohydrates',
    'fat_g': 'Fat',
    'fiber_g': 'Fiber',
  };
  if (aliases[value] != null) return aliases[value]!;
  return value
      .replaceAll(RegExp(r'_(mg|ug|mcg|g)$'), '')
      .replaceAll('_', ' ')
      .split(RegExp(r'\s+'))
      .where((word) => word.isNotEmpty)
      .map((word) => '${word[0].toUpperCase()}${word.substring(1).toLowerCase()}')
      .join(' ');
}

String _formatNutrient(String key, double value) {
  final unit = key.endsWith('_ug') || key.endsWith('_mcg')
      ? 'µg'
      : key.endsWith('_mg')
          ? 'mg'
          : key.endsWith('_g')
              ? 'g'
              : '';
  final text = value >= 100
      ? value.toStringAsFixed(0)
      : value >= 10
          ? value.toStringAsFixed(1)
          : value.toStringAsFixed(2);
  return unit.isEmpty ? text : '$text $unit';
}

String _fullDate(DateTime date) {
  const months = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ];
  return '${date.day} ${months[date.month - 1]} ${date.year}';
}
