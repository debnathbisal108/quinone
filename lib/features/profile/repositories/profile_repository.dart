import 'package:hive_flutter/hive_flutter.dart';

import '../models/user_profile.dart';

class ProfileRepository {
  ProfileRepository._();

  static const String _boxName = 'quinone_profile';
  static const String _profileKey = 'personalization_profile_v2';

  static Future<Box<dynamic>> _openBox() => Hive.openBox<dynamic>(_boxName);

  static Future<UserProfile?> getProfile() async {
    final box = await _openBox();
    final encoded = box.get(_profileKey);

    if (encoded is String && encoded.trim().isNotEmpty) {
      try {
        return UserProfile.decode(encoded);
      } catch (_) {
        // Continue to legacy migration below.
      }
    }

    final legacyCompleted = box.get('profile_completed', defaultValue: false) == true;
    if (!legacyCompleted) return null;

    final legacy = <String, dynamic>{
      'age': box.get('age'),
      'sex': box.get('sex'),
      'height_cm': box.get('height_cm'),
      'weight_kg': box.get('weight_kg'),
      'activity_level': box.get('activity_level'),
      'goal': box.get('goal'),
      'diet_type': box.get('diet_type'),
    }..removeWhere((_, value) => value == null);

    if (legacy.isEmpty) return null;

    final migrated = UserProfile.fromJson(legacy);
    await saveProfile(migrated);
    return migrated;
  }

  static Future<void> saveProfile(UserProfile profile) async {
    final box = await _openBox();
    await box.put(_profileKey, profile.encode());
    await box.put('profile_completed', !profile.isEmpty);
  }

  static Future<bool> hasCompletedProfile() async {
    final profile = await getProfile();
    return profile != null && !profile.isEmpty;
  }

  static Future<void> clearProfile() async {
    final box = await _openBox();
    await box.delete(_profileKey);
    await box.put('profile_completed', false);
  }
}
