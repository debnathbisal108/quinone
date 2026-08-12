import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../history/providers/analysis_history_provider.dart';
import '../../../profile/providers/profile_provider.dart';
import '../../../upload/models/analysis_job_progress.dart';
import '../../models/manual_recipe.dart';
import '../../models/usda_food_suggestion.dart';
import '../../repositories/saved_recipe_repository.dart';
import '../../services/recipe_service.dart';

class RecipeBuilderScreen extends ConsumerStatefulWidget {
  const RecipeBuilderScreen({
    super.key,
    this.initialRecipe,
    this.photoReview = false,
    this.analysisId,
    this.labelItems = const [],
  });

  final ManualRecipe? initialRecipe;
  final bool photoReview;
  final String? analysisId;
  final List<Map<String, dynamic>> labelItems;

  @override
  ConsumerState<RecipeBuilderScreen> createState() => _RecipeBuilderScreenState();
}

class _RecipeBuilderScreenState extends ConsumerState<RecipeBuilderScreen> {
  final _searchController = TextEditingController();
  final _nameController = TextEditingController(text: 'My recipe');
  final _servingsMadeController = TextEditingController(text: '1');
  final _servingsEatenController = TextEditingController(text: '1');
  final _service = RecipeService();
  final _savedRepository = SavedRecipeRepository();

  Timer? _debounce;
  List<UsdaFoodSuggestion> _suggestions = const [];
  List<ManualRecipeIngredient> _ingredients = const [];
  List<ManualRecipe> _savedRecipes = const [];
  bool _searching = false;
  bool _analyzing = false;
  String? _searchError;
  AnalysisJobProgress? _progress;

  @override
  void initState() {
    super.initState();
    final initial = widget.initialRecipe;
    if (initial != null) {
      _nameController.text = initial.name;
      _servingsMadeController.text = _format(initial.servingsMade);
      _servingsEatenController.text = _format(initial.servingsEaten);
      _ingredients = [...initial.ingredients];
    }
    for (final item in widget.labelItems) {
      final quantity = (item['quantity'] as num?)?.toDouble() ?? 1.0;
      _labelQuantityControllers.add(
        TextEditingController(text: _format(quantity)),
      );
    }
    _loadSaved();
  }

  @override
  void dispose() {
    for (final controller in _labelQuantityControllers) {
      controller.dispose();
    }
    _debounce?.cancel();
    _searchController.dispose();
    _nameController.dispose();
    _servingsMadeController.dispose();
    _servingsEatenController.dispose();
    super.dispose();
  }

  Future<void> _loadSaved() async {
    final items = await _savedRepository.getAll();
    if (mounted) setState(() => _savedRecipes = items);
  }

  void _onSearchChanged(String value) {
    _debounce?.cancel();
    final query = value.trim();
    if (query.length < 2) {
      setState(() {
        _suggestions = const [];
        _searchError = null;
        _searching = false;
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 350), () => _search(query));
  }

  Future<void> _search(String query) async {
    setState(() {
      _searching = true;
      _searchError = null;
    });
    try {
      final results = await _service.searchFoods(query);
      if (!mounted || _searchController.text.trim() != query) return;
      setState(() => _suggestions = results);
    } catch (error) {
      if (!mounted) return;
      setState(() => _searchError = _cleanError(error));
    } finally {
      if (mounted && _searchController.text.trim() == query) {
        setState(() => _searching = false);
      }
    }
  }

  Future<void> _chooseSuggestion(UsdaFoodSuggestion food) async {
    final controller = TextEditingController(text: '100');
    final grams = await showDialog<double>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(food.displayName),
        content: TextField(
          controller: controller,
          autofocus: true,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(
            labelText: 'Amount used',
            suffixText: 'g',
            helperText: 'Enter the ingredient weight used in the full recipe.',
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              final value = double.tryParse(controller.text.trim());
              if (value == null || value <= 0) return;
              Navigator.pop(dialogContext, value);
            },
            child: const Text('Add'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (grams == null || !mounted) return;

    final existingIndex = _ingredients.indexWhere((item) => item.food.fdcId == food.fdcId);
    setState(() {
      if (existingIndex >= 0) {
        final copy = [..._ingredients];
        final current = copy[existingIndex];
        copy[existingIndex] = current.copyWith(grams: current.grams + grams);
        _ingredients = copy;
      } else {
        _ingredients = [..._ingredients, ManualRecipeIngredient(food: food, grams: grams)];
      }
      _searchController.clear();
      _suggestions = const [];
    });
  }

  Future<void> _editIngredient(int index) async {
    final ingredient = _ingredients[index];
    final controller = TextEditingController(text: _format(ingredient.grams));
    final value = await showDialog<double>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(ingredient.food.displayName),
        content: TextField(
          controller: controller,
          autofocus: true,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(labelText: 'Amount', suffixText: 'g'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, -1.0),
            child: const Text('Remove'),
          ),
          FilledButton(
            onPressed: () {
              final parsed = double.tryParse(controller.text.trim());
              if (parsed == null || parsed <= 0) return;
              Navigator.pop(dialogContext, parsed);
            },
            child: const Text('Update'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (value == null || !mounted) return;
    setState(() {
      final copy = [..._ingredients];
      if (value < 0) {
        copy.removeAt(index);
      } else {
        copy[index] = ingredient.copyWith(grams: value);
      }
      _ingredients = copy;
    });
  }

  ManualRecipe? _buildRecipe() {
    if (_ingredients.isEmpty) return null;
    final made = double.tryParse(_servingsMadeController.text.trim()) ?? 1;
    final eaten = double.tryParse(_servingsEatenController.text.trim()) ?? 1;
    if (made <= 0 || eaten <= 0 || eaten > made) return null;
    return ManualRecipe(
      id: DateTime.now().microsecondsSinceEpoch.toString(),
      name: _nameController.text.trim().isEmpty ? 'My recipe' : _nameController.text.trim(),
      ingredients: List.unmodifiable(_ingredients),
      servingsMade: made,
      servingsEaten: eaten,
      source: widget.photoReview ? 'photo_confirmed' : 'manual',
    );
  }

  Future<void> _saveRecipe() async {
    final recipe = _buildRecipe();
    if (recipe == null) {
      _message('Add at least one ingredient and check the serving values.');
      return;
    }
    await _savedRepository.save(recipe);
    await _loadSaved();
    if (mounted) _message('Recipe saved.');
  }

  Future<void> _analyze() async {
    final recipe = _buildRecipe();
    if (recipe == null || _analyzing) {
      if (recipe == null) _message('Add at least one ingredient and check the serving values.');
      return;
    }
    setState(() {
      _analyzing = true;
      _progress = null;
    });
    try {
      final profile = ref.read(profileProvider).backendPayload;
      final analysisId = widget.analysisId?.trim();
      late final Map<String, dynamic> result;
      if (analysisId != null &&
          analysisId.isNotEmpty &&
          widget.labelItems.isNotEmpty) {
        final confirmedLabels = <Map<String, dynamic>>[];
        for (var i = 0; i < widget.labelItems.length; i++) {
          final quantity = double.tryParse(
            _labelQuantityControllers[i].text.trim(),
          );
          if (quantity == null || quantity <= 0) {
            throw const RecipeServiceException(
              'Enter a valid amount for every packaged food.',
            );
          }
          confirmedLabels.add({
            'food_id': widget.labelItems[i]['food_id']?.toString() ?? '',
            'quantity': quantity,
            'unit': widget.labelItems[i]['unit']?.toString() ?? 'serving',
          });
        }
        result = await _service.analyzeConfirmedMixedMeal(
          analysisId: analysisId,
          recipe: recipe,
          labelItems: confirmedLabels,
          onProgress: (progress) {
            if (mounted) setState(() => _progress = progress);
          },
        );
      } else {
        result = await _service.analyzeRecipe(
          recipe: recipe,
          profile: profile,
          onProgress: (progress) {
            if (mounted) setState(() => _progress = progress);
          },
        );
      }
      await ref.read(analysisHistoryProvider.notifier).saveResult(result);
      if (!mounted) return;
      context.pushReplacement('/result', extra: result);
    } catch (error) {
      if (mounted) _message(_cleanError(error));
    } finally {
      if (mounted) setState(() => _analyzing = false);
    }
  }

  void _loadRecipe(ManualRecipe recipe) {
    setState(() {
      _nameController.text = recipe.name;
      _servingsMadeController.text = _format(recipe.servingsMade);
      _servingsEatenController.text = _format(recipe.servingsEaten);
      _ingredients = [...recipe.ingredients];
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Scaffold(
      appBar: AppBar(title: Text(widget.photoReview ? 'Review detected meal' : 'Add recipe')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 36),
          children: [
            Text(
              widget.photoReview
                  ? 'Check what Quinone detected'
                  : 'Build your meal from exact ingredients',
              style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 8),
            Text(
              widget.photoReview
                  ? 'Edit quantities, remove incorrect foods, or search and add anything the image missed. Final nutrition and health scores are calculated only after you confirm.'
                  : 'Search USDA foods, enter the amount used, and Quinone will skip image recognition.',
              style: theme.textTheme.bodyLarge?.copyWith(color: scheme.onSurfaceVariant),
            ),
            if (!widget.photoReview && _savedRecipes.isNotEmpty) ...[
              const SizedBox(height: 20),
              Text('Saved recipes', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: 10),
              SizedBox(
                height: 46,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: _savedRecipes.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 8),
                  itemBuilder: (context, index) {
                    final recipe = _savedRecipes[index];
                    return ActionChip(
                      avatar: const Icon(Icons.bookmark_outline_rounded, size: 18),
                      label: Text(recipe.name),
                      onPressed: _analyzing ? null : () => _loadRecipe(recipe),
                    );
                  },
                ),
              ),
            ],
            const SizedBox(height: 22),
            TextField(
              controller: _nameController,
              enabled: !_analyzing,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                labelText: 'Recipe name',
                prefixIcon: Icon(Icons.restaurant_menu_rounded),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _searchController,
              enabled: !_analyzing,
              onChanged: _onSearchChanged,
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(
                labelText: 'Search ingredient',
                hintText: 'e.g. paneer, oats, banana',
                prefixIcon: const Icon(Icons.search_rounded),
                suffixIcon: _searching
                    ? const Padding(
                        padding: EdgeInsets.all(14),
                        child: SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2)),
                      )
                    : null,
              ),
            ),
            if (_searchError != null) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
                decoration: BoxDecoration(
                  color: scheme.errorContainer,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.wifi_off_rounded,
                      color: scheme.onErrorContainer,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        _searchError!,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: scheme.onErrorContainer,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    TextButton(
                      onPressed: _searching
                          ? null
                          : () {
                              final query = _searchController.text.trim();
                              if (query.length >= 2) {
                                _search(query);
                              }
                            },
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              ),
            ],
            if (_suggestions.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                decoration: BoxDecoration(
                  color: scheme.surfaceContainerLow,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: scheme.outlineVariant),
                ),
                child: Column(
                  children: [
                    for (var i = 0; i < _suggestions.length; i++) ...[
                      ListTile(
                        title: Text(_suggestions[i].displayName, maxLines: 2, overflow: TextOverflow.ellipsis),
                        subtitle: Text(
                          [
                            _friendlyDataType(_suggestions[i].dataType),
                            if (_suggestions[i].brandOwner != null) _suggestions[i].brandOwner!,
                          ].join(' • '),
                        ),
                        trailing: const Icon(Icons.add_circle_outline_rounded),
                        onTap: () => _chooseSuggestion(_suggestions[i]),
                      ),
                      if (i != _suggestions.length - 1) Divider(height: 1, color: scheme.outlineVariant),
                    ],
                  ],
                ),
              ),
            ],
            const SizedBox(height: 24),
            Row(
              children: [
                Expanded(child: Text('Ingredients', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900))),
                Text('${_ingredients.length} added', style: theme.textTheme.labelLarge),
              ],
            ),
            const SizedBox(height: 10),
            if (_ingredients.isEmpty)
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: scheme.surfaceContainerLow,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: scheme.outlineVariant),
                ),
                child: const Text('Search above and add every ingredient used in the recipe.'),
              )
            else
              ..._ingredients.asMap().entries.map((entry) {
                final ingredient = entry.value;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Card(
                    elevation: 0,
                    child: ListTile(
                      leading: const CircleAvatar(child: Icon(Icons.restaurant_rounded)),
                      title: Text(ingredient.food.displayName, maxLines: 2, overflow: TextOverflow.ellipsis),
                      subtitle: Text('${_format(ingredient.grams)} g • ${_friendlyDataType(ingredient.food.dataType)}'),
                      trailing: const Icon(Icons.edit_outlined),
                      onTap: _analyzing ? null : () => _editIngredient(entry.key),
                    ),
                  ),
                );
              }),
            const SizedBox(height: 22),
            Text('Portion', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _servingsMadeController,
                    enabled: !_analyzing,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Recipe makes', suffixText: 'servings'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _servingsEatenController,
                    enabled: !_analyzing,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'You ate', suffixText: 'servings'),
                  ),
                ),
              ],
            ),
            if (_analyzing) ...[
              const SizedBox(height: 24),
              LinearProgressIndicator(value: _progress?.progress),
              const SizedBox(height: 10),
              Text(_progress?.message ?? 'Starting recipe analysis…'),
            ],
            const SizedBox(height: 26),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _analyzing ? null : _saveRecipe,
                    icon: const Icon(Icons.bookmark_add_outlined),
                    label: const Text('Save recipe'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _analyzing ? null : _analyze,
                    icon: const Icon(Icons.analytics_outlined),
                    label: Text(_analyzing ? 'Analyzing…' : (widget.photoReview ? 'Confirm & analyze' : 'Analyze')),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _friendlyDataType(String value) {
    switch (value) {
      case 'Foundation':
        return 'USDA Foundation';
      case 'SR Legacy':
        return 'USDA reference';
      case 'Survey (FNDDS)':
        return 'USDA prepared food';
      case 'Branded':
        return 'Branded food';
      default:
        return value;
    }
  }

  String _format(double value) => value == value.roundToDouble() ? value.toStringAsFixed(0) : value.toStringAsFixed(1);

  String _cleanError(Object error) {
    if (error is RecipeServiceException) {
      return error.message;
    }

    // Never render networking/framework exception dumps directly to users.
    final text = error
        .toString()
        .replaceFirst(RegExp(r'^(Exception|StateError):\s*'), '')
        .trim();
    final lower = text.toLowerCase();

    if (lower.contains('dioexception') ||
        lower.contains('status code') ||
        lower.contains('http://') ||
        lower.contains('https://')) {
      return 'Couldn’t complete the request. Please try again.';
    }

    return text.isEmpty
        ? 'Couldn’t complete the request. Please try again.'
        : text;
  }

  void _message(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }
}
