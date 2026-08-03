import 'dart:convert';

class UserProfile {
  const UserProfile({
    this.age,
    this.sex,
    this.heightCm,
    this.weightKg,
    this.activityLevel,
    this.goal,
    this.dietType,
    this.smokingStatus,
    this.pregnant = false,
    this.trimester,
    this.lactating = false,
    this.lactationStageMonths,
    this.frailty = false,
    this.lowAppetite = false,
    this.resistanceTraining = false,
    this.enduranceTraining = false,
    this.ckdStage,
    this.dialysisModality,
    this.bloodPressureStatus,
    this.glycemicStatus,
    this.chronicConditions = const <String>{},
    this.medications = const <String>{},
    this.allergies = const <String>{},
  });

  final int? age;

  /// `male` or `female`
  final String? sex;

  final double? heightCm;
  final double? weightKg;

  /// `sedentary`, `low_active`, `active`, `very_active`
  final String? activityLevel;

  /// `general_health`, `weight_maintenance`,
  /// `weight_loss`, `fat_loss`, `muscle_gain`
  final String? goal;

  /// `omnivore`, `vegetarian`, `vegan`
  final String? dietType;

  /// `non_smoker`, `former_smoker`, `smoker`
  final String? smokingStatus;

  final bool pregnant;

  /// 1, 2, or 3
  final int? trimester;

  final bool lactating;
  final double? lactationStageMonths;

  final bool frailty;
  final bool lowAppetite;
  final bool resistanceTraining;
  final bool enduranceTraining;

  /// `none`, `g1`, `g2`, `g3a`, `g3b`, `g4`, `g5`
  final String? ckdStage;

  /// `none`, `hemodialysis`, `peritoneal_dialysis`
  final String? dialysisModality;

  final String? bloodPressureStatus;
  final String? glycemicStatus;

  final Set<String> chronicConditions;
  final Set<String> medications;
  final Set<String> allergies;

  static const Object _unset = Object();

  bool get isEmpty {
    return age == null &&
        sex == null &&
        heightCm == null &&
        weightKg == null &&
        activityLevel == null &&
        goal == null &&
        dietType == null &&
        smokingStatus == null &&
        !pregnant &&
        trimester == null &&
        !lactating &&
        lactationStageMonths == null &&
        !frailty &&
        !lowAppetite &&
        !resistanceTraining &&
        !enduranceTraining &&
        ckdStage == null &&
        dialysisModality == null &&
        bloodPressureStatus == null &&
        glycemicStatus == null &&
        chronicConditions.isEmpty &&
        medications.isEmpty &&
        allergies.isEmpty;
  }

  bool get hasCkd {
    return chronicConditions.contains(
          'chronic_kidney_disease',
        ) ||
        chronicConditions.contains('ckd') ||
        (ckdStage != null && ckdStage != 'none');
  }

  /// Used for local storage.
  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'age': age,
      'sex': sex,
      'height_cm': heightCm,
      'weight_kg': weightKg,
      'activity_level': activityLevel,
      'goal': goal,
      'diet_type': dietType,
      'smoking_status': smokingStatus,
      'pregnant': pregnant,
      'trimester': pregnant ? trimester : null,
      'lactating': lactating,
      'lactation_stage_months':
          lactating ? lactationStageMonths : null,
      'frailty': frailty,
      'low_appetite': lowAppetite,
      'resistance_training': resistanceTraining,
      'endurance_training': enduranceTraining,
      'ckd_stage': hasCkd ? ckdStage : null,
      'dialysis_modality':
          hasCkd ? dialysisModality : null,
      'blood_pressure_status':
          bloodPressureStatus,
      'glycemic_status': glycemicStatus,
      'chronic_conditions': _sortedList(
        chronicConditions,
      ),
      'medications': _sortedList(
        medications,
      ),
      'allergies': _sortedList(
        allergies,
      ),
    };
  }

  /// Used in the multipart `profile` field sent to FastAPI.
  ///
  /// Empty values are omitted so the backend can distinguish
  /// missing information from actual zero or false values.
  Map<String, dynamic> toBackendJson() {
    final payload = <String, dynamic>{};

    void addText(
      String key,
      String? value,
    ) {
      final cleaned = value?.trim();

      if (cleaned != null &&
          cleaned.isNotEmpty) {
        payload[key] = cleaned;
      }
    }

    if (age != null) {
      payload['age'] = age;
    }

    if (heightCm != null) {
      payload['height_cm'] = heightCm;
    }

    if (weightKg != null) {
      payload['weight_kg'] = weightKg;
    }

    addText('sex', sex);
    addText(
      'activity_level',
      activityLevel,
    );
    addText('goal', goal);
    addText('diet_type', dietType);
    addText(
      'smoking_status',
      smokingStatus,
    );
    addText(
      'blood_pressure_status',
      bloodPressureStatus,
    );
    addText(
      'glycemic_status',
      glycemicStatus,
    );

    if (pregnant) {
      payload['pregnant'] = true;

      if (trimester != null) {
        payload['trimester'] = trimester;
      }
    }

    if (lactating) {
      payload['lactating'] = true;

      if (lactationStageMonths != null) {
        payload['lactation_stage_months'] =
            lactationStageMonths;
      }
    }

    if (frailty) {
      payload['frailty'] = true;
    }

    if (lowAppetite) {
      payload['low_appetite'] = true;
    }

    if (resistanceTraining) {
      payload['resistance_training'] = true;
    }

    if (enduranceTraining) {
      payload['endurance_training'] = true;
    }

    if (chronicConditions.isNotEmpty) {
      payload['chronic_conditions'] =
          _sortedList(chronicConditions);
    }

    if (hasCkd) {
      addText('ckd_stage', ckdStage);
      addText(
        'dialysis_modality',
        dialysisModality,
      );
    }

    if (medications.isNotEmpty) {
      payload['medications'] =
          _sortedList(medications);
    }

    if (allergies.isNotEmpty) {
      payload['allergies'] =
          _sortedList(allergies);
    }

    return payload;
  }

  String toBackendJsonString() {
    return jsonEncode(
      toBackendJson(),
    );
  }

  factory UserProfile.fromJson(
    Map<String, dynamic> json,
  ) {
    final conditions = _stringSet(
      json['chronic_conditions'] ??
          json['conditions'],
    );

    String? dietType = _cleanString(
      json['diet_type'],
    );

    // Compatibility with the old profile format.
    if (dietType == null &&
        json['vegan'] == true) {
      dietType = 'vegan';
    } else if (dietType == null &&
        json['vegetarian'] == true) {
      dietType = 'vegetarian';
    }

    return UserProfile(
      age: _intValue(json['age']),
      sex: _cleanString(
        json['sex'] ?? json['gender'],
      ),
      heightCm: _doubleValue(
        json['height_cm'] ??
            json['height'],
      ),
      weightKg: _doubleValue(
        json['weight_kg'] ??
            json['weight'],
      ),
      activityLevel: _normalizeActivity(
        _cleanString(
          json['activity_level'],
        ),
      ),
      goal: _normalizeGoal(
        _cleanString(json['goal']),
      ),
      dietType: dietType,
      smokingStatus: _cleanString(
        json['smoking_status'],
      ),
      pregnant: json['pregnant'] == true,
      trimester: _intValue(
        json['trimester'],
      ),
      lactating: json['lactating'] == true,
      lactationStageMonths: _doubleValue(
        json['lactation_stage_months'],
      ),
      frailty: json['frailty'] == true,
      lowAppetite:
          json['low_appetite'] == true,
      resistanceTraining:
          json['resistance_training'] ==
              true,
      enduranceTraining:
          json['endurance_training'] ==
              true,
      ckdStage: _cleanString(
        json['ckd_stage'],
      ),
      dialysisModality: _cleanString(
        json['dialysis_modality'],
      ),
      bloodPressureStatus: _cleanString(
        json['blood_pressure_status'],
      ),
      glycemicStatus: _cleanString(
        json['glycemic_status'],
      ),
      chronicConditions:
          Set<String>.unmodifiable(
        conditions,
      ),
      medications: Set<String>.unmodifiable(
        _stringSet(json['medications']),
      ),
      allergies: Set<String>.unmodifiable(
        _stringSet(json['allergies']),
      ),
    ).normalized();
  }

  UserProfile normalized() {
    final validSex =
        sex == 'male' || sex == 'female'
            ? sex
            : null;

    final validPregnancy =
        validSex == 'female' && pregnant;

    final validLactation =
        validSex == 'female' && lactating;

    final normalizedConditions =
        Set<String>.from(
      chronicConditions,
    );

    if (ckdStage != null &&
        ckdStage != 'none') {
      normalizedConditions.add(
        'chronic_kidney_disease',
      );
    }

    return UserProfile(
      age: age != null &&
              age! > 0 &&
              age! < 130
          ? age
          : null,
      sex: validSex,
      heightCm: heightCm != null &&
              heightCm! > 0
          ? heightCm
          : null,
      weightKg: weightKg != null &&
              weightKg! > 0
          ? weightKg
          : null,
      activityLevel: _normalizeActivity(
        activityLevel,
      ),
      goal: _normalizeGoal(goal),
      dietType: _cleanString(dietType),
      smokingStatus: _cleanString(
        smokingStatus,
      ),
      pregnant: validPregnancy,
      trimester: validPregnancy &&
              trimester != null &&
              trimester! >= 1 &&
              trimester! <= 3
          ? trimester
          : null,
      lactating: validLactation,
      lactationStageMonths:
          validLactation &&
                  lactationStageMonths !=
                      null &&
                  lactationStageMonths! >= 0
              ? lactationStageMonths
              : null,
      frailty: frailty,
      lowAppetite: lowAppetite,
      resistanceTraining:
          resistanceTraining,
      enduranceTraining:
          enduranceTraining,
      ckdStage: _cleanString(ckdStage),
      dialysisModality: _cleanString(
        dialysisModality,
      ),
      bloodPressureStatus: _cleanString(
        bloodPressureStatus,
      ),
      glycemicStatus: _cleanString(
        glycemicStatus,
      ),
      chronicConditions:
          Set<String>.unmodifiable(
        normalizedConditions,
      ),
      medications:
          Set<String>.unmodifiable(
        medications,
      ),
      allergies: Set<String>.unmodifiable(
        allergies,
      ),
    );
  }

  UserProfile copyWith({
    Object? age = _unset,
    Object? sex = _unset,
    Object? heightCm = _unset,
    Object? weightKg = _unset,
    Object? activityLevel = _unset,
    Object? goal = _unset,
    Object? dietType = _unset,
    Object? smokingStatus = _unset,
    bool? pregnant,
    Object? trimester = _unset,
    bool? lactating,
    Object? lactationStageMonths = _unset,
    bool? frailty,
    bool? lowAppetite,
    bool? resistanceTraining,
    bool? enduranceTraining,
    Object? ckdStage = _unset,
    Object? dialysisModality = _unset,
    Object? bloodPressureStatus = _unset,
    Object? glycemicStatus = _unset,
    Set<String>? chronicConditions,
    Set<String>? medications,
    Set<String>? allergies,
  }) {
    return UserProfile(
      age: identical(age, _unset)
          ? this.age
          : age as int?,
      sex: identical(sex, _unset)
          ? this.sex
          : sex as String?,
      heightCm:
          identical(heightCm, _unset)
              ? this.heightCm
              : heightCm as double?,
      weightKg:
          identical(weightKg, _unset)
              ? this.weightKg
              : weightKg as double?,
      activityLevel:
          identical(activityLevel, _unset)
              ? this.activityLevel
              : activityLevel as String?,
      goal: identical(goal, _unset)
          ? this.goal
          : goal as String?,
      dietType:
          identical(dietType, _unset)
              ? this.dietType
              : dietType as String?,
      smokingStatus:
          identical(smokingStatus, _unset)
              ? this.smokingStatus
              : smokingStatus as String?,
      pregnant:
          pregnant ?? this.pregnant,
      trimester:
          identical(trimester, _unset)
              ? this.trimester
              : trimester as int?,
      lactating:
          lactating ?? this.lactating,
      lactationStageMonths:
          identical(
            lactationStageMonths,
            _unset,
          )
              ? this.lactationStageMonths
              : lactationStageMonths
                  as double?,
      frailty: frailty ?? this.frailty,
      lowAppetite:
          lowAppetite ?? this.lowAppetite,
      resistanceTraining:
          resistanceTraining ??
              this.resistanceTraining,
      enduranceTraining:
          enduranceTraining ??
              this.enduranceTraining,
      ckdStage:
          identical(ckdStage, _unset)
              ? this.ckdStage
              : ckdStage as String?,
      dialysisModality:
          identical(
            dialysisModality,
            _unset,
          )
              ? this.dialysisModality
              : dialysisModality
                  as String?,
      bloodPressureStatus:
          identical(
            bloodPressureStatus,
            _unset,
          )
              ? this.bloodPressureStatus
              : bloodPressureStatus
                  as String?,
      glycemicStatus:
          identical(
            glycemicStatus,
            _unset,
          )
              ? this.glycemicStatus
              : glycemicStatus as String?,
      chronicConditions:
          chronicConditions ??
              this.chronicConditions,
      medications:
          medications ?? this.medications,
      allergies:
          allergies ?? this.allergies,
    ).normalized();
  }

  static List<String> _sortedList(
    Iterable<String> values,
  ) {
    final result = values
        .map((value) => value.trim())
        .where((value) => value.isNotEmpty)
        .toSet()
        .toList()
      ..sort();

    return result;
  }

  static Set<String> _stringSet(
    dynamic value,
  ) {
    final result = <String>{};

    if (value is Map) {
      for (final entry in value.entries) {
        if (entry.value == true) {
          final cleaned = _cleanString(
            entry.key,
          );

          if (cleaned != null) {
            result.add(cleaned);
          }
        }
      }

      return result;
    }

    if (value is Iterable) {
      for (final item in value) {
        final cleaned = _cleanString(item);

        if (cleaned != null) {
          result.add(cleaned);
        }
      }
    }

    return result;
  }

  static String? _cleanString(
    dynamic value,
  ) {
    if (value == null) {
      return null;
    }

    final cleaned = value
        .toString()
        .trim()
        .toLowerCase()
        .replaceAll(' ', '_')
        .replaceAll('-', '_');

    return cleaned.isEmpty
        ? null
        : cleaned;
  }

  static int? _intValue(
    dynamic value,
  ) {
    if (value == null ||
        value is bool) {
      return null;
    }

    if (value is int) {
      return value;
    }

    if (value is num) {
      return value.round();
    }

    return int.tryParse(
      value.toString().trim(),
    );
  }

  static double? _doubleValue(
    dynamic value,
  ) {
    if (value == null ||
        value is bool) {
      return null;
    }

    if (value is num) {
      return value.toDouble();
    }

    return double.tryParse(
      value.toString().trim(),
    );
  }

  static String? _normalizeActivity(
    String? value,
  ) {
    switch (_cleanString(value)) {
      case 'inactive':
        return 'sedentary';

      case 'lightly_active':
        return 'low_active';

      case 'moderately_active':
        return 'active';

      case 'highly_active':
        return 'very_active';

      case 'sedentary':
      case 'low_active':
      case 'active':
      case 'very_active':
        return _cleanString(value);

      default:
        return null;
    }
  }

  static String? _normalizeGoal(
    String? value,
  ) {
    switch (_cleanString(value)) {
      case 'lose_weight':
      case 'weight_reduction':
        return 'weight_loss';

      case 'gain_muscle':
      case 'build_muscle':
      case 'hypertrophy':
      case 'bulking':
        return 'muscle_gain';

      default:
        return _cleanString(value);
    }
  }
}
