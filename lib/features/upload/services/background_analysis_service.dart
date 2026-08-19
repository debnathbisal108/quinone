import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_foreground_task/flutter_foreground_task.dart';

import '../../../core/api/dio_client.dart';
import '../../../core/config/api_config.dart';

const _jobIdKey = 'quinone_background_analysis_job_id';
const _jobUrlKey = 'quinone_background_analysis_job_url';
const _pendingResultKey = 'quinone_background_analysis_pending_result';
const _pendingStatusKey = 'quinone_background_analysis_pending_status';
const _openRequestedKey = 'quinone_background_analysis_open_requested';
const _pendingErrorKey = 'quinone_background_analysis_pending_error';

@pragma('vm:entry-point')
void backgroundAnalysisStartCallback() {
  FlutterForegroundTask.setTaskHandler(_BackgroundAnalysisTaskHandler());
}

class BackgroundAnalysisRoute {
  const BackgroundAnalysisRoute(this.path, this.extra);

  final String path;
  final Map<String, dynamic> extra;
}

class BackgroundAnalysisService {
  BackgroundAnalysisService._();

  static final BackgroundAnalysisService instance = BackgroundAnalysisService._();

  void initialize() {
    FlutterForegroundTask.init(
      androidNotificationOptions: AndroidNotificationOptions(
        channelId: 'quinone_meal_analysis',
        channelName: 'Meal analysis',
        channelDescription: 'Shows meal-analysis progress while Quinone is in the background.',
        onlyAlertOnce: true,
      ),
      iosNotificationOptions: IOSNotificationOptions(
        showNotification: true,
        playSound: false,
      ),
      foregroundTaskOptions: ForegroundTaskOptions(
        eventAction: ForegroundTaskEventAction.repeat(1500),
        autoRunOnBoot: false,
        autoRunOnMyPackageReplaced: false,
        allowWakeLock: true,
        allowWifiLock: true,
      ),
    );
  }

  Future<void> start(String jobId) async {
    final id = jobId.trim();
    if (id.isEmpty) return;

    final permission = await FlutterForegroundTask.checkNotificationPermission();
    if (permission != NotificationPermission.granted) {
      await FlutterForegroundTask.requestNotificationPermission();
    }

    await FlutterForegroundTask.saveData(key: _jobIdKey, value: id);
    await FlutterForegroundTask.saveData(
      key: _jobUrlKey,
      value: '${DioClient.baseUrl}${ApiConfig.analysisJobEndpoint(id)}',
    );
    await FlutterForegroundTask.removeData(key: _pendingResultKey);
    await FlutterForegroundTask.removeData(key: _pendingStatusKey);
    await FlutterForegroundTask.removeData(key: _pendingErrorKey);
    await FlutterForegroundTask.saveData(key: _openRequestedKey, value: false);

    if (await FlutterForegroundTask.isRunningService) {
      await FlutterForegroundTask.restartService();
      return;
    }

    await FlutterForegroundTask.startService(
      serviceId: 7319,
      notificationTitle: 'Analyzing meal',
      notificationText: 'Starting analysis…',
      notificationInitialRoute: '/splash',
      callback: backgroundAnalysisStartCallback,
    );
  }

  Future<void> stopAndClear() async {
    if (await FlutterForegroundTask.isRunningService) {
      await FlutterForegroundTask.stopService();
    }
    await FlutterForegroundTask.removeData(key: _jobIdKey);
    await FlutterForegroundTask.removeData(key: _jobUrlKey);
    await FlutterForegroundTask.removeData(key: _pendingResultKey);
    await FlutterForegroundTask.removeData(key: _pendingStatusKey);
    await FlutterForegroundTask.removeData(key: _pendingErrorKey);
    await FlutterForegroundTask.removeData(key: _openRequestedKey);
  }

  Future<BackgroundAnalysisRoute?> takeRequestedRoute() async {
    final openRequested = await FlutterForegroundTask.getData(key: _openRequestedKey);
    if (openRequested != true) return null;

    final raw = await FlutterForegroundTask.getData(key: _pendingResultKey);
    Map<String, dynamic>? payload;
    if (raw is String && raw.trim().isNotEmpty) {
      try {
        final decoded = jsonDecode(raw);
        if (decoded is Map) {
          payload = Map<String, dynamic>.from(decoded);
        }
      } catch (_) {
        payload = null;
      }
    }
    if (payload == null) {
      final error = await FlutterForegroundTask.getData(key: _pendingErrorKey);
      final message = error?.toString().trim() ?? '';
      if (message.isNotEmpty) {
        payload = <String, dynamic>{
          'status': 'failed',
          'error': message,
        };
      }
    }
    if (payload == null) return null;

    await FlutterForegroundTask.saveData(key: _openRequestedKey, value: false);
    final route = routeForPayload(payload);
    if (route != null) {
      if (await FlutterForegroundTask.isRunningService) {
        await FlutterForegroundTask.stopService();
      }
      await FlutterForegroundTask.removeData(key: _pendingResultKey);
      await FlutterForegroundTask.removeData(key: _pendingStatusKey);
    }
    return route;
  }

  BackgroundAnalysisRoute? routeForPayload(Map<String, dynamic> payload) {
    final status = payload['status']?.toString().trim().toLowerCase();
    switch (status) {
      case 'waiting_for_serving_confirmation':
        return BackgroundAnalysisRoute('/serving-confirmation', payload);
      case 'waiting_for_meal_confirmation':
        final draft = payload['meal_draft'];
        if (draft is Map) {
          return BackgroundAnalysisRoute('/recipe', <String, dynamic>{
            'recipe': Map<String, dynamic>.from(draft),
            'photo_review': true,
            'analysis_id': payload['analysis_id']?.toString(),
            if (payload['label_items'] is List) 'label_items': payload['label_items'],
          });
        }
        return BackgroundAnalysisRoute('/upload', payload);
      case 'waiting_for_back_label':
      case 'no_food_detected':
      case 'failed':
      case 'cancelled':
        return BackgroundAnalysisRoute('/upload', payload);
      case 'completed':
      case 'complete':
      case 'success':
      case 'finished':
      case 'analysis_complete':
        return BackgroundAnalysisRoute('/result', payload);
      default:
        if (payload.containsKey('health_scores') ||
            payload.containsKey('final_result') ||
            payload.containsKey('nutrition') ||
            payload.containsKey('meal_analysis')) {
          return BackgroundAnalysisRoute('/result', payload);
        }
        return null;
    }
  }
}

class _BackgroundAnalysisTaskHandler extends TaskHandler {
  String? _jobUrl;
  bool _polling = false;
  bool _terminal = false;

  @override
  Future<void> onStart(DateTime timestamp, TaskStarter starter) async {
    final value = await FlutterForegroundTask.getData(key: _jobUrlKey);
    _jobUrl = value?.toString();
    if (_jobUrl == null || _jobUrl!.isEmpty) {
      _terminal = true;
      await FlutterForegroundTask.updateService(
        notificationTitle: 'Meal analysis unavailable',
        notificationText: 'Open Quinone to retry.',
      );
      return;
    }
    unawaited(_pollOnce());
  }

  @override
  void onRepeatEvent(DateTime timestamp) {
    if (_terminal || _polling) return;
    unawaited(_pollOnce());
  }

  Future<void> _pollOnce() async {
    final jobUrl = _jobUrl;
    if (jobUrl == null || jobUrl.isEmpty || _polling || _terminal) return;
    _polling = true;
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 20);
    try {
      final request = await client.getUrl(Uri.parse(jobUrl));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final response = await request.close().timeout(const Duration(seconds: 30));
      final body = await response.transform(utf8.decoder).join();
      if (response.statusCode < 200 || response.statusCode >= 300) return;
      final decoded = jsonDecode(body);
      if (decoded is! Map) return;
      final map = Map<String, dynamic>.from(decoded);
      final status = map['status']?.toString().trim().toLowerCase() ?? '';
      final progressValue = map['progress'];
      final progress = (progressValue is num
              ? progressValue.toDouble().clamp(0.0, 1.0)
              : double.tryParse(progressValue?.toString() ?? '')
                      ?.clamp(0.0, 1.0) ??
                  0.0)
          .toDouble();
      final message = map['message']?.toString().trim();
      final percent = (progress * 100).round().clamp(0, 100);

      if (_isTerminal(status)) {
        _terminal = true;
        final result = map['result'];
        if (result is Map) {
          final payload = Map<String, dynamic>.from(result);
          payload.putIfAbsent('status', () => status);
          await FlutterForegroundTask.saveData(
            key: _pendingResultKey,
            value: jsonEncode(payload),
          );
          await FlutterForegroundTask.saveData(key: _pendingStatusKey, value: status);
          await FlutterForegroundTask.updateService(
            notificationTitle: _terminalTitle(status),
            notificationText: 'Tap to open Quinone.',
          );
          FlutterForegroundTask.sendDataToMain(<String, dynamic>{
            'type': 'background_analysis_ready',
            'status': status,
          });
        } else {
          await FlutterForegroundTask.updateService(
            notificationTitle: 'Meal analysis needs attention',
            notificationText: 'Tap to return to Quinone.',
          );
        }
        return;
      }

      if (status == 'failed' || status == 'cancelled') {
        _terminal = true;
        final error = map['error']?.toString().trim();
        await FlutterForegroundTask.saveData(
          key: _pendingErrorKey,
          value: (error?.isNotEmpty == true ? error : message) ?? 'Analysis failed.',
        );
        await FlutterForegroundTask.updateService(
          notificationTitle: 'Meal analysis failed',
          notificationText: 'Tap to return to Quinone.',
        );
        return;
      }

      await FlutterForegroundTask.updateService(
        notificationTitle: 'Analyzing meal · $percent%',
        notificationText: message?.isNotEmpty == true ? message! : 'Working…',
      );
    } catch (_) {
      // Network interruptions are retried on the next foreground-task tick.
    } finally {
      client.close(force: true);
      _polling = false;
    }
  }

  bool _isTerminal(String status) => const {
        'completed',
        'waiting_for_back_label',
        'waiting_for_meal_confirmation',
        'waiting_for_serving_confirmation',
        'no_food_detected',
      }.contains(status);

  String _terminalTitle(String status) {
    switch (status) {
      case 'completed':
        return 'Meal analysis complete';
      case 'waiting_for_meal_confirmation':
        return 'Meal review is ready';
      case 'waiting_for_serving_confirmation':
        return 'Serving confirmation needed';
      case 'waiting_for_back_label':
        return 'Nutrition label needed';
      case 'no_food_detected':
        return 'Meal analysis needs attention';
      default:
        return 'Meal analysis ready';
    }
  }

  @override
  void onNotificationPressed() {
    unawaited(
      FlutterForegroundTask.saveData(key: _openRequestedKey, value: true),
    );
    FlutterForegroundTask.sendDataToMain(
      const <String, dynamic>{'type': 'background_analysis_notification_pressed'},
    );
  }

  @override
  Future<void> onDestroy(DateTime timestamp) async {}
}
