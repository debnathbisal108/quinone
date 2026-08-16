import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';

class AppPreferencesRepository {
  AppPreferencesRepository._();

  static const String boxName = 'quinone_app_preferences';
  static const String _onboardingCompletedKey = 'onboarding_completed';
  static const String _themeModeKey = 'theme_mode';
  static const String _healthRiskNotificationsKey =
      'health_risk_notifications_enabled';
  static const String _dailyRiskNotificationsKey =
      'daily_risk_notifications_enabled';
  static const String _weeklyRiskNotificationsKey =
      'weekly_risk_notifications_enabled';
  static const String _monthlyRiskNotificationsKey =
      'monthly_risk_notifications_enabled';
  static const String _notificationPermissionRequestedKey =
      'notification_permission_requested';
  static const String _notificationSignaturePrefix =
      'health_risk_notification_signature_';

  static late Box<dynamic> _box;

  static Future<void> initialize() async {
    _box = await Hive.openBox<dynamic>(boxName);
  }

  static bool get onboardingCompleted =>
      _box.get(_onboardingCompletedKey, defaultValue: false) == true;

  static Future<void> completeOnboarding() async {
    await _box.put(_onboardingCompletedKey, true);
  }

  static ThemeMode get themeMode {
    final value = _box.get(_themeModeKey, defaultValue: 'system')?.toString();

    switch (value) {
      case 'light':
        return ThemeMode.light;
      case 'dark':
        return ThemeMode.dark;
      default:
        return ThemeMode.system;
    }
  }

  static Future<void> saveThemeMode(ThemeMode mode) async {
    await _box.put(_themeModeKey, mode.name);
  }

  static bool get healthRiskNotificationsEnabled =>
      _box.get(_healthRiskNotificationsKey, defaultValue: true) == true;

  static bool get dailyRiskNotificationsEnabled =>
      _box.get(_dailyRiskNotificationsKey, defaultValue: true) == true;

  static bool get weeklyRiskNotificationsEnabled =>
      _box.get(_weeklyRiskNotificationsKey, defaultValue: true) == true;

  static bool get monthlyRiskNotificationsEnabled =>
      _box.get(_monthlyRiskNotificationsKey, defaultValue: true) == true;

  static bool get notificationPermissionRequested =>
      _box.get(_notificationPermissionRequestedKey, defaultValue: false) == true;

  static Future<void> saveHealthRiskNotificationsEnabled(bool value) async {
    await _box.put(_healthRiskNotificationsKey, value);
  }

  static Future<void> saveDailyRiskNotificationsEnabled(bool value) async {
    await _box.put(_dailyRiskNotificationsKey, value);
  }

  static Future<void> saveWeeklyRiskNotificationsEnabled(bool value) async {
    await _box.put(_weeklyRiskNotificationsKey, value);
  }

  static Future<void> saveMonthlyRiskNotificationsEnabled(bool value) async {
    await _box.put(_monthlyRiskNotificationsKey, value);
  }

  static Future<void> markNotificationPermissionRequested() async {
    await _box.put(_notificationPermissionRequestedKey, true);
  }

  static String? notificationSignature(int periodDays) => _box
      .get('$_notificationSignaturePrefix$periodDays')
      ?.toString();

  static Future<void> saveNotificationSignature(
    int periodDays,
    String signature,
  ) async {
    await _box.put('$_notificationSignaturePrefix$periodDays', signature);
  }

  static Future<void> clearNotificationSignature(int periodDays) async {
    await _box.delete('$_notificationSignaturePrefix$periodDays');
  }

  static Future<void> clearNotificationSignatures() async {
    await Future.wait([
      for (final days in const [1, 7, 30])
        _box.delete('$_notificationSignaturePrefix$days'),
    ]);
  }
}
