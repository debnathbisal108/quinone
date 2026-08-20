import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/preferences/app_preferences_repository.dart';
import '../../../upload/services/background_analysis_service.dart';
import '../../../history/models/analysis_history_record.dart';
import '../../../history/repositories/analysis_history_repository.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    unawaited(_continue());
  }

  Future<void> _continue() async {
    await Future<void>.delayed(const Duration(milliseconds: 2500));
    if (!mounted) return;
    final pending = await BackgroundAnalysisService.instance.takeRequestedRoute();
    if (!mounted) return;
    if (pending != null) {
      if (pending.path == '/result') {
        try {
          await AnalysisHistoryRepository().save(
            AnalysisHistoryRecord.fromAnalysisJson(pending.extra),
          );
        } catch (_) {
          // Opening a completed result must not be blocked by a local-history write.
        }
      }
      if (!mounted) return;
      context.go(pending.path, extra: pending.extra);
      return;
    }
    context.go(
      AppPreferencesRepository.onboardingCompleted ? '/app' : '/onboarding',
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 92,
                height: 92,
                decoration: BoxDecoration(
                  color: scheme.primaryContainer,
                  borderRadius: BorderRadius.circular(28),
                ),
                child: Icon(
                  Icons.eco_rounded,
                  size: 50,
                  color: scheme.onPrimaryContainer,
                ),
              ),
              const SizedBox(height: 22),
              Text(
                'Quinone',
                style: theme.textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                  letterSpacing: -0.5,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Nutrition intelligence for every meal',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: scheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 28),
              const SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(strokeWidth: 2.5),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
