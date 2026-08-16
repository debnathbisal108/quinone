import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'core/api/dio_client.dart';
import 'core/config/api_config.dart';
import 'core/preferences/app_preferences_repository.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';
import 'core/theme/theme_mode_provider.dart';
import 'features/history/repositories/analysis_history_repository.dart';
import 'features/notifications/services/health_risk_notification_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Hive.initFlutter();
  await AppPreferencesRepository.initialize();
  await AnalysisHistoryRepository.initialize();
  await HealthRiskNotificationService.instance.initialize(
    onOpen: (destination) {
      AppRouter.router.go(
        '/risk-recommendations',
        extra: <String, dynamic>{
          'period_days': destination.periodDays,
          if (destination.asOf != null)
            'as_of': destination.asOf!.toIso8601String(),
        },
      );
    },
  );

  await HealthRiskNotificationService.instance.refresh(
    AnalysisHistoryRepository().getAll(),
  );

  runApp(
    const ProviderScope(
      child: QuinoneApp(),
    ),
  );
  WidgetsBinding.instance.addPostFrameCallback((_) {
    HealthRiskNotificationService.instance.consumePendingLaunch();
  });

  // Render's free service may be asleep. Wake it while the user is browsing
  // the home screen or choosing a photograph instead of making the analysis
  // button pay the entire cold-start delay. This is best-effort and never
  // blocks app startup.
  unawaited(_warmAnalysisBackend());
}

Future<void> _warmAnalysisBackend() async {
  try {
    await DioClient.instance.get<dynamic>(
      ApiConfig.healthEndpoint,
    );
  } catch (_) {
    // The real upload flow still reports connectivity errors. A warm-up
    // failure must not interrupt onboarding or home-screen navigation.
  }
}

class QuinoneApp extends ConsumerWidget {
  const QuinoneApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeMode = ref.watch(themeModeProvider);

    return MaterialApp.router(
      title: 'Quinone',
      debugShowCheckedModeBanner: false,
      routerConfig: AppRouter.router,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: themeMode,
      builder: (context, child) {
        return GestureDetector(
          behavior: HitTestBehavior.translucent,
          onTap: () => FocusManager.instance.primaryFocus?.unfocus(),
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}
