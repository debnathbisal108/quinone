from __future__ import annotations

import asyncio
import copy
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

try:
    from health_domain_scoring import collect_domain_evidence, DomainAggregator
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "personalization_engine.py requires health_domain_scoring.py to be "
        "importable alongside it - this module reuses its evidence-collection "
        "traversal and scoring/aggregation logic rather than reimplementing "
        "them, per the 'consume, don't recompute' design."
    ) from exc

# =========================================================================
# LOGGING
# =========================================================================

logger = logging.getLogger("nutrica.personalization_engine")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
logger.setLevel(os.environ.get("NUTRICA_LOG_LEVEL", "INFO"))


# =========================================================================
# CONFIG
# =========================================================================

# PERSONALIZATION_VERSION = "1.1.0"

# # When multiple active modifiers touch the same evidence item, their
# # effects combine ADDITIVELY (not multiplicatively) - see apply_modifier()
# # - bounded to this range so stacking many modifiers can meaningfully
# # amplify or dampen a weight without ever reaching an absurd extreme.
# COMBINED_MULTIPLIER_BOUNDS = (0.3, 2.5)

# _ROUND_DP = 2

PERSONALIZATION_VERSION = "1.2.0"

COMBINED_MULTIPLIER_BOUNDS = (
    0.3,
    2.5,
)

_ROUND_DP = 2


# =========================================================================
# NUTRITION IMMUTABILITY GUARD
# =========================================================================

def _nutrition_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Capture fields that personalization is never allowed to change."""
    meal = payload.get("meal")
    if not isinstance(meal, dict):
        return {}

    return copy.deepcopy({
        "foods": meal.get("foods"),
        "nutrition": meal.get("nutrition"),
        "nutrition_totals": meal.get("nutrition_totals"),
        "total_nutrition": meal.get("total_nutrition"),
        "nutrition_summary": meal.get("nutrition_summary"),
        "estimated_visible_food_weight_g": meal.get(
            "estimated_visible_food_weight_g"
        ),
    })


def _assert_nutrition_unchanged(
    before: Dict[str, Any],
    payload: Dict[str, Any],
    *,
    stage: str,
) -> None:
    after = _nutrition_snapshot(payload)
    if before != after:
        raise RuntimeError(
            f"{stage} attempted to modify detected foods or nutrition. "
            "Personalization may only add data under meal.personalization."
        )


# =========================================================================
# DATA STRUCTURES
# =========================================================================

@dataclass(frozen=True)
class Modifier:
    """
    One reusable, self-contained personalization rule. `applies_when` is a
    predicate over a user_profile dict (built via the factory functions
    below, never an inline lambda scattered in application logic) -
    everything the engine needs to know about WHEN and HOW this modifier
    applies lives on the object itself.
    """
    id: str
    category: str  # which of the nine named databases this belongs to
    applies_when: Callable[[Dict[str, Any]], bool]
    reason: str
    affected_domains: Tuple[str, ...] = ()
    affected_features: Tuple[str, ...] = ()
    affected_rules: Tuple[str, ...] = ()
    adjustment_type: str = "weight"  # "weight" (feature/rule-level) or "domain" (whole-domain)
    multiplier: float = 1.0
    confidence: float = 0.75
    evidence_strength: str = "Moderate"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "affected_domains": list(self.affected_domains),
            "affected_features": list(self.affected_features),
            "affected_rules": list(self.affected_rules),
            "adjustment_type": self.adjustment_type,
            "multiplier": self.multiplier,
            "reason": self.reason,
            "confidence": self.confidence,
            "evidence_strength": self.evidence_strength,
        }


@dataclass
class ModifierIndex:
    """
    Pre-built lookup structure over the currently-ACTIVE modifiers only
    (see initialize_modifier_index) - O(1) lookup per evidence item during
    the main traversal, regardless of how many hundreds of ingredients or
    how many total modifiers exist in the full database.
    """
    by_domain: Dict[str, List[Modifier]] = field(default_factory=dict)
    by_feature: Dict[str, List[Modifier]] = field(default_factory=dict)
    by_rule: Dict[str, List[Modifier]] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(set(id(m) for lst in (*self.by_domain.values(), *self.by_feature.values(), *self.by_rule.values()) for m in lst))


# =========================================================================
# PREDICATE FACTORIES
# =========================================================================
#
# Small, generic, reusable builders - each returns a closure that reads
# user_profile defensively (missing/None fields simply don't match,
# never raise). These are the ONLY place anything resembling "logic"
# lives; every Modifier below just plugs one of these in as applies_when.

def _age_at_least(years: int) -> Callable[[Dict[str, Any]], bool]:
    def _check(profile: Dict[str, Any]) -> bool:
        age = profile.get("age")
        return isinstance(age, (int, float)) and age >= years

    return _check


def _age_below(years: int) -> Callable[[Dict[str, Any]], bool]:
    def _check(profile: Dict[str, Any]) -> bool:
        age = profile.get("age")
        return isinstance(age, (int, float)) and age < years

    return _check


def _flag_is_true(field_name: str) -> Callable[[Dict[str, Any]], bool]:
    def _check(profile: Dict[str, Any]) -> bool:
        return bool(profile.get(field_name))

    return _check


def _field_in(field_name: str, *values: str) -> Callable[[Dict[str, Any]], bool]:
    normalized = {v.strip().lower() for v in values}

    def _check(profile: Dict[str, Any]) -> bool:
        value = profile.get(field_name)
        if not value:
            return False
        return str(value).strip().lower() in normalized

    return _check


def _has_any_condition(*names: str) -> Callable[[Dict[str, Any]], bool]:
    normalized = {n.strip().lower() for n in names}

    def _check(profile: Dict[str, Any]) -> bool:
        conditions = profile.get("chronic_conditions") or []
        if not isinstance(conditions, (list, tuple, set)):
            return False
        condition_set = {str(c).strip().lower() for c in conditions}
        return bool(normalized & condition_set)

    return _check


def _all_of(*predicates: Callable[[Dict[str, Any]], bool]) -> Callable[[Dict[str, Any]], bool]:
    def _check(profile: Dict[str, Any]) -> bool:
        return all(p(profile) for p in predicates)

    return _check


# =========================================================================
# MODIFIER DATABASES
# =========================================================================
#
# Nine named groups, matching the requested architecture. Each modifier's
# reason/multiplier/confidence reflects the same scientific grounding
# already used for evidence_engine.py's POPULATION_MODIFIERS and the
# per-domain "population modifier" notes in the coefficient reference
# documents - this module implements that same knowledge as reusable
# objects, rather than inventing new science.

AGE_MODIFIERS: List[Modifier] = [
    Modifier(
        id="older_adult", category="age", applies_when=_age_at_least(65),
        reason="Anabolic resistance raises protein/leucine needs with age; fall and fracture risk raise calcium and vitamin D relevance",
        affected_domains=("Musculoskeletal Health & Healthy Aging", "Bone Health"),
        affected_features=("protein_density", "protein_quality_leucine_proxy", "vitamin_d_density", "calcium_density"),
        adjustment_type="weight", multiplier=1.25, confidence=0.90, evidence_strength="Strong",
    ),
    Modifier(
        id="child_adolescent", category="age", applies_when=_age_below(18),
        reason="Added sugar and sugary beverages carry disproportionate long-term metabolic risk when intake patterns are established in childhood/adolescence",
        affected_domains=("Glycemic Control",),
        affected_features=("added_sugar_density", "liquid_sugar_tag"),
        adjustment_type="weight", multiplier=1.20, confidence=0.75, evidence_strength="Moderate-Strong",
    ),
]

GOAL_MODIFIERS: List[Modifier] = [
    Modifier(
        id="fat_loss_goal", category="goal", applies_when=_field_in("goal", "fat_loss", "weight_loss"),
        reason="Satiety- and energy-density-related evidence becomes directly actionable when the goal is fat loss",
        affected_domains=("Weight Management",),
        affected_features=("fiber_density", "protein_density", "energy_density", "liquid_calories_tag"),
        adjustment_type="weight", multiplier=1.25, confidence=0.85, evidence_strength="Moderate-Strong",
    ),
    Modifier(
        id="muscle_gain_goal", category="goal", applies_when=_field_in("goal", "muscle_gain", "hypertrophy", "bulking"),
        reason="Protein and leucine adequacy are central to a muscle-gain goal",
        affected_domains=("Musculoskeletal Health & Healthy Aging",),
        affected_features=("protein_density", "protein_quality_leucine_proxy", "energy_adequacy"),
        adjustment_type="weight", multiplier=1.20, confidence=0.85, evidence_strength="Moderate-Strong",
    ),
]

DISEASE_MODIFIERS: List[Modifier] = [
    Modifier(
        id="type_2_diabetes", category="disease",
        applies_when=_has_any_condition("type_2_diabetes", "diabetes", "prediabetes", "insulin_resistance"),
        reason="Glycemic-control evidence (fiber, whole grains, added sugar, glycemic load) is directly actionable with a diabetes/prediabetes diagnosis",
        affected_domains=("Glycemic Control", "Metabolic Syndrome"),
        affected_features=("glycemic_load", "added_sugar_density", "fiber_density", "whole_grain_tag", "liquid_sugar_tag"),
        adjustment_type="weight", multiplier=1.35, confidence=0.95, evidence_strength="Strong",
    ),
    Modifier(
        id="hypertension", category="disease", applies_when=_has_any_condition("hypertension", "high_blood_pressure"),
        reason="DASH-pattern sodium/potassium evidence is directly actionable with a hypertension diagnosis",
        affected_domains=("Blood Pressure", "Cardiovascular Health"),
        affected_features=("sodium_density", "potassium_density", "food_form_penalty"),
        adjustment_type="weight", multiplier=1.35, confidence=0.95, evidence_strength="Strong",
    ),
    Modifier(
        id="chronic_kidney_disease", category="disease",
        applies_when=_has_any_condition("chronic_kidney_disease", "ckd", "kidney_disease"),
        reason="Sodium, potassium, protein, and phosphorus burden all carry elevated clinical relevance in CKD",
        affected_domains=("Renal Health",),
        affected_features=("sodium_density", "potassium_density", "protein_density", "phosphorus_density"),
        adjustment_type="weight", multiplier=1.40, confidence=0.90, evidence_strength="Strong",
    ),
    Modifier(
        id="heart_failure", category="disease", applies_when=_has_any_condition("heart_failure", "chf"),
        reason="Fluid-retention risk makes sodium burden especially relevant in heart failure",
        affected_domains=("Cardiovascular Health", "Blood Pressure"),
        affected_features=("sodium_density",),
        adjustment_type="weight", multiplier=1.30, confidence=0.85, evidence_strength="Moderate-Strong",
    ),
    Modifier(
        id="dyslipidemia", category="disease",
        applies_when=_has_any_condition("dyslipidemia", "high_cholesterol", "hyperlipidemia"),
        reason="Saturated fat, trans fat, and fat-quality evidence directly targets lipid management",
        affected_domains=("Cardiovascular Health",),
        affected_features=("saturated_fat_density", "trans_fat_density", "unsaturated_fat_quality", "cholesterol_density"),
        adjustment_type="weight", multiplier=1.25, confidence=0.85, evidence_strength="Moderate-Strong",
    ),
    Modifier(
        id="ibs", category="disease", applies_when=_has_any_condition("ibs", "irritable_bowel_syndrome"),
        reason="Fiber tolerance in IBS is highly individual and fermentation-pattern dependent rather than simply 'more is better'",
        affected_domains=("Gut Health",),
        affected_features=("fiber_density", "fermented_food_tag"),
        adjustment_type="weight", multiplier=1.20, confidence=0.60, evidence_strength="Moderate",
    ),
    Modifier(
        id="ibd", category="disease",
        applies_when=_has_any_condition("ibd", "inflammatory_bowel_disease", "crohns", "crohns_disease", "ulcerative_colitis"),
        reason="Gut-barrier and fiber-tolerance evidence carries elevated relevance in inflammatory bowel disease",
        affected_domains=("Gut Health", "Inflammation & Joint Support"),
        affected_features=("fiber_density", "ultra_processed_tag", "fermented_food_tag"),
        adjustment_type="weight", multiplier=1.25, confidence=0.70, evidence_strength="Moderate",
    ),
    Modifier(
        id="osteoarthritis", category="disease", applies_when=_has_any_condition("osteoarthritis", "oa"),
        reason="Weight-bearing joint load makes energy-density and weight-related evidence especially relevant in osteoarthritis",
        affected_domains=("Inflammation & Joint Support",),
        affected_features=("energy_density", "omega3_density", "central_adiposity_proxy"),
        adjustment_type="weight", multiplier=1.25, confidence=0.80, evidence_strength="Moderate-Strong",
    ),
    Modifier(
        id="rheumatoid_arthritis", category="disease",
        applies_when=_has_any_condition("rheumatoid_arthritis", "ra", "psoriatic_arthritis", "spondyloarthritis"),
        reason="Omega-3 and anti-inflammatory dietary pattern evidence is directly actionable in inflammatory arthritis",
        affected_domains=("Inflammation & Joint Support",),
        affected_features=("omega3_density", "ultra_processed_tag", "fiber_density"),
        adjustment_type="weight", multiplier=1.30, confidence=0.80, evidence_strength="Moderate-Strong",
    ),
    Modifier(
        id="osteoporosis", category="disease", applies_when=_has_any_condition("osteoporosis", "osteopenia"),
        reason="Calcium, vitamin D, vitamin K, and protein evidence directly targets bone mineral density maintenance",
        affected_domains=("Bone Health",),
        affected_features=("calcium_density", "vitamin_d_density", "vitamin_k_density", "protein_density"),
        adjustment_type="weight", multiplier=1.35, confidence=0.90, evidence_strength="Strong",
    ),
]

ACTIVITY_MODIFIERS: List[Modifier] = [
    Modifier(
        id="high_activity", category="activity", applies_when=_field_in("activity_level", "active", "very_active"),
        reason="Higher activity raises energy and protein turnover needs",
        affected_domains=("Musculoskeletal Health & Healthy Aging",),
        affected_features=("protein_density", "energy_density", "energy_adequacy"),
        adjustment_type="weight", multiplier=1.15, confidence=0.75, evidence_strength="Moderate",
    ),
    Modifier(
        id="sedentary_activity", category="activity", applies_when=_field_in("activity_level", "sedentary"),
        reason="Lower energy expenditure raises the practical relevance of energy-density evidence",
        affected_domains=("Weight Management",),
        affected_features=("energy_density",),
        adjustment_type="weight", multiplier=1.15, confidence=0.65, evidence_strength="Moderate",
    ),
]

DIET_MODIFIERS: List[Modifier] = [
    Modifier(
        id="vegetarian_diet", category="diet", applies_when=_field_in("diet_type", "vegetarian"),
        reason="Vitamin B12, iron, zinc, omega-3, and protein quality require more deliberate attention without meat/fish",
        affected_domains=("Musculoskeletal Health & Healthy Aging", "Cardiovascular Health"),
        affected_features=(
            "protein_quality_leucine_proxy", "iron_density", "omega3_density",
            "vitamin_b12_density", "zinc_density",
        ),
        adjustment_type="weight", multiplier=1.20, confidence=0.85, evidence_strength="Moderate-Strong",
    ),
    Modifier(
        id="vegan_diet", category="diet", applies_when=_field_in("diet_type", "vegan"),
        reason="Excluding all animal products (including dairy/eggs) further raises B12, iron, zinc, calcium, and omega-3 relevance beyond vegetarian",
        affected_domains=("Musculoskeletal Health & Healthy Aging", "Cardiovascular Health", "Bone Health"),
        affected_features=(
            "protein_quality_leucine_proxy", "iron_density", "omega3_density", "calcium_density",
            "vitamin_b12_density", "zinc_density",
        ),
        adjustment_type="weight", multiplier=1.30, confidence=0.85, evidence_strength="Moderate-Strong",
    ),
]

PREGNANCY_MODIFIERS: List[Modifier] = [
    Modifier(
        id="pregnancy", category="pregnancy", applies_when=_flag_is_true("pregnant"),
        reason="Folate, iron, iodine, DHA, and choline all have elevated, well-established relevance during pregnancy",
        affected_domains=("Cognitive & Mood Health",),
        affected_features=(
            "iron_density", "choline_density", "omega3_density", "b_vitamin_density_index",
            "folate_density", "iodine_density",
        ),
        adjustment_type="weight", multiplier=1.40, confidence=0.90, evidence_strength="Strong",
    ),
    Modifier(
        id="lactation", category="pregnancy", applies_when=_flag_is_true("lactating"),
        reason="DHA, choline, and iodine remain elevated in relevance during lactation, alongside overall energy adequacy",
        affected_domains=("Cognitive & Mood Health",),
        affected_features=(
            "choline_density", "omega3_density", "energy_adequacy",
            "iodine_density",
        ),
        adjustment_type="weight", multiplier=1.30, confidence=0.85, evidence_strength="Moderate-Strong",
    ),
]

FRAILTY_MODIFIERS: List[Modifier] = [
    Modifier(
        id="frailty", category="frailty", applies_when=_flag_is_true("frailty"),
        reason="Frailty substantially raises protein, energy, and vitamin D relevance to slow further muscle and functional decline",
        affected_domains=("Musculoskeletal Health & Healthy Aging",),
        affected_features=("protein_density", "energy_density", "vitamin_d_density", "protein_quality_leucine_proxy"),
        adjustment_type="weight", multiplier=1.35, confidence=0.85, evidence_strength="Moderate-Strong",
    ),
]

LOW_APPETITE_MODIFIERS: List[Modifier] = [
    Modifier(
        id="low_appetite", category="low_appetite", applies_when=_flag_is_true("low_appetite"),
        reason="With reduced intake volume, nutrient- and energy-dense choices matter disproportionately more per bite",
        affected_domains=("Musculoskeletal Health & Healthy Aging", "Weight Management"),
        affected_features=("protein_density", "energy_density"),
        adjustment_type="weight", multiplier=1.25, confidence=0.75, evidence_strength="Moderate",
    ),
]

TRAINING_MODIFIERS: List[Modifier] = [
    Modifier(
        id="resistance_training", category="training", applies_when=_flag_is_true("resistance_training"),
        reason="Resistance training amplifies the muscle-protein-synthesis relevance of protein, leucine, and energy adequacy",
        affected_domains=("Musculoskeletal Health & Healthy Aging",),
        affected_features=("protein_density", "protein_quality_leucine_proxy", "energy_adequacy"),
        adjustment_type="weight", multiplier=1.25, confidence=0.90, evidence_strength="Strong",
    ),
]

ALL_MODIFIER_GROUPS: Tuple[List[Modifier], ...] = (
    AGE_MODIFIERS, GOAL_MODIFIERS, DISEASE_MODIFIERS, ACTIVITY_MODIFIERS,
    DIET_MODIFIERS, PREGNANCY_MODIFIERS, FRAILTY_MODIFIERS,
    LOW_APPETITE_MODIFIERS, TRAINING_MODIFIERS,
)


# =========================================================================
# LOAD / ACTIVATE / INDEX
# =========================================================================

def load_modifier_database() -> List[Modifier]:
    """
    Assemble every modifier across all nine categories into one flat
    list. The full database is small (dozens of entries, not hundreds),
    so this is deliberately NOT cached/memoized (see PERFORMANCE / "remain
    cache-free" in the module docstring) - recomputing a plain list
    concatenation every call is effectively free and keeps this function
    trivially correct.
    """
    all_modifiers: List[Modifier] = []
    for group in ALL_MODIFIER_GROUPS:
        all_modifiers.extend(group)
    return all_modifiers

def normalize_user_profile(
    profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Normalize the optional profile into the shared schema consumed by both
    score personalization and the separate nutrient-target engine.

    Unknown fields are ignored. Missing fields remain absent rather than
    being converted into false values.
    """
    if not isinstance(profile, dict):
        return {}

    normalized: Dict[str, Any] = {}

    def clean_text(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None

        cleaned = (
            value.strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

        return cleaned or None

    age_months = profile.get("age_months")
    if (
        isinstance(age_months, (int, float))
        and not isinstance(age_months, bool)
        and 0 <= float(age_months) < 1560
    ):
        normalized["age_months"] = int(round(float(age_months)))

    age = profile.get("age")
    if (
        isinstance(age, (int, float))
        and not isinstance(age, bool)
        and 0 <= float(age) < 130
    ):
        normalized["age"] = float(age)
        normalized.setdefault("age_months", int(round(float(age) * 12.0)))

    for field_name in (
        "height_cm",
        "weight_kg",
        "lactation_stage_months",
    ):
        value = profile.get(field_name)

        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and float(value) >= 0
        ):
            normalized[field_name] = float(value)

    sex = clean_text(
        profile.get("sex")
        or profile.get("gender")
    )
    if sex in {"male", "female"}:
        normalized["sex"] = sex

    for field_name in (
        "goal",
        "activity_level",
        "diet_type",
        "diet_pattern",
        "smoking_status",
        "ckd_stage",
        "dialysis_modality",
        "blood_pressure_status",
        "glycemic_status",
    ):
        value = clean_text(
            profile.get(field_name)
        )

        if value:
            normalized[field_name] = value

    activity_aliases = {
        "inactive": "sedentary",
        "lightly_active": "low_active",
        "moderately_active": "active",
        "highly_active": "very_active",
    }

    if "activity_level" in normalized:
        normalized["activity_level"] = (
            activity_aliases.get(
                normalized["activity_level"],
                normalized["activity_level"],
            )
        )

    trimester = profile.get("trimester")
    if (
        isinstance(trimester, int)
        and not isinstance(trimester, bool)
        and trimester in (1, 2, 3)
    ):
        normalized["trimester"] = trimester

    raw_conditions = (
        profile.get("chronic_conditions")
        if profile.get("chronic_conditions") is not None
        else profile.get("conditions")
    )

    conditions: List[str] = []

    if isinstance(raw_conditions, dict):
        for key, enabled in raw_conditions.items():
            if enabled:
                cleaned = clean_text(key)
                if cleaned:
                    conditions.append(cleaned)

    elif isinstance(
        raw_conditions,
        (list, tuple, set),
    ):
        for condition in raw_conditions:
            cleaned = clean_text(condition)
            if cleaned:
                conditions.append(cleaned)

    normalized["chronic_conditions"] = list(
        dict.fromkeys(conditions)
    )

    raw_medications = profile.get("medications")
    medications: List[str] = []

    if isinstance(
        raw_medications,
        (list, tuple, set),
    ):
        for medication in raw_medications:
            cleaned = clean_text(medication)
            if cleaned:
                medications.append(cleaned)

    normalized["medications"] = list(
        dict.fromkeys(medications)
    )

    raw_allergies = profile.get("allergies")
    allergies: List[str] = []

    if isinstance(
        raw_allergies,
        (list, tuple, set),
    ):
        for allergy in raw_allergies:
            cleaned = clean_text(allergy)
            if cleaned:
                allergies.append(cleaned)

    normalized["allergies"] = list(
        dict.fromkeys(allergies)
    )

    for field_name in (
        "intolerances",
        "food_intolerances",
        "excluded_foods",
        "disliked_foods",
    ):
        raw_values = profile.get(field_name)
        if not isinstance(raw_values, (list, tuple, set)):
            continue
        cleaned_values = [
            cleaned
            for value in raw_values
            if (cleaned := clean_text(value))
        ]
        normalized[field_name] = list(dict.fromkeys(cleaned_values))

    for field_name in (
        "pregnant",
        "lactating",
        "frailty",
        "low_appetite",
        "resistance_training",
        "endurance_training",
    ):
        value = profile.get(field_name)

        if isinstance(value, bool):
            normalized[field_name] = value

    return normalized


def determine_active_modifiers(
    user_profile: Optional[Dict[str, Any]],
    all_modifiers: Optional[List[Modifier]] = None,
) -> List[Modifier]:
    """
    Evaluate every modifier's applies_when against user_profile. Every
    field in user_profile is optional and every predicate is defensive
    (missing fields simply don't match) - an empty or None user_profile
    always yields an empty active-modifier list, never an error.
    """
    user_profile = user_profile or {}
    all_modifiers = all_modifiers if all_modifiers is not None else load_modifier_database()

    active: List[Modifier] = []
    for modifier in all_modifiers:
        try:
            if modifier.applies_when(user_profile):
                active.append(modifier)
        except Exception as exc:  # noqa: BLE001 - a single bad predicate must not break personalization
            logger.warning("Modifier %r's applies_when raised %s; treating as inactive.", modifier.id, exc)
    return active


def initialize_modifier_index(active_modifiers: Sequence[Modifier]) -> ModifierIndex:
    """
    Build (once per call, over the already-small ACTIVE subset only) the
    by_domain/by_feature/by_rule lookup dicts used for O(1) matching per
    evidence item during personalize_domain_scores() - the engine never
    re-scans the modifier list per evidence item, regardless of how many
    hundreds of ingredients a meal has.
    """
    index = ModifierIndex()
    for modifier in active_modifiers:
        if modifier.adjustment_type == "domain":
            for domain_label in modifier.affected_domains:
                index.by_domain.setdefault(domain_label, []).append(modifier)
        else:  # "weight" - feature/rule-level
            for feature_key in modifier.affected_features:
                index.by_feature.setdefault(feature_key, []).append(modifier)
            for rule_id in modifier.affected_rules:
                index.by_rule.setdefault(rule_id, []).append(modifier)
            # A "weight" modifier with affected_domains set (but no
            # specific features/rules) still applies broadly across that
            # domain - registered under by_domain too so it isn't silently
            # dropped just because it has no feature/rule-level specificity.
            if not modifier.affected_features and not modifier.affected_rules:
                for domain_label in modifier.affected_domains:
                    index.by_domain.setdefault(domain_label, []).append(modifier)
    return index


# =========================================================================
# APPLYING MODIFIERS
# =========================================================================

def apply_domain_modifiers(evidence_item: Dict[str, Any], modifier_index: ModifierIndex) -> List[Modifier]:
    """Every active domain-level modifier whose affected_domains includes
    this evidence item's health_domain."""
    domain_label = evidence_item.get("health_domain")
    if not domain_label:
        return []
    return list(modifier_index.by_domain.get(domain_label, []))


def apply_evidence_modifiers(evidence_item: Dict[str, Any], modifier_index: ModifierIndex) -> List[Modifier]:
    """Every active feature- or rule-level modifier matching this evidence
    item's own feature key or rule_id."""
    matches = list(modifier_index.by_feature.get(evidence_item.get("feature"), []))
    for modifier in modifier_index.by_rule.get(evidence_item.get("rule_id"), []):
        if modifier not in matches:
            matches.append(modifier)
    return matches


def apply_modifier(
    base_weight: float,
    applicable_modifiers: Sequence[Modifier],
    bounds: Tuple[float, float] = COMBINED_MULTIPLIER_BOUNDS,
) -> Tuple[float, List[str]]:
    """
    Combine every applicable modifier into a single multiplier and apply
    it to base_weight. Modifiers combine ADDITIVELY on their (multiplier -
    1.0) delta, each scaled by the modifier's own confidence (a modifier
    with confidence=0.5 only ever contributes half of its stated
    multiplier's effect) - this grows linearly as modifiers stack rather
    than compounding multiplicatively into runaway values, and a
    less-certain modifier naturally pulls less weight than a well-
    established one. Returns (adjusted_weight, [modifier ids that fired]).
    """
    if not applicable_modifiers:
        return base_weight, []

    combined_multiplier = 1.0
    applied_ids: List[str] = []
    for modifier in applicable_modifiers:
        delta = (modifier.multiplier - 1.0) * modifier.confidence
        combined_multiplier += delta
        applied_ids.append(modifier.id)

    lo, hi = bounds
    combined_multiplier = max(lo, min(combined_multiplier, hi))
    return base_weight * combined_multiplier, applied_ids


def _dedupe_modifiers(modifiers: Sequence[Modifier]) -> List[Modifier]:
    seen_ids: set = set()
    result: List[Modifier] = []
    for m in modifiers:
        if m.id not in seen_ids:
            seen_ids.add(m.id)
            result.append(m)
    return result


# =========================================================================
# PERSONALIZED SCORING
# =========================================================================

def personalize_domain_scores(
    domain_evidence: Dict[str, List[Dict[str, Any]]],
    modifier_index: ModifierIndex,
    aggregator: Optional[DomainAggregator] = None,
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    For every domain's raw evidence items, compute a personalized copy of
    each item's effective_weight (original items are never mutated - a
    shallow copy per item carries the adjusted weight), then re-run
    health_domain_scoring's own DomainAggregator over BOTH the original
    and personalized weights so every number reported is directly
    comparable.

    Returns (personalized_domain_scores, domain_adjustments, evidence_adjustments).
    """
    aggregator = aggregator or DomainAggregator()

    personalized_scores: Dict[str, Dict[str, Any]] = {}
    domain_adjustments: List[Dict[str, Any]] = []
    evidence_adjustments: List[Dict[str, Any]] = []

    for domain_label, items in domain_evidence.items():
        personalized_items: List[Dict[str, Any]] = []
        touched_modifier_ids: set = set()

        for item in items:
            domain_mods = apply_domain_modifiers(item, modifier_index)
            evidence_mods = apply_evidence_modifiers(item, modifier_index)
            applicable = _dedupe_modifiers(domain_mods + evidence_mods)

            original_weight = item.get("effective_weight", 0.0) or 0.0
            personalized_weight, applied_ids = apply_modifier(original_weight, applicable)

            personalized_item = dict(item)
            personalized_item["effective_weight"] = personalized_weight
            personalized_items.append(personalized_item)

            if applied_ids:
                touched_modifier_ids.update(applied_ids)
                evidence_adjustments.append({
                    "rule_id": item.get("rule_id"),
                    "rule_name": item.get("rule_name"),
                    "feature": item.get("feature"),
                    "domain": domain_label,
                    "original_weight": round(original_weight, 4),
                    "personalized_weight": round(personalized_weight, 4),
                    "modifiers_applied": applied_ids,
                })

        # original_score = aggregator.score(domain_label, items)
        # personalized_score = aggregator.score(domain_label, personalized_items)
        health_domain_label = (
            items[0].get("health_domain")
            if items
            else domain_label
        )
        
        if (
            not isinstance(health_domain_label, str)
            or not health_domain_label
        ):
            health_domain_label = domain_label
        
        original_score = aggregator.score(
            domain=domain_label,
            health_domain=health_domain_label,
            evidence_items=items,
        )
        
        personalized_score = aggregator.score(
            domain=domain_label,
            health_domain=health_domain_label,
            evidence_items=personalized_items,
        )
        
        personalized_scores[domain_label] = personalized_score.to_dict()

        if touched_modifier_ids:
            domain_adjustments.append({
                "domain": domain_label,
                "modifiers_applied": sorted(touched_modifier_ids),
                "original_score": original_score.score,
                "personalized_score": personalized_score.score,
                "score_delta": round(personalized_score.score - original_score.score, _ROUND_DP),
                "original_confidence": original_score.confidence,
                "personalized_confidence": personalized_score.confidence,
            })

    return personalized_scores, domain_adjustments, evidence_adjustments


# =========================================================================
# EXPLANATION / SUMMARY
# =========================================================================


def build_personalization_summary(
    active_modifiers: Sequence[Modifier],
    domain_adjustments: Sequence[Dict[str, Any]],
    evidence_adjustments: Sequence[Dict[str, Any]],
    user_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    user_profile = user_profile or {}

    domains_improved = sum(1 for d in domain_adjustments if d["score_delta"] > 0)
    domains_reduced = sum(1 for d in domain_adjustments if d["score_delta"] < 0)
    most_affected = sorted(domain_adjustments, key=lambda d: abs(d["score_delta"]), reverse=True)[:5]

    return {
        "personalization_version": PERSONALIZATION_VERSION,
        "modifier_count": len(active_modifiers),
        "active_modifier_ids": sorted({m.id for m in active_modifiers}),
        "domains_adjusted": len(domain_adjustments),
        "domains_improved": domains_improved,
        "domains_reduced": domains_reduced,
        "evidence_items_adjusted": len(evidence_adjustments),
        "most_affected_domains": [
            {"domain": d["domain"], "score_delta": d["score_delta"]} for d in most_affected
        ],
        # Passed through for downstream awareness only - see module
        # docstring "Allergies and medications" for why these don't
        # participate in scoring.
        "allergies_noted": list(user_profile.get("allergies") or []),
        "medications_noted": list(user_profile.get("medications") or []),
    }


# =========================================================================
# TRAVERSAL + ORCHESTRATION
# =========================================================================

def process_meal(meal_json: Dict[str, Any], user_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Deep-copies `meal_json`, computes personalization, and returns the
    enriched copy with meal["personalization"] attached. The input is
    never mutated - the ORIGINAL meal object (including its untouched
    meal["health_domain_scores"]) remains fully intact.
    """
    if not isinstance(meal_json, dict) or "meal" not in meal_json:
        raise ValueError("Input must be a dict with a top-level 'meal' key")

    nutrition_before = _nutrition_snapshot(meal_json)
    result = copy.deepcopy(meal_json)
    # user_profile = user_profile or {}
    user_profile = normalize_user_profile(
        user_profile
    )

    all_modifiers = load_modifier_database()
    active_modifiers = determine_active_modifiers(user_profile, all_modifiers)
    modifier_index = initialize_modifier_index(active_modifiers)

    domain_accumulators = collect_domain_evidence(result, is_meal=True)
    domain_evidence_items = {domain: acc.evidence_items for domain, acc in domain_accumulators.items()}

    personalized_scores, domain_adjustments, evidence_adjustments = personalize_domain_scores(
        domain_evidence_items, modifier_index,
    )

    summary = build_personalization_summary(active_modifiers, domain_adjustments, evidence_adjustments, user_profile)

    result["meal"]["personalization"] = {
        "active_modifiers": [
            modifier.to_dict()
            for modifier in active_modifiers
        ],
        "domain_adjustments": (
            domain_adjustments
        ),
        "evidence_adjustments": (
            evidence_adjustments
        ),
        "personalized_domain_scores": (
            personalized_scores
        ),
        "profile_applied": bool(
            user_profile
        ),
        "summary": summary,
    }

    _assert_nutrition_unchanged(
        nutrition_before,
        result,
        stage="Health-score personalization",
    )
    return result


# =========================================================================
# PUBLIC ENTRY POINTS
# =========================================================================

async def attach_personalization(
    meal_json: Dict[str, Any],
    user_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main entry point. Takes a meal JSON that has already been through
    attach_domain_scores() and an optional user_profile dict (every field
    optional - missing/None is handled gracefully throughout), and
    returns a deep copy with meal["personalization"] attached.

    This function performs no I/O and needs nothing awaited internally -
    it's async purely so this phase composes naturally with the other
    five async pipeline phases.
    """
    return process_meal(meal_json, user_profile)


def attach_personalization_sync(
    meal_json: Dict[str, Any],
    user_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Synchronous convenience wrapper around attach_personalization().

    Works out of the box in plain scripts, FastAPI background tasks, and
    Celery workers. In notebook environments (Colab/Jupyter) where a loop
    is already running per cell, this detects that automatically and uses
    nest_asyncio if installed, or raises a clear error pointing you at
    `await attach_personalization(...)` if it isn't - same behavior as
    the rest of the Nutrica pipeline.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(attach_personalization(meal_json, user_profile))

    try:
        import nest_asyncio  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "attach_personalization_sync() was called from inside a running "
            "event loop (this is normal in Colab/Jupyter). Either:\n"
            "  1) use `await attach_personalization(meal_json, user_profile)` directly, or\n"
            "  2) `pip install nest_asyncio`, then `import nest_asyncio; "
            "nest_asyncio.apply()` before calling attach_personalization_sync()."
        ) from exc

    nest_asyncio.apply()
    return asyncio.run(attach_personalization(meal_json, user_profile))


async def resolve_enrich_featurize_evaluate_score_and_personalize(
    gemini_json: Dict[str, Any],
    user_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience orchestrator chaining all six pipeline phases end to end.
    Requires food_resolver.py, nutrient_profile.py, feature_engineering.py,
    evidence_engine.py, and health_domain_scoring.py to be importable
    alongside this module; each phase also works fully standalone if you
    only need one of them.
    """
    try:
        from food_resolver import resolve_meal
        from nutrient_profile import attach_nutrients
        from feature_engineering import compute_features
        from evidence_engine import attach_evidence
        from health_domain_scoring import attach_domain_scores
    except ImportError as exc:
        raise ImportError(
            "resolve_enrich_featurize_evaluate_score_and_personalize() requires "
            "food_resolver.py, nutrient_profile.py, feature_engineering.py, "
            "evidence_engine.py, and health_domain_scoring.py to be importable "
            "alongside personalization_engine.py. Call each phase yourself and "
            "pass the result into attach_personalization() instead."
        ) from exc

    resolved = await resolve_meal(gemini_json)
    enriched = await attach_nutrients(resolved)
    featurized = await compute_features(enriched)
    evaluated = await attach_evidence(featurized)
    scored = await attach_domain_scores(evaluated)
    return await attach_personalization(scored, user_profile)


# =========================================================================
# DEMO
# =========================================================================

if __name__ == "__main__":
    import json

    # A meal that has already been through attach_domain_scores() - each
    # food/ingredient/spice already carries "evidence", and the meal
    # already carries "health_domain_scores". A minimal hand-built example
    # with a sodium-heavy ingredient is enough to demonstrate a
    # hypertension modifier visibly reweighting Blood Pressure evidence.
    SAMPLE_SCORED_MEAL = {
        "meal": {
            "health_domain_scores": {
                "Blood Pressure": {"score": 32.0, "confidence": 0.85, "coverage": 0.6},
            },
            "foods": [
                {
                    "id": "food_0001",
                    "name": "Salted Snack Mix",
                    "evidence": {
                        "items": [
                            {
                                "rule_id": "bp_sodium", "rule_name": "Sodium Density",
                                "domain": "blood_pressure", "health_domain": "Blood Pressure",
                                "feature": "sodium_density", "feature_value": 3.2,
                                "direction": "negative", "evidence_type": "risk",
                                "mechanism": "Sodium raises blood pressure",
                                "pathway": "Fluid balance", "organ": "Blood vessels",
                                "coefficient": 1.00, "raw_effect": 0.9, "base_weight": 1.00,
                                "curve_multiplier": 0.95, "interaction_multiplier": 0.85,
                                "confidence_multiplier": 1.00, "effective_weight": 0.81,
                                "confidence": 1.00, "evidence_strength": "Strong",
                                "applied_interactions": [], "citation": None,
                                "source": "Nutrica coefficient reference document",
                            },
                        ],
                        "interactions": [],
                    },
                    "ingredients": [], "spices": [],
                },
            ],
        }
    }

    # example_user_profile = {
    #     "age": 68,
    #     "chronic_conditions": ["hypertension"],
    #     "resistance_training": True,
    # }

    # personalized = attach_personalization_sync(SAMPLE_SCORED_MEAL, example_user_profile)
    # print(json.dumps(personalized["meal"]["personalization"], indent=2))
