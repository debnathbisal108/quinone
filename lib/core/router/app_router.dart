import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../features/onboarding/presentation/screens/onboarding_screen.dart';
import '../../features/result/presentation/screens/result_screen.dart';
import '../../features/upload/presentation/screens/upload_screen.dart';
import '../../features/profile/presentation/screens/profile_setup_screen.dart';

class AppRouter {
  AppRouter._();

  static final GoRouter router = GoRouter(
    initialLocation: '/onboarding',
    routes: [
      GoRoute(
        path: '/onboarding',
        name: 'onboarding',
        builder: (context, state) {
          return const OnboardingScreen();
        },
      ),
      GoRoute(
        path: '/upload',
        name: 'upload',
        builder: (context, state) {
          return const UploadScreen();
        },
      ),
      GoRoute(
        path: '/result',
        name: 'result',
        builder: (context, state) {
          final result = _normalizeResult(
            state.extra,
          );

          if (result == null) {
            return const _MissingResultScreen();
          }

          return ResultScreen(
            result: result,
          );
        },
      ),
    ],
    errorBuilder: (context, state) {
      return _RouterErrorScreen(
        errorMessage: state.error?.message,
      );
    },
  );

  static Map<String, dynamic>? _normalizeResult(
    Object? extra,
  ) {
    if (extra is Map<String, dynamic>) {
      return extra;
    }

    if (extra is Map) {
      try {
        return Map<String, dynamic>.from(extra);
      } catch (_) {
        return null;
      }
    }

    return null;
  }
}

class _MissingResultScreen extends StatelessWidget {
  const _MissingResultScreen();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Analysis result'),
      ),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.analytics_outlined,
                  size: 58,
                  color:
                      theme.colorScheme.onSurfaceVariant,
                ),
                const SizedBox(height: 18),
                Text(
                  'No analysis result found',
                  textAlign: TextAlign.center,
                  style:
                      theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  'Analyze a meal before opening the result page.',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyLarge?.copyWith(
                    color:
                        theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  onPressed: () {
                    context.go('/upload');
                  },
                  icon: const Icon(
                    Icons.add_a_photo_outlined,
                  ),
                  label: const Text(
                    'Analyze a meal',
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _RouterErrorScreen extends StatelessWidget {
  final String? errorMessage;

  const _RouterErrorScreen({
    required this.errorMessage,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Page unavailable'),
      ),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.error_outline_rounded,
                  size: 58,
                  color: theme.colorScheme.error,
                ),
                const SizedBox(height: 18),
                Text(
                  'This page could not be opened',
                  textAlign: TextAlign.center,
                  style:
                      theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (errorMessage != null &&
                    errorMessage!.trim().isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text(
                    errorMessage!,
                    textAlign: TextAlign.center,
                    style:
                        theme.textTheme.bodyMedium?.copyWith(
                      color:
                          theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: () {
                    context.go('/upload');
                  },
                  child: const Text(
                    'Go to food analysis',
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}