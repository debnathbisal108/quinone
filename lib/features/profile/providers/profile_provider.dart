import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/user_profile.dart';
import '../repositories/profile_repository.dart';

class ProfileState {
  const ProfileState({
    required this.profile,
    required this.isLoading,
    required this.isSaving,
    this.error,
  });

  factory ProfileState.initial() {
    return const ProfileState(
      profile: UserProfile(),
      isLoading: true,
      isSaving: false,
    );
  }

  final UserProfile profile;
  final bool isLoading;
  final bool isSaving;
  final String? error;

  bool get hasProfile => !profile.isEmpty;

  /// Clean JSON sent to FastAPI under the multipart field `profile`.
  Map<String, dynamic>? get backendPayload {
    if (profile.isEmpty) {
      return null;
    }

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
  ProfileNotifier({
    ProfileRepository? repository,
  })  : _repository =
            repository ?? ProfileRepository.instance,
        super(ProfileState.initial()) {
    loadProfile();
  }

  final ProfileRepository _repository;

  Future<void> loadProfile() async {
    state = state.copyWith(
      isLoading: true,
      clearError: true,
    );

    try {
      final savedProfile =
          await _repository.loadProfile();

      state = state.copyWith(
        profile:
            savedProfile ?? const UserProfile(),
        isLoading: false,
        clearError: true,
      );
    } catch (error) {
      state = state.copyWith(
        isLoading: false,
        error: 'Could not load profile: $error',
      );
    }
  }

  Future<bool> saveProfile() async {
    state = state.copyWith(
      isSaving: true,
      clearError: true,
    );

    try {
      final normalized =
          state.profile.normalized();

      if (normalized.isEmpty) {
        await _repository.clearProfile();
      } else {
        await _repository.saveProfile(
          normalized,
        );
      }

      state = state.copyWith(
        profile: normalized,
        isSaving: false,
        clearError: true,
      );

      return true;
    } catch (error) {
      state = state.copyWith(
        isSaving: false,
        error: 'Could not save profile: $error',
      );

      return false;
    }
  }

  Future<void> clearProfile() async {
    state = state.copyWith(
      isSaving: true,
      clearError: true,
    );

    try {
      await _repository.clearProfile();

      state = const ProfileState(
        profile: UserProfile(),
        isLoading: false,
        isSaving: false,
      );
    } catch (error) {
      state = state.copyWith(
        isSaving: false,
        error: 'Could not clear profile: $error',
      );
    }
  }

  void replaceProfile(
    UserProfile profile,
  ) {
    state = state.copyWith(
      profile: profile.normalized(),
      clearError: true,
    );
  }

  void setAge(int? value) {
    _update(
      state.profile.copyWith(
        age: value,
      ),
    );
  }

  void setSex(String? value) {
    final updated = state.profile.copyWith(
      sex: value,
    );

    // Pregnancy and lactation cannot remain enabled
    // when the selected DRI sex is not female.
    if (value != 'female') {
      _update(
        updated.copyWith(
          pregnant: false,
          trimester: null,
          lactating: false,
          lactationStageMonths: null,
        ),
      );

      return;
    }

    _update(updated);
  }

  void setHeightCm(double? value) {
    _update(
      state.profile.copyWith(
        heightCm: value,
      ),
    );
  }

  void setWeightKg(double? value) {
    _update(
      state.profile.copyWith(
        weightKg: value,
      ),
    );
  }

  void setActivityLevel(String? value) {
    _update(
      state.profile.copyWith(
        activityLevel: value,
      ),
    );
  }

  void setGoal(String? value) {
    _update(
      state.profile.copyWith(
        goal: value,
      ),
    );
  }

  void setDietType(String? value) {
    _update(
      state.profile.copyWith(
        dietType: value,
      ),
    );
  }

  void setSmokingStatus(String? value) {
    _update(
      state.profile.copyWith(
        smokingStatus: value,
      ),
    );
  }

  void setPregnant(bool value) {
    if (state.profile.sex != 'female') {
      return;
    }

    _update(
      state.profile.copyWith(
        pregnant: value,
        trimester:
            value ? state.profile.trimester : null,
      ),
    );
  }

  void setTrimester(int? value) {
    if (!state.profile.pregnant) {
      return;
    }

    _update(
      state.profile.copyWith(
        trimester: value,
      ),
    );
  }

  void setLactating(bool value) {
    if (state.profile.sex != 'female') {
      return;
    }

    _update(
      state.profile.copyWith(
        lactating: value,
        lactationStageMonths: value
            ? state.profile.lactationStageMonths
            : null,
      ),
    );
  }

  void setLactationStageMonths(
    double? value,
  ) {
    if (!state.profile.lactating) {
      return;
    }

    _update(
      state.profile.copyWith(
        lactationStageMonths: value,
      ),
    );
  }

  void setFrailty(bool value) {
    _update(
      state.profile.copyWith(
        frailty: value,
      ),
    );
  }

  void setLowAppetite(bool value) {
    _update(
      state.profile.copyWith(
        lowAppetite: value,
      ),
    );
  }

  void setResistanceTraining(bool value) {
    _update(
      state.profile.copyWith(
        resistanceTraining: value,
      ),
    );
  }

  void setEnduranceTraining(bool value) {
    _update(
      state.profile.copyWith(
        enduranceTraining: value,
      ),
    );
  }

  void setCkdStage(String? value) {
    final conditions =
        Set<String>.from(
      state.profile.chronicConditions,
    );

    if (value == null || value == 'none') {
      conditions.remove('ckd');
      conditions.remove(
        'chronic_kidney_disease',
      );
    } else {
      conditions.add(
        'chronic_kidney_disease',
      );
    }

    _update(
      state.profile.copyWith(
        ckdStage: value,
        chronicConditions: conditions,
        dialysisModality:
            value == null || value == 'none'
                ? null
                : state.profile.dialysisModality,
      ),
    );
  }

  void setDialysisModality(String? value) {
    if (!state.profile.hasCkd) {
      return;
    }

    _update(
      state.profile.copyWith(
        dialysisModality: value,
      ),
    );
  }

  void setBloodPressureStatus(
    String? value,
  ) {
    _update(
      state.profile.copyWith(
        bloodPressureStatus: value,
      ),
    );
  }

  void setGlycemicStatus(String? value) {
    _update(
      state.profile.copyWith(
        glycemicStatus: value,
      ),
    );
  }

  void setChronicConditions(
    Set<String> values,
  ) {
    final updated =
        Set<String>.from(values);

    final hasCkdCondition =
        updated.contains('ckd') ||
            updated.contains(
              'chronic_kidney_disease',
            );

    _update(
      state.profile.copyWith(
        chronicConditions: updated,
        ckdStage: hasCkdCondition
            ? state.profile.ckdStage
            : null,
        dialysisModality: hasCkdCondition
            ? state.profile.dialysisModality
            : null,
      ),
    );
  }

  void toggleChronicCondition(
    String condition,
  ) {
    final values = Set<String>.from(
      state.profile.chronicConditions,
    );

    if (values.contains(condition)) {
      values.remove(condition);
    } else {
      values.add(condition);
    }

    setChronicConditions(values);
  }

  void setMedications(
    Set<String> values,
  ) {
    _update(
      state.profile.copyWith(
        medications:
            Set<String>.from(values),
      ),
    );
  }

  void toggleMedication(String medication) {
    final values = Set<String>.from(
      state.profile.medications,
    );

    if (values.contains(medication)) {
      values.remove(medication);
    } else {
      values.add(medication);
    }

    setMedications(values);
  }

  void setAllergies(
    Set<String> values,
  ) {
    _update(
      state.profile.copyWith(
        allergies:
            Set<String>.from(values),
      ),
    );
  }

  void toggleAllergy(String allergy) {
    final values = Set<String>.from(
      state.profile.allergies,
    );

    if (values.contains(allergy)) {
      values.remove(allergy);
    } else {
      values.add(allergy);
    }

    setAllergies(values);
  }

  void clearError() {
    state = state.copyWith(
      clearError: true,
    );
  }

  void _update(UserProfile profile) {
    state = state.copyWith(
      profile: profile.normalized(),
      clearError: true,
    );
  }
}

final profileProvider = StateNotifierProvider<
    ProfileNotifier,
    ProfileState>(
  (ref) => ProfileNotifier(),
);
