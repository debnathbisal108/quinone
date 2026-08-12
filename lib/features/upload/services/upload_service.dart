import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';

import '../../../core/config/api_config.dart';
import '../models/analysis_job_progress.dart';
import '../models/upload_request.dart';
import '../models/upload_response.dart';

typedef AnalysisProgressCallback = void Function(
  AnalysisJobProgress progress,
);

class UploadService {
  const UploadService({required Dio dio}) : _dio = dio;

  final Dio _dio;

  Future<UploadResponse> uploadImages({
    required UploadRequest request,
    ProgressCallback? onSendProgress,
    AnalysisProgressCallback? onAnalysisProgress,
    CancelToken? cancelToken,
  }) async {
    final analysisId = request.analysisId?.trim();
    final isBackLabel = analysisId != null && analysisId.isNotEmpty;

    final jobId = isBackLabel
        ? await _startBackLabelJob(
            request: request,
            analysisId: analysisId,
            onSendProgress: onSendProgress,
            cancelToken: cancelToken,
          )
        : await _startMealJob(
            request: request,
            onSendProgress: onSendProgress,
            cancelToken: cancelToken,
          );

    return _pollJob(
      jobId: jobId,
      onAnalysisProgress: onAnalysisProgress,
      cancelToken: cancelToken,
    );
  }

  Future<String> _startMealJob({
    required UploadRequest request,
    ProgressCallback? onSendProgress,
    CancelToken? cancelToken,
  }) async {
    if (request.imagePaths.isEmpty) {
      throw const UploadServiceException('At least one meal image is required.');
    }

    final formData = FormData();
    for (final imagePath in request.imagePaths) {
      final file = File(imagePath);
      if (!await file.exists()) {
        throw UploadServiceException('The selected image could not be found: $imagePath');
      }
      formData.files.add(MapEntry(
        'images',
        await MultipartFile.fromFile(
          imagePath,
          filename: _fileName(file, fallback: 'meal_image.jpg'),
        ),
      ));
    }

    final profile = request.userProfile;
    if (profile != null && profile.isNotEmpty) {
      formData.fields.add(MapEntry('profile', jsonEncode(profile)));
    }

    final response = await _dio.post<dynamic>(
      ApiConfig.analyzeStartEndpoint,
      data: formData,
      cancelToken: cancelToken,
      onSendProgress: onSendProgress,
      options: _jsonMultipartOptions,
    );
    return _extractJobId(response.data);
  }

  Future<String> _startBackLabelJob({
    required UploadRequest request,
    required String analysisId,
    ProgressCallback? onSendProgress,
    CancelToken? cancelToken,
  }) async {
    if (request.imagePaths.isEmpty) {
      throw const UploadServiceException('Select a nutrition-label image.');
    }
    final foodId = request.foodId?.trim();
    if (foodId == null || foodId.isEmpty) {
      throw const UploadServiceException('The branded food identifier is missing.');
    }

    final imagePath = request.imagePaths.first;
    final file = File(imagePath);
    if (!await file.exists()) {
      throw UploadServiceException('The nutrition-label image could not be found: $imagePath');
    }

    final formData = FormData.fromMap({
      'analysis_id': analysisId,
      'target_food_id': foodId,
      'label': await MultipartFile.fromFile(
        imagePath,
        filename: _fileName(file, fallback: 'nutrition_label.jpg'),
      ),
    });

    final response = await _dio.post<dynamic>(
      ApiConfig.backLabelStartEndpoint,
      data: formData,
      cancelToken: cancelToken,
      onSendProgress: onSendProgress,
      options: _jsonMultipartOptions,
    );
    return _extractJobId(response.data);
  }

  Future<UploadResponse> _pollJob({
    required String jobId,
    AnalysisProgressCallback? onAnalysisProgress,
    CancelToken? cancelToken,
  }) async {
    while (true) {
      if (cancelToken?.isCancelled == true) {
        await _requestServerCancellation(jobId);
        throw const UploadServiceException('Upload cancelled.');
      }

      late final Response<dynamic> response;
      try {
        response = await _dio.get<dynamic>(
          ApiConfig.analysisJobEndpoint(jobId),
          cancelToken: cancelToken,
          options: Options(responseType: ResponseType.json),
        );
      } on DioException catch (error) {
        if (CancelToken.isCancel(error)) {
          await _requestServerCancellation(jobId);
        }
        rethrow;
      }
      final map = _asMap(response.data);
      final progress = AnalysisJobProgress.fromJson(map);
      onAnalysisProgress?.call(progress);

      switch (progress.status) {
        case 'completed':
        case 'waiting_for_back_label':
        case 'waiting_for_meal_confirmation':
        case 'waiting_for_serving_confirmation':
        case 'no_food_detected':
          final result = progress.result;
          if (result == null) {
            throw const UploadServiceException('The completed job did not include a result.');
          }
          return UploadResponse.fromJson(result);
        case 'failed':
          throw UploadServiceException(
            progress.error?.trim().isNotEmpty == true
                ? progress.error!.trim()
                : progress.message,
          );
        case 'cancelled':
          throw const UploadServiceException('Analysis cancelled.');
      }

      await Future<void>.delayed(const Duration(milliseconds: 700));
    }
  }

  Future<void> _requestServerCancellation(String jobId) async {
    try {
      await _dio.post<dynamic>(ApiConfig.cancelAnalysisJobEndpoint(jobId));
    } catch (_) {
      // Local cancellation must still complete even if this best-effort call fails.
    }
  }

  String _extractJobId(dynamic data) {
    final map = _asMap(data);
    final jobId = map['job_id']?.toString().trim();
    if (jobId == null || jobId.isEmpty) {
      throw const UploadServiceException('The server did not return an analysis job ID.');
    }
    return jobId;
  }

  Map<String, dynamic> _asMap(dynamic data) {
    if (data is Map<String, dynamic>) return data;
    if (data is Map) return Map<String, dynamic>.from(data);
    throw const UploadServiceException('The server returned an unsupported response format.');
  }

  Options get _jsonMultipartOptions => Options(
        contentType: Headers.multipartFormDataContentType,
        responseType: ResponseType.json,
        headers: const {'Accept': 'application/json'},
      );

  String _fileName(File file, {required String fallback}) =>
      file.uri.pathSegments.isNotEmpty ? file.uri.pathSegments.last : fallback;
}

class UploadServiceException implements Exception {
  const UploadServiceException(this.message);
  final String message;
  @override
  String toString() => message;
}
