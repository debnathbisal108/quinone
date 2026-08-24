import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../notifications/services/health_risk_notification_service.dart';
import '../../upload/services/analysis_image_archive_service.dart';
import '../models/analysis_history_record.dart';
import '../repositories/analysis_history_repository.dart';

final analysisHistoryRepositoryProvider = Provider<AnalysisHistoryRepository>(
  (ref) => AnalysisHistoryRepository(),
);

final analysisHistoryProvider = StateNotifierProvider<
    AnalysisHistoryNotifier, List<AnalysisHistoryRecord>>((ref) {
  return AnalysisHistoryNotifier(
    repository: ref.watch(analysisHistoryRepositoryProvider),
    onHistoryChanged: (records, {required requestPermission}) {
      unawaited(
        HealthRiskNotificationService.instance.refresh(
          records,
          requestPermissionIfNeeded: requestPermission,
        ),
      );
    },
  );
});

typedef AnalysisHistoryChanged = void Function(
  List<AnalysisHistoryRecord> records, {
  required bool requestPermission,
});

class AnalysisHistoryNotifier
    extends StateNotifier<List<AnalysisHistoryRecord>> {
  AnalysisHistoryNotifier({
    required AnalysisHistoryRepository repository,
    AnalysisHistoryChanged? onHistoryChanged,
  })
      : _repository = repository,
        _onHistoryChanged = onHistoryChanged,
        super(repository.getAll());

  final AnalysisHistoryRepository _repository;
  final AnalysisHistoryChanged? _onHistoryChanged;

  Future<void> saveResult(Map<String, dynamic> result) async {
    final status = result['status']?.toString().toLowerCase();
    if (status == 'waiting_for_back_label' || status == 'no_food_detected') {
      return;
    }
    final inputMethod = result['input_method']?.toString().trim().toLowerCase();
    final shouldAttachPending = inputMethod != 'manual_recipe' && inputMethod != 'draft_guidance';
    final enriched = shouldAttachPending
        ? AnalysisImageArchiveService.instance.attachPendingImages(result)
        : result;
    final record = AnalysisHistoryRecord.fromAnalysisJson(enriched);
    final imagePaths = enriched['meal_image_paths'];
    if (imagePaths is List && imagePaths.isNotEmpty) {
      await AnalysisImageArchiveService.instance.clearPendingMealImages();
    }
    await _repository.save(record);
    state = _repository.getAll();
    _onHistoryChanged?.call(state, requestPermission: true);
  }

  Future<void> delete(String analysisId) async {
    await _repository.delete(analysisId);
    state = _repository.getAll();
    _onHistoryChanged?.call(state, requestPermission: false);
  }

  Future<void> clear() async {
    await _repository.clear();
    state = const [];
    _onHistoryChanged?.call(state, requestPermission: false);
  }

  void refresh() {
    state = _repository.getAll();
    _onHistoryChanged?.call(state, requestPermission: false);
  }
}
