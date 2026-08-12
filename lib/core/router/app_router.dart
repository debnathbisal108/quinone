import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../preferences/app_preferences_repository.dart';
import '../../features/navigation/presentation/screens/bottom_navigation_screen.dart';
import '../../features/onboarding/presentation/screens/onboarding_screen.dart';
import '../../features/profile/presentation/screens/profile_setup_screen.dart';
import '../../features/recipe/presentation/screens/recipe_builder_screen.dart';
import '../../features/recipe/presentation/screens/serving_confirmation_screen.dart';
import '../../features/recipe/models/manual_recipe.dart';
import '../../features/result/models/analysis_result.dart';
import '../../features/result/presentation/screens/result_screen.dart';
import '../../features/upload/presentation/screens/upload_screen.dart';

class AppRouter {
  AppRouter._();

  static final GoRouter router = GoRouter(
    initialLocation:
        AppPreferencesRepository.onboardingCompleted ? '/app' : '/onboarding',
    routes: [
      GoRoute(
        path: '/onboarding',
        builder: (context, state) => const OnboardingScreen(),
      ),
      GoRoute(
        path: '/app',
        builder: (context, state) => const BottomNavigationScreen(),
      ),
      GoRoute(
        path: '/upload',
        builder: (context, state) => const UploadScreen(),
      ),
      GoRoute(
        path: '/serving-confirmation',
        builder: (context, state) {
          final extra = state.extra;
          final payload = extra is Map
              ? Map<String, dynamic>.from(extra)
              : <String, dynamic>{};
          return ServingConfirmationScreen(payload: payload);
        },
      ),
      GoRoute(
        path: '/recipe',
        builder: (context, state) {
          ManualRecipe? initialRecipe;
          var photoReview = false;
          final extra = state.extra;
          if (extra is Map) {
            photoReview = extra['photo_review'] == true;
            final rawRecipe = extra['recipe'];
            if (rawRecipe is Map) {
              try {
                initialRecipe = ManualRecipe.fromJson(
                  Map<String, dynamic>.from(rawRecipe),
                );
              } catch (_) {
                initialRecipe = null;
              }
            }
          }
          String? analysisId;
          List<Map<String, dynamic>> labelItems = const [];
          if (extra is Map) {
            analysisId = extra['analysis_id']?.toString();
            final rawLabels = extra['label_items'];
            if (rawLabels is List) {
              labelItems = rawLabels
                  .whereType<Map>()
                  .map((item) => Map<String, dynamic>.from(item))
                  .toList(growable: false);
            }
          }
          return RecipeBuilderScreen(
            initialRecipe: initialRecipe,
            photoReview: photoReview,
            analysisId: analysisId,
            labelItems: labelItems,
          );
        },
      ),
      GoRoute(
        path: '/profile',
        builder: (context, state) => const ProfileSetupScreen(),
      ),
      GoRoute(
        path: '/result',
        builder: (context, state) {
          final result = _normalizeResult(state.extra);
          if (result == null) return const _MissingResultScreen();
          return ResultScreen(result: AnalysisResult.fromJson(result));
        },
      ),
    ],
  );

  static Map<String, dynamic>? _normalizeResult(Object? extra) {
    if (extra is Map<String, dynamic>) return extra;
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
    return Scaffold(
      appBar: AppBar(title: const Text('Analysis result')),
      body: Center(
        child: FilledButton.icon(
          onPressed: () => context.go('/upload'),
          icon: const Icon(Icons.add_a_photo_outlined),
          label: const Text('Analyze a meal'),
        ),
      ),
    );
  }
}
