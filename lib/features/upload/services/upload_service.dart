import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';

import '../../../core/config/api_config.dart';
import '../models/upload_request.dart';
import '../models/upload_response.dart';

class UploadService {
  UploadService({
    required Dio dio,
  }) : _dio = dio;

  final Dio _dio;

  /// Uploads images to the same analysis endpoint for:
  ///
  /// 1. Initial meal analysis
  /// 2. Nutrition-label continuation after the backend requests it
  Future<UploadResponse> uploadImages({
    required UploadRequest request,
    ProgressCallback? onSendProgress,
    CancelToken? cancelToken,
  }) async {
    if (request.imagePaths.isEmpty) {
      throw const UploadServiceException(
        'At least one image is required.',
      );
    }

    try {
      final formData = FormData();

      for (final path in request.imagePaths) {
        final file = File(path);

        if (!await file.exists()) {
          throw UploadServiceException(
            'The selected image could not be found: $path',
          );
        }

        formData.files.add(
          MapEntry(
            'images[]',
            await MultipartFile.fromFile(
              path,
              filename: file.uri.pathSegments.isNotEmpty
                  ? file.uri.pathSegments.last
                  : 'food_image.jpg',
            ),
          ),
        );
      }

      final userProfile = request.userProfile;

      if (userProfile != null && userProfile.isNotEmpty) {
        formData.fields.add(
          MapEntry(
            'user_profile',
            jsonEncode(userProfile),
          ),
        );
      }

      final analysisId = request.analysisId?.trim();

      if (analysisId != null && analysisId.isNotEmpty) {
        formData.fields.add(
          MapEntry(
            'analysis_id',
            analysisId,
          ),
        );
      }

      final foodId = request.foodId?.trim();

      if (foodId != null && foodId.isNotEmpty) {
        formData.fields.add(
          MapEntry(
            'food_id',
            foodId,
          ),
        );
      }

      final response = await _dio.post<dynamic>(
        ApiConfig.analyzeEndpoint,
        data: formData,
        cancelToken: cancelToken,
        onSendProgress: onSendProgress,
        options: Options(
          contentType: Headers.multipartFormDataContentType,
          responseType: ResponseType.json,
          headers: const {
            'Accept': 'application/json',
          },
        ),
      );

      final responseData = response.data;

      if (responseData is Map<String, dynamic>) {
        return UploadResponse.fromJson(responseData);
      }

      if (responseData is Map) {
        return UploadResponse.fromJson(
          Map<String, dynamic>.from(responseData),
        );
      }

      throw const UploadServiceException(
        'The server returned an unsupported response format.',
      );
    } on UploadServiceException {
      rethrow;
    } on DioException {
      // The repository is responsible for mapping Dio errors
      // into user-friendly messages.
      rethrow;
    } on FormatException catch (error) {
      throw UploadServiceException(
        'The server returned invalid JSON: ${error.message}',
      );
    } catch (error) {
      throw UploadServiceException(
        'Unable to prepare or process the upload: $error',
      );
    }
  }
}

class UploadServiceException implements Exception {
  final String message;

  const UploadServiceException(this.message);

  @override
  String toString() => message;
}