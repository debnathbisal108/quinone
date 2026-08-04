import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/user_profile.dart';
import '../repositories/profile_repository.dart';

final profileProvider =
    StateNotifierProvider<ProfileNotifier, ProfileState>((ref) {
  return ProfileNotifier();
});

class ProfileState {
  const ProfileState({
    this.profile = const UserProfile(),
    this.isLoading = false,
    this.isSaving = false,
    this.error,
  });

  final UserProfile profile;
  final bool isLoading;
  final bool isSaving;
  final String? error;

  bool get hasProfile => !profile.isEmpty;

  Map<String, dynamic>? get backendPayload {
    if (profile.isEmpty) return null;
    final payload = profile.toBackendJson();
    return payload.isEmpty ? null : payload;
  }

  ProfileState copyWith({
    UserProfile? profile,
    bool? isLoading,
    bool? isSaving,
    String? error,
    bool clearError = false,
  }) {
    return ProfileState(
      profile: profile ?? this.profile,
      isLoading: isLoading ?? this.isLoading,
      isSaving: isSaving ?? this.isSaving,
      error: clearError ? null : error ?? this.error,
    );
  }
}

class ProfileNotifier extends StateNotifier<ProfileState> {
  ProfileNotifier() : super(const ProfileState(isLoading: true)) {
    loadProfile();
  }

  Future<void> loadProfile() async {
    try {
      state = state.copyWith(
        profile: await ProfileRepository.getProfile() ?? const UserProfile(),
        isLoading: false,
        clearError: true,
      );
    } catch (_) {
      state = state.copyWith(
        isLoading: false,
        error: 'Your saved profile could not be loaded.',
      );
    }
  }

  Future<bool> saveProfile() async {
    state = state.copyWith(isSaving: true, clearError: true);
    try {
      if (state.profile.isEmpty) {
        await ProfileRepository.clearProfile();
      } else {
        await ProfileRepository.saveProfile(state.profile);
      }
      state = state.copyWith(isSaving: false, clearError: true);
      return true;
    } catch (_) {
      state = state.copyWith(
        isSaving: false,
        error: 'Your profile could not be saved.',
      );
      return false;
    }
  }

  Future<void> clearProfile() async {
    await ProfileRepository.clearProfile();
    state = const ProfileState(profile: UserProfile());
  }

  void clearError() => state = state.copyWith(clearError: true);
  void update(UserProfile profile) =>
      state = state.copyWith(profile: profile, clearError: true);

  void setAge(int? value) => update(state.profile.copyWith(age: value, ageMonths: null));
  void setAgeMonths(int? value) =>
      update(state.profile.copyWith(ageMonths: value, age: null));
  void setAgeUnit(String value) => update(state.profile.copyWith(
        ageUnit: value,
        age: value == 'years' ? state.profile.age : null,
        ageMonths: value == 'months' ? state.profile.ageMonths : null,
      ));
  void setSex(String? value) => update(state.profile.copyWith(
        sex: value,
        pregnant: value == 'female' ? state.profile.pregnant : false,
        trimester: value == 'female' ? state.profile.trimester : null,
        lactating: value == 'female' ? state.profile.lactating : false,
        lactationStageMonths:
            value == 'female' ? state.profile.lactationStageMonths : null,
      ));
  void setHeight(double? value) => update(state.profile.copyWith(heightCm: value));
  void setWeight(double? value) => update(state.profile.copyWith(weightKg: value));
  void setActivity(String? value) =>
      update(state.profile.copyWith(activityLevel: value));
  void setGoal(String? value) => update(state.profile.copyWith(goal: value));
  void setDiet(String? value) => update(state.profile.copyWith(dietType: value));
  void setDietPattern(String? value) =>
      update(state.profile.copyWith(dietPattern: value));
  void setSmoking(String? value) =>
      update(state.profile.copyWith(smokingStatus: value));
  void setBloodPressureStatus(String? value) =>
      update(state.profile.copyWith(bloodPressureStatus: value));
  void setGlycemicStatus(String? value) =>
      update(state.profile.copyWith(glycemicStatus: value));
  void setPregnant(bool value) => update(state.profile.copyWith(
        pregnant: value,
        trimester: value ? state.profile.trimester : null,
      ));
  void setTrimester(int? value) => update(state.profile.copyWith(trimester: value));
  void setLactating(bool value) => update(state.profile.copyWith(
        lactating: value,
        lactationStageMonths: value ? state.profile.lactationStageMonths : null,
      ));
  void setLactationMonths(double? value) =>
      update(state.profile.copyWith(lactationStageMonths: value));
  void setFrailty(bool value) => update(state.profile.copyWith(frailty: value));
  void setLowAppetite(bool value) =>
      update(state.profile.copyWith(lowAppetite: value));
  void setResistanceTraining(bool value) =>
      update(state.profile.copyWith(resistanceTraining: value));
  void setEnduranceTraining(bool value) =>
      update(state.profile.copyWith(enduranceTraining: value));

  void setCkdStage(String? value) {
    final conditions = Set<String>.from(state.profile.chronicConditions);
    if (value == null || value == 'none') {
      conditions.remove('chronic_kidney_disease');
    } else {
      conditions.add('chronic_kidney_disease');
    }
    update(state.profile.copyWith(
      ckdStage: value,
      chronicConditions: conditions,
      dialysisModality:
          value == null || value == 'none' ? null : state.profile.dialysisModality,
    ));
  }

  void setDialysisModality(String? value) =>
      update(state.profile.copyWith(dialysisModality: value));

  void toggleCondition(String value) {
    final values = Set<String>.from(state.profile.chronicConditions);
    values.contains(value) ? values.remove(value) : values.add(value);
    update(state.profile.copyWith(
      chronicConditions: values,
      ckdStage: values.contains('chronic_kidney_disease')
          ? state.profile.ckdStage
          : null,
      dialysisModality: values.contains('chronic_kidney_disease')
          ? state.profile.dialysisModality
          : null,
    ));
  }

  void toggleMedication(String value) {
    final values = Set<String>.from(state.profile.medications);
    values.contains(value) ? values.remove(value) : values.add(value);
    update(state.profile.copyWith(medications: values));
  }

  void toggleAllergy(String value) {
    final values = Set<String>.from(state.profile.allergies);
    values.contains(value) ? values.remove(value) : values.add(value);
    update(state.profile.copyWith(allergies: values));
  }

  // Compatibility aliases used by the existing onboarding profile screen.
  void setHeightCm(double? value) => setHeight(value);
  void setWeightKg(double? value) => setWeight(value);
  void setLactationStageMonths(double? value) =>
      setLactationMonths(value);
  void setActivityLevel(String? value) => setActivity(value);
  void setDietType(String? value) => setDiet(value);
  void setSmokingStatus(String? value) => setSmoking(value);
  void toggleChronicCondition(String value) => toggleCondition(value);
}
