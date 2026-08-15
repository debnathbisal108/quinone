class UploadRequest {
  final List<String> imagePaths;

  final Map<String, dynamic>? userProfile;

  /// Present only when continuing an existing analysis.
  final String? analysisId;

  /// Food that requested the back label.
  final String? foodId;

  /// True when the user is uploading a label image directly, with no
  /// prior meal photo and no existing analysisId.
  final bool isLabelOnly;

  const UploadRequest({
    required this.imagePaths,
    this.userProfile,
    this.analysisId,
    this.foodId,
    this.isLabelOnly = false,
  });
}
