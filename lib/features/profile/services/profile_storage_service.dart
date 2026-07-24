import 'package:hive_flutter/hive_flutter.dart';

import '../models/user_profile.dart';

class ProfileStorageService {
  ProfileStorageService._();

  static const String _boxName = 'quinone_profile';
  static const String _profileKey = 'profile';

  static Future<Box<String>> _openBox() async {
    return await Hive.openBox<String>(_boxName);
  }

  static Future<UserProfile?> loadProfile() async {
    final box = await _openBox();

    final encoded = box.get(_profileKey);

    if (encoded == null || encoded.isEmpty) {
      return null;
    }

    try {
      return UserProfile.decode(encoded);
    } catch (_) {
      return null;
    }
  }

  static Future<void> saveProfile(
    UserProfile profile,
  ) async {
    final box = await _openBox();

    await box.put(
      _profileKey,
      profile.encode(),
    );
  }

  static Future<void> clearProfile() async {
    final box = await _openBox();

    await box.delete(_profileKey);
  }

  static Future<bool> hasProfile() async {
    final profile = await loadProfile();

    return profile != null && !profile.isEmpty;
  }
}