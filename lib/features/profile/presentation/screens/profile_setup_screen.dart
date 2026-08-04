import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../providers/profile_provider.dart';

class ProfileSetupScreen extends ConsumerStatefulWidget {
  const ProfileSetupScreen({super.key});

  @override
  ConsumerState<ProfileSetupScreen> createState() =>
      _ProfileSetupScreenState();
}

class _ProfileSetupScreenState extends ConsumerState<ProfileSetupScreen> {
  final _formKey = GlobalKey<FormState>();
  final _age = TextEditingController();
  final _height = TextEditingController();
  final _weight = TextEditingController();
  final _lactationMonths = TextEditingController();
  bool _initialized = false;

  @override
  void dispose() {
    _age.dispose();
    _height.dispose();
    _weight.dispose();
    _lactationMonths.dispose();
    super.dispose();
  }

  void _initialize(ProfileState state) {
    if (_initialized || state.isLoading) return;
    final profile = state.profile;
    _age.text = profile.ageUnit == 'months'
        ? profile.ageMonths?.toString() ?? ''
        : profile.age?.toString() ?? '';
    _height.text = _format(profile.heightCm);
    _weight.text = _format(profile.weightKg);
    _lactationMonths.text = _format(profile.lactationStageMonths);
    _initialized = true;
  }

  String _format(double? value) {
    if (value == null) return '';
    return value == value.roundToDouble()
        ? value.round().toString()
        : value.toStringAsFixed(1);
  }

  int? _int(String value) => int.tryParse(value.trim());
  double? _double(String value) => double.tryParse(value.trim());

  String? _validateAge(String? value, String unit) {
    final parsed = int.tryParse(value?.trim() ?? '');
    if (value == null || value.trim().isEmpty) return null;
    if (parsed == null || parsed < 0) return 'Enter a valid age.';
    if (unit == 'months' && parsed > 35) {
      return 'Use years for ages above 35 months.';
    }
    if (unit == 'years' && parsed > 129) return 'Enter an age below 130.';
    return null;
  }

  String? _validatePositive(String? value, String label) {
    if (value == null || value.trim().isEmpty) return null;
    final parsed = double.tryParse(value.trim());
    if (parsed == null || parsed <= 0) return 'Enter a valid $label.';
    return null;
  }

  Future<void> _save() async {
    FocusScope.of(context).unfocus();
    if (!(_formKey.currentState?.validate() ?? false)) return;

    final state = ref.read(profileProvider);
    final profile = state.profile;

    if (profile.pregnant && profile.trimester == null) {
      _message('Select the pregnancy trimester.');
      return;
    }
    if (profile.lactating && profile.lactationStageMonths == null) {
      _message('Enter the number of months postpartum.');
      return;
    }
    if (profile.hasCkd && profile.ckdStage == null) {
      _message('Select the CKD stage or Unknown.');
      return;
    }

    final saved = await ref.read(profileProvider.notifier).saveProfile();
    if (!mounted) return;
    if (saved) {
      _message('Personalization profile saved.');
      context.go('/upload');
    }
  }

  void _message(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(profileProvider);
    _initialize(state);
    final profile = state.profile;
    final notifier = ref.read(profileProvider.notifier);

    ref.listen<ProfileState>(profileProvider, (previous, next) {
      if (next.error != null && next.error != previous?.error) {
        _message(next.error!);
        notifier.clearError();
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Personalization')),
      body: state.isLoading
          ? const Center(child: CircularProgressIndicator())
          : SafeArea(
              child: Form(
                key: _formKey,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 36),
                  children: [
                    Text(
                      'Personalize your results',
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Everything is optional. Selected details personalize health scores and daily nutrient targets.',
                      style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                            color: Theme.of(context).colorScheme.onSurfaceVariant,
                            height: 1.4,
                          ),
                    ),
                    const SizedBox(height: 20),
                    _Section(
                      title: 'Personal details',
                      icon: Icons.person_outline_rounded,
                      children: [
                        SegmentedButton<String>(
                          segments: const [
                            ButtonSegment(value: 'years', label: Text('Years')),
                            ButtonSegment(value: 'months', label: Text('Months')),
                          ],
                          selected: {profile.ageUnit},
                          onSelectionChanged: (value) {
                            notifier.setAgeUnit(value.first);
                            _age.clear();
                          },
                        ),
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: _age,
                          keyboardType: TextInputType.number,
                          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                          decoration: InputDecoration(
                            labelText: 'Age',
                            suffixText: profile.ageUnit,
                          ),
                          validator: (value) => _validateAge(value, profile.ageUnit),
                          onChanged: (value) => profile.ageUnit == 'months'
                              ? notifier.setAgeMonths(_int(value))
                              : notifier.setAge(_int(value)),
                        ),
                        const SizedBox(height: 16),
                        _Choices(
                          label: 'Sex used for nutrient recommendations',
                          selected: profile.sex,
                          options: const {'female': 'Female', 'male': 'Male'},
                          onSelected: notifier.setSex,
                        ),
                        const SizedBox(height: 16),
                        Row(
                          children: [
                            Expanded(
                              child: TextFormField(
                                controller: _height,
                                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                decoration: const InputDecoration(labelText: 'Height', suffixText: 'cm'),
                                validator: (value) => _validatePositive(value, 'height'),
                                onChanged: (value) => notifier.setHeight(_double(value)),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: TextFormField(
                                controller: _weight,
                                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                decoration: const InputDecoration(labelText: 'Weight', suffixText: 'kg'),
                                validator: (value) => _validatePositive(value, 'weight'),
                                onChanged: (value) => notifier.setWeight(_double(value)),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                    _Section(
                      title: 'Lifestyle and goals',
                      icon: Icons.directions_run_rounded,
                      children: [
                        _Choices(
                          label: 'Activity level',
                          selected: profile.activityLevel,
                          options: const {
                            'sedentary': 'Sedentary',
                            'low_active': 'Lightly active',
                            'active': 'Active',
                            'very_active': 'Very active',
                          },
                          onSelected: notifier.setActivity,
                        ),
                        _Choices(
                          label: 'Primary goal',
                          selected: profile.goal,
                          options: const {
                            'general_health': 'General health',
                            'weight_maintenance': 'Maintain weight',
                            'fat_loss': 'Lose fat',
                            'muscle_gain': 'Gain muscle',
                          },
                          onSelected: notifier.setGoal,
                        ),
                        _Choices(
                          label: 'Diet type',
                          selected: profile.dietType,
                          options: const {
                            'omnivore': 'No restriction',
                            'vegetarian': 'Vegetarian',
                            'vegan': 'Vegan',
                          },
                          onSelected: notifier.setDiet,
                        ),
                        _Choices(
                          label: 'Special diet pattern',
                          selected: profile.dietPattern,
                          options: const {
                            'low_carb': 'Low carbohydrate',
                            'ketogenic': 'Ketogenic',
                          },
                          onSelected: notifier.setDietPattern,
                        ),
                        _Choices(
                          label: 'Smoking',
                          selected: profile.smokingStatus,
                          options: const {
                            'non_smoker': 'Non-smoker',
                            'former_smoker': 'Former smoker',
                            'smoker': 'Current smoker',
                          },
                          onSelected: notifier.setSmoking,
                        ),
                      ],
                    ),
                    _Section(
                      title: 'Training and appetite',
                      icon: Icons.fitness_center_rounded,
                      children: [
                        _Toggle('Resistance training', profile.resistanceTraining, notifier.setResistanceTraining),
                        _Toggle('Endurance training', profile.enduranceTraining, notifier.setEnduranceTraining),
                        _Toggle('Frailty or reduced physical resilience', profile.frailty, notifier.setFrailty),
                        _Toggle('Low appetite', profile.lowAppetite, notifier.setLowAppetite),
                      ],
                    ),
                    _Section(
                      title: 'Health conditions',
                      icon: Icons.health_and_safety_outlined,
                      children: [
                        _MultiChoices(
                          selected: profile.chronicConditions,
                          options: _conditions,
                          onToggle: notifier.toggleCondition,
                        ),
                        _Choices(
                          label: 'Blood-pressure status',
                          selected: profile.bloodPressureStatus,
                          options: const {
                            'normal': 'Normal',
                            'elevated': 'Elevated',
                            'hypertension': 'Hypertension',
                          },
                          onSelected: notifier.setBloodPressureStatus,
                        ),
                        _Choices(
                          label: 'Glycemic status',
                          selected: profile.glycemicStatus,
                          options: const {
                            'normal': 'Normal',
                            'prediabetes': 'Prediabetes',
                            'type_2_diabetes': 'Type 2 diabetes',
                          },
                          onSelected: notifier.setGlycemicStatus,
                        ),
                        if (profile.hasCkd) ...[
                          _Choices(
                            label: 'CKD stage',
                            selected: profile.ckdStage,
                            allowClear: false,
                            options: const {
                              'unknown': 'Unknown',
                              'g1': 'G1',
                              'g2': 'G2',
                              'g3a': 'G3a',
                              'g3b': 'G3b',
                              'g4': 'G4',
                              'g5': 'G5',
                            },
                            onSelected: notifier.setCkdStage,
                          ),
                          _Choices(
                            label: 'Dialysis',
                            selected: profile.dialysisModality,
                            options: const {
                              'none': 'None',
                              'hemodialysis': 'Hemodialysis',
                              'peritoneal_dialysis': 'Peritoneal dialysis',
                            },
                            onSelected: notifier.setDialysisModality,
                          ),
                        ],
                      ],
                    ),
                    if (profile.sex == 'female')
                      _Section(
                        title: 'Pregnancy and lactation',
                        icon: Icons.child_friendly_rounded,
                        children: [
                          _Toggle('Pregnant', profile.pregnant, notifier.setPregnant),
                          if (profile.pregnant)
                            _Choices(
                              label: 'Trimester',
                              selected: profile.trimester?.toString(),
                              allowClear: false,
                              options: const {'1': 'First', '2': 'Second', '3': 'Third'},
                              onSelected: (value) => notifier.setTrimester(int.tryParse(value ?? '')),
                            ),
                          _Toggle('Lactating', profile.lactating, notifier.setLactating),
                          if (profile.lactating)
                            TextFormField(
                              controller: _lactationMonths,
                              keyboardType: const TextInputType.numberWithOptions(decimal: true),
                              decoration: const InputDecoration(
                                labelText: 'Months postpartum',
                                suffixText: 'months',
                              ),
                              validator: (value) => _validatePositive(value, 'postpartum duration'),
                              onChanged: (value) => notifier.setLactationMonths(_double(value)),
                            ),
                        ],
                      ),
                    _Section(
                      title: 'Medications',
                      icon: Icons.medication_outlined,
                      children: [
                        _MultiChoices(
                          selected: profile.medications,
                          options: _medications,
                          onToggle: notifier.toggleMedication,
                        ),
                      ],
                    ),
                    _Section(
                      title: 'Allergies',
                      icon: Icons.warning_amber_rounded,
                      children: [
                        _MultiChoices(
                          selected: profile.allergies,
                          options: _allergies,
                          onToggle: notifier.toggleAllergy,
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    SizedBox(
                      height: 54,
                      child: FilledButton.icon(
                        onPressed: state.isSaving ? null : _save,
                        icon: state.isSaving
                            ? const SizedBox.square(
                                dimension: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.check_rounded),
                        label: Text(state.isSaving ? 'Saving…' : 'Save and continue'),
                      ),
                    ),
                    TextButton(
                      onPressed: state.isSaving ? null : () => context.go('/upload'),
                      child: const Text('Skip for now'),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.icon, required this.children});
  final String title;
  final IconData icon;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(children: [
              Icon(icon, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
            ]),
            const SizedBox(height: 18),
            for (var index = 0; index < children.length; index++) ...[
              children[index],
              if (index < children.length - 1) const SizedBox(height: 16),
            ],
          ],
        ),
      ),
    );
  }
}

class _Choices extends StatelessWidget {
  const _Choices({
    required this.label,
    required this.selected,
    required this.options,
    required this.onSelected,
    this.allowClear = true,
  });

  final String label;
  final String? selected;
  final Map<String, String> options;
  final ValueChanged<String?> onSelected;
  final bool allowClear;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: options.entries.map((entry) {
            final active = selected == entry.key;
            return ChoiceChip(
              label: Text(entry.value),
              selected: active,
              onSelected: (enabled) {
                if (enabled) {
                  onSelected(entry.key);
                } else if (allowClear) {
                  onSelected(null);
                }
              },
            );
          }).toList(),
        ),
      ],
    );
  }
}

class _MultiChoices extends StatelessWidget {
  const _MultiChoices({
    required this.selected,
    required this.options,
    required this.onToggle,
  });
  final Set<String> selected;
  final Map<String, String> options;
  final ValueChanged<String> onToggle;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: options.entries
          .map(
            (entry) => FilterChip(
              label: Text(entry.value),
              selected: selected.contains(entry.key),
              onSelected: (_) => onToggle(entry.key),
            ),
          )
          .toList(),
    );
  }
}

class _Toggle extends StatelessWidget {
  const _Toggle(this.title, this.value, this.onChanged);
  final String title;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return SwitchListTile.adaptive(
      contentPadding: EdgeInsets.zero,
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
      value: value,
      onChanged: onChanged,
    );
  }
}

const _conditions = <String, String>{
  'prediabetes': 'Prediabetes',
  'type_2_diabetes': 'Type 2 diabetes',
  'hypertension': 'Hypertension',
  'chronic_kidney_disease': 'Chronic kidney disease',
  'heart_failure': 'Heart failure',
  'dyslipidemia': 'High cholesterol',
  'fatty_liver': 'Fatty liver',
  'ibs': 'IBS',
  'ibd': 'IBD',
  'osteoarthritis': 'Osteoarthritis',
  'rheumatoid_arthritis': 'Rheumatoid arthritis',
  'osteoporosis': 'Osteoporosis or osteopenia',
  'iron_deficiency': 'Iron deficiency',
  'thyroid_disease': 'Thyroid disease',
};

const _medications = <String, String>{
  'metformin': 'Metformin',
  'warfarin': 'Warfarin',
  'ppi': 'Proton pump inhibitor',
  'loop_diuretic': 'Loop diuretic',
  'thiazide_diuretic': 'Thiazide diuretic',
  'raas_inhibitor': 'ACE inhibitor or ARB',
  'potassium_sparing_diuretic': 'Potassium-sparing diuretic',
};

const _allergies = <String, String>{
  'milk': 'Milk',
  'egg': 'Egg',
  'peanut': 'Peanut',
  'tree_nuts': 'Tree nuts',
  'soy': 'Soy',
  'wheat': 'Wheat',
  'fish': 'Fish',
  'shellfish': 'Shellfish',
  'sesame': 'Sesame',
};
