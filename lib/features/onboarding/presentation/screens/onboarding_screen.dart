import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() =>
      _OnboardingScreenState();
}

class _OnboardingScreenState
    extends State<OnboardingScreen> {
  final PageController _pageController =
      PageController();

  int _currentPage = 0;

  static const List<_OnboardingPageData> _pages = [
    _OnboardingPageData(
      icon: Icons.camera_alt_outlined,
      title: 'Understand every meal',
      description:
          'Upload one or more food images and let Quinone identify the foods, estimate portions, and analyse the complete meal.',
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
          'Add your health information for personalised insights, or skip it and continue with a general meal analysis.',
    ),
  ];

  bool get _isLastPage =>
      _currentPage == _pages.length - 1;

  void _nextPage() {
    if (_isLastPage) {
      _openUpload();
      return;
    }

    _pageController.nextPage(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOutCubic,
    );
  }

  void _openUpload() {
    context.go('/upload');
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Align(
              alignment: Alignment.centerRight,
              child: Padding(
                padding: const EdgeInsets.only(
                  top: 8,
                  right: 12,
                ),
                child: TextButton(
                  onPressed: _openUpload,
                  child: const Text('Skip'),
                ),
              ),
            ),
            Expanded(
              child: PageView.builder(
                controller: _pageController,
                itemCount: _pages.length,
                onPageChanged: (index) {
                  setState(() {
                    _currentPage = index;
                  });
                },
                itemBuilder: (context, index) {
                  return _OnboardingPage(
                    data: _pages[index],
                  );
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                24,
                12,
                24,
                24,
              ),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment:
                        MainAxisAlignment.center,
                    children: List.generate(
                      _pages.length,
                      (index) {
                        final isSelected =
                            index == _currentPage;

                        return AnimatedContainer(
                          duration: const Duration(
                            milliseconds: 220,
                          ),
                          curve: Curves.easeOut,
                          width: isSelected ? 28 : 8,
                          height: 8,
                          margin:
                              const EdgeInsets.symmetric(
                            horizontal: 4,
                          ),
                          decoration: BoxDecoration(
                            color: isSelected
                                ? colorScheme.primary
                                : colorScheme
                                    .surfaceContainerHighest,
                            borderRadius:
                                BorderRadius.circular(999),
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(height: 28),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: _nextPage,
                      child: Text(
                        _isLastPage
                            ? 'Start analysing'
                            : 'Continue',
                      ),
                    ),
                  ),
                  if (_isLastPage) ...[
                    const SizedBox(height: 10),
                    TextButton(
                      onPressed: () {
                        context.push('/profile');
                      },
                      child: const Text(
                        'Set up my profile first',
                      ),
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

class _OnboardingPage extends StatelessWidget {
  final _OnboardingPageData data;

  const _OnboardingPage({
    required this.data,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: 28,
      ),
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
          ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: 520,
            ),
            child: Text(
              data.description,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyLarge?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _OnboardingPageData {
  final IconData icon;
  final String title;
  final String description;

  const _OnboardingPageData({
    required this.icon,
    required this.title,
    required this.description,
  });
}