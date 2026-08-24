import 'dart:io';

import 'package:hive_flutter/hive_flutter.dart';
import 'package:path_provider/path_provider.dart';

/// Keeps meal photos available after analysis for Result, History and sharing.
class AnalysisImageArchiveService {
  AnalysisImageArchiveService._();

  static final AnalysisImageArchiveService instance =
      AnalysisImageArchiveService._();

  static const _boxName = 'analysis_image_archive_v1';
  static const _pendingKey = 'pending_meal_images';

  Box<dynamic>? _box;

  Future<void> initialize() async {
    _box ??= await Hive.openBox<dynamic>(_boxName);
  }

  Future<List<String>> archiveMealImages(List<String> sourcePaths) async {
    await initialize();
    final valid = sourcePaths
        .map((path) => path.trim())
        .where((path) => path.isNotEmpty && File(path).existsSync())
        .toList(growable: false);
    if (valid.isEmpty) return const [];

    final root = await getApplicationDocumentsDirectory();
    final directory = Directory('${root.path}/meal_images');
    await directory.create(recursive: true);

    final stamp = DateTime.now().microsecondsSinceEpoch;
    final archived = <String>[];
    for (var index = 0; index < valid.length; index++) {
      final source = File(valid[index]);
      final destination = File(
        '${directory.path}/meal_${stamp}_${index + 1}${_extension(source.path)}',
      );
      await source.copy(destination.path);
      archived.add(destination.path);
    }

    await _box!.put(_pendingKey, archived);
    return archived;
  }

  List<String> get pendingMealImages {
    final raw = _box?.get(_pendingKey);
    if (raw is! List) return const [];
    return raw
        .map((item) => item.toString().trim())
        .where((path) => path.isNotEmpty && File(path).existsSync())
        .toList(growable: false);
  }

  Map<String, dynamic> attachPendingImages(Map<String, dynamic> result) {
    final existing = _paths(result['meal_image_paths']);
    if (existing.isNotEmpty) return result;
    final pending = pendingMealImages;
    if (pending.isEmpty) return result;
    return <String, dynamic>{...result, 'meal_image_paths': pending};
  }

  Future<void> clearPendingMealImages() async {
    await initialize();
    await _box!.delete(_pendingKey);
  }

  static List<String> _paths(dynamic value) {
    if (value is! List) return const [];
    return value
        .map((item) => item.toString().trim())
        .where((path) => path.isNotEmpty && File(path).existsSync())
        .toList(growable: false);
  }

  static String _extension(String path) {
    final dot = path.lastIndexOf('.');
    if (dot < 0 || dot == path.length - 1) return '.jpg';
    final extension = path.substring(dot).toLowerCase();
    if (const {'.jpg', '.jpeg', '.png', '.webp'}.contains(extension)) {
      return extension == '.jpeg' ? '.jpg' : extension;
    }
    return '.jpg';
  }
}
