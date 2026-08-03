import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/user_profile.dart';

class ProfileRepository {
  ProfileRepository._();

  static final ProfileRepository instance =
      ProfileRepository._();

  static const _storageKey = 'user_profile';

  Future<UserProfile?> loadProfile() async {
    final prefs = await SharedPreferences.getInstance();

    final jsonString = prefs.getString(_storageKey);

    if (jsonString == null || jsonString.isEmpty) {
      return null;
    }

    try {
      final json =
          jsonDecode(jsonString) as Map<String, dynamic>;

      return UserProfile.fromJson(json);
    } catch (_) {
      return null;
    }
  }

  Future<void> saveProfile(
    UserProfile profile,
  ) async {
    final prefs = await SharedPreferences.getInstance();

    await prefs.setString(
      _storageKey,
      jsonEncode(profile.toJson()),
    );
  }

  Future<void> clearProfile() async {
    final prefs = await SharedPreferences.getInstance();

    await prefs.remove(_storageKey);
  }

  Future<bool> hasProfile() async {
    final prefs = await SharedPreferences.getInstance();

    return prefs.containsKey(_storageKey);
  }
}
