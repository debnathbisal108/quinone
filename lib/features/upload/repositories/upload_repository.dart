import 'package:dio/dio.dart';

import '../../../core/api/dio_client.dart';
import '../models/upload_request.dart';
import '../models/upload_response.dart';
import '../services/upload_service.dart';

class UploadRepository {
  UploadRepository({
    UploadService? service,
  }) : _service = service ??
            UploadService(
              dio: DioClient.instance,
            );

  final UploadService _service;

  CancelToken? _cancelToken;

  Future<UploadResponse> uploadImages({
    required UploadRequest request,
    void Function(int sent, int total)? onSendProgress,
  }) async {
    _cancelCurrentRequest();

    final cancelToken = CancelToken();
    _cancelToken = cancelToken;

    try {
      final response = await _service.uploadImages(
        request: request,
        cancelToken: cancelToken,
        onSendProgress: onSendProgress,
      );

      return response;
    } on DioException catch (error) {
      throw _mapDioException(error);
    } finally {
      if (identical(_cancelToken, cancelToken)) {
        _cancelToken = null;
      }
    }
  }

  void cancelUpload() {
    _cancelCurrentRequest(
      reason: 'Upload cancelled by user.',
    );
  }

  void _cancelCurrentRequest({
    String reason = 'A new upload was started.',
  }) {
    final currentToken = _cancelToken;

    if (currentToken == null ||
        currentToken.isCancelled) {
      return;
    }

    currentToken.cancel(reason);
    _cancelToken = null;
  }

  Exception _mapDioException(
    DioException error,
  ) {
    if (CancelToken.isCancel(error)) {
      return Exception('Upload cancelled.');
    }

    switch (error.type) {
      case DioExceptionType.connectionTimeout:
        return Exception(
          'The server took too long to connect.',
        );

      case DioExceptionType.sendTimeout:
        return Exception(
          'The food images took too long to upload.',
        );

      case DioExceptionType.receiveTimeout:
        return Exception(
          'The server took too long to finish the analysis.',
        );

      case DioExceptionType.connectionError:
        return Exception(
          'Could not connect to the analysis server. '
          'Check your internet connection and server URL.',
        );

      case DioExceptionType.badCertificate:
        return Exception(
          'The server certificate could not be verified.',
        );

      case DioExceptionType.badResponse:
        return _mapBadResponse(error.response);

      case DioExceptionType.cancel:
        return Exception('Upload cancelled.');

      case DioExceptionType.unknown:
        final originalError = error.error;

        if (originalError != null) {
          return Exception(
            originalError.toString(),
          );
        }

        return Exception(
          'An unexpected network error occurred.',
        );
    }
  }

  Exception _mapBadResponse(
    Response<dynamic>? response,
  ) {
    final statusCode = response?.statusCode;
    final serverMessage =
        _extractServerMessage(response?.data);

    if (serverMessage != null &&
        serverMessage.isNotEmpty) {
      return Exception(serverMessage);
    }

    switch (statusCode) {
      case 400:
        return Exception(
          'The server could not process the uploaded data.',
        );

      case 401:
        return Exception(
          'The analysis request was not authorized.',
        );

      case 403:
        return Exception(
          'The server refused the analysis request.',
        );

      case 404:
        return Exception(
          'The analysis endpoint was not found.',
        );

      case 408:
        return Exception(
          'The analysis request timed out.',
        );

      case 413:
        return Exception(
          'The selected images are too large to upload.',
        );

      case 415:
        return Exception(
          'One or more selected image formats are unsupported.',
        );

      case 422:
        return Exception(
          'The server could not validate the analysis request.',
        );

      case 429:
        return Exception(
          'Too many analysis requests were sent. '
          'Please try again shortly.',
        );

      case 500:
        return Exception(
          'The server encountered an internal error.',
        );

      case 502:
      case 503:
      case 504:
        return Exception(
          'The analysis service is temporarily unavailable.',
        );

      default:
        return Exception(
          statusCode == null
              ? 'The analysis request failed.'
              : 'The analysis request failed '
                  'with status code $statusCode.',
        );
    }
  }

  String? _extractServerMessage(
    dynamic data,
  ) {
    if (data == null) {
      return null;
    }

    if (data is String) {
      final value = data.trim();
      return value.isEmpty ? null : value;
    }

    if (data is Map<String, dynamic>) {
      return _messageFromMap(data);
    }

    if (data is Map) {
      return _messageFromMap(
        Map<String, dynamic>.from(data),
      );
    }

    return null;
  }

  String? _messageFromMap(
    Map<String, dynamic> data,
  ) {
    const messageKeys = [
      'message',
      'error',
      'detail',
      'description',
    ];

    for (final key in messageKeys) {
      final value = data[key];

      if (value is String &&
          value.trim().isNotEmpty) {
        return value.trim();
      }

      if (value is List && value.isNotEmpty) {
        return value.join(', ');
      }

      if (value is Map) {
        final nestedMessage =
            _extractServerMessage(value);

        if (nestedMessage != null) {
          return nestedMessage;
        }
      }
    }

    return null;
  }
}
