import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:hive_flutter/hive_flutter.dart';

class ProfileSetupScreen extends StatefulWidget {
  const ProfileSetupScreen({super.key});

  @override
  State<ProfileSetupScreen> createState() =>
      _ProfileSetupScreenState();
}

class _ProfileSetupScreenState
    extends State<ProfileSetupScreen> {
  static const String _profileBoxName =
      'quinone_profile';

  final GlobalKey<FormState> _formKey =
      GlobalKey<FormState>();

  final TextEditingController _nameController =
      TextEditingController();

  final TextEditingController _ageController =
      TextEditingController();

  final TextEditingController _heightController =
      TextEditingController();

  final TextEditingController _weightController =
      TextEditingController();

  final TextEditingController
      _healthConditionsController =
      TextEditingController();

  final TextEditingController _allergiesController =
      TextEditingController();

  final TextEditingController _dietaryPreferencesController =
      TextEditingController();

  String? _selectedSex;
  String? _selectedActivityLevel;
  String? _selectedGoal;

  bool _isSaving = false;
  bool _isLoading = true;

  static const List<String> _sexOptions = [
    'Male',
    'Female',
    'Other',
    'Prefer not to say',
  ];

  static const List<String> _activityLevels = [
    'Sedentary',
    'Lightly active',
    'Moderately active',
    'Very active',
    'Extremely active',
  ];

  static const List<String> _goalOptions = [
    'Maintain weight',
    'Lose weight',
    'Gain weight',
    'Improve nutrition',
    'Manage a health condition',
    'General wellness',
  ];

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  Future<Box<dynamic>> _openProfileBox() {
    return Hive.openBox<dynamic>(_profileBoxName);
  }

  Future<void> _loadProfile() async {
    try {
      final box = await _openProfileBox();

      if (!mounted) {
        return;
      }

      _nameController.text =
          box.get('name', defaultValue: '') as String;

      final age = box.get('age');
      final height = box.get('height_cm');
      final weight = box.get('weight_kg');

      _ageController.text =
          age == null ? '' : age.toString();

      _heightController.text =
          height == null ? '' : height.toString();

      _weightController.text =
          weight == null ? '' : weight.toString();

      _healthConditionsController.text =
          box.get(
            'health_conditions',
            defaultValue: '',
          ) as String;

      _allergiesController.text =
          box.get(
            'allergies',
            defaultValue: '',
          ) as String;

      _dietaryPreferencesController.text =
          box.get(
            'dietary_preferences',
            defaultValue: '',
          ) as String;

      setState(() {
        _selectedSex = box.get('sex') as String?;
        _selectedActivityLevel =
            box.get('activity_level') as String?;
        _selectedGoal = box.get('goal') as String?;
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }

      setState(() {
        _isLoading = false;
      });

      _showMessage(
        'Your saved profile could not be loaded.',
        isError: true,
      );
    }
  }

  Future<void> _saveProfile() async {
    FocusManager.instance.primaryFocus?.unfocus();

    if (!(_formKey.currentState?.validate() ?? false)) {
      return;
    }

    setState(() {
      _isSaving = true;
    });

    try {
      final box = await _openProfileBox();

      final age = _parseInteger(
        _ageController.text,
      );

      final height = _parseDouble(
        _heightController.text,
      );

      final weight = _parseDouble(
        _weightController.text,
      );

      await box.putAll({
        'name': _nameController.text.trim(),
        'age': age,
        'sex': _selectedSex,
        'height_cm': height,
        'weight_kg': weight,
        'activity_level': _selectedActivityLevel,
        'goal': _selectedGoal,
        'health_conditions':
            _healthConditionsController.text.trim(),
        'allergies':
            _allergiesController.text.trim(),
        'dietary_preferences':
            _dietaryPreferencesController.text.trim(),
        'profile_completed': true,
        'updated_at':
            DateTime.now().toIso8601String(),
      });

      if (!mounted) {
        return;
      }

      _showMessage('Profile saved.');

      context.go('/upload');
    } catch (_) {
      if (!mounted) {
        return;
      }

      _showMessage(
        'Your profile could not be saved.',
        isError: true,
      );
    } finally {
      if (mounted) {
        setState(() {
          _isSaving = false;
        });
      }
    }
  }

  void _skipProfile() {
    context.go('/upload');
  }

  int? _parseInteger(String value) {
    final normalized = value.trim();

    if (normalized.isEmpty) {
      return null;
    }

    return int.tryParse(normalized);
  }

  double? _parseDouble(String value) {
    final normalized = value
        .trim()
        .replaceAll(',', '.');

    if (normalized.isEmpty) {
      return null;
    }

    return double.tryParse(normalized);
  }

  String? _validateAge(String? value) {
    if (value == null || value.trim().isEmpty) {
      return null;
    }

    final age = int.tryParse(value.trim());

    if (age == null) {
      return 'Enter a valid age.';
    }

    if (age < 13 || age > 120) {
      return 'Age must be between 13 and 120.';
    }

    return null;
  }

  String? _validateHeight(String? value) {
    if (value == null || value.trim().isEmpty) {
      return null;
    }

    final height = _parseDouble(value);

    if (height == null) {
      return 'Enter a valid height.';
    }

    if (height < 80 || height > 250) {
      return 'Height must be between 80 and 250 cm.';
    }

    return null;
  }

  String? _validateWeight(String? value) {
    if (value == null || value.trim().isEmpty) {
      return null;
    }

    final weight = _parseDouble(value);

    if (weight == null) {
      return 'Enter a valid weight.';
    }

    if (weight < 20 || weight > 400) {
      return 'Weight must be between 20 and 400 kg.';
    }

    return null;
  }

  void _showMessage(
    String message, {
    bool isError = false,
  }) {
    final colorScheme =
        Theme.of(context).colorScheme;

    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          backgroundColor: isError
              ? colorScheme.error
              : null,
          content: Text(message),
        ),
      );
  }

  @override
  void dispose() {
    _nameController.dispose();
    _ageController.dispose();
    _heightController.dispose();
    _weightController.dispose();
    _healthConditionsController.dispose();
    _allergiesController.dispose();
    _dietaryPreferencesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        body: SafeArea(
          child: Center(
            child: CircularProgressIndicator(),
          ),
        ),
      );
    }

    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Your profile'),
        actions: [
          TextButton(
            onPressed:
                _isSaving ? null : _skipProfile,
            child: const Text('Skip'),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(
              20,
              12,
              20,
              32,
            ),
            children: [
              Text(
                'Personalise your nutrition insights',
                style:
                    theme.textTheme.headlineSmall,
              ),
              const SizedBox(height: 10),
              Text(
                'All fields are optional. Quinone can still analyse meals without personal information.',
                style:
                    theme.textTheme.bodyLarge?.copyWith(
                  color:
                      colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 28),

              _SectionHeader(
                icon: Icons.person_outline_rounded,
                title: 'Basic information',
              ),
              const SizedBox(height: 14),

              TextFormField(
                controller: _nameController,
                textCapitalization:
                    TextCapitalization.words,
                textInputAction:
                    TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'Name',
                  hintText: 'Optional',
                  prefixIcon:
                      Icon(Icons.badge_outlined),
                ),
              ),
              const SizedBox(height: 14),

              Row(
                crossAxisAlignment:
                    CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _ageController,
                      keyboardType:
                          TextInputType.number,
                      textInputAction:
                          TextInputAction.next,
                      validator: _validateAge,
                      decoration:
                          const InputDecoration(
                        labelText: 'Age',
                        hintText: 'Years',
                        prefixIcon:
                            Icon(Icons.cake_outlined),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child:
                        DropdownButtonFormField<
                            String>(
                      initialValue: _selectedSex,
                      isExpanded: true,
                      decoration:
                          const InputDecoration(
                        labelText: 'Sex',
                      ),
                      items: _sexOptions
                          .map(
                            (option) =>
                                DropdownMenuItem(
                              value: option,
                              child: Text(
                                option,
                                overflow:
                                    TextOverflow.ellipsis,
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: (value) {
                        setState(() {
                          _selectedSex = value;
                        });
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),

              Row(
                crossAxisAlignment:
                    CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: TextFormField(
                      controller:
                          _heightController,
                      keyboardType:
                          const TextInputType
                              .numberWithOptions(
                        decimal: true,
                      ),
                      textInputAction:
                          TextInputAction.next,
                      validator: _validateHeight,
                      decoration:
                          const InputDecoration(
                        labelText: 'Height',
                        suffixText: 'cm',
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      controller:
                          _weightController,
                      keyboardType:
                          const TextInputType
                              .numberWithOptions(
                        decimal: true,
                      ),
                      textInputAction:
                          TextInputAction.next,
                      validator: _validateWeight,
                      decoration:
                          const InputDecoration(
                        labelText: 'Weight',
                        suffixText: 'kg',
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 28),

              _SectionHeader(
                icon:
                    Icons.directions_run_outlined,
                title: 'Lifestyle and goal',
              ),
              const SizedBox(height: 14),

              DropdownButtonFormField<String>(
                initialValue:
                    _selectedActivityLevel,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Activity level',
                  prefixIcon:
                      Icon(Icons.bolt_outlined),
                ),
                items: _activityLevels
                    .map(
                      (option) =>
                          DropdownMenuItem(
                        value: option,
                        child: Text(option),
                      ),
                    )
                    .toList(),
                onChanged: (value) {
                  setState(() {
                    _selectedActivityLevel =
                        value;
                  });
                },
              ),
              const SizedBox(height: 14),

              DropdownButtonFormField<String>(
                initialValue: _selectedGoal,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Primary goal',
                  prefixIcon:
                      Icon(Icons.flag_outlined),
                ),
                items: _goalOptions
                    .map(
                      (option) =>
                          DropdownMenuItem(
                        value: option,
                        child: Text(
                          option,
                          overflow:
                              TextOverflow.ellipsis,
                        ),
                      ),
                    )
                    .toList(),
                onChanged: (value) {
                  setState(() {
                    _selectedGoal = value;
                  });
                },
              ),
              const SizedBox(height: 28),

              _SectionHeader(
                icon:
                    Icons.health_and_safety_outlined,
                title: 'Health preferences',
              ),
              const SizedBox(height: 14),

              TextFormField(
                controller:
                    _healthConditionsController,
                minLines: 2,
                maxLines: 4,
                textCapitalization:
                    TextCapitalization.sentences,
                decoration: const InputDecoration(
                  labelText: 'Health conditions',
                  hintText:
                      'For example: diabetes, high blood pressure',
                  alignLabelWithHint: true,
                  prefixIcon:
                      Icon(Icons.medical_information_outlined),
                ),
              ),
              const SizedBox(height: 14),

              TextFormField(
                controller:
                    _allergiesController,
                minLines: 2,
                maxLines: 4,
                textCapitalization:
                    TextCapitalization.sentences,
                decoration: const InputDecoration(
                  labelText: 'Food allergies',
                  hintText:
                      'For example: peanuts, dairy, shellfish',
                  alignLabelWithHint: true,
                  prefixIcon:
                      Icon(Icons.warning_amber_rounded),
                ),
              ),
              const SizedBox(height: 14),

              TextFormField(
                controller:
                    _dietaryPreferencesController,
                minLines: 2,
                maxLines: 4,
                textCapitalization:
                    TextCapitalization.sentences,
                decoration: const InputDecoration(
                  labelText:
                      'Dietary preferences',
                  hintText:
                      'For example: vegetarian, vegan, halal',
                  alignLabelWithHint: true,
                  prefixIcon:
                      Icon(Icons.restaurant_outlined),
                ),
              ),
              const SizedBox(height: 30),

              FilledButton.icon(
                onPressed:
                    _isSaving ? null : _saveProfile,
                icon: _isSaving
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
                  _isSaving
                      ? 'Saving profile...'
                      : 'Save and continue',
                ),
              ),
              const SizedBox(height: 10),

              TextButton(
                onPressed:
                    _isSaving ? null : _skipProfile,
                child: const Text(
                  'Continue without saving',
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final IconData icon;
  final String title;

  const _SectionHeader({
    required this.icon,
    required this.title,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Row(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: colorScheme.primaryContainer,
            borderRadius:
                BorderRadius.circular(12),
          ),
          child: Icon(
            icon,
            size: 21,
            color:
                colorScheme.onPrimaryContainer,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            title,
            style:
                theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }
}