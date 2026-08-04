import 'dart:convert';

class UserProfile {
  const UserProfile({
    this.age,
    this.ageMonths,
    this.ageUnit = 'years',
    this.sex,
    this.heightCm,
    this.weightKg,
    this.activityLevel,
    this.goal,
    this.dietType,
    this.dietPattern,
    this.smokingStatus,
    this.bloodPressureStatus,
    this.glycemicStatus,
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
    this.chronicConditions = const <String>{},
    this.medications = const <String>{},
    this.allergies = const <String>{},
  });

  final int? age;
  final int? ageMonths;
  final String ageUnit;
  final String? sex;
  final double? heightCm;
  final double? weightKg;
  final String? activityLevel;
  final String? goal;
  final String? dietType;
  final String? dietPattern;
  final String? smokingStatus;
  final String? bloodPressureStatus;
  final String? glycemicStatus;
  final bool pregnant;
  final int? trimester;
  final bool lactating;
  final double? lactationStageMonths;
  final bool frailty;
  final bool lowAppetite;
  final bool resistanceTraining;
  final bool enduranceTraining;
  final String? ckdStage;
  final String? dialysisModality;
  final Set<String> chronicConditions;
  final Set<String> medications;
  final Set<String> allergies;

  static const Object _unset = Object();

  bool get hasCkd =>
      chronicConditions.contains('chronic_kidney_disease') ||
      (ckdStage != null && ckdStage != 'none');

  bool get isEmpty =>
      age == null &&
      ageMonths == null &&
      sex == null &&
      heightCm == null &&
      weightKg == null &&
      activityLevel == null &&
      goal == null &&
      dietType == null &&
      dietPattern == null &&
      smokingStatus == null &&
      bloodPressureStatus == null &&
      glycemicStatus == null &&
      !pregnant &&
      !lactating &&
      !frailty &&
      !lowAppetite &&
      !resistanceTraining &&
      !enduranceTraining &&
      chronicConditions.isEmpty &&
      medications.isEmpty &&
      allergies.isEmpty;

  Map<String, dynamic> toJson() => <String, dynamic>{
        ...toBackendJson(),
        'age_unit': ageUnit,
        'pregnant': pregnant,
        'lactating': lactating,
        'frailty': frailty,
        'low_appetite': lowAppetite,
        'resistance_training': resistanceTraining,
        'endurance_training': enduranceTraining,
      };

  Map<String, dynamic> toBackendJson() {
    final output = <String, dynamic>{};

    void addText(String key, String? value) {
      final normalized = value?.trim();
      if (normalized != null && normalized.isNotEmpty) {
        output[key] = normalized;
      }
    }

    if (ageUnit == 'months' && ageMonths != null) {
      output['age_months'] = ageMonths;
    } else if (age != null) {
      output['age'] = age;
    }

    if (heightCm != null) output['height_cm'] = heightCm;
    if (weightKg != null) output['weight_kg'] = weightKg;

    addText('sex', sex);
    addText('activity_level', activityLevel);
    addText('goal', goal);
    addText('diet_type', dietType);
    addText('diet_pattern', dietPattern);
    addText('smoking_status', smokingStatus);
    addText('blood_pressure_status', bloodPressureStatus);
    addText('glycemic_status', glycemicStatus);

    if (pregnant) {
      output['pregnant'] = true;
      if (trimester != null) output['trimester'] = trimester;
    }

    if (lactating) {
      output['lactating'] = true;
      if (lactationStageMonths != null) {
        output['lactation_stage_months'] = lactationStageMonths;
      }
    }

    if (frailty) output['frailty'] = true;
    if (lowAppetite) output['low_appetite'] = true;
    if (resistanceTraining) output['resistance_training'] = true;
    if (enduranceTraining) output['endurance_training'] = true;

    if (chronicConditions.isNotEmpty) {
      output['chronic_conditions'] = _sorted(chronicConditions);
    }
    if (hasCkd) addText('ckd_stage', ckdStage);
    if (hasCkd) addText('dialysis_modality', dialysisModality);
    if (medications.isNotEmpty) output['medications'] = _sorted(medications);
    if (allergies.isNotEmpty) output['allergies'] = _sorted(allergies);

    return output;
  }

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      age: _int(json['age']),
      ageMonths: _int(json['age_months']),
      ageUnit: json['age_unit']?.toString() ??
          (json['age_months'] != null ? 'months' : 'years'),
      sex: _text(json['sex'] ?? json['gender']),
      heightCm: _double(json['height_cm']),
      weightKg: _double(json['weight_kg']),
      activityLevel: _text(json['activity_level']),
      goal: _text(json['goal']),
      dietType: _text(json['diet_type']),
      dietPattern: _text(json['diet_pattern']),
      smokingStatus: _text(json['smoking_status']),
      bloodPressureStatus: _text(json['blood_pressure_status']),
      glycemicStatus: _text(json['glycemic_status']),
      pregnant: json['pregnant'] == true,
      trimester: _int(json['trimester']),
      lactating: json['lactating'] == true,
      lactationStageMonths: _double(json['lactation_stage_months']),
      frailty: json['frailty'] == true,
      lowAppetite: json['low_appetite'] == true,
      resistanceTraining: json['resistance_training'] == true,
      enduranceTraining: json['endurance_training'] == true,
      ckdStage: _text(json['ckd_stage']),
      dialysisModality: _text(json['dialysis_modality']),
      chronicConditions: _set(json['chronic_conditions'] ?? json['conditions']),
      medications: _set(json['medications']),
      allergies: _set(json['allergies']),
    );
  }

  UserProfile copyWith({
    Object? age = _unset,
    Object? ageMonths = _unset,
    String? ageUnit,
    Object? sex = _unset,
    Object? heightCm = _unset,
    Object? weightKg = _unset,
    Object? activityLevel = _unset,
    Object? goal = _unset,
    Object? dietType = _unset,
    Object? dietPattern = _unset,
    Object? smokingStatus = _unset,
    Object? bloodPressureStatus = _unset,
    Object? glycemicStatus = _unset,
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
    Set<String>? chronicConditions,
    Set<String>? medications,
    Set<String>? allergies,
  }) {
    return UserProfile(
      age: identical(age, _unset) ? this.age : age as int?,
      ageMonths: identical(ageMonths, _unset) ? this.ageMonths : ageMonths as int?,
      ageUnit: ageUnit ?? this.ageUnit,
      sex: identical(sex, _unset) ? this.sex : sex as String?,
      heightCm: identical(heightCm, _unset) ? this.heightCm : heightCm as double?,
      weightKg: identical(weightKg, _unset) ? this.weightKg : weightKg as double?,
      activityLevel: identical(activityLevel, _unset)
          ? this.activityLevel
          : activityLevel as String?,
      goal: identical(goal, _unset) ? this.goal : goal as String?,
      dietType: identical(dietType, _unset) ? this.dietType : dietType as String?,
      dietPattern: identical(dietPattern, _unset)
          ? this.dietPattern
          : dietPattern as String?,
      smokingStatus: identical(smokingStatus, _unset)
          ? this.smokingStatus
          : smokingStatus as String?,
      bloodPressureStatus: identical(bloodPressureStatus, _unset)
          ? this.bloodPressureStatus
          : bloodPressureStatus as String?,
      glycemicStatus: identical(glycemicStatus, _unset)
          ? this.glycemicStatus
          : glycemicStatus as String?,
      pregnant: pregnant ?? this.pregnant,
      trimester: identical(trimester, _unset) ? this.trimester : trimester as int?,
      lactating: lactating ?? this.lactating,
      lactationStageMonths: identical(lactationStageMonths, _unset)
          ? this.lactationStageMonths
          : lactationStageMonths as double?,
      frailty: frailty ?? this.frailty,
      lowAppetite: lowAppetite ?? this.lowAppetite,
      resistanceTraining: resistanceTraining ?? this.resistanceTraining,
      enduranceTraining: enduranceTraining ?? this.enduranceTraining,
      ckdStage: identical(ckdStage, _unset) ? this.ckdStage : ckdStage as String?,
      dialysisModality: identical(dialysisModality, _unset)
          ? this.dialysisModality
          : dialysisModality as String?,
      chronicConditions: chronicConditions ?? this.chronicConditions,
      medications: medications ?? this.medications,
      allergies: allergies ?? this.allergies,
    );
  }

  String encode() => jsonEncode(toJson());

  factory UserProfile.decode(String source) =>
      UserProfile.fromJson(Map<String, dynamic>.from(jsonDecode(source) as Map));

  static String? _text(dynamic value) {
    final text = value?.toString().trim();
    return text == null || text.isEmpty ? null : text;
  }

  static int? _int(dynamic value) =>
      value is num ? value.toInt() : int.tryParse(value?.toString() ?? '');

  static double? _double(dynamic value) =>
      value is num ? value.toDouble() : double.tryParse(value?.toString() ?? '');

  static Set<String> _set(dynamic value) {
    if (value is Map) {
      return value.entries
          .where((entry) => entry.value == true)
          .map((entry) => entry.key.toString())
          .toSet();
    }
    if (value is Iterable) return value.map((item) => item.toString()).toSet();
    return <String>{};
  }

  static List<String> _sorted(Iterable<String> values) {
    final output = values.toSet().toList()..sort();
    return output;
  }
}
