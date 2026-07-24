import 'package:hive_flutter/hive_flutter.dart';

class ProfileRepository {
  ProfileRepository._();

  static const String _boxName = 'quinone_profile';

  static Future<Box<dynamic>> _openBox() {
    return Hive.openBox<dynamic>(_boxName);
  }

  static Future<bool> hasCompletedProfile() async {
    final box = await _openBox();

    return box.get(
          'profile_completed',
          defaultValue: false,
        ) ==
        true;
  }

  static Future<Map<String, dynamic>?> getProfile() async {
    final box = await _openBox();

    final isCompleted = box.get(
          'profile_completed',
          defaultValue: false,
        ) ==
        true;

    if (!isCompleted) {
      return null;
    }

    final profile = <String, dynamic>{
      'name': _nullableString(box.get('name')),
      'age': _nullableInt(box.get('age')),
      'sex': _nullableString(box.get('sex')),
      'height_cm': _nullableDouble(
        box.get('height_cm'),
      ),
      'weight_kg': _nullableDouble(
        box.get('weight_kg'),
      ),
      'activity_level': _nullableString(
        box.get('activity_level'),
      ),
      'goal': _nullableString(box.get('goal')),
      'health_conditions': _nullableString(
        box.get('health_conditions'),
      ),
      'allergies': _nullableString(
        box.get('allergies'),
      ),
      'dietary_preferences': _nullableString(
        box.get('dietary_preferences'),
      ),
    };

    profile.removeWhere(
      (key, value) => value == null,
    );

    return profile.isEmpty ? null : profile;
  }

  static Future<void> clearProfile() async {
    final box = await _openBox();
    await box.clear();
  }

  static String? _nullableString(
    dynamic value,
  ) {
    if (value == null) {
      return null;
    }

    final normalized = value.toString().trim();

    return normalized.isEmpty ? null : normalized;
  }

  static int? _nullableInt(
    dynamic value,
  ) {
    if (value is int) {
      return value;
    }

    if (value is num) {
      return value.toInt();
    }

    return int.tryParse(
      value?.toString() ?? '',
    );
  }

  static double? _nullableDouble(
    dynamic value,
  ) {
    if (value is double) {
      return value;
    }

    if (value is num) {
      return value.toDouble();
    }

    return double.tryParse(
      value?.toString() ?? '',
    );
  }
}