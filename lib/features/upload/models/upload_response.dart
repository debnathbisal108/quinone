class UploadResponse {
  final bool success;

  final Map<String, dynamic> data;

  final String? message;

  const UploadResponse({
    required this.success,
    required this.data,
    this.message,
  });

  factory UploadResponse.fromJson(
    Map<String, dynamic> json,
  ) {
    return UploadResponse(
      success: json["success"] ?? true,
      data: json,
      message: json["message"],
    );
  }
}