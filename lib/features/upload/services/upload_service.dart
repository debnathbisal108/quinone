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
    if (request.imagePaths.isEmpty) {
      throw const UploadServiceException(
        'At least one image is required.',
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
            'images[]',
            await MultipartFile.fromFile(
              imagePath,
              filename: file.uri.pathSegments.isNotEmpty
                  ? file.uri.pathSegments.last
                  : 'meal_image.jpg',
            ),
          ),
        );
      }

      final profile = request.userProfile;
      if (profile != null && profile.isNotEmpty) {
        formData.fields.add(
          MapEntry(
            'user_profile',
            jsonEncode(profile),
          ),
        );
      }

      final analysisId = request.analysisId?.trim();
      if (analysisId != null && analysisId.isNotEmpty) {
        formData.fields.add(
          MapEntry('analysis_id', analysisId),
        );
      }

      final foodId = request.foodId?.trim();
      if (foodId != null && foodId.isNotEmpty) {
        formData.fields.add(
          MapEntry('food_id', foodId),
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

      final data = response.data;

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
    } on UploadServiceException {
      rethrow;
    } on DioException {
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
  const UploadServiceException(this.message);

  final String message;

  @override
  String toString() => message;
}
