import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'core/api/dio_client.dart';
import 'core/config/api_config.dart';
import 'core/preferences/app_preferences_repository.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';
import 'core/theme/theme_mode_provider.dart';
import 'features/history/repositories/analysis_history_repository.dart';
import 'features/history/providers/analysis_history_provider.dart';
import 'features/notifications/services/health_risk_notification_service.dart';
import 'features/upload/services/background_analysis_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  FlutterForegroundTask.initCommunicationPort();
  BackgroundAnalysisService.instance.initialize();

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

class QuinoneApp extends ConsumerStatefulWidget {
  const QuinoneApp({super.key});

  @override
  ConsumerState<QuinoneApp> createState() => _QuinoneAppState();
}

class _QuinoneAppState extends ConsumerState<QuinoneApp>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    FlutterForegroundTask.addTaskDataCallback(_onBackgroundTaskData);
  }

  @override
  void dispose() {
    FlutterForegroundTask.removeTaskDataCallback(_onBackgroundTaskData);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  void _onBackgroundTaskData(Object data) {
    if (data is! Map) return;
    if (data['type'] != 'background_analysis_notification_pressed') return;
    unawaited(_openRequestedBackgroundResult());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_openRequestedBackgroundResult());
    }
  }

  Future<void> _openRequestedBackgroundResult() async {
    final destination =
        await BackgroundAnalysisService.instance.takeRequestedRoute();
    if (destination == null) return;
    if (destination.path == '/result') {
      try {
        await ref
            .read(analysisHistoryProvider.notifier)
            .saveResult(destination.extra);
      } catch (_) {
        // Navigation to a completed result is more important than a local write.
      }
    }
    AppRouter.router.go(destination.path, extra: destination.extra);
  }

  @override
  Widget build(BuildContext context) {
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
