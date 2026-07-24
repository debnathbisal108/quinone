import 'dart:convert';

class UserProfile {
  final int? age;
  final String? gender;

  final double? heightCm;
  final double? weightKg;

  final String? activityLevel;

  final bool pregnant;
  final bool lactating;

  final bool vegetarian;
  final bool resistanceTraining;

  final bool diabetes;
  final bool chronicKidneyDisease;
  final bool hypertension;
  final bool hyperlipidemia;
  final bool fattyLiver;
  final bool ibs;

  // Future extensibility
  final List<String> medications;
  final List<String> allergies;

  const UserProfile({
    this.age,
    this.gender,
    this.heightCm,
    this.weightKg,
    this.activityLevel,
    this.pregnant = false,
    this.lactating = false,
    this.vegetarian = false,
    this.resistanceTraining = false,
    this.diabetes = false,
    this.chronicKidneyDisease = false,
    this.hypertension = false,
    this.hyperlipidemia = false,
    this.fattyLiver = false,
    this.ibs = false,
    this.medications = const [],
    this.allergies = const [],
  });

  UserProfile copyWith({
    int? age,
    String? gender,
    double? heightCm,
    double? weightKg,
    String? activityLevel,
    bool? pregnant,
    bool? lactating,
    bool? vegetarian,
    bool? resistanceTraining,
    bool? diabetes,
    bool? chronicKidneyDisease,
    bool? hypertension,
    bool? hyperlipidemia,
    bool? fattyLiver,
    bool? ibs,
    List<String>? medications,
    List<String>? allergies,
  }) {
    return UserProfile(
      age: age ?? this.age,
      gender: gender ?? this.gender,
      heightCm: heightCm ?? this.heightCm,
      weightKg: weightKg ?? this.weightKg,
      activityLevel: activityLevel ?? this.activityLevel,
      pregnant: pregnant ?? this.pregnant,
      lactating: lactating ?? this.lactating,
      vegetarian: vegetarian ?? this.vegetarian,
      resistanceTraining:
          resistanceTraining ?? this.resistanceTraining,
      diabetes: diabetes ?? this.diabetes,
      chronicKidneyDisease:
          chronicKidneyDisease ??
              this.chronicKidneyDisease,
      hypertension:
          hypertension ?? this.hypertension,
      hyperlipidemia:
          hyperlipidemia ?? this.hyperlipidemia,
      fattyLiver:
          fattyLiver ?? this.fattyLiver,
      ibs: ibs ?? this.ibs,
      medications:
          medications ?? this.medications,
      allergies:
          allergies ?? this.allergies,
    );
  }

  /// EXACT payload sent to the Python backend.
  Map<String, dynamic> toBackendJson() {
    return {
      "age": age,
      "gender": gender,
      "height_cm": heightCm,
      "weight_kg": weightKg,
      "activity_level": activityLevel,
      "pregnant": pregnant,
      "lactating": lactating,
      "vegetarian": vegetarian,
      "resistance_training":
          resistanceTraining,
      "chronic_conditions": {
        "diabetes": diabetes,
        "ckd": chronicKidneyDisease,
        "hypertension": hypertension,
        "hyperlipidemia": hyperlipidemia,
        "fatty_liver": fattyLiver,
        "ibs": ibs,
      },
      "medications": medications,
      "allergies": allergies,
    };
  }

  Map<String, dynamic> toJson() {
    return {
      "age": age,
      "gender": gender,
      "height_cm": heightCm,
      "weight_kg": weightKg,
      "activity_level": activityLevel,
      "pregnant": pregnant,
      "lactating": lactating,
      "vegetarian": vegetarian,
      "resistance_training":
          resistanceTraining,
      "diabetes": diabetes,
      "chronic_kidney_disease":
          chronicKidneyDisease,
      "hypertension": hypertension,
      "hyperlipidemia":
          hyperlipidemia,
      "fatty_liver": fattyLiver,
      "ibs": ibs,
      "medications": medications,
      "allergies": allergies,
    };
  }

  factory UserProfile.fromJson(
      Map<String, dynamic> json) {
    return UserProfile(
      age: json["age"],
      gender: json["gender"],
      heightCm:
          (json["height_cm"] as num?)?.toDouble(),
      weightKg:
          (json["weight_kg"] as num?)?.toDouble(),
      activityLevel:
          json["activity_level"],
      pregnant:
          json["pregnant"] ?? false,
      lactating:
          json["lactating"] ?? false,
      vegetarian:
          json["vegetarian"] ?? false,
      resistanceTraining:
          json["resistance_training"] ??
              false,
      diabetes:
          json["diabetes"] ?? false,
      chronicKidneyDisease:
          json["chronic_kidney_disease"] ??
              false,
      hypertension:
          json["hypertension"] ??
              false,
      hyperlipidemia:
          json["hyperlipidemia"] ??
              false,
      fattyLiver:
          json["fatty_liver"] ??
              false,
      ibs: json["ibs"] ?? false,
      medications:
          (json["medications"] as List?)
                  ?.cast<String>() ??
              [],
      allergies:
          (json["allergies"] as List?)
                  ?.cast<String>() ??
              [],
    );
  }

  String encode() =>
      jsonEncode(toJson());

  factory UserProfile.decode(
      String source) {
    return UserProfile.fromJson(
      jsonDecode(source),
    );
  }

  bool get isEmpty {
    return age == null &&
        gender == null &&
        heightCm == null &&
        weightKg == null &&
        activityLevel == null;
  }
}