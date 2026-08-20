import 'dart:convert';

import 'package:dio/dio.dart';

import '../../../core/api/dio_client.dart';
import '../../../core/config/api_config.dart';
import '../models/post_analysis_recommendations.dart';

class RecommendationServiceException implements Exception {
  const RecommendationServiceException(this.message);

  final String message;

  @override
  String toString() => message;
}

class RecommendationService {
  RecommendationService({Dio? dio}) : _dio = dio ?? DioClient.instance;

  final Dio _dio;

  static final Map<String, Future<PostAnalysisRecommendations>> _requestCache = {};

  Future<PostAnalysisRecommendations> afterAnalysis({
    required Map<String, dynamic> currentResult,
    required List<Map<String, dynamic>> todayResults,
    Map<String, dynamic>? profile,
    int? localHour,
    int maximumResults = 5,
    List<String> preferredDomainKeys = const [],
    List<String> preferredNutrientKeys = const [],
  }) async {
    final payload = {
      'current_result': currentResult,
      'today_results': todayResults,
      if (profile != null && profile.isNotEmpty) 'profile': profile,
      'local_hour': localHour ?? DateTime.now().hour,
      'maximum_results': maximumResults,
      if (preferredDomainKeys.isNotEmpty)
        'preferred_domain_keys': preferredDomainKeys,
      if (preferredNutrientKeys.isNotEmpty)
        'preferred_nutrient_keys': preferredNutrientKeys,
    };
    final cacheKey = jsonEncode(payload);
    final cached = _requestCache[cacheKey];
    if (cached != null) return cached;

    final request = _fetchAfterAnalysis(payload);
    _requestCache[cacheKey] = request;
    try {
      return await request;
    } catch (_) {
      _requestCache.remove(cacheKey);
      rethrow;
    }
  }

  Future<PostAnalysisRecommendations> _fetchAfterAnalysis(
    Map<String, dynamic> payload,
  ) async {
    try {
      final response = await _dio.post<dynamic>(
        _absoluteUrl(ApiConfig.postAnalysisRecommendationEndpoint),
        data: jsonEncode(payload),
        options: Options(
          responseType: ResponseType.json,
          contentType: Headers.jsonContentType,
          headers: const {'Accept': 'application/json'},
          receiveTimeout: const Duration(seconds: 60),
        ),
      );
      final data = response.data;
      if (data is Map<String, dynamic>) {
        return PostAnalysisRecommendations.fromJson(data);
      }
      if (data is Map) {
        return PostAnalysisRecommendations.fromJson(
          Map<String, dynamic>.from(data),
        );
      }
      throw const RecommendationServiceException(
        'The recommendation response was invalid.',
      );
    } on RecommendationServiceException {
      rethrow;
    } on DioException catch (error) {
      final body = error.response?.data;
      String? detail;
      if (body is Map) detail = body['detail']?.toString();
      throw RecommendationServiceException(
        detail?.trim().isNotEmpty == true
            ? detail!.trim()
            : 'Recommendations are temporarily unavailable.',
      );
    }
  }

  Future<Map<String, dynamic>> applyToMeal({
    required Map<String, dynamic> currentResult,
    required List<Map<String, dynamic>> todayResults,
    required String recommendationId,
    Map<String, dynamic>? recommendation,
    Map<String, dynamic>? profile,
    int? localHour,
  }) async {
    final payload = {
      'current_result': currentResult,
      'today_results': todayResults,
      'recommendation_id': recommendationId,
      if (recommendation != null && recommendation.isNotEmpty)
        'recommendation': recommendation,
      if (profile != null && profile.isNotEmpty) 'profile': profile,
      'local_hour': localHour ?? DateTime.now().hour,
    };
    try {
      final response = await _dio.post<dynamic>(
        _absoluteUrl(ApiConfig.postAnalysisRecommendationApplyEndpoint),
        data: jsonEncode(payload),
        options: Options(
          responseType: ResponseType.json,
          contentType: Headers.jsonContentType,
          headers: const {'Accept': 'application/json'},
          receiveTimeout: const Duration(minutes: 2),
        ),
      );
      final data = response.data;
      if (data is Map<String, dynamic>) return data;
      if (data is Map) return Map<String, dynamic>.from(data);
      throw const RecommendationServiceException(
        'The combined meal response was invalid.',
      );
    } on RecommendationServiceException {
      rethrow;
    } on DioException catch (error) {
      final body = error.response?.data;
      String? detail;
      if (body is Map) detail = body['detail']?.toString();
      throw RecommendationServiceException(
        detail?.trim().isNotEmpty == true
            ? detail!.trim()
            : 'The recommendation could not be applied to this meal.',
      );
    }
  }

  String _absoluteUrl(String endpoint) {
    final base = ApiConfig.baseUrl.endsWith('/')
        ? ApiConfig.baseUrl.substring(0, ApiConfig.baseUrl.length - 1)
        : ApiConfig.baseUrl;
    final path = endpoint.startsWith('/') ? endpoint : '/$endpoint';
    return '$base$path';
  }
}
