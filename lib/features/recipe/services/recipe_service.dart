import 'dart:async';

import 'package:dio/dio.dart';

import '../../../core/api/dio_client.dart';
import '../../../core/config/api_config.dart';
import '../../upload/models/analysis_job_progress.dart';
import '../models/manual_recipe.dart';
import '../models/usda_food_suggestion.dart';

class RecipeService {
  RecipeService({Dio? dio}) : _dio = dio ?? DioClient.instance;

  final Dio _dio;

  Future<List<UsdaFoodSuggestion>> searchFoods(String query) async {
    final cleaned = query.trim();
    if (cleaned.length < 2) return const [];
    final response = await _dio.get<dynamic>(
      ApiConfig.recipeSearchEndpoint,
      queryParameters: {'q': cleaned},
      options: Options(responseType: ResponseType.json),
    );
    final map = _asMap(response.data);
    final raw = map['foods'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map>()
        .map((item) => UsdaFoodSuggestion.fromJson(Map<String, dynamic>.from(item)))
        .toList(growable: false);
  }

  Future<Map<String, dynamic>> analyzeRecipe({
    required ManualRecipe recipe,
    Map<String, dynamic>? profile,
    void Function(AnalysisJobProgress progress)? onProgress,
  }) async {
    final start = await _dio.post<dynamic>(
      ApiConfig.recipeAnalyzeStartEndpoint,
      data: recipe.toBackendJson(profile: profile),
      options: Options(responseType: ResponseType.json),
    );
    final startMap = _asMap(start.data);
    final jobId = startMap['job_id']?.toString().trim();
    if (jobId == null || jobId.isEmpty) {
      throw StateError('The server did not return a recipe analysis job ID.');
    }

    while (true) {
      final response = await _dio.get<dynamic>(
        ApiConfig.analysisJobEndpoint(jobId),
        options: Options(responseType: ResponseType.json),
      );
      final progress = AnalysisJobProgress.fromJson(_asMap(response.data));
      onProgress?.call(progress);
      if (progress.status == 'completed') {
        final result = progress.result;
        if (result == null) throw StateError('Recipe analysis completed without a result.');
        return result;
      }
      if (progress.status == 'failed') {
        throw StateError(progress.error ?? progress.message);
      }
      if (progress.status == 'cancelled') {
        throw StateError('Recipe analysis was cancelled.');
      }
      await Future<void>.delayed(const Duration(milliseconds: 650));
    }
  }

  Map<String, dynamic> _asMap(dynamic value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return Map<String, dynamic>.from(value);
    throw StateError('The server returned an unsupported response.');
  }
}
