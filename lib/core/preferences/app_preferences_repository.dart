import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';

class AppPreferencesRepository {
  AppPreferencesRepository._();

  static const String boxName = 'quinone_app_preferences';
  static const String _onboardingCompletedKey = 'onboarding_completed';
  static const String _themeModeKey = 'theme_mode';

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
}
