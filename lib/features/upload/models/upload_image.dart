import 'dart:io';

import 'package:equatable/equatable.dart';

enum UploadImageType {
  meal,
  backLabel,
}

enum UploadStatus {
  ready,
  uploading,
  uploaded,
  failed,
}

class UploadImage extends Equatable {
  const UploadImage({
    required this.id,
    required this.path,
    this.type = UploadImageType.meal,
    this.status = UploadStatus.ready,
    this.uploadProgress = 0,
    this.backendId,
    this.message,
  });

  final String id;
  final String path;
  final UploadImageType type;
  final UploadStatus status;
  final double uploadProgress;
  final String? backendId;
  final String? message;

  File get file => File(path);

  bool get isBackLabel => type == UploadImageType.backLabel;

  UploadImage copyWith({
    String? id,
    String? path,
    UploadImageType? type,
    UploadStatus? status,
    double? uploadProgress,
    String? backendId,
    String? message,
    bool clearBackendId = false,
    bool clearMessage = false,
  }) {
    return UploadImage(
      id: id ?? this.id,
      path: path ?? this.path,
      type: type ?? this.type,
      status: status ?? this.status,
      uploadProgress: uploadProgress ?? this.uploadProgress,
      backendId: clearBackendId ? null : backendId ?? this.backendId,
      message: clearMessage ? null : message ?? this.message,
    );
  }

  @override
  List<Object?> get props => [
        id,
        path,
        type,
        status,
        uploadProgress,
        backendId,
        message,
      ];
}
