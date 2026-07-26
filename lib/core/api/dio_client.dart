import 'package:dio/dio.dart';

class DioClient {
  DioClient._();

  /// Change this when you deploy.
  static const String baseUrl =
      'https://quinone.onrender.com';

  static final Dio instance = Dio(
    BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(
        seconds: 30,
      ),
      receiveTimeout: const Duration(
        minutes: 2,
      ),
      sendTimeout: const Duration(
        minutes: 2,
      ),
      responseType: ResponseType.json,
      contentType: 'multipart/form-data',
      headers: const {
        'Accept': 'application/json',
      },
    ),
  )..interceptors.add(
      InterceptorsWrapper(
        onRequest: (
          options,
          handler,
        ) {
          // Useful for debugging
          // debugPrint(
          //   '${options.method} ${options.uri}',
          // );

          handler.next(options);
        },
        onResponse: (
          response,
          handler,
        ) {
          handler.next(response);
        },
        onError: (
          error,
          handler,
        ) {
          handler.next(error);
        },
      ),
    );

  static void changeBaseUrl(
    String url,
  ) {
    instance.options.baseUrl = url;
  }
}
