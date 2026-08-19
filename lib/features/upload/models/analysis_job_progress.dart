class AnalysisJobProgress {
  const AnalysisJobProgress({
    required this.jobId,
    required this.status,
    required this.stage,
    required this.message,
    required this.progress,
    this.error,
    this.result,
  });

  final String jobId;
  final String status;
  final String stage;
  final String message;
  final double progress;
  final String? error;
  final Map<String, dynamic>? result;

  bool get isTerminal => const {
        'completed',
        'failed',
        'cancelled',
        'waiting_for_back_label',
        'waiting_for_meal_confirmation',
        'waiting_for_serving_confirmation',
        'no_food_detected',
      }.contains(status);

  factory AnalysisJobProgress.fromJson(Map<String, dynamic> json) {
    final rawProgress = json['progress'];
    final parsedProgress = rawProgress is num
        ? rawProgress.toDouble()
        : double.tryParse(rawProgress?.toString() ?? '') ?? 0;

    final rawResult = json['result'];
    return AnalysisJobProgress(
      jobId: json['job_id']?.toString() ?? '',
      status: json['status']?.toString() ?? 'unknown',
      stage: json['stage']?.toString() ?? 'unknown',
      message: json['message']?.toString() ?? 'Working…',
      progress: parsedProgress.clamp(0, 1).toDouble(),
      error: json['error']?.toString(),
      result: rawResult is Map
          ? Map<String, dynamic>.from(rawResult)
          : null,
    );
  }
}
