import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../profile/providers/profile_provider.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({
    super.key,
  });

  @override
  ConsumerState<ProfileScreen> createState() =>
      _ProfileScreenState();
}

class _ProfileScreenState
    extends ConsumerState<ProfileScreen> {
  final _ageController = TextEditingController();
  final _heightController = TextEditingController();
  final _weightController = TextEditingController();
  final _lactationMonthsController =
      TextEditingController();

  bool _controllersInitialized = false;

  @override
  void dispose() {
    _ageController.dispose();
    _heightController.dispose();
    _weightController.dispose();
    _lactationMonthsController.dispose();

    super.dispose();
  }

  void _initializeControllers(
    ProfileState state,
  ) {
    if (_controllersInitialized ||
        state.isLoading) {
      return;
    }

    final profile = state.profile;

    _ageController.text =
        profile.age?.toString() ?? '';

    _heightController.text =
        _formatInputNumber(profile.heightCm);

    _weightController.text =
        _formatInputNumber(profile.weightKg);

    _lactationMonthsController.text =
        _formatInputNumber(
      profile.lactationStageMonths,
    );

    _controllersInitialized = true;
  }

  String _formatInputNumber(double? value) {
    if (value == null) {
      return '';
    }

    if (value == value.roundToDouble()) {
      return value.round().toString();
    }

    return value.toStringAsFixed(1);
  }

  int? _parseInt(String value) {
    final cleaned = value.trim();

    if (cleaned.isEmpty) {
      return null;
    }

    return int.tryParse(cleaned);
  }

  double? _parseDouble(String value) {
    final cleaned = value.trim();

    if (cleaned.isEmpty) {
      return null;
    }

    return double.tryParse(cleaned);
  }

  Future<void> _saveProfile() async {
    FocusScope.of(context).unfocus();

    final notifier = ref.read(
      profileProvider.notifier,
    );

    notifier.setAge(
      _parseInt(_ageController.text),
    );

    notifier.setHeightCm(
      _parseDouble(_heightController.text),
    );

    notifier.setWeightKg(
      _parseDouble(_weightController.text),
    );

    notifier.setLactationStageMonths(
      _parseDouble(
        _lactationMonthsController.text,
      ),
    );

    final saved = await notifier.saveProfile();

    if (!mounted) {
      return;
    }

    if (saved) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Personalization profile saved.',
          ),
        ),
      );
    }
  }

  Future<void> _clearProfile() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text(
            'Clear personalization profile?',
          ),
          content: const Text(
            'All saved personal, lifestyle and health selections will be removed.',
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(false);
              },
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(true);
              },
              child: const Text('Clear'),
            ),
          ],
        );
      },
    );

    if (confirmed != true) {
      return;
    }

    await ref
        .read(profileProvider.notifier)
        .clearProfile();

    if (!mounted) {
      return;
    }

    _ageController.clear();
    _heightController.clear();
    _weightController.clear();
    _lactationMonthsController.clear();

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(
          'Personalization profile cleared.',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(profileProvider);

    _initializeControllers(state);

    final theme = Theme.of(context);
    final profile = state.profile;
    final notifier = ref.read(
      profileProvider.notifier,
    );

    ref.listen<ProfileState>(
      profileProvider,
      (previous, next) {
        final error = next.error;

        if (error != null &&
            error != previous?.error) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(error),
            ),
          );

          notifier.clearError();
        }
      },
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Personalization',
        ),
        leading: IconButton(
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go('/home');
            }
          },
          icon: const Icon(
            Icons.arrow_back_rounded,
          ),
        ),
      ),
      body: state.isLoading
          ? const Center(
              child: CircularProgressIndicator(),
            )
          : SafeArea(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(
                  20,
                  12,
                  20,
                  36,
                ),
                child: Align(
                  alignment: Alignment.topCenter,
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(
                      maxWidth: 760,
                    ),
                    child: Column(
                      crossAxisAlignment:
                          CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          'Personalize your results',
                          style: theme
                              .textTheme
                              .headlineSmall
                              ?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Everything is optional. Your selections are used to personalize health scores and nutrient targets.',
                          style: theme
                              .textTheme
                              .bodyLarge
                              ?.copyWith(
                            color: theme
                                .colorScheme
                                .onSurfaceVariant,
                            height: 1.45,
                          ),
                        ),
                        const SizedBox(height: 24),

                        _ProfileSection(
                          title: 'Personal details',
                          icon: Icons.person_outline_rounded,
                          child: Column(
                            crossAxisAlignment:
                                CrossAxisAlignment.stretch,
                            children: [
                              _NumberField(
                                controller: _ageController,
                                label: 'Age',
                                suffix: 'years',
                                hint: 'For example, 30',
                                allowDecimal: false,
                                onChanged: (value) {
                                  notifier.setAge(
                                    _parseInt(value),
                                  );
                                },
                              ),
                              const SizedBox(height: 16),
                              Text(
                                'Sex used for nutrient recommendations',
                                style: theme
                                    .textTheme
                                    .titleSmall
                                    ?.copyWith(
                                  fontWeight:
                                      FontWeight.w700,
                                ),
                              ),
                              const SizedBox(height: 10),
                              _SingleChoiceChips(
                                selectedValue:
                                    profile.sex,
                                options: const [
                                  _ChoiceOption(
                                    label: 'Female',
                                    value: 'female',
                                  ),
                                  _ChoiceOption(
                                    label: 'Male',
                                    value: 'male',
                                  ),
                                ],
                                onSelected: notifier.setSex,
                              ),
                              const SizedBox(height: 16),
                              Row(
                                children: [
                                  Expanded(
                                    child: _NumberField(
                                      controller:
                                          _heightController,
                                      label: 'Height',
                                      suffix: 'cm',
                                      hint: '170',
                                      onChanged: (value) {
                                        notifier.setHeightCm(
                                          _parseDouble(
                                            value,
                                          ),
                                        );
                                      },
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: _NumberField(
                                      controller:
                                          _weightController,
                                      label: 'Weight',
                                      suffix: 'kg',
                                      hint: '70',
                                      onChanged: (value) {
                                        notifier.setWeightKg(
                                          _parseDouble(
                                            value,
                                          ),
                                        );
                                      },
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 16),

                        _ProfileSection(
                          title: 'Lifestyle',
                          icon: Icons.directions_run_rounded,
                          child: Column(
                            crossAxisAlignment:
                                CrossAxisAlignment.stretch,
                            children: [
                              const _FieldLabel(
                                'Activity level',
                              ),
                              const SizedBox(height: 10),
                              _SingleChoiceChips(
                                selectedValue:
                                    profile.activityLevel,
                                options: const [
                                  _ChoiceOption(
                                    label: 'Sedentary',
                                    value: 'sedentary',
                                  ),
                                  _ChoiceOption(
                                    label: 'Lightly active',
                                    value: 'low_active',
                                  ),
                                  _ChoiceOption(
                                    label: 'Active',
                                    value: 'active',
                                  ),
                                  _ChoiceOption(
                                    label: 'Very active',
                                    value: 'very_active',
                                  ),
                                ],
                                onSelected:
                                    notifier.setActivityLevel,
                              ),
                              const SizedBox(height: 20),
                              const _FieldLabel(
                                'Primary goal',
                              ),
                              const SizedBox(height: 10),
                              _SingleChoiceChips(
                                selectedValue:
                                    profile.goal,
                                options: const [
                                  _ChoiceOption(
                                    label: 'General health',
                                    value: 'general_health',
                                  ),
                                  _ChoiceOption(
                                    label: 'Maintain weight',
                                    value:
                                        'weight_maintenance',
                                  ),
                                  _ChoiceOption(
                                    label: 'Lose fat',
                                    value: 'fat_loss',
                                  ),
                                  _ChoiceOption(
                                    label: 'Gain muscle',
                                    value: 'muscle_gain',
                                  ),
                                ],
                                onSelected: notifier.setGoal,
                              ),
                              const SizedBox(height: 20),
                              const _FieldLabel(
                                'Diet type',
                              ),
                              const SizedBox(height: 10),
                              _SingleChoiceChips(
                                selectedValue:
                                    profile.dietType,
                                options: const [
                                  _ChoiceOption(
                                    label: 'No restriction',
                                    value: 'omnivore',
                                  ),
                                  _ChoiceOption(
                                    label: 'Vegetarian',
                                    value: 'vegetarian',
                                  ),
                                  _ChoiceOption(
                                    label: 'Vegan',
                                    value: 'vegan',
                                  ),
                                ],
                                onSelected:
                                    notifier.setDietType,
                              ),
                              const SizedBox(height: 20),
                              const _FieldLabel(
                                'Smoking',
                              ),
                              const SizedBox(height: 10),
                              _SingleChoiceChips(
                                selectedValue:
                                    profile.smokingStatus,
                                options: const [
                                  _ChoiceOption(
                                    label: 'Non-smoker',
                                    value: 'non_smoker',
                                  ),
                                  _ChoiceOption(
                                    label: 'Former smoker',
                                    value: 'former_smoker',
                                  ),
                                  _ChoiceOption(
                                    label: 'Current smoker',
                                    value: 'smoker',
                                  ),
                                ],
                                onSelected:
                                    notifier.setSmokingStatus,
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 16),

                        _ProfileSection(
                          title: 'Training and appetite',
                          icon: Icons.fitness_center_rounded,
                          child: Column(
                            children: [
                              _OptionalSwitchTile(
                                title: 'Resistance training',
                                subtitle:
                                    'Weight training or muscle-focused exercise',
                                value:
                                    profile.resistanceTraining,
                                onChanged:
                                    notifier.setResistanceTraining,
                              ),
                              _OptionalSwitchTile(
                                title: 'Endurance training',
                                subtitle:
                                    'Running, cycling, swimming or similar training',
                                value:
                                    profile.enduranceTraining,
                                onChanged:
                                    notifier.setEnduranceTraining,
                              ),
                              _OptionalSwitchTile(
                                title: 'Frailty',
                                subtitle:
                                    'Reduced strength or physical resilience',
                                value: profile.frailty,
                                onChanged:
                                    notifier.setFrailty,
                              ),
                              _OptionalSwitchTile(
                                title: 'Low appetite',
                                subtitle:
                                    'Regular difficulty eating enough food',
                                value: profile.lowAppetite,
                                onChanged:
                                    notifier.setLowAppetite,
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 16),

                        _ProfileSection(
                          title: 'Health conditions',
                          icon:
                              Icons.health_and_safety_outlined,
                          child: Column(
                            crossAxisAlignment:
                                CrossAxisAlignment.stretch,
                            children: [
                              Text(
                                'Select all that apply',
                                style: theme
                                    .textTheme
                                    .bodyMedium
                                    ?.copyWith(
                                  color: theme
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                              ),
                              const SizedBox(height: 12),
                              _MultiChoiceChips(
                                selectedValues:
                                    profile.chronicConditions,
                                options:
                                    _conditionOptions,
                                onToggle: notifier
                                    .toggleChronicCondition,
                              ),
                              if (profile.hasCkd) ...[
                                const SizedBox(height: 22),
                                const _FieldLabel(
                                  'CKD stage',
                                ),
                                const SizedBox(height: 10),
                                _SingleChoiceChips(
                                  selectedValue:
                                      profile.ckdStage,
                                  allowClear: false,
                                  options: const [
                                    _ChoiceOption(
                                      label: 'Unknown',
                                      value: 'unknown',
                                    ),
                                    _ChoiceOption(
                                      label: 'G1',
                                      value: 'g1',
                                    ),
                                    _ChoiceOption(
                                      label: 'G2',
                                      value: 'g2',
                                    ),
                                    _ChoiceOption(
                                      label: 'G3a',
                                      value: 'g3a',
                                    ),
                                    _ChoiceOption(
                                      label: 'G3b',
                                      value: 'g3b',
                                    ),
                                    _ChoiceOption(
                                      label: 'G4',
                                      value: 'g4',
                                    ),
                                    _ChoiceOption(
                                      label: 'G5',
                                      value: 'g5',
                                    ),
                                  ],
                                  onSelected:
                                      notifier.setCkdStage,
                                ),
                                const SizedBox(height: 20),
                                const _FieldLabel(
                                  'Dialysis',
                                ),
                                const SizedBox(height: 10),
                                _SingleChoiceChips(
                                  selectedValue: profile
                                      .dialysisModality,
                                  options: const [
                                    _ChoiceOption(
                                      label: 'None',
                                      value: 'none',
                                    ),
                                    _ChoiceOption(
                                      label: 'Hemodialysis',
                                      value: 'hemodialysis',
                                    ),
                                    _ChoiceOption(
                                      label:
                                          'Peritoneal dialysis',
                                      value:
                                          'peritoneal_dialysis',
                                    ),
                                  ],
                                  onSelected: notifier
                                      .setDialysisModality,
                                ),
                              ],
                            ],
                          ),
                        ),

                        const SizedBox(height: 16),

                        if (profile.sex == 'female')
                          _ProfileSection(
                            title:
                                'Pregnancy and lactation',
                            icon:
                                Icons.child_friendly_rounded,
                            child: Column(
                              crossAxisAlignment:
                                  CrossAxisAlignment.stretch,
                              children: [
                                _OptionalSwitchTile(
                                  title: 'Pregnant',
                                  subtitle:
                                      'Enables pregnancy-specific nutrient targets',
                                  value:
                                      profile.pregnant,
                                  onChanged:
                                      notifier.setPregnant,
                                ),
                                if (profile.pregnant) ...[
                                  const SizedBox(
                                    height: 12,
                                  ),
                                  const _FieldLabel(
                                    'Trimester',
                                  ),
                                  const SizedBox(
                                    height: 10,
                                  ),
                                  _SingleChoiceChips(
                                    selectedValue: profile
                                        .trimester
                                        ?.toString(),
                                    allowClear: false,
                                    options: const [
                                      _ChoiceOption(
                                        label: 'First',
                                        value: '1',
                                      ),
                                      _ChoiceOption(
                                        label: 'Second',
                                        value: '2',
                                      ),
                                      _ChoiceOption(
                                        label: 'Third',
                                        value: '3',
                                      ),
                                    ],
                                    onSelected: (value) {
                                      notifier.setTrimester(
                                        int.tryParse(
                                          value ?? '',
                                        ),
                                      );
                                    },
                                  ),
                                ],
                                const SizedBox(height: 8),
                                _OptionalSwitchTile(
                                  title: 'Lactating',
                                  subtitle:
                                      'Enables lactation-specific nutrient targets',
                                  value:
                                      profile.lactating,
                                  onChanged:
                                      notifier.setLactating,
                                ),
                                if (profile.lactating) ...[
                                  const SizedBox(
                                    height: 12,
                                  ),
                                  _NumberField(
                                    controller:
                                        _lactationMonthsController,
                                    label:
                                        'Months postpartum',
                                    suffix: 'months',
                                    hint: 'For example, 4',
                                    onChanged: (value) {
                                      notifier
                                          .setLactationStageMonths(
                                        _parseDouble(
                                          value,
                                        ),
                                      );
                                    },
                                  ),
                                ],
                              ],
                            ),
                          ),

                        if (profile.sex == 'female')
                          const SizedBox(height: 16),

                        _ProfileSection(
                          title: 'Medications',
                          icon:
                              Icons.medication_outlined,
                          child: Column(
                            crossAxisAlignment:
                                CrossAxisAlignment.stretch,
                            children: [
                              Text(
                                'Only select medicines you currently use. These create safety flags and do not automatically change every target.',
                                style: theme
                                    .textTheme
                                    .bodyMedium
                                    ?.copyWith(
                                  color: theme
                                      .colorScheme
                                      .onSurfaceVariant,
                                  height: 1.4,
                                ),
                              ),
                              const SizedBox(height: 12),
                              _MultiChoiceChips(
                                selectedValues:
                                    profile.medications,
                                options:
                                    _medicationOptions,
                                onToggle:
                                    notifier.toggleMedication,
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 16),

                        _ProfileSection(
                          title: 'Allergies',
                          icon: Icons.warning_amber_rounded,
                          child: Column(
                            crossAxisAlignment:
                                CrossAxisAlignment.stretch,
                            children: [
                              Text(
                                'Allergies are stored for future meal-safety checks. They do not currently modify nutrient scores.',
                                style: theme
                                    .textTheme
                                    .bodyMedium
                                    ?.copyWith(
                                  color: theme
                                      .colorScheme
                                      .onSurfaceVariant,
                                  height: 1.4,
                                ),
                              ),
                              const SizedBox(height: 12),
                              _MultiChoiceChips(
                                selectedValues:
                                    profile.allergies,
                                options: _allergyOptions,
                                onToggle:
                                    notifier.toggleAllergy,
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 24),

                        SizedBox(
                          height: 54,
                          child: FilledButton.icon(
                            onPressed: state.isSaving
                                ? null
                                : _saveProfile,
                            icon: state.isSaving
                                ? const SizedBox.square(
                                    dimension: 20,
                                    child:
                                        CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Icon(
                                    Icons.check_rounded,
                                  ),
                            label: Text(
                              state.isSaving
                                  ? 'Saving…'
                                  : 'Save profile',
                            ),
                          ),
                        ),

                        const SizedBox(height: 10),

                        TextButton.icon(
                          onPressed: state.isSaving
                              ? null
                              : _clearProfile,
                          icon: const Icon(
                            Icons.delete_outline_rounded,
                          ),
                          label: const Text(
                            'Clear profile',
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
    );
  }
}

const _conditionOptions = <_ChoiceOption>[
  _ChoiceOption(
    label: 'Prediabetes',
    value: 'prediabetes',
  ),
  _ChoiceOption(
    label: 'Type 2 diabetes',
    value: 'type_2_diabetes',
  ),
  _ChoiceOption(
    label: 'Hypertension',
    value: 'hypertension',
  ),
  _ChoiceOption(
    label: 'Chronic kidney disease',
    value: 'chronic_kidney_disease',
  ),
  _ChoiceOption(
    label: 'Heart failure',
    value: 'heart_failure',
  ),
  _ChoiceOption(
    label: 'High cholesterol',
    value: 'dyslipidemia',
  ),
  _ChoiceOption(
    label: 'IBS',
    value: 'ibs',
  ),
  _ChoiceOption(
    label: 'IBD',
    value: 'ibd',
  ),
  _ChoiceOption(
    label: 'Osteoarthritis',
    value: 'osteoarthritis',
  ),
  _ChoiceOption(
    label: 'Rheumatoid arthritis',
    value: 'rheumatoid_arthritis',
  ),
  _ChoiceOption(
    label: 'Osteoporosis or osteopenia',
    value: 'osteoporosis',
  ),
];

const _medicationOptions = <_ChoiceOption>[
  _ChoiceOption(
    label: 'Metformin',
    value: 'metformin',
  ),
  _ChoiceOption(
    label: 'Warfarin',
    value: 'warfarin',
  ),
  _ChoiceOption(
    label: 'Proton pump inhibitor',
    value: 'ppi',
  ),
];

const _allergyOptions = <_ChoiceOption>[
  _ChoiceOption(
    label: 'Milk',
    value: 'milk',
  ),
  _ChoiceOption(
    label: 'Egg',
    value: 'egg',
  ),
  _ChoiceOption(
    label: 'Peanut',
    value: 'peanut',
  ),
  _ChoiceOption(
    label: 'Tree nuts',
    value: 'tree_nuts',
  ),
  _ChoiceOption(
    label: 'Soy',
    value: 'soy',
  ),
  _ChoiceOption(
    label: 'Wheat',
    value: 'wheat',
  ),
  _ChoiceOption(
    label: 'Fish',
    value: 'fish',
  ),
  _ChoiceOption(
    label: 'Shellfish',
    value: 'shellfish',
  ),
  _ChoiceOption(
    label: 'Sesame',
    value: 'sesame',
  ),
];

class _ProfileSection extends StatelessWidget {
  const _ProfileSection({
    required this.title,
    required this.icon,
    required this.child,
  });

  final String title;
  final IconData icon;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(
                icon,
                color: theme.colorScheme.primary,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  style:
                      theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          child,
        ],
      ),
    );
  }
}

class _FieldLabel extends StatelessWidget {
  const _FieldLabel(this.label);

  final String label;

  @override
  Widget build(BuildContext context) {
    return Text(
      label,
      style: Theme.of(context)
          .textTheme
          .titleSmall
          ?.copyWith(
            fontWeight: FontWeight.w700,
          ),
    );
  }
}

class _NumberField extends StatelessWidget {
  const _NumberField({
    required this.controller,
    required this.label,
    required this.suffix,
    required this.hint,
    required this.onChanged,
    this.allowDecimal = true,
  });

  final TextEditingController controller;
  final String label;
  final String suffix;
  final String hint;
  final ValueChanged<String> onChanged;
  final bool allowDecimal;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: TextInputType.numberWithOptions(
        decimal: allowDecimal,
      ),
      inputFormatters: [
        if (allowDecimal)
          FilteringTextInputFormatter.allow(
            RegExp(r'^\d*\.?\d{0,2}'),
          )
        else
          FilteringTextInputFormatter.digitsOnly,
      ],
      onChanged: onChanged,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        suffixText: suffix,
        border: const OutlineInputBorder(),
      ),
    );
  }
}

class _OptionalSwitchTile extends StatelessWidget {
  const _OptionalSwitchTile({
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
  });

  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return SwitchListTile.adaptive(
      contentPadding: EdgeInsets.zero,
      title: Text(
        title,
        style: const TextStyle(
          fontWeight: FontWeight.w700,
        ),
      ),
      subtitle: Text(subtitle),
      value: value,
      onChanged: onChanged,
    );
  }
}

class _SingleChoiceChips extends StatelessWidget {
  const _SingleChoiceChips({
    required this.selectedValue,
    required this.options,
    required this.onSelected,
    this.allowClear = true,
  });

  final String? selectedValue;
  final List<_ChoiceOption> options;
  final ValueChanged<String?> onSelected;
  final bool allowClear;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: options.map(
        (option) {
          final selected =
              selectedValue == option.value;

          return ChoiceChip(
            label: Text(option.label),
            selected: selected,
            onSelected: (enabled) {
              if (enabled) {
                onSelected(option.value);
              } else if (allowClear) {
                onSelected(null);
              }
            },
          );
        },
      ).toList(),
    );
  }
}

class _MultiChoiceChips extends StatelessWidget {
  const _MultiChoiceChips({
    required this.selectedValues,
    required this.options,
    required this.onToggle,
  });

  final Set<String> selectedValues;
  final List<_ChoiceOption> options;
  final ValueChanged<String> onToggle;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: options.map(
        (option) {
          return FilterChip(
            label: Text(option.label),
            selected: selectedValues.contains(
              option.value,
            ),
            onSelected: (_) {
              onToggle(option.value);
            },
          );
        },
      ).toList(),
    );
  }
}

class _ChoiceOption {
  const _ChoiceOption({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;
}
