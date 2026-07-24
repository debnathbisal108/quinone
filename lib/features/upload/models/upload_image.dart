import 'dart:io';

import 'package:equatable/equatable.dart';

enum UploadImageType {
  unknown,

  food,

  nutritionLabel,

  brandedProduct,

  ignored,
}

enum UploadStatus {
  pending,

  uploading,

  uploaded,

  waitingBackLabel,

  processing,

  completed,

  failed,
}

class UploadImage extends Equatable {
  final String id;

  final File file;

  final UploadImageType type;

  final UploadStatus status;

  final double uploadProgress;

  final String? backendId;

  final String? message;

  final bool isBackLabel;

  const UploadImage({
    required this.id,
    required this.file,
    this.type = UploadImageType.unknown,
    this.status = UploadStatus.pending,
    this.uploadProgress = 0,
    this.backendId,
    this.message,
    this.isBackLabel = false,
  });

  UploadImage copyWith({
    String? id,
    File? file,
    UploadImageType? type,
    UploadStatus? status,
    double? uploadProgress,
    String? backendId,
    String? message,
    bool? isBackLabel,
  }) {
    return UploadImage(
      id: id ?? this.id,
      file: file ?? this.file,
      type: type ?? this.type,
      status: status ?? this.status,
      uploadProgress: uploadProgress ?? this.uploadProgress,
      backendId: backendId ?? this.backendId,
      message: message ?? this.message,
      isBackLabel: isBackLabel ?? this.isBackLabel,
    );
  }

  @override
  List<Object?> get props => [
        id,
        file.path,
        type,
        status,
        uploadProgress,
        backendId,
        message,
        isBackLabel,
      ];
}