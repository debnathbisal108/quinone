import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../../../core/api/dio_client.dart';
import '../../../core/config/api_config.dart';
import '../../upload/models/analysis_job_progress.dart';
import '../models/manual_recipe.dart';
import '../models/usda_food_suggestion.dart';

class RecipeServiceException implements Exception {
  const RecipeServiceException(
    this.message, {
    this.statusCode,
    this.requestUri,
  });

  final String message;
  final int? statusCode;
  final Uri? requestUri;

  @override
  String toString() => message;
}

class RecipeService {
  RecipeService({Dio? dio}) : _dio = dio ?? DioClient.instance;

  final Dio _dio;

  /// Recipe endpoints deliberately use absolute URLs.
  ///
  /// The rest of the app may configure DioClient with either the server root
  /// or an `/api/v1` base path. An absolute URL prevents that shared setting
  /// from accidentally turning `/recipes/...` into another route.
  String _absoluteUrl(String endpoint) {
    final base = ApiConfig.baseUrl.endsWith('/')
        ? ApiConfig.baseUrl.substring(0, ApiConfig.baseUrl.length - 1)
        : ApiConfig.baseUrl;
    final path = endpoint.startsWith('/') ? endpoint : '/$endpoint';
    return '$base$path';
  }

  Future<List<UsdaFoodSuggestion>> searchFoods(String query) async {
    final cleaned = query.trim();
    if (cleaned.length < 2) {
      return const [];
    }

    final url = _absoluteUrl(ApiConfig.recipeSearchEndpoint);

    try {
      final response = await _dio.get<dynamic>(
        url,
        queryParameters: {'q': cleaned},
        options: Options(responseType: ResponseType.json),
      );

      final map = _asMap(response.data);
      final raw = map['foods'];
      if (raw is! List) {
        return const [];
      }

      return raw
          .whereType<Map>()
          .map(
            (item) => UsdaFoodSuggestion.fromJson(
              Map<String, dynamic>.from(item),
            ),
          )
          .toList(growable: false);
    } on DioException catch (error, stackTrace) {
      throw _mapDioError(
        error,
        operation: 'search foods',
        stackTrace: stackTrace,
      );
    }
  }

  Future<Map<String, dynamic>> analyzeRecipe({
    required ManualRecipe recipe,
    Map<String, dynamic>? profile,
    void Function(AnalysisJobProgress progress)? onProgress,
  }) async {
    try {
      final start = await _dio.post<dynamic>(
        _absoluteUrl(ApiConfig.recipeAnalyzeStartEndpoint),
        data: recipe.toBackendJson(profile: profile),
        options: Options(responseType: ResponseType.json),
      );

      final startMap = _asMap(start.data);
      final jobId = startMap['job_id']?.toString().trim();
      if (jobId == null || jobId.isEmpty) {
        throw const RecipeServiceException(
          'The server could not start recipe analysis. Please try again.',
        );
      }

      while (true) {
        final response = await _dio.get<dynamic>(
          _absoluteUrl(ApiConfig.analysisJobEndpoint(jobId)),
          options: Options(responseType: ResponseType.json),
        );

        final progress = AnalysisJobProgress.fromJson(
          _asMap(response.data),
        );
        onProgress?.call(progress);

        if (progress.status == 'completed') {
          final result = progress.result;
          if (result == null) {
            throw const RecipeServiceException(
              'Recipe analysis finished without a result. Please try again.',
            );
          }
          return result;
        }

        if (progress.status == 'failed') {
          throw RecipeServiceException(
            _friendlyServerMessage(
              progress.error ?? progress.message,
              fallback: 'Recipe analysis failed. Please try again.',
            ),
          );
        }

        if (progress.status == 'cancelled') {
          throw const RecipeServiceException(
            'Recipe analysis was cancelled.',
          );
        }

        await Future<void>.delayed(
          const Duration(milliseconds: 650),
        );
      }
    } on RecipeServiceException {
      rethrow;
    } on DioException catch (error, stackTrace) {
      throw _mapDioError(
        error,
        operation: 'analyze recipe',
        stackTrace: stackTrace,
      );
    }
  }

  RecipeServiceException _mapDioError(
    DioException error, {
    required String operation,
    required StackTrace stackTrace,
  }) {
    final statusCode = error.response?.statusCode;
    final uri = error.requestOptions.uri;

    // Keep the technical detail in development logs, never in user-facing UI.
    debugPrint(
      '[RecipeService] $operation failed: '
      '${error.type}; status=$statusCode; uri=$uri',
    );
    debugPrintStack(stackTrace: stackTrace);

    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.sendTimeout ||
        error.type == DioExceptionType.receiveTimeout) {
      return RecipeServiceException(
        'The food service is taking too long to respond. Please try again.',
        statusCode: statusCode,
        requestUri: uri,
      );
    }

    if (error.type == DioExceptionType.connectionError) {
      return RecipeServiceException(
        'Couldn’t connect to Quinone. Check your internet connection and try again.',
        statusCode: statusCode,
        requestUri: uri,
      );
    }

    if (statusCode == 404) {
      return RecipeServiceException(
        'Food search is not available on the server right now. Please try again shortly.',
        statusCode: statusCode,
        requestUri: uri,
      );
    }

    if (statusCode == 429) {
      return RecipeServiceException(
        'Food search is busy right now. Please wait a moment and try again.',
        statusCode: statusCode,
        requestUri: uri,
      );
    }

    final serverDetail = _extractServerDetail(error.response?.data);

    if (statusCode != null && statusCode >= 500) {
      return RecipeServiceException(
        _friendlyServerMessage(
          serverDetail,
          fallback: 'The food service is temporarily unavailable. Please try again.',
        ),
        statusCode: statusCode,
        requestUri: uri,
      );
    }

    if (statusCode != null && statusCode >= 400) {
      return RecipeServiceException(
        _friendlyServerMessage(
          serverDetail,
          fallback: 'The request could not be completed. Please check the recipe and try again.',
        ),
        statusCode: statusCode,
        requestUri: uri,
      );
    }

    return RecipeServiceException(
      'Something went wrong while contacting the food service. Please try again.',
      statusCode: statusCode,
      requestUri: uri,
    );
  }

  String? _extractServerDetail(dynamic data) {
    if (data is Map) {
      final detail = data['detail'];
      if (detail is String && detail.trim().isNotEmpty) {
        return detail.trim();
      }
    }
    return null;
  }

  String _friendlyServerMessage(
    String? value, {
    required String fallback,
  }) {
    final text = value?.trim();
    if (text == null || text.isEmpty) {
      return fallback;
    }

    // Do not surface tracebacks, exception class names, request URLs, or
    // framework internals in production UI.
    final lower = text.toLowerCase();
    const unsafeTokens = <String>[
      'traceback',
      'dioexception',
      'http://',
      'https://',
      'exception',
      'stack trace',
    ];
    if (unsafeTokens.any(lower.contains)) {
      return fallback;
    }

    return text;
  }

  Map<String, dynamic> _asMap(dynamic value) {
    if (value is Map<String, dynamic>) {
      return value;
    }
    if (value is Map) {
      return Map<String, dynamic>.from(value);
    }
    throw const RecipeServiceException(
      'The server returned an unexpected response. Please try again.',
    );
  }
}
