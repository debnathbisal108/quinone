import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/analysis_history_record.dart';
import '../repositories/analysis_history_repository.dart';

final analysisHistoryRepositoryProvider = Provider<AnalysisHistoryRepository>(
  (ref) => AnalysisHistoryRepository(),
);

final analysisHistoryProvider = StateNotifierProvider<
    AnalysisHistoryNotifier, List<AnalysisHistoryRecord>>((ref) {
  return AnalysisHistoryNotifier(
    repository: ref.watch(analysisHistoryRepositoryProvider),
  );
});

class AnalysisHistoryNotifier
    extends StateNotifier<List<AnalysisHistoryRecord>> {
  AnalysisHistoryNotifier({required AnalysisHistoryRepository repository})
      : _repository = repository,
        super(repository.getAll());

  final AnalysisHistoryRepository _repository;

  Future<void> saveResult(Map<String, dynamic> result) async {
    final status = result['status']?.toString().toLowerCase();
    if (status == 'waiting_for_back_label' || status == 'no_food_detected') {
      return;
    }
    final record = AnalysisHistoryRecord.fromAnalysisJson(result);
    await _repository.save(record);
    state = _repository.getAll();
  }

  Future<void> delete(String analysisId) async {
    await _repository.delete(analysisId);
    state = _repository.getAll();
  }

  Future<void> clear() async {
    await _repository.clear();
    state = const [];
  }

  void refresh() => state = _repository.getAll();
}
