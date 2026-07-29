import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';

import '../../../core/config/api_config.dart';
import '../models/upload_request.dart';
import '../models/upload_response.dart';

class UploadService {
  const UploadService({
    required Dio dio,
  }) : _dio = dio;

  final Dio _dio;

  Future<UploadResponse> uploadImages({
    required UploadRequest request,
    ProgressCallback? onSendProgress,
    CancelToken? cancelToken,
  }) async {
    final analysisId = request.analysisId?.trim();

    final isBackLabelRequest =
        analysisId != null && analysisId.isNotEmpty;

    if (isBackLabelRequest) {
      return _uploadBackLabel(
        request: request,
        analysisId: analysisId,
        onSendProgress: onSendProgress,
        cancelToken: cancelToken,
      );
    }

    return _uploadMealImages(
      request: request,
      onSendProgress: onSendProgress,
      cancelToken: cancelToken,
    );
  }

  Future<UploadResponse> _uploadMealImages({
    required UploadRequest request,
    ProgressCallback? onSendProgress,
    CancelToken? cancelToken,
  }) async {
    if (request.imagePaths.isEmpty) {
      throw const UploadServiceException(
        'At least one meal image is required.',
      );
    }

    try {
      final formData = FormData();

      for (final imagePath in request.imagePaths) {
        final file = File(imagePath);

        if (!await file.exists()) {
          throw UploadServiceException(
            'The selected image could not be found: $imagePath',
          );
        }

        formData.files.add(
          MapEntry(
            'images',
            await MultipartFile.fromFile(
              imagePath,
              filename: _fileName(
                file,
                fallback: 'meal_image.jpg',
              ),
            ),
          ),
        );
      }

      final profile = request.userProfile;

      if (profile != null && profile.isNotEmpty) {
        formData.fields.add(
          MapEntry(
            // This matches server.py:
            // profile: str | None = Form(default=None)
            'profile',
            jsonEncode(profile),
          ),
        );
      }

      final response = await _dio.post<dynamic>(
        ApiConfig.analyzeEndpoint,
        data: formData,
        cancelToken: cancelToken,
        onSendProgress: onSendProgress,
        options: Options(
          contentType:
              Headers.multipartFormDataContentType,
          responseType: ResponseType.json,
          headers: const {
            'Accept': 'application/json',
          },
        ),
      );

      return _parseResponse(response.data);
    } on UploadServiceException {
      rethrow;
    } on DioException {
      rethrow;
    } on FormatException catch (error) {
      throw UploadServiceException(
        'The server returned invalid JSON: '
        '${error.message}',
      );
    } catch (error) {
      throw UploadServiceException(
        'Unable to process the meal upload: $error',
      );
    }
  }

  Future<UploadResponse> _uploadBackLabel({
    required UploadRequest request,
    required String analysisId,
    ProgressCallback? onSendProgress,
    CancelToken? cancelToken,
  }) async {
    if (request.imagePaths.isEmpty) {
      throw const UploadServiceException(
        'Select a nutrition-label image.',
      );
    }

    final foodId = request.foodId?.trim();

    if (foodId == null || foodId.isEmpty) {
      throw const UploadServiceException(
        'The branded food identifier is missing.',
      );
    }

    final imagePath = request.imagePaths.first;
    final file = File(imagePath);

    if (!await file.exists()) {
      throw UploadServiceException(
        'The nutrition-label image could not be found: '
        '$imagePath',
      );
    }

    try {
      final formData = FormData.fromMap({
        'analysis_id': analysisId,

        // This matches server.py.
        'target_food_id': foodId,

        // Server expects label, not images.
        'label': await MultipartFile.fromFile(
          imagePath,
          filename: _fileName(
            file,
            fallback: 'nutrition_label.jpg',
          ),
        ),
      });

      final response = await _dio.post<dynamic>(
        ApiConfig.backLabelEndpoint,
        data: formData,
        cancelToken: cancelToken,
        onSendProgress: onSendProgress,
        options: Options(
          contentType:
              Headers.multipartFormDataContentType,
          responseType: ResponseType.json,
          headers: const {
            'Accept': 'application/json',
          },
        ),
      );

      return _parseResponse(response.data);
    } on UploadServiceException {
      rethrow;
    } on DioException {
      rethrow;
    } on FormatException catch (error) {
      throw UploadServiceException(
        'The server returned invalid JSON: '
        '${error.message}',
      );
    } catch (error) {
      throw UploadServiceException(
        'Unable to upload the nutrition label: $error',
      );
    }
  }

  UploadResponse _parseResponse(dynamic data) {
    if (data is Map<String, dynamic>) {
      return UploadResponse.fromJson(data);
    }

    if (data is Map) {
      return UploadResponse.fromJson(
        Map<String, dynamic>.from(data),
      );
    }

    throw const UploadServiceException(
      'The server returned an unsupported response format.',
    );
  }

  String _fileName(
    File file, {
    required String fallback,
  }) {
    return file.uri.pathSegments.isNotEmpty
        ? file.uri.pathSegments.last
        : fallback;
  }
}

class UploadServiceException implements Exception {
  const UploadServiceException(this.message);

  final String message;

  @override
  String toString() => message;
}
