import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../history/providers/analysis_history_provider.dart';
import '../../../profile/providers/profile_provider.dart';
import '../../../recommendation/models/post_analysis_recommendations.dart';
import '../../../recommendation/services/recommendation_service.dart';
import '../../models/analysis_result.dart';
import '../widgets/food_card.dart';
import '../widgets/health_score_card.dart';
import '../widgets/macro_circle.dart';
import '../widgets/micronutrient_bar.dart';
import '../widgets/nutrient_target_view_data.dart';
import '../widgets/score_gauge.dart';
import '../../share/services/meal_share_service.dart';

class ResultScreen extends ConsumerStatefulWidget {
  const ResultScreen({
    super.key,
    required this.result,
    required this.rawResult,
  });

  final AnalysisResult result;
  final Map<String, dynamic> rawResult;

  @override
  ConsumerState<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends ConsumerState<ResultScreen> {
  final _recommendationService = RecommendationService();
  PostAnalysisRecommendations? _recommendations;
  bool _recommendationsLoading = false;
  String? _recommendationError;
  String? _applyingRecommendationId;
  late List<String> _mealImagePaths;

  AnalysisResult get result => widget.result;

  @override
  void initState() {
    super.initState();
    _mealImagePaths = List<String>.from(widget.result.mealImagePaths);
    if (_mealImagePaths.isEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _resolveHistoryImages());
    }
  }

  Future<void> _resolveHistoryImages() async {
    final id = _analysisId(widget.rawResult);
    if (!mounted || id == null || id.isEmpty) return;
    for (final record in ref.read(analysisHistoryProvider)) {
      if (record.analysisId != id) continue;
      if (record.mealImagePaths.isNotEmpty && mounted) {
        setState(() => _mealImagePaths = List<String>.from(record.mealImagePaths));
      }
      return;
    }
  }

  Future<void> _shareMeal() async {
    try {
      await MealShareService.instance.shareMeal(context: context, result: result, imagePaths: _mealImagePaths);
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not create the share card: $error')));
    }
  }

  Future<void> _loadRecommendations() async {
    if (!mounted) return;
    setState(() {
      _recommendationsLoading = true;
      _recommendationError = null;
    });

    final now = DateTime.now();
    final history = ref.read(analysisHistoryProvider);
    final currentId = _analysisId(widget.rawResult);
    final matchingRecords = history
        .where((record) => currentId != null && record.analysisId == currentId)
        .toList();
    final matchingRecord = matchingRecords.isEmpty ? null : matchingRecords.first;
    if (matchingRecord != null && !_sameLocalDay(matchingRecord.createdAt, now)) {
      if (mounted) {
        setState(() {
          _recommendationsLoading = false;
          _recommendationError = null;
        });
      }
      return;
    }

    final todayResults = history
        .where((record) => _sameLocalDay(record.createdAt, now))
        .where((record) => currentId == null || record.analysisId != currentId)
        .map((record) => record.rawResult)
        .where((result) => result.isNotEmpty)
        .map(Map<String, dynamic>.from)
        .toList(growable: false);

    try {
      if (ref.read(profileProvider).isLoading) {
        await ref.read(profileProvider.notifier).loadProfile();
        if (!mounted) return;
      }
      final recommendations = await _recommendationService.afterAnalysis(
        currentResult: widget.rawResult,
        todayResults: todayResults,
        profile: ref.read(profileProvider).backendPayload,
        localHour: now.hour,
      );
      if (!mounted) return;
      setState(() {
        _recommendations = recommendations;
        _recommendationsLoading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _recommendationsLoading = false;
        _recommendationError = error.toString();
      });
    }
  }

  List<Map<String, dynamic>> _todayResultsExcludingCurrent(DateTime now) {
    final history = ref.read(analysisHistoryProvider);
    final currentId = _analysisId(widget.rawResult);
    return history
        .where((record) => _sameLocalDay(record.createdAt, now))
        .where((record) => currentId == null || record.analysisId != currentId)
        .map((record) => record.rawResult)
        .where((result) => result.isNotEmpty)
        .map(Map<String, dynamic>.from)
        .toList(growable: false);
  }

  Future<void> _applyRecommendation(FoodRecommendation item) async {
    if (_applyingRecommendationId != null) return;
    final now = DateTime.now();
    setState(() {
      _applyingRecommendationId = item.id;
      _recommendationError = null;
    });
    try {
      final combined = await _recommendationService.applyToMeal(
        currentResult: widget.rawResult,
        todayResults: _todayResultsExcludingCurrent(now),
        recommendationId: item.id,
        recommendation: item.rawPayload,
        profile: ref.read(profileProvider).backendPayload,
        localHour: now.hour,
      );
      await ref.read(analysisHistoryProvider.notifier).saveResult(combined);
      if (!mounted) return;
      context.pushReplacement('/result', extra: combined);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _applyingRecommendationId = null;
        _recommendationError = error.toString();
      });
    }
  }

  void _showNutrientDetails(
    BuildContext context, {
    required String title,
    required String nutrientKey,
    required double amount,
    required String unit,
    List<_NutrientDetailItem> summaryValues = const [],
    String summaryTitle = 'Coverage summary',
    String? summaryNote,
    List<_NutrientDetailItem> relatedValues = const [],
    String breakdownTitle = 'Breakdown',
    String? breakdownNote,
    String contributorTitle = 'Food contributors',
    String? contributorNote,
  }) {
    final contributions = result.contributionsFor(nutrientKey);

    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) {
        final theme = Theme.of(sheetContext);

        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: 0.52,
          minChildSize: 0.35,
          maxChildSize: 0.88,
          builder: (context, scrollController) {
            return ListView(
              controller: scrollController,
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
              children: [
                Text(
                  title,
                  style: theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  '${_formatNumber(amount)} $unit total',
                  style: theme.textTheme.bodyLarge?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                if (summaryValues.any((item) => item.available)) ...[
                  const SizedBox(height: 20),
                  Text(
                    summaryTitle,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  if (summaryNote != null && summaryNote.trim().isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      summaryNote,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                        height: 1.4,
                      ),
                    ),
                  ],
                  const SizedBox(height: 10),
                  _NutrientDetailList(items: summaryValues),
                ],
                if (relatedValues.any((item) => item.available)) ...[
                  const SizedBox(height: 20),
                  Text(
                    breakdownTitle,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  if (breakdownNote != null &&
                      breakdownNote.trim().isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      breakdownNote,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                        height: 1.4,
                      ),
                    ),
                  ],
                  const SizedBox(height: 10),
                  _NutrientDetailList(items: relatedValues),
                ],
                if (contributions.isNotEmpty) ...[
                  const SizedBox(height: 20),
                  Text(
                    contributorTitle,
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  if (contributorNote != null &&
                      contributorNote.trim().isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      contributorNote,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                        height: 1.4,
                      ),
                    ),
                  ],
                  const SizedBox(height: 10),
                  ...contributions.map(
                    (item) => Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 14,
                        ),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.surfaceContainerLow,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: theme.colorScheme.outlineVariant,
                          ),
                        ),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                item.foodName,
                                style: theme.textTheme.titleSmall?.copyWith(
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Text(
                              '${_formatNumber(item.amount)} $unit',
                              style: theme.textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ],
            );
          },
        );
      },
    );
  }

  void _showHealthScoreDetails(
    BuildContext context,
    HealthScore score,
  ) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (sheetContext) {
        final theme = Theme.of(sheetContext);

        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: 0.72,
          minChildSize: 0.45,
          maxChildSize: 0.92,
          builder: (context, scrollController) {
            return ListView(
              controller: scrollController,
              padding: const EdgeInsets.fromLTRB(
                20,
                4,
                20,
                30,
              ),
              children: [
                Text(
                  score.label,
                  style:
                      theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  '${score.score.toStringAsFixed(0)} / 100',
                  style:
                      theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _ScoreMetricChip(
                      label: 'Confidence',
                      value:
                          '${(score.confidence * 100).round()}%',
                    ),
                    _ScoreMetricChip(
                      label: 'Coverage',
                      value:
                          '${(score.coverage * 100).round()}%',
                    ),
                    _ScoreMetricChip(
                      label: 'Reliability',
                      value:
                          '${(score.reliability * 100).round()}%',
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                _HealthContributorSection(
                  title: 'Positive contributors',
                  emptyText:
                      'No positive contributor was identified.',
                  contributors:
                      score.positiveContributors,
                  positive: true,
                ),
                const SizedBox(height: 22),
                _HealthContributorSection(
                  title: 'Negative contributors',
                  emptyText:
                      'No negative contributor was identified.',
                  contributors:
                      score.negativeContributors,
                  positive: false,
                ),
              ],
            );
          },
        );
      },
    );
  }

  NutrientTargetViewData _targetFor(
    String nutrientKey,
    double fallbackValue,
    String fallbackUnit,
  ) {
    if (result.personalizationApplied) {
      final personalizedTarget = result.targetForNutrient(nutrientKey);
      if (personalizedTarget != null && personalizedTarget.isResolved) {
        return NutrientTargetViewData.personalized(
          personalizedTarget,
          fallbackValue: fallbackValue,
          fallbackUnit: fallbackUnit,
        );
      }
    }

    if (nutrientKey == 'carbohydrate_g') {
      return NutrientTargetViewData.generic(
        value: 220,
        upperBound: 330,
        unit: fallbackUnit,
        targetType: 'range',
      );
    }
    if (nutrientKey == 'fat_g') {
      return NutrientTargetViewData.generic(
        value: 62.4,
        upperBound: 93.6,
        unit: fallbackUnit,
        targetType: 'range',
      );
    }
    return NutrientTargetViewData.generic(
      value: fallbackValue,
      unit: fallbackUnit,
      targetType: 'minimum',
    );
  }

  double _reportedMajorFatTotal() {
    final reported = (result.saturatedFat ?? 0) +
        (result.monounsaturatedFat ?? 0) +
        (result.polyunsaturatedFat ?? 0);
    return reported.clamp(0, result.fat).toDouble();
  }

  double _unclassifiedFat() =>
      (result.fat - _reportedMajorFatTotal()).clamp(0, result.fat).toDouble();

  List<_NutrientDetailItem> _carbohydrateDetails() {
    final items = <_NutrientDetailItem>[
      _NutrientDetailItem(
        label: 'Total carbohydrate',
        value: result.carbohydrates,
        unit: 'g',
        available: true,
      ),
    ];

    void addReported(
      String label,
      String key, {
      bool nested = false,
      bool showContributors = false,
    }) {
      final value = result.carbohydrateComposition[key];
      if (value == null) return;
      items.add(
        _NutrientDetailItem(
          label: nested ? '  ↳ $label' : label,
          value: value,
          unit: 'g',
          available: true,
          contributors:
              showContributors ? result.contributionsFor(key) : const [],
        ),
      );
    }

    addReported(
      'Carbohydrate, by difference',
      'carbohydrate_by_difference_g',
    );
    addReported(
      'Carbohydrate, by summation',
      'carbohydrate_by_summation_g',
    );
    addReported('Dietary fiber', 'fiber_g');

    items.add(
      _NutrientDetailItem(
        label: 'Total sugars',
        value: result.sugars ?? 0,
        unit: 'g',
        available: result.sugars != null,
        contributors: result.contributionsFor('sugars_g'),
      ),
    );
    if (result.addedSugars != null) {
      items.add(
        _NutrientDetailItem(
          label: '  ↳ Added sugars',
          value: result.addedSugars!,
          unit: 'g',
          available: true,
          contributors: result.contributionsFor('added_sugars_g'),
        ),
      );
    }

    addReported('Sucrose', 'sucrose_g', nested: true, showContributors: true);
    addReported('Glucose', 'glucose_g', nested: true, showContributors: true);
    addReported('Fructose', 'fructose_g', nested: true, showContributors: true);
    addReported('Lactose', 'lactose_g', nested: true, showContributors: true);
    addReported('Maltose', 'maltose_g', nested: true, showContributors: true);
    addReported('Galactose', 'galactose_g', nested: true, showContributors: true);
    addReported('Starch', 'starch_g');
    addReported('Component-derived carbohydrate', 'component_sum_g');

    return items;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final macros = <_MacroItem>[
      _MacroItem(
        label: 'Protein',
        value: result.protein,
        target: _targetFor('protein_g', 50, 'g'),
        nutrientKey: 'protein_g',
        icon: Icons.fitness_center_rounded,
      ),
      _MacroItem(
        label: 'Carbohydrates',
        value: result.carbohydrates,
        target: _targetFor('carbohydrate_g', 275, 'g'),
        nutrientKey: 'carbohydrate_g',
        icon: Icons.grain_rounded,
      ),
      _MacroItem(
        label: 'Fat',
        value: result.fat,
        target: _targetFor('fat_g', 78, 'g'),
        nutrientKey: 'fat_g',
        icon: Icons.water_drop_outlined,
      ),
      _MacroItem(
        label: 'Fiber',
        value: result.fiber,
        target: _targetFor('fiber_g', 28, 'g'),
        nutrientKey: 'fiber_g',
        icon: Icons.eco_outlined,
      ),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Meal analysis'),
        leading: IconButton(
          onPressed: () => context.canPop()
              ? context.pop()
              : context.go('/app'),
          icon: const Icon(Icons.arrow_back_rounded),
        ),
        actions: [
          IconButton(
            tooltip: 'Share meal analysis',
            onPressed: _shareMeal,
            icon: const Icon(Icons.ios_share_rounded),
          ),
        ],
      ),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final horizontalPadding = constraints.maxWidth >= 700 ? 32.0 : 20.0;
            final contentWidth = constraints.maxWidth >= 900 ? 820.0 : double.infinity;

            return SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(
                horizontalPadding,
                12,
                horizontalPadding,
                36,
              ),
              child: Align(
                alignment: Alignment.topCenter,
                child: ConstrainedBox(
                  constraints: BoxConstraints(maxWidth: contentWidth),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        result.mealName,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
                      ),
                      if (_mealImagePaths.isNotEmpty) ...[
                        const SizedBox(height: 14),
                        _MealPhotoStrip(paths: _mealImagePaths),
                      ],
                      if (result.summary != null && result.summary!.trim().isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Text(
                          result.summary!,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant, height: 1.3),
                        ),
                      ],
                      const SizedBox(height: 24),
                      _OverviewCard(result: result),
                      const SizedBox(height: 24),
                      _RecommendationSection(
                        loading: _recommendationsLoading,
                        recommendations: _recommendations,
                        error: _recommendationError,
                        onRetry: _loadRecommendations,
                        applyingRecommendationId: _applyingRecommendationId,
                        onApply: _applyRecommendation,
                      ),
                      if (result.displayFoods.isNotEmpty) ...[
                        const SizedBox(height: 28),
                        const _SectionTitle('Detected foods', icon: Icons.restaurant_rounded),
                        const SizedBox(height: 14),
                        ...result.displayFoods.map(
                          (food) => Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: FoodCard(food: food),
                          ),
                        ),
                      ],
                      const SizedBox(height: 28),
                      const _SectionTitle('Macronutrients', icon: Icons.pie_chart_outline_rounded),
                      const SizedBox(height: 14),
                      LayoutBuilder(
                        builder: (context, gridConstraints) {
                          final width = gridConstraints.maxWidth;
                          final columns = width >= 720 ? 4 : 2;
                          const spacing = 12.0;
                          final itemWidth =
                              (width - spacing * (columns - 1)) / columns;

                          return Wrap(
                            spacing: spacing,
                            runSpacing: spacing,
                            children: [
                              for (final macro in macros)
                                SizedBox(
                                  width: itemWidth,
                                  child: MacroCircle(
                                    label: macro.label,
                                    value: macro.value,
                                    target: macro.target,
                                    icon: macro.icon,
                                    onTap: () {
                                    if (macro.nutrientKey == 'fat_g') {
                                      _showNutrientDetails(
                                        context,
                                        title: 'Fat',
                                        nutrientKey: 'fat_g',
                                        amount: result.fat,
                                        unit: 'g',
                                        summaryTitle: 'How the total is covered',
                                        summaryNote:
                                            'Total fat is authoritative; reported subtypes may not add up.',
                                        summaryValues: [
                                          _NutrientDetailItem(
                                            label: 'Total fat',
                                            value: result.fat,
                                            unit: 'g',
                                            available: true,
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Reported major subtypes',
                                            value: _reportedMajorFatTotal(),
                                            unit: 'g',
                                            available: result.saturatedFat != null ||
                                                result.monounsaturatedFat != null ||
                                                result.polyunsaturatedFat != null,
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Not classified by source',
                                            value: _unclassifiedFat(),
                                            unit: 'g',
                                            available: _unclassifiedFat() > 0.0001,
                                          ),
                                        ],
                                        breakdownTitle: 'Reported fat details',
                                        breakdownNote:
                                            'Saturated, mono- and polyunsaturated fat are the main classes. Omega-3/6 are polyunsaturated subsets.',
                                        contributorTitle:
                                            'Total-fat contributors',
                                        contributorNote:
                                            'These values show how much total fat each food contributed. They are not saturated-fat or unsaturated-fat amounts.',
                                        relatedValues: [
                                          _NutrientDetailItem(
                                            label: 'Saturated fat',
                                            value: result.saturatedFat ?? 0,
                                            unit: 'g',
                                            available: result.saturatedFat != null,
                                            contributors: result.contributionsFor(
                                              'saturated_fat_g',
                                            ),
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Monounsaturated fat',
                                            value: result.monounsaturatedFat ?? 0,
                                            unit: 'g',
                                            available: result.monounsaturatedFat != null,
                                            contributors: result.contributionsFor(
                                              'monounsaturated_fat_g',
                                            ),
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Polyunsaturated fat',
                                            value: result.polyunsaturatedFat ?? 0,
                                            unit: 'g',
                                            available: result.polyunsaturatedFat != null,
                                            contributors: result.contributionsFor(
                                              'polyunsaturated_fat_g',
                                            ),
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Trans fat',
                                            value: result.transFat ?? 0,
                                            unit: 'g',
                                            available: result.transFat != null,
                                            contributors: result.contributionsFor(
                                              'trans_fat_g',
                                            ),
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Omega-3',
                                            value: result.omega3 ?? 0,
                                            unit: 'g',
                                            available: result.omega3 != null,
                                            contributors: result.contributionsFor(
                                              'omega3_g',
                                            ),
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Omega-6',
                                            value: result.omega6 ?? 0,
                                            unit: 'g',
                                            available: result.omega6 != null,
                                            contributors: result.contributionsFor(
                                              'omega6_g',
                                            ),
                                          ),
                                          _NutrientDetailItem(
                                            label: 'Cholesterol',
                                            value: result.cholesterol ?? 0,
                                            unit: 'mg',
                                            available: result.cholesterol != null,
                                            contributors: result.contributionsFor(
                                              'cholesterol_mg',
                                            ),
                                          ),
                                        ],
                                      );

                                      return;
                                    }

                                    if (macro.nutrientKey == 'carbohydrate_g') {
                                      _showNutrientDetails(
                                        context,
                                        title: macro.label,
                                        nutrientKey: macro.nutrientKey,
                                        amount: macro.value,
                                        unit: 'g',
                                        breakdownTitle: 'Carbohydrate composition',
                                        breakdownNote:
                                            'Sugars, starch and fiber are components of total carbohydrate.',
                                        relatedValues:
                                            _carbohydrateDetails(),
                                      );

                                      return;
                                    }

                                    _showNutrientDetails(
                                      context,
                                      title: macro.label,
                                      nutrientKey: macro.nutrientKey,
                                      amount: macro.value,
                                      unit: 'g',
                                    );
                                  },
                                  ),
                                ),
                            ],
                          );
                        },
                      ),
                      if (result.healthScores.isNotEmpty) ...[
                        const SizedBox(height: 32),
                        const _SectionTitle('Health scores', icon: Icons.favorite_rounded),
                        const SizedBox(height: 14),
                        ...result.healthScores.map(
                          (score) => Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            // child: HealthScoreCard(item: score),
                            child: HealthScoreCard(
                              item: score,
                                onTap: () => _showHealthScoreDetails(
                                  context,
                                  score,
                                ),
                              ),
                          ),
                        ),
                      ],
                      if (result.micronutrients.isNotEmpty) ...[
                        const SizedBox(height: 32),
                        const _SectionTitle('Micronutrients', icon: Icons.science_outlined),
                        const SizedBox(height: 14),
                        Column(
                          children: [
                            for (var index = 0;
                                index < result.micronutrients.length;
                                index++)
                              Padding(
                                padding: EdgeInsets.only(
                                  bottom: index < result.micronutrients.length - 1
                                      ? 10
                                      : 0,
                                ),
                                child: MicronutrientBar(
                                  nutrient: result.micronutrients[index],
                                  target: _targetFor(
                                    result.micronutrients[index].key,
                                    result.micronutrients[index].dailyValue,
                                    result.micronutrients[index].unit,
                                  ),
                                  onTap: () {
                                    final nutrient = result.micronutrients[index];
                                    _showNutrientDetails(
                                      context,
                                      title: nutrient.label,
                                      nutrientKey: nutrient.key,
                                      amount: nutrient.amount,
                                      unit: nutrient.unit,
                                    );
                                  },
                                ),
                              ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Text(
                          result.personalizationApplied
                              ? 'Tap a nutrient for contributors. Percentages use your personalized target.'
                              : 'Tap a nutrient for contributors. Percentages use general references.',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                            height: 1.4,
                          ),
                        ),
                      ],
                      if (result.personalizationApplied &&
                          result.nutrientRiskFlags.isNotEmpty) ...[
                        const SizedBox(height: 22),
                        const _SectionTitle('Personalization notes', icon: Icons.tune_rounded),
                        const SizedBox(height: 12),
                        ...result.nutrientRiskFlags.map(
                          (flag) => Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: _RiskFlagCard(flag: flag),
                          ),
                        ),
                      ],
                      const SizedBox(height: 28),
                      SizedBox(
                        height: 52,
                        child: FilledButton.icon(
                          onPressed: () => context.push('/upload'),
                          icon: const Icon(Icons.add_a_photo_outlined),
                          label: const Text('Analyze another meal'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  String _formatNumber(double value) {
    return value >= 10 ? value.toStringAsFixed(1) : value.toStringAsFixed(2);
  }
}

String? _analysisId(Map<String, dynamic> result) {
  final direct = result['analysis_id']?.toString().trim();
  if (direct != null && direct.isNotEmpty) return direct;
  for (final key in const ['final_result', 'meal_analysis', 'data', 'result']) {
    final nested = result[key];
    if (nested is! Map) continue;
    final value = nested['analysis_id']?.toString().trim();
    if (value != null && value.isNotEmpty) return value;
  }
  return null;
}

bool _sameLocalDay(DateTime a, DateTime b) {
  final left = a.toLocal();
  final right = b.toLocal();
  return left.year == right.year &&
      left.month == right.month &&
      left.day == right.day;
}

class _RecommendationSection extends StatelessWidget {
  const _RecommendationSection({
    required this.loading,
    required this.recommendations,
    required this.error,
    required this.onRetry,
    required this.applyingRecommendationId,
    required this.onApply,
  });

  final bool loading;
  final PostAnalysisRecommendations? recommendations;
  final String? error;
  final VoidCallback onRetry;
  final String? applyingRecommendationId;
  final ValueChanged<FoodRecommendation> onApply;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: scheme.primaryContainer.withOpacity(0.45),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: scheme.primary.withOpacity(0.22)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: scheme.primary,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(Icons.auto_awesome_rounded, color: scheme.onPrimary),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Improve this meal’s weakest score',
                      style: theme.textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    Text(
                      loading
                          ? 'Finding safe food options…'
                          : recommendations == null
                              ? 'Get a few targeted food swaps.'
                              : '${recommendations!.mealsIncluded} '
                                  '${recommendations!.mealsIncluded == 1 ? 'meal' : 'meals'} '
                                  'included · ${recommendations!.context}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              if (!loading && (recommendations != null || error != null))
                IconButton(
                  tooltip: 'Recalculate',
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh_rounded),
                ),
            ],
          ),
          if (loading) ...[
            const SizedBox(height: 18),
            const LinearProgressIndicator(),
          ] else if (recommendations == null && error == null) ...[
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.restaurant_menu_rounded),
              label: const Text('Find food recommendations'),
            ),
          ] else if (error != null) ...[
            const SizedBox(height: 14),
            Text(
              error!,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: scheme.error,
              ),
            ),
          ] else if (recommendations != null) ...[
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _RecommendationScoreTile(
                    label: 'Current meal',
                    value: recommendations!.currentDayScore,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _RecommendationScoreTile(
                    label: 'Nutrient balance',
                    value: recommendations!.nutritionBalanceScore,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            if (recommendations!.items.isEmpty)
              Text(
                recommendations!.message,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: scheme.onSurfaceVariant,
                  height: 1.4,
                ),
              )
            else
              ...recommendations!.items.map(
                (item) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _FoodRecommendationCard(
                    item: item,
                    applying: applyingRecommendationId == item.id,
                    applyDisabled: applyingRecommendationId != null,
                    onApply: () => onApply(item),
                  ),
                ),
              ),
            if (recommendations!.items.isNotEmpty &&
                recommendations!.disclaimer.trim().isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                recommendations!.disclaimer,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                  height: 1.35,
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }
}

class _RecommendationScoreTile extends StatelessWidget {
  const _RecommendationScoreTile({required this.label, required this.value});

  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface.withOpacity(0.72),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            value.toStringAsFixed(0),
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w900,
            ),
          ),
          Text(label, style: theme.textTheme.bodySmall),
        ],
      ),
    );
  }
}

class _FoodRecommendationCard extends StatelessWidget {
  const _FoodRecommendationCard({
    required this.item,
    required this.applying,
    required this.applyDisabled,
    required this.onApply,
  });

  final FoodRecommendation item;
  final bool applying;
  final bool applyDisabled;
  final VoidCallback onApply;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: scheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
                decoration: BoxDecoration(
                  color: scheme.secondaryContainer,
                  borderRadius: BorderRadius.circular(99),
                ),
                child: Text(
                  item.actionLabel,
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: scheme.onSecondaryContainer,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              const Spacer(),
              Icon(Icons.trending_up_rounded, color: scheme.primary, size: 18),
              const SizedBox(width: 4),
              Text(
                '+${(item.targetDomain?.delta ?? item.scoreDelta).toStringAsFixed(1)}',
                style: theme.textTheme.labelLarge?.copyWith(
                  color: scheme.primary,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            item.title,
            style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 5),
          Text(
            item.reason,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.bodyMedium?.copyWith(color: scheme.onSurfaceVariant, height: 1.25),
          ),
          const SizedBox(height: 10),
          if (item.targetDomain != null)
            Text(
              '${item.targetDomain!.label}: '
              '${item.targetDomain!.before.toStringAsFixed(0)} → '
              '${item.targetDomain!.after.toStringAsFixed(0)} '
              '(+${item.targetDomain!.delta.toStringAsFixed(1)})',
              style: theme.textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.w800,
                color: scheme.primary,
              ),
            )
          else
            Text(
              'Combined meal score: '
              '${item.baselineScore.toStringAsFixed(0)} → '
              '${item.predictedScore.toStringAsFixed(0)}',
              style: theme.textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
          if (item.nutrientEffects.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: item.nutrientEffects.take(3).map((effect) {
                return Chip(
                  visualDensity: VisualDensity.compact,
                  label: Text(effect.label),
                );
              }).toList(growable: false),
            ),
          ],
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton.icon(
              onPressed: applyDisabled ? null : onApply,
              icon: applying
                  ? const SizedBox.square(
                      dimension: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.add_circle_outline_rounded),
              label: Text(applying ? 'Updating meal…' : 'Apply to this meal'),
            ),
          ),
        ],
      ),
    );
  }
}

String _displayFeatureName(String value) {
  return value
      .replaceAll('_', ' ')
      .split(RegExp(r'\s+'))
      .where((word) => word.isNotEmpty)
      .map(
        (word) =>
            '${word[0].toUpperCase()}'
            '${word.substring(1).toLowerCase()}',
      )
      .join(' ');
}

class _MealPhotoStrip extends StatelessWidget {
  const _MealPhotoStrip({required this.paths});
  final List<String> paths;

  @override
  Widget build(BuildContext context) {
    final existing = paths.where((path) => File(path).existsSync()).toList(growable: false);
    if (existing.isEmpty) return const SizedBox.shrink();
    return SizedBox(
      height: 210,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: existing.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (context, index) => ClipRRect(
          borderRadius: BorderRadius.circular(22),
          child: SizedBox(
            width: existing.length == 1 ? (MediaQuery.sizeOf(context).width - 40).clamp(260.0, 820.0).toDouble() : 300,
            child: Image.file(File(existing[index]), fit: BoxFit.cover, errorBuilder: (_, __, ___) => Center(child: Icon(Icons.broken_image_outlined, color: Theme.of(context).colorScheme.onSurfaceVariant))),
          ),
        ),
      ),
    );
  }
}

class _OverviewCard extends StatelessWidget {
  const _OverviewCard({required this.result});

  final AnalysisResult result;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(26),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 460;
          final score = ScoreGauge(score: result.overallScore, size: compact ? 140 : 154);
          final calories = _CaloriesCard(calories: result.calories);

          if (compact) {
            return Column(
              children: [
                score,
                const SizedBox(height: 18),
                calories,
              ],
            );
          }

          return Row(
            children: [
              score,
              const SizedBox(width: 24),
              Expanded(child: calories),
            ],
          );
        },
      ),
    );
  }
}

class _CaloriesCard extends StatelessWidget {
  const _CaloriesCard({required this.calories});

  final double calories;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          Icon(
            Icons.local_fire_department_rounded,
            size: 34,
            color: theme.colorScheme.onPrimaryContainer,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Energy',
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: theme.colorScheme.onPrimaryContainer,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${calories.round()} kcal',
                  style: theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                    color: theme.colorScheme.onPrimaryContainer,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RiskFlagCard extends StatelessWidget {
  const _RiskFlagCard({required this.flag});

  final NutrientRiskFlag flag;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.tertiaryContainer,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.info_outline_rounded,
            color: theme.colorScheme.onTertiaryContainer,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              flag.message ?? flag.id.replaceAll('_', ' '),
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onTertiaryContainer,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text, {this.icon});
  final String text;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(children: [
      if (icon != null) ...[
        Icon(icon, size: 22, color: theme.colorScheme.primary),
        const SizedBox(width: 9),
      ],
      Expanded(child: Text(text, style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800))),
    ]);
  }
}

class _MacroItem {
  const _MacroItem({
    required this.label,
    required this.value,
    required this.target,
    required this.nutrientKey,
    required this.icon,
  });

  final String label;
  final double value;
  final NutrientTargetViewData target;
  final String nutrientKey;
  final IconData icon;
}

class _NutrientDetailItem {
  const _NutrientDetailItem({
    required this.label,
    required this.value,
    required this.unit,
    required this.available,
    this.contributors = const [],
  });

  final String label;
  final double value;
  final String unit;
  final bool available;
  final List<NutrientContribution> contributors;
}

class _NutrientDetailList extends StatelessWidget {
  const _NutrientDetailList({required this.items});

  final List<_NutrientDetailItem> items;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final visibleItems =
        items.where((item) => item.available).toList(growable: false);
    if (visibleItems.isEmpty) return const SizedBox.shrink();

    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          for (var index = 0; index < visibleItems.length; index++) ...[
            _NutrientDetailRow(item: visibleItems[index]),
            if (index < visibleItems.length - 1)
              Divider(
                height: 1,
                color: theme.colorScheme.outlineVariant,
              ),
          ],
        ],
      ),
    );
  }
}

class _NutrientDetailRow extends StatelessWidget {
  const _NutrientDetailRow({required this.item});

  final _NutrientDetailItem item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final valueText = '${_formatResultNumber(item.value)} ${item.unit}';
    final contributors = item.contributors
        .where((entry) => entry.amount > 0)
        .toList(growable: false);

    if (contributors.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          children: [
            Expanded(
              child: Text(
                item.label,
                style: theme.textTheme.bodyLarge?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Text(
              valueText,
              style: theme.textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      );
    }

    return Theme(
      data: theme.copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 16),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        title: Row(
          children: [
            Expanded(
              child: Text(
                item.label,
                style: theme.textTheme.bodyLarge?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(width: 12),
            Text(
              valueText,
              style: theme.textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
        children: [
          for (final contribution in contributors)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      contribution.foodName,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    '${_formatResultNumber(contribution.amount)} ${item.unit}'
                    '${item.value > 0 ? ' · ${_resultContributionPercent(contribution.amount, item.value)}' : ''}',
                    style: theme.textTheme.labelMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

String _resultContributionPercent(double amount, double total) {
  if (amount <= 0 || total <= 0) return '';
  final percentage = amount / total * 100;
  if (percentage < 1) return '<1%';
  return '${percentage.toStringAsFixed(0)}%';
}

String _formatResultNumber(double value) =>
    value >= 10 ? value.toStringAsFixed(1) : value.toStringAsFixed(2);

class _ScoreMetricChip extends StatelessWidget {
  const _ScoreMetricChip({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 12,
        vertical: 8,
      ),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
        ),
      ),
      child: Text(
        '$label: $value',
        style: theme.textTheme.labelLarge?.copyWith(
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _HealthContributorSection
    extends StatelessWidget {
  const _HealthContributorSection({
    required this.title,
    required this.emptyText,
    required this.contributors,
    required this.positive,
  });

  final String title;
  final String emptyText;
  final List<HealthContributor> contributors;
  final bool positive;

  List<HealthContributor> get _uniqueContributors {
    final unique = <String, HealthContributor>{};

    for (final contributor in contributors) {
      final key = [
        contributor.ruleName.trim().toLowerCase(),
        contributor.feature.trim().toLowerCase(),
        (contributor.mechanism ?? '').trim().toLowerCase(),
        positive ? 'positive' : 'negative',
      ].join('|');

      final existing = unique[key];
      if (existing == null ||
          contributor.effectiveWeight.abs() >
              existing.effectiveWeight.abs()) {
        unique[key] = contributor;
      }
    }

    return unique.values.toList(growable: false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          title,
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 10),
        if (_uniqueContributors.isEmpty)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color:
                  theme.colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Text(emptyText),
          )
        else
          ..._uniqueContributors.map(
            (contributor) =>
                _HealthContributorTile(
              contributor: contributor,
              positive: positive,
            ),
          ),
      ],
    );
  }
}

class _HealthContributorTile
    extends StatelessWidget {
  const _HealthContributorTile({
    required this.contributor,
    required this.positive,
  });

  final HealthContributor contributor;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            positive
                ? Icons.add_circle_outline_rounded
                : Icons.remove_circle_outline_rounded,
            color: positive
                ? theme.colorScheme.primary
                : theme.colorScheme.error,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment:
                  CrossAxisAlignment.start,
              children: [
                Text(
                  contributor.ruleName,
                  style:
                      theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  _displayFeatureName(
                    contributor.feature,
                  ),
                  style: theme.textTheme.bodyMedium,
                ),
                if (contributor.mechanism != null &&
                    contributor
                        .mechanism!
                        .isNotEmpty) ...[
                  const SizedBox(height: 5),
                  Text(
                    contributor.mechanism!,
                    style:
                        theme.textTheme.bodySmall?.copyWith(
                      color: theme
                          .colorScheme
                          .onSurfaceVariant,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 10),
          _ImpactBadge(
            label: _impactLabel(
              contributor.effectiveWeight,
              positive: positive,
            ),
            positive: positive,
          ),
        ],
      ),
    );
  }
}

String _impactLabel(
  double effectiveWeight, {
  required bool positive,
}) {
  final magnitude = effectiveWeight.abs();

  String strength;
  if (magnitude >= 0.75) {
    strength = 'Very strong';
  } else if (magnitude >= 0.45) {
    strength = 'Strong';
  } else if (magnitude >= 0.20) {
    strength = 'Moderate';
  } else {
    strength = 'Small';
  }

  return '$strength ${positive ? 'benefit' : 'concern'}';
}

class _ImpactBadge extends StatelessWidget {
  const _ImpactBadge({
    required this.label,
    required this.positive,
  });

  final String label;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final foreground = positive
        ? theme.colorScheme.primary
        : theme.colorScheme.error;
    final background = foreground.withAlpha(31);

    return Container(
      constraints: const BoxConstraints(maxWidth: 96),
      padding: const EdgeInsets.symmetric(
        horizontal: 9,
        vertical: 6,
      ),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        textAlign: TextAlign.center,
        style: theme.textTheme.labelSmall?.copyWith(
          color: foreground,
          fontWeight: FontWeight.w800,
          height: 1.15,
        ),
      ),
    );
  }
}
