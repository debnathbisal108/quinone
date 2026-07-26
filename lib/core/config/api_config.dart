class ApiConfig {
  ApiConfig._();

  /// Change this when you deploy your backend.
  // static const String baseUrl = "https://your-render-url.onrender.com";

  static const String baseUrl = "https://quinone.onrender.com";

  /// API Version
  static const String apiVersion = "/api/v1";

  /// Analyze endpoint
  static const String analyzeEndpoint = "$apiVersion/analyze";

  /// Health check
  static const String healthEndpoint = "$apiVersion/health";

  /// Timeout
  static const Duration connectTimeout = Duration(seconds: 60);

  static const Duration receiveTimeout = Duration(minutes: 10);

  static const Duration sendTimeout = Duration(minutes: 10);
}
