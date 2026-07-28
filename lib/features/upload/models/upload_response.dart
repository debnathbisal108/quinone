import 'package:flutter/foundation.dart';
import '../../result/models/analysis_result.dart';

// import 'package:quinone/features/result/models/analysis_result.dart';

class UploadResponse {
  final bool success;
  final Map<String, dynamic> data;
  final String? message;

  const UploadResponse({
    required this.success,
    required this.data,
    this.message,
  });

  AnalysisResult? get analysisResult {
    final status = data['status']?.toString().toLowerCase();
    if (status == 'waiting_for_back_label' || status == 'no_food_detected') {
      return null;
    }

    try {
      return AnalysisResult.fromJson(data);
    } on FormatException catch (error, stackTrace) {
      debugPrint('Invalid analysis response: $error');
      debugPrintStack(stackTrace: stackTrace);
      rethrow;
    }
  }

  factory UploadResponse.fromJson(Map<String, dynamic> json) {
    return UploadResponse(
      success: json['success'] is bool ? json['success'] as bool : true,
      data: Map<String, dynamic>.unmodifiable(json),
      message: json['message']?.toString(),
    );
  }
}
