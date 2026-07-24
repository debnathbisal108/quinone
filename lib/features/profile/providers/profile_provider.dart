import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../repositories/profile_repository.dart';

final profileProvider = StateNotifierProvider<
    ProfileNotifier,
    ProfileState>(
  (ref) => ProfileNotifier(),
);

class ProfileState {
  final Map<String, dynamic>? profile;
  final bool isLoading;
  final bool isSaving;
  final String? error;

  const ProfileState({
    this.profile,
    this.isLoading = false,
    this.isSaving = false,
    this.error,
  });

  bool get hasProfile =>
      profile != null && profile!.isNotEmpty;

  ProfileState copyWith({
    Map<String, dynamic>? profile,
    bool? isLoading,
    bool? isSaving,
    String? error,
    bool clearProfile = false,
    bool clearError = false,
  }) {
    return ProfileState(
      profile: clearProfile
          ? null
          : profile ?? this.profile,
      isLoading: isLoading ?? this.isLoading,
      isSaving: isSaving ?? this.isSaving,
      error: clearError
          ? null
          : error ?? this.error,
    );
  }
}

class ProfileNotifier
    extends StateNotifier<ProfileState> {
  ProfileNotifier()
      : super(const ProfileState()) {
    loadProfile();
  }

  Future<void> loadProfile() async {
    state = state.copyWith(
      isLoading: true,
      clearError: true,
    );

    try {
      final profile =
          await ProfileRepository.getProfile();

      state = state.copyWith(
        profile: profile,
        clearProfile: profile == null,
        isLoading: false,
      );
    } catch (_) {
      state = state.copyWith(
        isLoading: false,
        error:
            'Your saved profile could not be loaded.',
      );
    }
  }

  Future<void> refresh() async {
    await loadProfile();
  }

  Future<void> clearProfile() async {
    state = state.copyWith(
      isSaving: true,
      clearError: true,
    );

    try {
      await ProfileRepository.clearProfile();

      state = state.copyWith(
        clearProfile: true,
        isSaving: false,
      );
    } catch (_) {
      state = state.copyWith(
        isSaving: false,
        error:
            'Your profile could not be deleted.',
      );
    }
  }

  void clearError() {
    state = state.copyWith(
      clearError: true,
    );
  }
}