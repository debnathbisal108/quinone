import 'package:hive_flutter/hive_flutter.dart';

import '../models/analysis_history_record.dart';

class AnalysisHistoryRepository {
  AnalysisHistoryRepository();

  static const _boxName = 'analysis_history_v1';
  static Box<dynamic>? _box;

  static Future<void> initialize() async {
    _box ??= await Hive.openBox<dynamic>(_boxName);
  }

  static Box<dynamic> get _historyBox {
    final box = _box;
    if (box == null) {
      throw StateError('AnalysisHistoryRepository.initialize() was not called.');
    }
    return box;
  }

  Future<void> save(AnalysisHistoryRecord record) async {
    await _historyBox.put(record.analysisId, record.toJson());
  }

  List<AnalysisHistoryRecord> getAll() {
    final records = <AnalysisHistoryRecord>[];
    for (final value in _historyBox.values) {
      if (value is Map) {
        try {
          records.add(
            AnalysisHistoryRecord.fromJson(Map<String, dynamic>.from(value)),
          );
        } catch (_) {
          // Ignore one damaged local row instead of breaking the whole history.
        }
      }
    }
    records.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return records;
  }

  Future<void> delete(String analysisId) => _historyBox.delete(analysisId);

  Future<void> clear() => _historyBox.clear();
}
