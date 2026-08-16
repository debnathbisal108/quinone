import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

import '../../../core/preferences/app_preferences_repository.dart';
import '../../history/models/analysis_history_record.dart';
import '../models/health_risk_snapshot.dart';

class HealthRiskNotificationDestination {
  const HealthRiskNotificationDestination({
    required this.periodDays,
    this.asOf,
  });

  final int periodDays;
  final DateTime? asOf;
}

typedef HealthRiskNotificationOpen = void Function(
  HealthRiskNotificationDestination destination,
);

class HealthRiskNotificationService {
  HealthRiskNotificationService._();

  static final HealthRiskNotificationService instance =
      HealthRiskNotificationService._();

  static const _channelId = 'quinone_health_risk_patterns';
  static const _channelName = 'Nutrition pattern alerts';
  static const _notificationIds = <int, int>{1: 7101, 7: 7107, 30: 7130};

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();
  HealthRiskNotificationOpen? _onOpen;
  HealthRiskNotificationDestination? _pendingLaunchDestination;
  bool _initialized = false;
  bool _navigationReady = false;

  Future<void> initialize({
    required HealthRiskNotificationOpen onOpen,
  }) async {
    if (_initialized) {
      _onOpen = onOpen;
      return;
    }
    _onOpen = onOpen;
    tz_data.initializeTimeZones();

    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const darwin = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );
    const settings = InitializationSettings(
      android: android,
      iOS: darwin,
      macOS: darwin,
    );
    await _plugin.initialize(
      settings,
      onDidReceiveNotificationResponse: (response) {
        _openPayload(response.payload);
      },
    );

    final launch = await _plugin.getNotificationAppLaunchDetails();
    if (launch?.didNotificationLaunchApp == true) {
      _pendingLaunchDestination = _destinationFromPayload(
        launch?.notificationResponse?.payload,
      );
    }
    _initialized = true;
  }

  void consumePendingLaunch() {
    _navigationReady = true;
    final destination = _pendingLaunchDestination;
    _pendingLaunchDestination = null;
    if (destination != null) _onOpen?.call(destination);
  }

  Future<bool> requestPermission() async {
    if (!_initialized) return false;
    await AppPreferencesRepository.markNotificationPermissionRequested();
    var granted = true;
    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    if (android != null) {
      granted = await android.requestNotificationsPermission() ?? false;
    }
    final ios = _plugin.resolvePlatformSpecificImplementation<
        IOSFlutterLocalNotificationsPlugin>();
    if (ios != null) {
      granted = await ios.requestPermissions(
            alert: true,
            badge: true,
            sound: true,
          ) ??
          false;
    }
    final mac = _plugin.resolvePlatformSpecificImplementation<
        MacOSFlutterLocalNotificationsPlugin>();
    if (mac != null) {
      granted = await mac.requestPermissions(
            alert: true,
            badge: true,
            sound: true,
          ) ??
          false;
    }
    return granted;
  }

  Future<void> refresh(
    List<AnalysisHistoryRecord> records, {
    bool requestPermissionIfNeeded = false,
  }) async {
    if (!_initialized) return;
    try {
      if (!AppPreferencesRepository.healthRiskNotificationsEnabled) {
        await cancelAllRiskNotifications();
        return;
      }
      if (requestPermissionIfNeeded &&
          !AppPreferencesRepository.notificationPermissionRequested) {
        await requestPermission();
      }

      for (final period in HealthRiskMonitor.supportedPeriods) {
        if (!_periodEnabled(period)) {
          await _cancelPeriod(period);
          continue;
        }
        final snapshot = HealthRiskMonitor.evaluate(
          records,
          periodDays: period,
        );
        if (!snapshot.hasConcerns) {
          if (period == 1 &&
              !_hasRecordsToday(records) &&
              await _hasPendingPeriod(period)) {
            // Preserve yesterday's completed-day follow-up until it fires.
            // Opening the app before 9 AM must not silently cancel it.
            continue;
          }
          await _cancelPeriod(period);
          continue;
        }
        await _schedule(snapshot);
      }
    } catch (error, stackTrace) {
      // Notifications are supportive and must never make meal analysis fail.
      debugPrint('Health-risk notification refresh failed: $error');
      debugPrintStack(stackTrace: stackTrace);
    }
  }

  Future<void> cancelAllRiskNotifications() async {
    for (final id in _notificationIds.values) {
      await _plugin.cancel(id);
    }
    await AppPreferencesRepository.clearNotificationSignatures();
  }

  Future<void> _schedule(HealthRiskSnapshot snapshot) async {
    final id = _notificationIds[snapshot.periodDays];
    if (id == null) return;
    final stored =
        AppPreferencesRepository.notificationSignature(snapshot.periodDays);
    final pending = await _plugin.pendingNotificationRequests();
    final sameRiskStillPending =
        stored?.startsWith('${snapshot.signature}|') == true &&
            pending.any((item) => item.id == id);
    if (sameRiskStillPending) return;

    final localDue = _dueDate(snapshot.periodDays);
    final bucket = _bucket(localDue, snapshot.periodDays);
    final signature = '${snapshot.signature}|$bucket';

    await _plugin.cancel(id);
    final scheduledUtc = localDue.toUtc();
    final scheduled = tz.TZDateTime.from(scheduledUtc, tz.UTC);
    final payload = jsonEncode(<String, dynamic>{
      'route': '/risk-recommendations',
      'period_days': snapshot.periodDays,
      'as_of': snapshot.asOf.toIso8601String(),
    });
    final body = snapshot.notificationBody;
    final details = NotificationDetails(
      android: AndroidNotificationDetails(
        _channelId,
        _channelName,
        channelDescription:
            'Personalized reminders based on logged nutrition patterns.',
        importance: Importance.high,
        priority: Priority.high,
        styleInformation: BigTextStyleInformation(body),
      ),
      iOS: const DarwinNotificationDetails(
        presentAlert: true,
        presentBadge: true,
        presentSound: true,
      ),
      macOS: const DarwinNotificationDetails(
        presentAlert: true,
        presentBadge: true,
        presentSound: true,
      ),
    );
    await _plugin.zonedSchedule(
      id,
      snapshot.notificationTitle,
      body,
      scheduled,
      details,
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      payload: payload,
    );
    await AppPreferencesRepository.saveNotificationSignature(
      snapshot.periodDays,
      signature,
    );
  }

  DateTime _dueDate(int periodDays) {
    final now = DateTime.now();
    final future = now.add(Duration(days: periodDays));
    // A predictable morning reminder is easier to act on than an alert at the
    // exact time the last meal happened.
    return DateTime(future.year, future.month, future.day, 9);
  }

  String _bucket(DateTime due, int periodDays) {
    if (periodDays == 1) {
      return '${due.year}-${due.month}-${due.day}';
    }
    if (periodDays == 7) {
      return '${due.year}-week-${due.difference(DateTime(due.year)).inDays ~/ 7}';
    }
    return '${due.year}-${due.month}';
  }

  bool _periodEnabled(int periodDays) {
    switch (periodDays) {
      case 1:
        return AppPreferencesRepository.dailyRiskNotificationsEnabled;
      case 7:
        return AppPreferencesRepository.weeklyRiskNotificationsEnabled;
      case 30:
        return AppPreferencesRepository.monthlyRiskNotificationsEnabled;
      default:
        return false;
    }
  }

  Future<void> _cancelPeriod(int periodDays) async {
    final id = _notificationIds[periodDays];
    if (id != null) await _plugin.cancel(id);
    await AppPreferencesRepository.clearNotificationSignature(periodDays);
  }

  Future<bool> _hasPendingPeriod(int periodDays) async {
    final id = _notificationIds[periodDays];
    if (id == null) return false;
    final pending = await _plugin.pendingNotificationRequests();
    return pending.any((item) => item.id == id);
  }

  bool _hasRecordsToday(List<AnalysisHistoryRecord> records) {
    final now = DateTime.now();
    return records.any((record) {
      final local = record.createdAt.toLocal();
      return local.year == now.year &&
          local.month == now.month &&
          local.day == now.day;
    });
  }

  void _openPayload(String? payload) {
    final destination = _destinationFromPayload(payload);
    if (destination == null) return;
    if (!_navigationReady) {
      _pendingLaunchDestination = destination;
      return;
    }
    _onOpen?.call(destination);
  }

  HealthRiskNotificationDestination? _destinationFromPayload(String? payload) {
    if (payload == null || payload.trim().isEmpty) return null;
    try {
      final decoded = jsonDecode(payload);
      if (decoded is! Map) return null;
      final value = decoded['period_days'];
      final parsed = value is num
          ? value.toInt()
          : int.tryParse(value?.toString() ?? '');
      if (!HealthRiskMonitor.supportedPeriods.contains(parsed)) return null;
      return HealthRiskNotificationDestination(
        periodDays: parsed!,
        asOf: DateTime.tryParse(decoded['as_of']?.toString() ?? '')?.toLocal(),
      );
    } catch (_) {
      return null;
    }
  }
}
