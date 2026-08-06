import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../repositories/upload_repository.dart';
import '../models/upload_image.dart';
import '../models/upload_request.dart';
import '../models/upload_response.dart';
import '../models/analysis_job_progress.dart';
import '../../history/providers/analysis_history_provider.dart';

final uploadRepositoryProvider = Provider<UploadRepository>((ref) {
  return UploadRepository();
});

final uploadProvider =
    StateNotifierProvider<UploadNotifier, UploadState>((ref) {
  return UploadNotifier(
    repository: ref.watch(uploadRepositoryProvider),
    historySaver: ref.read(analysisHistoryProvider.notifier).saveResult,
  );
});

class UploadNotifier extends StateNotifier<UploadState> {
  final UploadRepository _repository;
  final Future<void> Function(Map<String, dynamic>) _historySaver;

  UploadNotifier({
    required UploadRepository repository,
    required Future<void> Function(Map<String, dynamic>) historySaver,
  })  : _repository = repository,
        _historySaver = historySaver,
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
      uploadProgress: 0.02,
      progressMessage: 'Preparing images…',
      progressStage: 'preparing',
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
        onAnalysisProgress: _handleAnalysisProgress,
      );

      final responseData =
          _normalizeResponseData(response.data);

      if (responseData != null && _isCompletedResult(responseData)) {
        await _historySaver(responseData);
      }

      state = state.copyWith(
        isUploading: false,
        uploadProgress: 1,
        progressMessage: 'Analysis complete',
        response: response,
        analysisId: _extractAnalysisId(responseData),
        foodId: _extractFoodId(responseData),
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
      uploadProgress: 0.02,
      progressMessage: 'Uploading nutrition label…',
      progressStage: 'uploading_label',
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
        onAnalysisProgress: _handleAnalysisProgress,
      );

      final responseData =
          _normalizeResponseData(response.data);

      if (responseData != null && _isCompletedResult(responseData)) {
        await _historySaver(responseData);
      }

      state = state.copyWith(
        isUploading: false,
        uploadProgress: 1,
        progressMessage: 'Analysis complete',
        response: response,
        analysisId:
            _extractAnalysisId(responseData) ??
                resolvedAnalysisId,
        foodId:
            _extractFoodId(responseData) ??
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

  void _handleAnalysisProgress(AnalysisJobProgress progress) {
    if (!mounted || !state.isUploading) return;
    state = state.copyWith(
      uploadProgress: progress.progress,
      progressMessage: progress.message,
      progressStage: progress.stage,
    );
  }

  void _handleProgress(
    int sentBytes,
    int totalBytes,
  ) {
    if (totalBytes <= 0) {
      return;
    }

    final uploadFraction = (sentBytes / totalBytes).clamp(0.0, 1.0);
    final progress = 0.01 + (uploadFraction * 0.07);
    state = state.copyWith(
      uploadProgress: progress,
      progressMessage: uploadFraction < 1 ? 'Uploading images…' : 'Upload complete. Starting analysis…',
      progressStage: uploadFraction < 1 ? 'uploading' : 'upload_complete',
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

  String? _extractAnalysisId(
    Map<String, dynamic>? responseData,
  ) {
    if (responseData == null) {
      return null;
    }

    return _firstNonEmptyText([
      responseData['analysis_id'],
      _findFirstValue(
        responseData,
        const {'analysis_id'},
      ),
    ]);
  }

  String? _extractFoodId(
    Map<String, dynamic>? responseData,
  ) {
    if (responseData == null) {
      return null;
    }

    return _firstNonEmptyText([
      responseData['food_id'],
      responseData['target_food_id'],
      _findFirstValue(
        responseData,
        const {
          'food_id',
          'target_food_id',
        },
      ),
    ]);
  }

  dynamic _findFirstValue(
    dynamic value,
    Set<String> targetKeys,
  ) {
    if (value is List) {
      for (final item in value) {
        final result = _findFirstValue(
          item,
          targetKeys,
        );

        if (_firstNonEmptyText([result]) != null) {
          return result;
        }
      }

      return null;
    }

    if (value is! Map) {
      return null;
    }

    final map = Map<String, dynamic>.from(value);

    for (final key in targetKeys) {
      final directValue = map[key];

      if (_firstNonEmptyText([directValue]) != null) {
        return directValue;
      }
    }

    for (final nestedValue in map.values) {
      final result = _findFirstValue(
        nestedValue,
        targetKeys,
      );

      if (_firstNonEmptyText([result]) != null) {
        return result;
      }
    }

    return null;
  }

  String? _firstNonEmptyText(
    List<dynamic> values,
  ) {
    for (final value in values) {
      if (value == null) {
        continue;
      }

      final text = value.toString().trim();

      if (text.isNotEmpty &&
          text.toLowerCase() != 'null') {
        return text;
      }
    }

    return null;
  }

  bool _isCompletedResult(Map<String, dynamic> data) {
    final status = data['status']?.toString().trim().toLowerCase();
    if (status == 'waiting_for_back_label' || status == 'no_food_detected') {
      return false;
    }
    const completed = {
      'completed',
      'complete',
      'success',
      'finished',
      'analysis_complete',
    };
    return status == null || completed.contains(status) ||
        data.containsKey('meal') || data.containsKey('final_result');
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
  final String progressMessage;
  final String progressStage;

  const UploadState({
    this.images = const [],
    this.isUploading = false,
    this.uploadProgress = 0,
    this.response,
    this.error,
    this.analysisId,
    this.foodId,
    this.progressMessage = 'Preparing analysis…',
    this.progressStage = 'preparing',
  });

  UploadState copyWith({
    List<UploadImage>? images,
    bool? isUploading,
    double? uploadProgress,
    UploadResponse? response,
    String? error,
    String? analysisId,
    String? foodId,
    String? progressMessage,
    String? progressStage,
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
      progressMessage: progressMessage ?? this.progressMessage,
      progressStage: progressStage ?? this.progressStage,
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
