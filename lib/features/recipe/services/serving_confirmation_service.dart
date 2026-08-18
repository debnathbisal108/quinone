import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import '../../../core/api/dio_client.dart';
import '../../../core/config/api_config.dart';
import '../../upload/models/analysis_job_progress.dart';
import '../models/draft_meal_guidance.dart';

class ServingConfirmationService {
  ServingConfirmationService({Dio? dio}) : _dio = dio ?? DioClient.instance;

  final Dio _dio;

  String _absoluteUrl(String endpoint) {
    final base = ApiConfig.baseUrl.endsWith('/')
        ? ApiConfig.baseUrl.substring(0, ApiConfig.baseUrl.length - 1)
        : ApiConfig.baseUrl;
    final path = endpoint.startsWith('/') ? endpoint : '/$endpoint';
    return '$base$path';
  }

  Future<Map<String, dynamic>> confirm({
    required String analysisId,
    required List<Map<String, dynamic>> items,
    void Function(AnalysisJobProgress progress)? onProgress,
  }) async {
    final start = await _dio.post<dynamic>(
      _absoluteUrl(ApiConfig.servingConfirmationStartEndpoint),
      data: jsonEncode({
        'analysis_id': analysisId,
        'items': items,
      }),
      options: Options(
        responseType: ResponseType.json,
        contentType: Headers.jsonContentType,
        headers: const {'Accept': 'application/json'},
      ),
    );

    final startMap = _asMap(start.data);
    final jobId = startMap['job_id']?.toString().trim();
    if (jobId == null || jobId.isEmpty) {
      throw StateError('The server could not start final analysis.');
    }

    while (true) {
      final response = await _dio.get<dynamic>(
        _absoluteUrl(ApiConfig.analysisJobEndpoint(jobId)),
        options: Options(responseType: ResponseType.json),
      );
      final progress = AnalysisJobProgress.fromJson(_asMap(response.data));
      onProgress?.call(progress);

      if (progress.status == 'completed') {
        final result = progress.result;
        if (result == null) {
          throw StateError('Final analysis finished without a result.');
        }
        return result;
      }
      if (progress.status == 'failed') {
        throw StateError(
          progress.error?.trim().isNotEmpty == true
              ? progress.error!.trim()
              : progress.message,
        );
      }
      if (progress.status == 'cancelled') {
        throw StateError('Analysis was cancelled.');
      }

      await Future<void>.delayed(const Duration(milliseconds: 650));
    }
  }

  Future<DraftMealGuidance> evaluateGuidance({
    required String analysisId,
    required List<Map<String, dynamic>> items,
    Map<String, dynamic>? profile,
    List<Map<String, dynamic>> todayResults = const [],
    bool includeShortfalls = true,
    int? localHour,
  }) async {
    final response = await _dio.post<dynamic>(
      _absoluteUrl(ApiConfig.draftMealGuidanceEndpoint),
      data: jsonEncode({
        'recipe_name': 'Packaged meal',
        'ingredients': const <Map<String, dynamic>>[],
        'servings_made': 1.0,
        'servings_eaten': 1.0,
        'analysis_id': analysisId,
        'label_items': items,
        if (todayResults.isNotEmpty) 'today_results': todayResults,
        'include_shortfalls': includeShortfalls,
        if (profile != null && profile.isNotEmpty) 'profile': profile,
        'local_hour': localHour ?? DateTime.now().hour,
      }),
      options: Options(
        responseType: ResponseType.json,
        contentType: Headers.jsonContentType,
        headers: const {'Accept': 'application/json'},
        receiveTimeout: const Duration(seconds: 45),
      ),
    );
    return DraftMealGuidance.fromJson(_asMap(response.data));
  }

  Future<DraftMealGuidance> evaluateGuidanceSuggestions({
    required String analysisId,
    required List<Map<String, dynamic>> items,
    Map<String, dynamic>? profile,
    List<Map<String, dynamic>> todayResults = const [],
    bool includeShortfalls = true,
    int? localHour,
  }) async {
    final response = await _dio.post<dynamic>(
      _absoluteUrl(ApiConfig.draftMealGuidanceSuggestionsEndpoint),
      data: jsonEncode({
        'recipe_name': 'Packaged meal',
        'ingredients': const <Map<String, dynamic>>[],
        'servings_made': 1.0,
        'servings_eaten': 1.0,
        'analysis_id': analysisId,
        'label_items': items,
        if (todayResults.isNotEmpty) 'today_results': todayResults,
        'include_shortfalls': includeShortfalls,
        if (profile != null && profile.isNotEmpty) 'profile': profile,
        'local_hour': localHour ?? DateTime.now().hour,
      }),
      options: Options(
        responseType: ResponseType.json,
        contentType: Headers.jsonContentType,
        headers: const {'Accept': 'application/json'},
        receiveTimeout: const Duration(seconds: 60),
      ),
    );
    return DraftMealGuidance.fromJson(_asMap(response.data));
  }

  Map<String, dynamic> _asMap(dynamic value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return Map<String, dynamic>.from(value);
    return <String, dynamic>{};
  }
}
