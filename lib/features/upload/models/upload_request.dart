class UploadRequest {
  final List<String> imagePaths;

  final Map<String, dynamic>? userProfile;

  /// Present only when continuing an existing analysis.
  final String? analysisId;

  /// Food that requested the back label.
  final String? foodId;

  const UploadRequest({
    required this.imagePaths,
    this.userProfile,
    this.analysisId,
    this.foodId,
  });
}