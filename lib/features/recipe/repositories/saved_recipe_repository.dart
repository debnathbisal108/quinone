import 'package:hive_flutter/hive_flutter.dart';

import '../models/manual_recipe.dart';

class SavedRecipeRepository {
  static const _boxName = 'saved_manual_recipes_v1';
  static Box<dynamic>? _box;

  Future<Box<dynamic>> _ensureBox() async {
    return _box ??= await Hive.openBox<dynamic>(_boxName);
  }

  Future<List<ManualRecipe>> getAll() async {
    final box = await _ensureBox();
    final result = <ManualRecipe>[];
    for (final value in box.values) {
      if (value is! Map) continue;
      try {
        result.add(ManualRecipe.fromJson(Map<String, dynamic>.from(value)));
      } catch (_) {
        // Ignore one damaged saved recipe rather than breaking the recipe list.
      }
    }
    return result;
  }

  Future<void> save(ManualRecipe recipe) async {
    final box = await _ensureBox();
    await box.put(recipe.id, recipe.toJson());
  }

  Future<void> delete(String id) async {
    final box = await _ensureBox();
    await box.delete(id);
  }
}
