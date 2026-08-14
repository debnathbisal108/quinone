class ApiConfig {
  ApiConfig._();

  /// Change this when you deploy your backend.
  // static const String baseUrl = "https://your-render-url.onrender.com";

  static const String baseUrl = "https://quinone.onrender.com";

  /// API Version
  static const String apiVersion = "/api/v1";

  /// Analyze endpoint
  static const String analyzeEndpoint = "/analyze";

  static const String backLabelEndpoint =
      "/analyze/back-label";

  static const String analyzeStartEndpoint =
      "/analyze/start";

  static const String backLabelStartEndpoint =
      "/analyze/back-label/start";

  static const String servingConfirmationStartEndpoint =
      "/analyze/serving-confirmation/start";

  static const String mixedMealConfirmationStartEndpoint =
      "/analyze/mixed-meal-confirmation/start";

  static const String recipeSearchEndpoint =
      "/recipes/usda/search";

  static const String recipeAnalyzeStartEndpoint =
      "/recipes/analyze/start";

  static const String postAnalysisRecommendationEndpoint =
      "/recommendations/after-analysis";

  static String analysisJobEndpoint(String jobId) =>
      "/analyze/jobs/$jobId";

  static String cancelAnalysisJobEndpoint(String jobId) =>
      "/analyze/jobs/$jobId/cancel";

  /// Health check
  static const String healthEndpoint = "/health";

  /// Timeout
  static const Duration connectTimeout = Duration(seconds: 60);

  static const Duration receiveTimeout = Duration(minutes: 10);

  static const Duration sendTimeout = Duration(minutes: 10);
}
