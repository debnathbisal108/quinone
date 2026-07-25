
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../repositories/upload_repository.dart';
import '../models/upload_image.dart';
import '../models/upload_request.dart';
import '../models/upload_response.dart';

final uploadRepositoryProvider = Provider<UploadRepository>((ref) {
  return UploadRepository();
});

final uploadProvider =
    StateNotifierProvider<UploadNotifier, UploadState>((ref) {
  return UploadNotifier(
    repository: ref.watch(uploadRepositoryProvider),
  );
});

class UploadNotifier extends StateNotifier<UploadState> {
  final UploadRepository _repository;

  UploadNotifier({
    required UploadRepository repository,
  })  : _repository = repository,
        super(const UploadState());

  // -------------------------------------------------------
  // Add images
  // -------------------------------------------------------

  void addImages(List<UploadImage> images) {
    if (images.isEmpty || state.isUploading) {
      return;
    }

    final existingPaths = state.images
        .map((image) => image.path)
        .toSet();

    final uniqueImages = images
        .where((image) => !existingPaths.contains(image.path))
        .toList();

    if (uniqueImages.isEmpty) {
      return;
    }

    state = state.copyWith(
      images: [
        ...state.images,
        ...uniqueImages,
      ],
      clearError: true,
      clearResponse: true,
    );
  }

  void addImage(UploadImage image) {
    addImages([image]);
  }

  // -------------------------------------------------------
  // Remove images
  // -------------------------------------------------------

  void removeImage(String imageId) {
    if (state.isUploading) {
      return;
    }

    final updatedImages = state.images
        .where((image) => image.id != imageId)
        .toList();

    state = state.copyWith(
      images: updatedImages,
      clearError: true,
      clearResponse: true,
    );
  }

  void clearImages() {
    if (state.isUploading) {
      return;
    }

    state = state.copyWith(
      images: const [],
      uploadProgress: 0,
      clearError: true,
      clearResponse: true,
      clearAnalysisId: true,
      clearFoodId: true,
    );
  }

  // -------------------------------------------------------
  // Reorder images
  // -------------------------------------------------------

  void reorderImages(
    int oldIndex,
    int newIndex,
  ) {
    if (state.isUploading) {
      return;
    }

    if (oldIndex < 0 ||
        oldIndex >= state.images.length ||
        newIndex < 0 ||
        newIndex > state.images.length) {
      return;
    }

    final reorderedImages =
        List<UploadImage>.from(state.images);

    if (newIndex > oldIndex) {
      newIndex -= 1;
    }

    final movedImage =
        reorderedImages.removeAt(oldIndex);

    reorderedImages.insert(
      newIndex,
      movedImage,
    );

    state = state.copyWith(
      images: reorderedImages,
      clearError: true,
      clearResponse: true,
    );
  }

  // -------------------------------------------------------
  // Initial meal analysis
  // -------------------------------------------------------

  Future<void> upload({
    Map<String, dynamic>? userProfile,
  }) async {
    if (state.isUploading) {
      return;
    }

    if (state.images.isEmpty) {
      state = state.copyWith(
        error: 'Add at least one food image.',
        clearResponse: true,
      );
      return;
    }

    state = state.copyWith(
      isUploading: true,
      uploadProgress: 0,
      clearError: true,
      clearResponse: true,
      clearAnalysisId: true,
      clearFoodId: true,
    );

    try {
      final request = UploadRequest(
        imagePaths: state.images
            .map((image) => image.path)
            .toList(),
        userProfile: userProfile,
      );

      final response = await _repository.uploadImages(
        request: request,
        onSendProgress: _handleProgress,
      );

      final responseData =
          _normalizeResponseData(response.data);

      state = state.copyWith(
        isUploading: false,
        uploadProgress: 1,
        response: response,
        analysisId:
            responseData?['analysis_id']?.toString(),
        foodId: responseData?['food_id']?.toString(),
      );
    } catch (error) {
      state = state.copyWith(
        isUploading: false,
        uploadProgress: 0,
        error: _readableError(error),
        clearResponse: true,
      );
    }
  }

  // -------------------------------------------------------
  // Nutrition-label continuation
  // -------------------------------------------------------

  Future<void> uploadBackLabel({
    required String imagePath,
    String? analysisId,
    String? foodId,
    Map<String, dynamic>? userProfile,
  }) async {
    if (state.isUploading) {
      return;
    }

    final resolvedAnalysisId =
        analysisId ?? state.analysisId;

    final resolvedFoodId =
        foodId ?? state.foodId;

    if (resolvedAnalysisId == null ||
        resolvedAnalysisId.isEmpty) {
      state = state.copyWith(
        error:
            'The analysis session is missing. Please restart the analysis.',
      );
      return;
    }

    if (resolvedFoodId == null ||
        resolvedFoodId.isEmpty) {
      state = state.copyWith(
        error:
            'The branded food identifier is missing. Please restart the analysis.',
      );
      return;
    }

    if (imagePath.trim().isEmpty) {
      state = state.copyWith(
        error: 'Select a nutrition-label image.',
      );
      return;
    }

    state = state.copyWith(
      isUploading: true,
      uploadProgress: 0,
      clearError: true,
      clearResponse: true,
    );

    try {
      final request = UploadRequest(
        imagePaths: [imagePath],
        userProfile: userProfile,
        analysisId: resolvedAnalysisId,
        foodId: resolvedFoodId,
      );

      final response = await _repository.uploadImages(
        request: request,
        onSendProgress: _handleProgress,
      );

      final responseData =
          _normalizeResponseData(response.data);

      state = state.copyWith(
        isUploading: false,
        uploadProgress: 1,
        response: response,
        analysisId:
            responseData?['analysis_id']?.toString() ??
                resolvedAnalysisId,
        foodId:
            responseData?['food_id']?.toString() ??
                resolvedFoodId,
      );
    } catch (error) {
      state = state.copyWith(
        isUploading: false,
        uploadProgress: 0,
        error: _readableError(error),
        clearResponse: true,
      );
    }
  }

  // -------------------------------------------------------
  // Cancel upload
  // -------------------------------------------------------

  void cancelUpload() {
    if (!state.isUploading) {
      return;
    }

    _repository.cancelUpload();

    state = state.copyWith(
      isUploading: false,
      uploadProgress: 0,
      error: 'Upload cancelled.',
      clearResponse: true,
    );
  }

  // -------------------------------------------------------
  // Clear error or response
  // -------------------------------------------------------

  void clearError() {
    state = state.copyWith(
      clearError: true,
    );
  }

  void clearResponse() {
    state = state.copyWith(
      clearResponse: true,
    );
  }

  // -------------------------------------------------------
  // Reset
  // -------------------------------------------------------

  void reset() {
    if (state.isUploading) {
      _repository.cancelUpload();
    }

    state = const UploadState();
  }

  // -------------------------------------------------------
  // Internal helpers
  // -------------------------------------------------------

  void _handleProgress(
    int sentBytes,
    int totalBytes,
  ) {
    if (totalBytes <= 0) {
      return;
    }

    final progress =
        (sentBytes / totalBytes).clamp(0.0, 1.0);

    state = state.copyWith(
      uploadProgress: progress,
    );
  }

  Map<String, dynamic>? _normalizeResponseData(
    dynamic data,
  ) {
    if (data is Map<String, dynamic>) {
      return data;
    }

    if (data is Map) {
      return Map<String, dynamic>.from(data);
    }

    return null;
  }

  String _readableError(Object error) {
    final message = error.toString().trim();

    if (message.isEmpty) {
      return 'The analysis could not be completed.';
    }

    return message
        .replaceFirst('Exception: ', '')
        .replaceFirst('DioException: ', '');
  }
}

class UploadState {
  final List<UploadImage> images;
  final bool isUploading;
  final double uploadProgress;
  final UploadResponse? response;
  final String? error;
  final String? analysisId;
  final String? foodId;

  const UploadState({
    this.images = const [],
    this.isUploading = false,
    this.uploadProgress = 0,
    this.response,
    this.error,
    this.analysisId,
    this.foodId,
  });

  UploadState copyWith({
    List<UploadImage>? images,
    bool? isUploading,
    double? uploadProgress,
    UploadResponse? response,
    String? error,
    String? analysisId,
    String? foodId,
    bool clearResponse = false,
    bool clearError = false,
    bool clearAnalysisId = false,
    bool clearFoodId = false,
  }) {
    return UploadState(
      images: images ?? this.images,
      isUploading:
          isUploading ?? this.isUploading,
      uploadProgress:
          uploadProgress ?? this.uploadProgress,
      response: clearResponse
          ? null
          : response ?? this.response,
      error:
          clearError ? null : error ?? this.error,
      analysisId: clearAnalysisId
          ? null
          : analysisId ?? this.analysisId,
      foodId: clearFoodId
          ? null
          : foodId ?? this.foodId,
    );
  }

  bool get hasImages => images.isNotEmpty;

  bool get isWaitingForBackLabel {
    final Object? rawData = response?.data;
  
    if (rawData is! Map) {
      return false;
    }
  
    final data = Map<String, dynamic>.from(rawData);
  
    return data['status']?.toString() ==
        'waiting_for_back_label';
  }
}
