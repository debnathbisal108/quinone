import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/preferences/app_preferences_repository.dart';
import '../../../profile/models/user_profile.dart';
import '../../../profile/repositories/profile_repository.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();
  final TextEditingController _nameController = TextEditingController();
  int _currentPage = 0;
  String? _nameError;

  static const List<_OnboardingPageData> _pages = [
    _OnboardingPageData(
      icon: Icons.person_outline_rounded,
      title: 'Welcome to Quinone',
      description:
          'First, tell us what to call you. This name stays on your device and is not used for nutrition calculations.',
    ),
    _OnboardingPageData(
      icon: Icons.analytics_outlined,
      title: 'Go beyond calories',
      description:
          'Explore nutrition, health scores, ingredient insights, processing indicators, and practical recommendations.',
    ),
    _OnboardingPageData(
      icon: Icons.person_outline_rounded,
      title: 'Personalise when ready',
      description:
          'Add health information for personalised insights, or skip it and continue with a general analysis.',
    ),
  ];

  bool get _isLastPage => _currentPage == _pages.length - 1;

  Future<void> _finish({required bool openProfile}) async {
    if (!await _saveNameIfNeeded()) return;
    await AppPreferencesRepository.completeOnboarding();
    if (!mounted) return;
    context.go(openProfile ? '/profile' : '/app');
  }

  Future<void> _nextPage() async {
    if (_currentPage == 0 && !await _saveNameIfNeeded()) return;

    if (_isLastPage) {
      await _finish(openProfile: false);
      return;
    }

    await _pageController.nextPage(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOutCubic,
    );
  }

  Future<bool> _saveNameIfNeeded() async {
    final name = _nameController.text.trim();
    if (name.length < 2) {
      setState(() => _nameError = 'Enter at least 2 characters.');
      return false;
    }
    final existing = await ProfileRepository.getProfile() ?? const UserProfile();
    await ProfileRepository.saveProfile(existing.copyWith(displayName: name));
    if (mounted) setState(() => _nameError = null);
    return true;
  }

  @override
  void dispose() {
    _pageController.dispose();
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        child: Column(
          children: [
            Align(
              alignment: Alignment.centerRight,
              child: Padding(
                padding: const EdgeInsets.only(top: 8, right: 12),
                child: _currentPage == 0
                    ? const SizedBox(height: 48)
                    : TextButton(
                        onPressed: () => _finish(openProfile: false),
                        child: const Text('Skip'),
                      ),
              ),
            ),
            Expanded(
              child: PageView.builder(
                controller: _pageController,
                itemCount: _pages.length,
                onPageChanged: (index) => setState(() => _currentPage = index),
                itemBuilder: (context, index) {
                  final data = _pages[index];
                  return LayoutBuilder(
                    builder: (context, constraints) => SingleChildScrollView(
                      keyboardDismissBehavior:
                          ScrollViewKeyboardDismissBehavior.onDrag,
                      padding: const EdgeInsets.symmetric(horizontal: 28),
                      child: ConstrainedBox(
                        constraints: BoxConstraints(
                          minHeight: constraints.maxHeight,
                        ),
                        child: IntrinsicHeight(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Container(
                                width: 152,
                                height: 152,
                                decoration: BoxDecoration(
                                  color: colorScheme.primaryContainer,
                                  shape: BoxShape.circle,
                                ),
                                child: Icon(
                                  data.icon,
                                  size: 68,
                                  color: colorScheme.onPrimaryContainer,
                                ),
                              ),
                              const SizedBox(height: 44),
                              Text(
                                data.title,
                                textAlign: TextAlign.center,
                                style: theme.textTheme.headlineMedium?.copyWith(
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                              const SizedBox(height: 16),
                              Text(
                                data.description,
                                textAlign: TextAlign.center,
                                style: theme.textTheme.bodyLarge?.copyWith(
                                  color: colorScheme.onSurfaceVariant,
                                  height: 1.45,
                                ),
                              ),
                              if (index == 0) ...[
                                const SizedBox(height: 26),
                                TextField(
                                  controller: _nameController,
                                  autofocus: true,
                                  scrollPadding:
                                      const EdgeInsets.only(bottom: 140),
                                  textCapitalization:
                                      TextCapitalization.words,
                                  textInputAction: TextInputAction.done,
                                  decoration: InputDecoration(
                                    labelText: 'Your name',
                                    hintText: 'What should Quinone call you?',
                                    errorText: _nameError,
                                    prefixIcon:
                                        const Icon(Icons.badge_outlined),
                                  ),
                                  onChanged: (_) {
                                    if (_nameError != null) {
                                      setState(() => _nameError = null);
                                    }
                                  },
                                  onSubmitted: (_) => _nextPage(),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(_pages.length, (index) {
                      final selected = index == _currentPage;
                      return AnimatedContainer(
                        duration: const Duration(milliseconds: 220),
                        width: selected ? 28 : 8,
                        height: 8,
                        margin: const EdgeInsets.symmetric(horizontal: 4),
                        decoration: BoxDecoration(
                          color: selected
                              ? colorScheme.primary
                              : colorScheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(999),
                        ),
                      );
                    }),
                  ),
                  const SizedBox(height: 28),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _nextPage,
                      child: Text(_isLastPage ? 'Start analysing' : 'Continue'),
                    ),
                  ),
                  if (_isLastPage) ...[
                    const SizedBox(height: 10),
                    TextButton(
                      onPressed: () => _finish(openProfile: true),
                      child: const Text('Set up my profile first'),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OnboardingPageData {
  const _OnboardingPageData({
    required this.icon,
    required this.title,
    required this.description,
  });

  final IconData icon;
  final String title;
  final String description;
}
