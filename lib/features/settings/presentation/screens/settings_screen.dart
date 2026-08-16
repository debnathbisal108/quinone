import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/preferences/app_preferences_repository.dart';
import '../../../../core/theme/theme_mode_provider.dart';
import '../../../history/providers/analysis_history_provider.dart';
import '../../../notifications/services/health_risk_notification_service.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late bool _notificationsEnabled;
  late bool _dailyEnabled;
  late bool _weeklyEnabled;
  late bool _monthlyEnabled;

  @override
  void initState() {
    super.initState();
    _notificationsEnabled =
        AppPreferencesRepository.healthRiskNotificationsEnabled;
    _dailyEnabled = AppPreferencesRepository.dailyRiskNotificationsEnabled;
    _weeklyEnabled = AppPreferencesRepository.weeklyRiskNotificationsEnabled;
    _monthlyEnabled = AppPreferencesRepository.monthlyRiskNotificationsEnabled;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final selectedMode = ref.watch(themeModeProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
        children: [
          _SettingsCard(
            title: 'Personalisation',
            subtitle: 'Edit health details and nutrient-target modifiers.',
            icon: Icons.person_outline_rounded,
            onTap: () => context.push('/profile'),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: theme.colorScheme.outlineVariant),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Appearance',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Choose light, dark, or follow your device setting.',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 16),
                SegmentedButton<ThemeMode>(
                  segments: const [
                    ButtonSegment(
                      value: ThemeMode.system,
                      icon: Icon(Icons.brightness_auto_outlined),
                      label: Text('System'),
                    ),
                    ButtonSegment(
                      value: ThemeMode.light,
                      icon: Icon(Icons.light_mode_outlined),
                      label: Text('Light'),
                    ),
                    ButtonSegment(
                      value: ThemeMode.dark,
                      icon: Icon(Icons.dark_mode_outlined),
                      label: Text('Dark'),
                    ),
                  ],
                  selected: {selectedMode},
                  onSelectionChanged: (selection) {
                    ref
                        .read(themeModeProvider.notifier)
                        .setThemeMode(selection.first);
                  },
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Container(
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerLow,
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: theme.colorScheme.outlineVariant),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SwitchListTile.adaptive(
                  value: _notificationsEnabled,
                  onChanged: _setNotificationsEnabled,
                  secondary: const Icon(Icons.notifications_active_outlined),
                  title: const Text('Nutrition pattern alerts'),
                  subtitle: const Text(
                    'Private on-device reminders from logged scores and '
                    'personalized nutrient targets.',
                  ),
                ),
                const Divider(height: 1),
                SwitchListTile.adaptive(
                  value: _dailyEnabled,
                  onChanged: _notificationsEnabled
                      ? (value) => _setPeriod(1, value)
                      : null,
                  title: const Text('Daily follow-up'),
                  subtitle: const Text('Scheduled for 9:00 AM the next day.'),
                ),
                SwitchListTile.adaptive(
                  value: _weeklyEnabled,
                  onChanged: _notificationsEnabled
                      ? (value) => _setPeriod(7, value)
                      : null,
                  title: const Text('7-day pattern'),
                  subtitle: const Text(
                    'Only after at least 4 logged days show a persistent concern.',
                  ),
                ),
                SwitchListTile.adaptive(
                  value: _monthlyEnabled,
                  onChanged: _notificationsEnabled
                      ? (value) => _setPeriod(30, value)
                      : null,
                  title: const Text('30-day pattern'),
                  subtitle: const Text(
                    'Only after at least 10 logged days show a persistent concern.',
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(18, 0, 18, 16),
                  child: Text(
                    'Alerts describe dietary-support scores—not disease risk. '
                    'Missing days and nutrients without personalized targets '
                    'do not count as low.',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _setNotificationsEnabled(bool value) async {
    setState(() => _notificationsEnabled = value);
    await AppPreferencesRepository.saveHealthRiskNotificationsEnabled(value);
    if (!value) {
      await HealthRiskNotificationService.instance.cancelAllRiskNotifications();
      return;
    }
    final granted =
        await HealthRiskNotificationService.instance.requestPermission();
    await HealthRiskNotificationService.instance.refresh(
      ref.read(analysisHistoryProvider),
    );
    if (!granted && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Notifications are blocked by the device. Enable them in system settings.',
          ),
        ),
      );
    }
  }

  Future<void> _setPeriod(int days, bool value) async {
    setState(() {
      if (days == 1) _dailyEnabled = value;
      if (days == 7) _weeklyEnabled = value;
      if (days == 30) _monthlyEnabled = value;
    });
    if (days == 1) {
      await AppPreferencesRepository.saveDailyRiskNotificationsEnabled(value);
    } else if (days == 7) {
      await AppPreferencesRepository.saveWeeklyRiskNotificationsEnabled(value);
    } else {
      await AppPreferencesRepository.saveMonthlyRiskNotificationsEnabled(value);
    }
    await HealthRiskNotificationService.instance.refresh(
      ref.read(analysisHistoryProvider),
    );
  }
}

class _SettingsCard extends StatelessWidget {
  const _SettingsCard({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      color: theme.colorScheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(22),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(22),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(
            children: [
              CircleAvatar(
                backgroundColor: theme.colorScheme.primaryContainer,
                child: Icon(icon, color: theme.colorScheme.onPrimaryContainer),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      subtitle,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded),
            ],
          ),
        ),
      ),
    );
  }
}
