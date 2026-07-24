from __future__ import annotations

import asyncio
import copy
import logging
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# =========================================================================
# LOGGING
# =========================================================================

logger = logging.getLogger("nutrica.evidence_engine")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
logger.setLevel(os.environ.get("NUTRICA_LOG_LEVEL", "INFO"))


# =========================================================================
# CONFIG / ENUMS
# =========================================================================

ENGINE_VERSION = "1.0"


class CurveType:
    """Canonical set of threshold/shape policies used across the source
    document, consolidated from its qualitative descriptions (piecewise
    linear, saturating benefit, binary penalty, U-shaped, etc.)."""
    LINEAR = "linear"
    PIECEWISE_LINEAR = "piecewise_linear"
    SATURATING = "saturating"
    BINARY = "binary"
    BINARY_INTENSITY = "binary_intensity"
    THRESHOLD = "threshold"
    U_SHAPED = "u_shaped"
    INVERSE = "inverse"


class ScoreOrientation:
    RISK = "risk"        # higher raw score = worse (Blood Sugar, Blood Pressure, ...)
    SUPPORT = "support"  # higher raw score = better (Heart, Bone, Brain, Muscle)


DOMAIN_ORIENTATION: Dict[str, str] = {
    "blood_sugar": ScoreOrientation.RISK,
    "blood_pressure": ScoreOrientation.RISK,
    "heart": ScoreOrientation.SUPPORT,
    "metabolic_syndrome": ScoreOrientation.RISK,
    "kidney": ScoreOrientation.RISK,
    "liver": ScoreOrientation.RISK,
    "bone": ScoreOrientation.SUPPORT,
    "brain": ScoreOrientation.SUPPORT,
    "inflammation": ScoreOrientation.SUPPORT,
    "arthritis": ScoreOrientation.SUPPORT,
    "cancer": ScoreOrientation.RISK,
    "weight": ScoreOrientation.RISK,
    "muscle": ScoreOrientation.SUPPORT,
    "gut": ScoreOrientation.SUPPORT,
}

DOMAIN_HEALTH_LABEL: Dict[str, str] = {
    "blood_sugar": "Glycemic Control",
    "blood_pressure": "Blood Pressure",
    "heart": "Cardiovascular Health",
    "metabolic_syndrome": "Metabolic Syndrome",
    "kidney": "Renal Health",
    "liver": "Hepatic Health",
    "bone": "Bone Health",
    "brain": "Cognitive & Mood Health",
    "inflammation": "Inflammatory & Joint Health",
    "arthritis": "Joint / Arthritis Symptom Burden",
    "cancer": "Cancer-Preventive Pattern",
    "weight": "Weight Management",
    "muscle": "Musculoskeletal Health & Healthy Aging",
    "gut": "Gut Health",
}

# Qualitative "Confidence" column from the source document -> numeric
# confidence (0-1) and a categorical evidence_strength label. Mapping is
# monotonic and consistent across every domain.
_CONFIDENCE_MAP: Dict[str, Tuple[float, str]] = {
    "High": (0.90, "Strong"),
    "Medium-high": (0.75, "Moderate-Strong"),
    "Medium": (0.60, "Moderate"),
    "Low-medium": (0.45, "Weak-Moderate"),
    "Low": (0.30, "Weak"),
    "N/A": (0.0, "Not Applicable"),
}


def _confidence_from_label(label: str) -> Tuple[float, str]:
    return _CONFIDENCE_MAP.get(label, (0.50, "Moderate"))


# =========================================================================
# RULE / INTERACTION / MODIFIER DATA STRUCTURES
# =========================================================================
#
# These are pure data containers. Nothing here computes anything - see
# EVALUATION FUNCTIONS below for the (rule-agnostic) logic that executes
# them.

@dataclass(frozen=True)
class Rule:
    rule_id: str
    domain: str                     # key into DOMAIN_ORIENTATION / DOMAIN_HEALTH_LABEL
    feature: str                    # canonical feature key (see FEATURE RESOLVERS)
    display_name: str               # human label as given in the source document
    coefficient: float              # exactly as written in the source, in the domain's own orientation
    curve: str                      # one of CurveType
    curve_params: Dict[str, float] = field(default_factory=dict)
    mechanism: str = ""
    pathway: str = ""
    organ: str = ""
    confidence_label: str = "Medium"   # source document's own High/Medium/.../N/A label
    citation: Optional[str] = None
    source: str = "Nutrica coefficient reference document"

    @property
    def confidence(self) -> float:
        return _confidence_from_label(self.confidence_label)[0]

    @property
    def evidence_strength(self) -> str:
        return _confidence_from_label(self.confidence_label)[1]

    @property
    def health_domain(self) -> str:
        return DOMAIN_HEALTH_LABEL.get(self.domain, self.domain)

    @property
    def effective_weight(self) -> float:
        return round(abs(self.coefficient) * self.confidence, 4)


@dataclass(frozen=True)
class Interaction:
    interaction_id: str
    domain: str
    features: Tuple[str, ...]        # the features whose co-occurrence this interaction reacts to
    rule_text: str                   # human description of the rule ("multiply sodium term by CKD factor", "+0.20", etc.)
    coefficient: Optional[float]     # None when the source gives a qualitative rule rather than a number
    mechanism: str = ""
    modifier_gate: Optional[str] = None  # population modifier key this interaction is gated behind, if any


@dataclass(frozen=True)
class PopulationModifier:
    modifier_id: str
    domain: str
    label: str                       # e.g. "Hypertension", "Older adults", "CKD"
    description: str
    affected_features: Tuple[str, ...] = ()
    multiplier: float = 1.0          # applied to affected rules' coefficients when this modifier is active
    enabled_by_default: bool = False  # ALWAYS False per spec - modifiers are opt-in only


# =========================================================================
# FEATURE RESOLVERS
# =========================================================================
#
# A resolver is a pure function (ingredient_or_food: dict) -> Optional[float]
# (or Optional[bool] for binary tags) that extracts or mechanically derives
# a value from an entity's ALREADY-COMPUTED "features" dict (the output of
# feature_engineering.build_features), and occasionally from the entity's
# own plain metadata (name/category - already present alongside "features"
# on the same dict, never re-fetched from anywhere external). Resolvers
# never call USDA, never estimate a genuinely missing nutrient, and always
# return None when the underlying data isn't there - consistent with
# feature_engineering.py's own "never invent" principle.
#
# Density-type resolvers use feature_engineering's own per-100kcal
# convention (see feature_engineering.safe_density_per_100kcal) for
# consistency, EXCEPT where energy is None or negligible (< 1 kcal), in
# which case a density is not a meaningful concept (dividing by ~0 kcal
# would blow up) and the resolver returns None rather than a degenerate
# value.

_ENERGY_EPSILON = 1.0  # kcal; below this, per-100kcal density isn't meaningful


def _features(entity: Dict[str, Any]) -> Dict[str, Any]:
    return entity.get("features") or {}


def _valid_number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _energy_kcal(entity: Dict[str, Any]) -> Optional[float]:
    return _valid_number(_features(entity).get("macronutrients", {}).get("energy_kcal"))


def _density(entity: Dict[str, Any], amount: Optional[float]) -> Optional[float]:
    """Return amount per 100 kcal, with strict validation."""
    valid_amount = _valid_number(amount)
    energy = _energy_kcal(entity)
    if valid_amount is None or energy is None or energy < _ENERGY_EPSILON:
        return None
    return round((valid_amount / energy) * 100.0, 6)


def _get(entity: Dict[str, Any], *path: str) -> Optional[Any]:
    node: Any = _features(entity)
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _text(entity: Dict[str, Any]) -> str:
    return " ".join(
        [str(entity.get("name") or ""), str(entity.get("canonical_name") or "")]
    ).strip().lower()


def _contains_keyword(text: str, keyword: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(keyword.lower())}(?!\w)", text.lower()) is not None


def _any_kw(text: str, keywords: Tuple[str, ...]) -> bool:
    return any(_contains_keyword(text, keyword) for keyword in keywords)


def _unavailable(entity: Dict[str, Any]) -> None:
    return None


# ---- Direct pulls from the current feature_engineering.py schema ----

def _resolve_fiber_density(e): return _get(e, "densities", "fiber_g_per_100kcal")
def _resolve_protein_density(e): return _get(e, "densities", "protein_g_per_100kcal")
def _resolve_carb_density(e): return _get(e, "densities", "carbohydrate_g_per_100kcal")
def _resolve_sugar_density(e): return _get(e, "densities", "sugars_g_per_100kcal")
def _resolve_energy_density(e): return _get(e, "densities", "energy_kcal_per_100g")
def _resolve_water_density(e): return _get(e, "densities", "water_g_per_100kcal")


def _resolve_sodium_density(e): return _density(e, _get(e, "minerals", "sodium_mg"))
def _resolve_potassium_density(e): return _density(e, _get(e, "minerals", "potassium_mg"))
def _resolve_magnesium_density(e): return _density(e, _get(e, "minerals", "magnesium_mg"))
def _resolve_calcium_density(e): return _density(e, _get(e, "minerals", "calcium_mg"))
def _resolve_phosphorus_density(e): return _density(e, _get(e, "minerals", "phosphorus_mg"))
def _resolve_iron_density(e): return _density(e, _get(e, "minerals", "iron_mg"))


def _resolve_saturated_fat_density(e): return _density(e, _get(e, "fat_profile", "saturated_fat_g"))
def _resolve_trans_fat_density(e): return _density(e, _get(e, "fat_profile", "trans_fat_g"))
def _resolve_omega3_density(e): return _density(e, _get(e, "fat_profile", "omega3_g"))
def _resolve_omega6_density(e): return _density(e, _get(e, "fat_profile", "omega6_g"))
def _resolve_cholesterol_density(e): return _density(e, _get(e, "fat_profile", "cholesterol_mg"))


def _resolve_vitamin_d_density(e): return _density(e, _get(e, "vitamins", "vitamin_d_ug"))
def _resolve_vitamin_k_density(e): return _density(e, _get(e, "vitamins", "vitamin_k_ug"))
def _resolve_choline_density(e): return _density(e, _get(e, "vitamins", "choline_mg"))


def _resolve_added_sugar_density(e): return _density(e, _get(e, "sugars", "added_sugar_g"))
def _resolve_fructose_density(e): return _density(e, _get(e, "sugars", "fructose_g"))


def _resolve_caffeine_density(e): return _density(e, _get(e, "bioactives", "caffeine_mg"))
def _resolve_alcohol_density(e): return _density(e, _get(e, "macronutrients", "alcohol_g"))


def _resolve_unsaturated_fat_quality(e): return _get(e, "ratios", "unsaturated_saturated_ratio")


def _resolve_whole_grain_tag(e): return _get(e, "food_matrix", "is_whole_grain")
def _resolve_refined_grain_tag(e): return _get(e, "food_matrix", "is_refined_grain")
def _resolve_legume_tag(e): return _get(e, "food_matrix", "is_legume")


def _resolve_nut_seed_tag(e):
    is_nut = _get(e, "food_matrix", "is_nut")
    is_seed = _get(e, "food_matrix", "is_seed")
    if is_nut is None and is_seed is None:
        return None
    return bool(is_nut) or bool(is_seed)


def _resolve_fruit_vegetable_tag(e):
    is_fruit = _get(e, "food_matrix", "is_fruit")
    is_vegetable = _get(e, "food_matrix", "is_vegetable")
    if is_fruit is None and is_vegetable is None:
        return None
    return bool(is_fruit) or bool(is_vegetable)


def _resolve_dairy_or_fortified_tag(e): return _get(e, "food_matrix", "is_dairy")
def _resolve_ultra_processed_tag(e): return _get(e, "food_matrix", "is_ultra_processed_food")
def _resolve_processed_food_tag(e): return _get(e, "food_matrix", "is_processed_food")
def _resolve_red_meat_tag(e): return _get(e, "food_matrix", "is_red_meat")
def _resolve_fried_food_tag(e): return _get(e, "processing", "is_fried")


def _resolve_processing_score(e):
    """0=explicitly unprocessed, 1=processed, 2=ultra-processed; unknown stays None."""
    processed = _get(e, "food_matrix", "is_processed_food")
    ultra = _get(e, "food_matrix", "is_ultra_processed_food")
    if ultra is True:
        return 2.0
    if processed is True:
        return 1.0
    if processed is False and ultra is False:
        return 0.0
    return None


_PROCESSED_MEAT_KEYWORDS = (
    "bacon", "sausage", "ham", "hot dog", "salami", "pepperoni",
    "deli meat", "cured meat", "smoked meat", "processed meat", "jerky",
    "frankfurter", "chorizo", "pastrami", "corned beef",
)


def _resolve_processed_meat_tag(e):
    is_red = _get(e, "food_matrix", "is_red_meat")
    is_white = _get(e, "food_matrix", "is_white_meat")
    if is_red is None and is_white is None:
        return None
    if not (is_red or is_white):
        return False
    return _any_kw(_text(e), _PROCESSED_MEAT_KEYWORDS)


_SODA_KEYWORDS = ("soda", "cola", "soft drink", "pop", "fizzy drink")


def _resolve_soda_cola_burden(e):
    if _any_kw(_text(e), _SODA_KEYWORDS):
        return True
    return _resolve_liquid_sugar_tag(e)


def _resolve_liquid_sugar_tag(e):
    is_beverage = _get(e, "food_matrix", "is_beverage")
    if is_beverage is None:
        return None
    if not is_beverage:
        return False
    sugars_g = _valid_number(_get(e, "macronutrients", "sugars_g"))
    if sugars_g is None:
        return None
    return sugars_g > 0


def _resolve_liquid_calories_tag(e):
    is_beverage = _get(e, "food_matrix", "is_beverage")
    if is_beverage is None:
        return None
    if not is_beverage:
        return False
    energy = _energy_kcal(e)
    if energy is None:
        return None
    return energy > 0


def _resolve_food_form_penalty(e):
    unit = str(e.get("unit") or "").strip().lower()
    is_refined = _get(e, "food_matrix", "is_refined_grain")
    if unit in {"ml", "milliliter", "milliliters", "millilitre", "millilitres"}:
        return True
    if is_refined is None:
        return None
    return bool(is_refined)


_B_VITAMIN_KEYS = (
    "thiamin_mg", "riboflavin_mg", "niacin_mg", "pantothenic_acid_mg",
    "vitamin_b6_mg", "folate_ug", "vitamin_b12_ug", "choline_mg",
)


def _resolve_b_vitamin_density_index(e):
    # This preserves the original model's simple average. Values retain
    # their source units, so the output is an engineering index, not a
    # chemically unit-homogeneous concentration.
    densities = []
    for key in _B_VITAMIN_KEYS:
        density = _density(e, _get(e, "vitamins", key))
        if density is not None:
            densities.append(density)
    if not densities:
        return None
    return round(sum(densities) / len(densities), 6)


def _resolve_protein_quality_leucine_proxy(e):
    leucine = _valid_number(_get(e, "amino_acids", "leucine_g"))
    protein = _valid_number(_get(e, "macronutrients", "protein_g"))
    if leucine is None or protein is None or protein <= 0:
        return None
    return round(leucine / protein, 6)


def _resolve_fat_quality_composite(e):
    return _resolve_unsaturated_fat_quality(e)


# The canonical feature-key -> resolver registry. Every "feature" value
# used by any Rule in the database below MUST have an entry here (this is
# asserted in load_rule_database()).
FEATURE_RESOLVERS: Dict[str, Callable[[Dict[str, Any]], Optional[Any]]] = {
    # Macronutrient / energy
    "fiber_density": _resolve_fiber_density,
    "protein_density": _resolve_protein_density,
    "carbohydrate_density": _resolve_carb_density,
    "total_sugar_density": _resolve_sugar_density,
    "added_sugar_density": _resolve_added_sugar_density,
    "fructose_density": _resolve_fructose_density,
    "energy_density": _resolve_energy_density,
    "water_density": _resolve_water_density,
    # Minerals
    "sodium_density": _resolve_sodium_density,
    "potassium_density": _resolve_potassium_density,
    "magnesium_density": _resolve_magnesium_density,
    "calcium_density": _resolve_calcium_density,
    "phosphorus_density": _resolve_phosphorus_density,
    "iron_density": _resolve_iron_density,
    # Fats
    "saturated_fat_density": _resolve_saturated_fat_density,
    "trans_fat_density": _resolve_trans_fat_density,
    "omega3_density": _resolve_omega3_density,
    "omega6_density": _resolve_omega6_density,
    "cholesterol_density": _resolve_cholesterol_density,
    "unsaturated_fat_quality": _resolve_unsaturated_fat_quality,
    "fat_quality_composite": _resolve_fat_quality_composite,
    # Vitamins
    "vitamin_d_density": _resolve_vitamin_d_density,
    "vitamin_k_density": _resolve_vitamin_k_density,
    "choline_density": _resolve_choline_density,
    "b_vitamin_density_index": _resolve_b_vitamin_density_index,
    # Bioactives / other
    "caffeine_density": _resolve_caffeine_density,
    "alcohol_density": _resolve_alcohol_density,
    "protein_quality_leucine_proxy": _resolve_protein_quality_leucine_proxy,
    # Boolean tags
    "whole_grain_tag": _resolve_whole_grain_tag,
    "refined_grain_tag": _resolve_refined_grain_tag,
    "legume_tag": _resolve_legume_tag,
    "nut_seed_tag": _resolve_nut_seed_tag,
    "fruit_vegetable_tag": _resolve_fruit_vegetable_tag,
    "dairy_or_fortified_tag": _resolve_dairy_or_fortified_tag,
    "ultra_processed_tag": _resolve_ultra_processed_tag,
    "processed_food_tag": _resolve_processed_food_tag,
    "processed_meat_tag": _resolve_processed_meat_tag,
    "red_meat_tag": _resolve_red_meat_tag,
    "fried_food_tag": _resolve_fried_food_tag,
    "liquid_sugar_tag": _resolve_liquid_sugar_tag,
    "liquid_calories_tag": _resolve_liquid_calories_tag,
    "soda_cola_burden": _resolve_soda_cola_burden,
    "food_form_penalty": _resolve_food_form_penalty,
    "processing_score": _resolve_processing_score,
    # Person-level / day-level - genuinely unavailable from a single
    # ingredient's engineered features. See module docstring.
    "glycemic_load": _unavailable,
    "glycemic_index_proxy": _unavailable,
    "central_adiposity_proxy": _unavailable,
    "triglyceride_burden": _unavailable,
    "hdl_burden": _unavailable,
    "blood_pressure_biomarker": _unavailable,
    "albuminuria_proxy": _unavailable,
    "egfr_burden": _unavailable,
    "insulin_resistance_biomarker": _unavailable,
    "energy_adequacy": _unavailable,
    "resistance_training_context": _unavailable,
    "meal_regularity": _unavailable,
    "physical_activity_proxy": _unavailable,
}


def resolve_feature_value(feature_key: str, entity: Dict[str, Any]) -> Optional[Any]:
    resolver = FEATURE_RESOLVERS.get(feature_key)
    if resolver is None:
        logger.warning("No resolver registered for feature key %r", feature_key)
        return None
    return resolver(entity)


# =========================================================================
# THRESHOLD / CURVE EVALUATION
# =========================================================================
#
# evaluate_threshold() turns an observed feature_value into a "realized
# magnitude" in [0, ~1.3] representing how much of the rule's maximal
# effect is being expressed at this value - NOT a final score. A magnitude
# of 0 means the rule doesn't fire at all (no evidence object is emitted
# for it); a magnitude near 1 means the effect is close to fully realized
# given the curve's own saturation/threshold parameters.
#
# curve_params keys used below (all optional per curve, sensible defaults
# applied when the source document gives a shape qualitatively but not an
# exact numeric cutoff - this is flagged wherever it applies):
#   threshold          - the value at/above which a THRESHOLD/PIECEWISE
#                         curve engages
#   low_threshold       - U_SHAPED: below this, the penalty applies
#   high_threshold       - U_SHAPED: at/above this, the benefit applies (saturating)
#   saturation_point    - SATURATING: value at which effect reaches ~95% of max
#   steepness_above     - PIECEWISE_LINEAR: slope multiplier once above `threshold`
#   reference           - INVERSE: a "healthy reference" value

def evaluate_threshold(rule: Rule, feature_value: Optional[Any]) -> float:
    """
    Apply `rule`'s curve to `feature_value`. Returns a realized-magnitude
    float in roughly [0, 1.3] (saturating curves can slightly exceed 1 for
    values far beyond the saturation point, by design, to distinguish
    "very high" from "just past the knee" - PIECEWISE_LINEAR similarly can
    exceed 1). Returns 0.0 if feature_value is None (nothing to evaluate)
    or the rule's condition simply isn't met.
    """
    if feature_value is None:
        return 0.0

    curve = rule.curve
    params = rule.curve_params

    if curve == CurveType.BINARY:
        return 1.0 if bool(feature_value) else 0.0

    if curve == CurveType.BINARY_INTENSITY:
        if not bool(feature_value):
            return 0.0
        # feature_value being a bool carries no intensity information by
        # itself - BINARY_INTENSITY rules are always paired with a
        # companion density/amount feature evaluated via process_feature's
        # `intensity_feature` on the Rule; if none is configured, treat as
        # plain binary.
        return 1.0

    if curve == CurveType.THRESHOLD:
        threshold = params.get("threshold", 0.0)
        try:
            return 1.0 if float(feature_value) > threshold else 0.0
        except (TypeError, ValueError):
            return 0.0

    if curve == CurveType.LINEAR:
        scale = params.get("scale", 1.0)
        cap = params.get("cap", 1.5)
        try:
            magnitude = float(feature_value) * scale
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(magnitude, cap))

    if curve == CurveType.PIECEWISE_LINEAR:
        threshold = params.get("threshold", 0.0)
        base_scale = params.get("scale", 1.0)
        steepness_above = params.get("steepness_above", 2.0)
        cap = params.get("cap", 1.5)
        try:
            v = float(feature_value)
        except (TypeError, ValueError):
            return 0.0
        if v <= threshold:
            magnitude = v * base_scale
        else:
            magnitude = threshold * base_scale + (v - threshold) * base_scale * steepness_above
        return max(0.0, min(magnitude, cap))

    if curve == CurveType.SATURATING:
        saturation_point = params.get("saturation_point", 1.0)
        try:
            v = max(0.0, float(feature_value))
        except (TypeError, ValueError):
            return 0.0
        if saturation_point <= 0:
            return 0.0
        # 1 - e^(-3x/saturation_point) reaches ~95% of max at x = saturation_point.
        return round(1.0 - math.exp(-3.0 * v / saturation_point), 6)

    if curve == CurveType.U_SHAPED:
        low_threshold = params.get("low_threshold", 0.0)
        high_threshold = params.get("high_threshold", low_threshold)
        saturation_point = params.get("saturation_point", max(high_threshold, low_threshold * 2, 1.0))
        try:
            v = float(feature_value)
        except (TypeError, ValueError):
            return 0.0
        if v < low_threshold:
            # Below the low threshold: penalty magnitude grows the further
            # below it the value is (capped at 1).
            span = max(low_threshold, 1e-9)
            return max(0.0, min((low_threshold - v) / span, 1.0))
        if v >= high_threshold:
            # At/above the adequate threshold: saturating benefit.
            excess = v - high_threshold
            if saturation_point <= 0:
                return 1.0
            return round(1.0 - math.exp(-3.0 * excess / saturation_point), 6)
        return 0.0  # in the "adequate but not yet beneficial" middle zone

    if curve == CurveType.INVERSE:
        reference = params.get("reference", 1.0)
        try:
            v = float(feature_value)
        except (TypeError, ValueError):
            return 0.0
        if v <= 0 or reference <= 0:
            return 0.0
        return max(0.0, min(1.0 - (v / reference), 1.0))

    logger.warning("Unknown curve type %r on rule %s", curve, rule.rule_id)
    return 0.0


# =========================================================================
# EVIDENCE CONSTRUCTION
# =========================================================================

# confidence (0-1) -> confidence_multiplier. A straight pass-through would
# let "Low" confidence (0.30) crush effective_weight by 70% and "N/A"
# (0.0) zero it out entirely - too punishing, since even weakly-supported
# coefficients in the source document are still real, documented
# mechanisms, not guesses. This engine instead floors the multiplier at
# 0.4x and tops it out at 0.85x for "High" confidence (0.90), since no
# single nutrient-level coefficient here is asserted with total
# certainty. The source document never specifies a numeric
# confidence-to-multiplier formula, so this linear floor/span mapping is
# a deliberate, documented engineering choice - easy to recalibrate in
# one place if a different curve is wanted later.
_CONFIDENCE_MULTIPLIER_FLOOR = 0.4
_CONFIDENCE_MULTIPLIER_SPAN = 0.5


def _confidence_multiplier(confidence: float) -> float:
    return round(_CONFIDENCE_MULTIPLIER_FLOOR + _CONFIDENCE_MULTIPLIER_SPAN * confidence, 4)


# Fallback keyword buckets for Interactions whose source rule is
# qualitative only (coefficient is None - "stronger penalty", "extra
# protective bonus") rather than an explicit number. Interaction rows
# WITH an explicit numeric coefficient never use these.
_INTERACTION_DAMPEN_KEYWORDS = ("penalty", "worse", "negative", "unfavorable")
_INTERACTION_AMPLIFY_KEYWORDS = ("bonus", "protective", "benefit", "synerg", "positive", "amplify")
_QUALITATIVE_INTERACTION_AMPLIFY = 1.10
_QUALITATIVE_INTERACTION_DAMPEN = 0.90


def _interaction_contribution(interaction_record: Dict[str, Any]) -> float:
    """Turns one interaction record (as produced by evaluate_interactions)
    into a single multiplicative adjustment. An explicit numeric
    coefficient (most Blood Sugar/Blood Pressure/Heart interactions carry
    one) is applied directly as 1 + coefficient - e.g. a documented
    "-0.15" interaction becomes a 0.85x multiplier, clamped to a sane
    [0.5, 1.5] range. Purely qualitative interactions (coefficient is
    None) fall back to a fixed, documented nudge based on simple keyword
    direction-detection in their rule_text, since the source gives a
    direction but never a number for these rows."""
    coefficient = interaction_record.get("coefficient")
    if coefficient is not None:
        return max(0.5, min(1.0 + coefficient, 1.5))

    text = (interaction_record.get("rule_text") or "").lower()
    if any(kw in text for kw in _INTERACTION_DAMPEN_KEYWORDS):
        return _QUALITATIVE_INTERACTION_DAMPEN
    if any(kw in text for kw in _INTERACTION_AMPLIFY_KEYWORDS):
        return _QUALITATIVE_INTERACTION_AMPLIFY
    return 1.0


def _smart_title_case(text: str) -> str:
    """Title-cases a rule's display_name into a presentation-ready
    rule_name, without mangling acronyms - a word that's already
    all-uppercase (e.g. "CKD", "UPF", "B12") or contains a digit is
    passed through untouched rather than lowercased by naive
    str.title(); hyphenated/slashed compounds ("b-vitamin",
    "fruit/vegetable") get each segment capitalized individually."""

    def _cap_segment(seg: str) -> str:
        if not seg or seg.isupper() or any(ch.isdigit() for ch in seg):
            return seg
        return seg[0].upper() + seg[1:]

    out_words = []
    for word in text.split(" "):
        if not word or word.isupper() or any(ch.isdigit() for ch in word):
            out_words.append(word)
        elif "-" in word:
            out_words.append("-".join(_cap_segment(s) for s in word.split("-")))
        elif "/" in word:
            out_words.append("/".join(_cap_segment(s) for s in word.split("/")))
        else:
            out_words.append(_cap_segment(word))
    return " ".join(out_words)


# direction (already normalized to protective/adverse regardless of the
# domain's own RISK vs SUPPORT scoring convention - see build_evidence)
# -> evidence_type label.
_EVIDENCE_TYPE_BY_DIRECTION = {
    "positive": "protective",
    "negative": "risk",
    "neutral": "neutral",
}


def build_evidence(
    rule: Rule,
    feature_value: Any,
    magnitude: float,
    interaction_records: Sequence[Dict[str, Any]] = (),
) -> Dict[str, Any]:
    """
    Construct one evidence object for `rule`, given the observed
    `feature_value`, its curve-evaluated activation `magnitude` (see
    evaluate_threshold), and whichever interaction records (from
    evaluate_interactions) name this rule's feature among their own
    `features`, within this same domain, and actually apply to this
    entity.

    direction is normalized to "positive" (protective/beneficial) or
    "negative" (adverse) regardless of the domain's own RISK vs SUPPORT
    scoring convention (see DOMAIN_ORIENTATION); evidence_type mirrors
    that same normalization as "risk" / "protective" / "neutral".

    Every numeric field follows one calculation chain, in this order
    (also the field order below):

        coefficient -> base_weight -> curve_multiplier -> interaction_multiplier
        -> confidence_multiplier -> effective_weight -> raw_effect

    curve_multiplier IS `magnitude` - the curve's own activation at the
    observed value (see evaluate_threshold), so effective_weight is
    genuinely value-dependent, not a fixed rule-level constant.
    raw_effect is the final, fully-realized contribution: effective_weight
    scaled once more by the raw feature_value itself. For example:
    coefficient=0.80 -> base_weight=0.80; curve_multiplier=0.75;
    interaction_multiplier=0.90; confidence_multiplier=0.95 ->
    effective_weight = 0.80*0.75*0.90*0.95 = 0.513; at feature_value=0.84,
    raw_effect = 0.513*0.84 = 0.431.

    When no interactions apply to this feature on this entity,
    interaction_multiplier is exactly 1.0 and applied_interactions is
    exactly [] - effective_weight never carries a hidden interaction
    adjustment that isn't also listed in applied_interactions.
    """
    orientation = DOMAIN_ORIENTATION.get(rule.domain, ScoreOrientation.SUPPORT)
    coefficient_is_beneficial = (rule.coefficient < 0) if orientation == ScoreOrientation.RISK else (rule.coefficient > 0)
    direction = "positive" if coefficient_is_beneficial else ("negative" if rule.coefficient != 0 else "neutral")
    evidence_type = _EVIDENCE_TYPE_BY_DIRECTION[direction]

    relevant_interactions = [
        rec for rec in interaction_records
        if rule.feature in rec.get("features", ()) and rec.get("domain") == rule.domain
    ]
    interaction_multiplier = 1.0
    for rec in relevant_interactions:
        interaction_multiplier *= _interaction_contribution(rec)
    interaction_multiplier = round(interaction_multiplier, 4)

    base_weight = round(abs(rule.coefficient), 4)
    curve_multiplier = round(magnitude, 6)
    confidence_multiplier = _confidence_multiplier(rule.confidence)
    effective_weight = round(base_weight * curve_multiplier * interaction_multiplier * confidence_multiplier, 4)

    # The curve multiplier already encodes the observed feature value.
    # Multiplying by the raw value again would double-count it and make
    # scores depend on arbitrary units (for example mg versus g).
    if direction == "positive":
        raw_effect = round(effective_weight, 6)
    elif direction == "negative":
        raw_effect = round(-effective_weight, 6)
    else:
        raw_effect = 0.0

    return {
        "rule_id": rule.rule_id,
        "rule_name": _smart_title_case(rule.display_name),
        "domain": rule.domain,
        "health_domain": rule.health_domain,
        "feature": rule.feature,
        "feature_value": feature_value,
        "direction": direction,
        "evidence_type": evidence_type,
        "mechanism": rule.mechanism,
        "pathway": rule.pathway,
        "organ": rule.organ,
        "coefficient": rule.coefficient,
        "base_weight": base_weight,
        "curve_multiplier": curve_multiplier,
        "interaction_multiplier": interaction_multiplier,
        "confidence_multiplier": confidence_multiplier,
        "effective_weight": effective_weight,
        "raw_effect": raw_effect,
        "confidence": rule.confidence,
        "evidence_strength": rule.evidence_strength,
        "applied_interactions": [rec["interaction_id"] for rec in relevant_interactions],
        "citation": rule.citation,
        "source": rule.source,
    }


# =========================================================================
# DOMAIN RULE DATABASES
# =========================================================================
#
# Twelve domains, each extracted from the coefficient reference document's
# own coefficient table + interaction table + threshold policy +
# population-modifier section. Coefficients are exactly as written in the
# source, in that domain's own RISK/SUPPORT orientation (see
# DOMAIN_ORIENTATION) - build_evidence() normalizes direction, not these
# raw values.
#
# curve_params are populated with the source's qualitative shape ("binary
# penalty", "saturating benefit", "piecewise linear, steeper above
# moderate") mapped onto a CurveType + reasonable numeric parameters.
# Where the source doesn't give an exact numeric cutoff (it rarely does -
# it speaks in qualitative terms like "moderate GL" or "any meaningful
# amount"), the chosen numeric default is an implementation judgment call,
# clearly distinct from the coefficient/confidence/mechanism fields, which
# ARE extracted verbatim.

# -------------------------------------------------------------------
# 1. BLOOD SUGAR (glycemic burden) - RISK oriented
# -------------------------------------------------------------------

BLOOD_SUGAR_RULES: List[Rule] = [
    Rule(
        rule_id="bs_glycemic_load", domain="blood_sugar", feature="glycemic_load",
        display_name="Glycemic load estimate", coefficient=0.60,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 15.0, "scale": 0.05, "steepness_above": 2.0, "cap": 1.5},
        mechanism="Rapid carbohydrate absorption raises postprandial glucose and insulin demand",
        pathway="Postprandial glycemic response", organ="Pancreas / systemic glucose-insulin axis",
        confidence_label="High",
    ),
    Rule(
        rule_id="bs_added_sugar", domain="blood_sugar", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=0.55,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 2.0, "scale": 0.2, "steepness_above": 1.5, "cap": 1.5},
        mechanism="Free/added sugars are rapidly absorbed, raising glucose and insulin demand",
        pathway="Postprandial glycemic response", organ="Pancreas",
        confidence_label="High",
    ),
    Rule(
        rule_id="bs_total_sugar", domain="blood_sugar", feature="total_sugar_density",
        display_name="Total sugar density", coefficient=0.20,
        curve=CurveType.LINEAR, curve_params={"scale": 0.1, "cap": 1.5},
        mechanism="Non-specific sugar load contributes modestly to glycemic burden",
        pathway="Postprandial glycemic response", organ="Pancreas",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bs_fiber", domain="blood_sugar", feature="fiber_density",
        display_name="Fiber density", coefficient=-0.50,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Fiber slows gastric emptying and carbohydrate absorption, blunting the glucose/insulin response",
        pathway="Carbohydrate absorption kinetics", organ="Small intestine / pancreas",
        confidence_label="High",
    ),
    Rule(
        rule_id="bs_whole_grain", domain="blood_sugar", feature="whole_grain_tag",
        display_name="Whole grain tag", coefficient=-0.30,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Intact bran and germ slow starch digestion and improve insulin sensitivity",
        pathway="Carbohydrate absorption kinetics", organ="Small intestine",
        confidence_label="High",
    ),
    Rule(
        rule_id="bs_refined_grain", domain="blood_sugar", feature="refined_grain_tag",
        display_name="Refined grain tag", coefficient=0.35,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Removal of bran/germ increases starch digestibility and glycemic response",
        pathway="Carbohydrate absorption kinetics", organ="Small intestine",
        confidence_label="High",
    ),
    Rule(
        rule_id="bs_liquid_sugar", domain="blood_sugar", feature="liquid_sugar_tag",
        display_name="Liquid sugar tag", coefficient=0.65,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Liquid sugars bypass satiety signaling and are absorbed rapidly, producing a sharp glycemic spike",
        pathway="Postprandial glycemic response", organ="Pancreas",
        confidence_label="High",
    ),
    Rule(
        rule_id="bs_carbohydrate_density", domain="blood_sugar", feature="carbohydrate_density",
        display_name="Carbohydrate density", coefficient=0.25,
        curve=CurveType.LINEAR, curve_params={"scale": 0.067, "cap": 1.5},
        mechanism="Higher total carbohydrate load increases glucose delivery per serving",
        pathway="Postprandial glycemic response", organ="Pancreas",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="bs_glycemic_index", domain="blood_sugar", feature="glycemic_index_proxy",
        display_name="Glycemic index proxy", coefficient=0.25,
        curve=CurveType.LINEAR, curve_params={"scale": 1.0, "cap": 1.5},
        mechanism="Higher-GI carbohydrate sources produce a faster, sharper glucose rise",
        pathway="Postprandial glycemic response", organ="Pancreas",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="bs_protein_density", domain="blood_sugar", feature="protein_density",
        display_name="Protein density", coefficient=-0.15,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 6.0},
        mechanism="Protein co-ingestion slows gastric emptying and stimulates insulin independent of glucose, blunting glycemic excursions",
        pathway="Gastric emptying / incretin response", organ="Stomach / pancreas",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bs_fat_quality", domain="blood_sugar", feature="fat_quality_composite",
        display_name="Favorable fat-quality composite", coefficient=-0.10,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Unsaturated fat replacing saturated fat modestly improves insulin sensitivity and slows gastric emptying",
        pathway="Gastric emptying / insulin sensitivity", organ="Stomach / adipose tissue",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bs_processing_score", domain="blood_sugar", feature="processing_score",
        display_name="Processing score", coefficient=0.20,
        curve=CurveType.LINEAR, curve_params={"scale": 0.5, "cap": 1.5},
        mechanism="Processing typically strips fiber and concentrates refined carbohydrate, acting as a proxy for poor carbohydrate quality",
        pathway="Carbohydrate quality proxy", organ="Small intestine",
        confidence_label="Medium-high",
    ),
]

BLOOD_SUGAR_INTERACTIONS: List[Interaction] = [
    Interaction("bs_int_gl_fiber", "blood_sugar", ("glycemic_load", "fiber_density"),
                "GL x Fiber: -0.20", -0.20, "Fiber buffers glycemic impact"),
    Interaction("bs_int_gl_protein", "blood_sugar", ("glycemic_load", "protein_density"),
                "GL x Protein: -0.10", -0.10, "Protein blunts postprandial glucose"),
    Interaction("bs_int_gl_liquid_sugar", "blood_sugar", ("glycemic_load", "liquid_sugar_tag"),
                "GL x Liquid sugar: +0.25", 0.25, "Rapid absorption increases burden"),
    Interaction("bs_int_added_sugar_liquid", "blood_sugar", ("added_sugar_density", "liquid_sugar_tag"),
                "Added sugar x Liquid sugar: +0.30", 0.30, "Beverage sugar is particularly adverse"),
    Interaction("bs_int_whole_grain_fiber", "blood_sugar", ("whole_grain_tag", "fiber_density"),
                "Whole grain x Fiber: -0.15", -0.15, "Synergistic benefit"),
    Interaction("bs_int_refined_low_fiber", "blood_sugar", ("refined_grain_tag", "fiber_density"),
                "Refined grain x Low fiber: +0.20", 0.20, "Worse-than-additive risk pattern"),
    Interaction("bs_int_processing_added_sugar", "blood_sugar", ("processing_score", "added_sugar_density"),
                "Processing x Added sugar: +0.15", 0.15, "Common high-burden formulation"),
    Interaction("bs_int_carb_fiber", "blood_sugar", ("carbohydrate_density", "fiber_density"),
                "Carbohydrate x Fiber: -0.10", -0.10, "Slower absorption"),
]
# -------------------------------------------------------------------
# 2. BLOOD PRESSURE - RISK oriented
# -------------------------------------------------------------------

BLOOD_PRESSURE_RULES: List[Rule] = [
    Rule(
        rule_id="bp_sodium", domain="blood_pressure", feature="sodium_density",
        display_name="Sodium density", coefficient=1.00,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 100.0, "scale": 0.005, "steepness_above": 2.5, "cap": 1.5},
        mechanism="Excess sodium promotes fluid retention and raises vascular resistance",
        pathway="Renin-angiotensin-aldosterone / fluid balance", organ="Blood vessels / kidneys",
        confidence_label="High",
    ),
    Rule(
        rule_id="bp_potassium", domain="blood_pressure", feature="potassium_density",
        display_name="Potassium density", coefficient=-0.80,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 200.0},
        mechanism="Potassium promotes renal sodium excretion and vascular smooth-muscle relaxation, counterbalancing sodium's pressor effect",
        pathway="Renal sodium handling / vascular tone", organ="Kidneys / blood vessels",
        confidence_label="High",
    ),
    Rule(
        rule_id="bp_fiber", domain="blood_pressure", feature="fiber_density",
        display_name="Fiber density", coefficient=-0.35,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Fiber supports better overall cardiometabolic and vascular patterns",
        pathway="Cardiometabolic dietary pattern", organ="Blood vessels",
        confidence_label="High",
    ),
    Rule(
        rule_id="bp_trans_fat", domain="blood_pressure", feature="trans_fat_density",
        display_name="Trans fat", coefficient=0.90,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.05},
        mechanism="Trans fats impair endothelial function and worsen the vascular lipid profile",
        pathway="Endothelial function / lipid profile", organ="Blood vessel endothelium",
        confidence_label="High",
    ),
    Rule(
        rule_id="bp_saturated_fat", domain="blood_pressure", feature="saturated_fat_density",
        display_name="Saturated fat", coefficient=0.30,
        curve=CurveType.LINEAR, curve_params={"scale": 0.05, "cap": 1.5},
        mechanism="Saturated fat contributes an unfavorable cardiovascular lipid pattern",
        pathway="Lipid profile / vascular health", organ="Blood vessels",
        confidence_label="High",
    ),
    Rule(
        rule_id="bp_ultra_processed", domain="blood_pressure", feature="ultra_processed_tag",
        display_name="Ultra-processed indicator", coefficient=0.35,
        curve=CurveType.BINARY_INTENSITY, curve_params={},
        mechanism="Ultra-processed foods often co-track with high sodium, poor fat quality, and low fiber",
        pathway="Sodium / fat-quality / fiber co-pattern", organ="Blood vessels / kidneys",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="bp_processed_meat", domain="blood_pressure", feature="processed_meat_tag",
        display_name="Processed meat tag", coefficient=0.45,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Processed meats carry a consistent high-risk cardiometabolic dietary pattern (sodium, nitrates, saturated fat)",
        pathway="Sodium / vascular burden", organ="Blood vessels",
        confidence_label="High",
    ),
    Rule(
        rule_id="bp_whole_grain", domain="blood_pressure", feature="whole_grain_tag",
        display_name="Whole grain tag", coefficient=-0.25,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Whole grains mark a favorable overall dietary pattern associated with better BP control",
        pathway="Cardiometabolic dietary pattern", organ="Blood vessels",
        confidence_label="High",
    ),
    Rule(
        rule_id="bp_added_sugar", domain="blood_pressure", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=0.15,
        curve=CurveType.LINEAR, curve_params={"scale": 0.15, "cap": 1.0},
        mechanism="Added sugar contributes indirect BP burden through adiposity and metabolic effects",
        pathway="Adiposity / metabolic burden", organ="Adipose tissue / blood vessels",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bp_energy_density", domain="blood_pressure", feature="energy_density",
        display_name="Energy density", coefficient=0.10,
        curve=CurveType.LINEAR, curve_params={"scale": 0.002, "cap": 1.0},
        mechanism="Higher energy density contributes indirect BP burden through weight gain and overeating",
        pathway="Weight regulation", organ="Adipose tissue",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bp_magnesium", domain="blood_pressure", feature="magnesium_density",
        display_name="Magnesium density", coefficient=-0.20,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 15.0},
        mechanism="Magnesium supports vascular smooth-muscle tone and relaxation",
        pathway="Vascular tone", organ="Blood vessels",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="bp_omega3", domain="blood_pressure", feature="omega3_density",
        display_name="Omega-3 density", coefficient=-0.15,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 0.3},
        mechanism="Omega-3 fatty acids provide a small vascular and anti-inflammatory benefit",
        pathway="Vascular / inflammatory tone", organ="Blood vessels",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bp_food_form", domain="blood_pressure", feature="food_form_penalty",
        display_name="Adverse food form (liquid/refined)", coefficient=0.10,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Liquid and refined food forms have weaker satiety signaling, an indirect quality effect",
        pathway="Satiety signaling", organ="Gastrointestinal tract",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bp_calcium", domain="blood_pressure", feature="calcium_density",
        display_name="Calcium density", coefficient=-0.10,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 80.0},
        mechanism="Calcium plays a secondary supportive role in vascular and BP regulation",
        pathway="Vascular tone", organ="Blood vessels",
        confidence_label="Medium",
    ),
]

BLOOD_PRESSURE_INTERACTIONS: List[Interaction] = [
    Interaction("bp_int_sodium_potassium", "blood_pressure", ("sodium_density", "potassium_density"),
                "Sodium x Potassium: +0.25 x (Na/K ratio)", 0.25, "High sodium-to-potassium ratio worsens BP burden"),
    Interaction("bp_int_sodium_ckd", "blood_pressure", ("sodium_density",),
                "Sodium x CKD: multiply sodium term by a CKD factor", None,
                "Sodium sensitivity rises in CKD", modifier_gate="ckd"),
    Interaction("bp_int_sodium_hypertension", "blood_pressure", ("sodium_density",),
                "Sodium x Hypertension: multiply sodium term by a hypertension factor", None,
                "Sodium sensitivity rises in hypertension", modifier_gate="hypertension"),
    Interaction("bp_int_sodium_upf", "blood_pressure", ("sodium_density", "ultra_processed_tag"),
                "Sodium x Ultra-processed: +0.20", 0.20, "UPF often carries hidden sodium burden"),
    Interaction("bp_int_fiber_sodium", "blood_pressure", ("fiber_density", "sodium_density"),
                "Fiber x Sodium: -0.10", -0.10, "Better overall dietary quality partially buffers risk"),
    Interaction("bp_int_potassium_magnesium", "blood_pressure", ("potassium_density", "magnesium_density"),
                "Potassium x Magnesium: -0.05", -0.05, "Small synergistic vascular benefit"),
    Interaction("bp_int_transfat_satfat", "blood_pressure", ("trans_fat_density", "saturated_fat_density"),
                "Trans fat x Saturated fat: +0.15", 0.15, "Combined lipid-vascular burden"),
    Interaction("bp_int_procmeat_sodium", "blood_pressure", ("processed_meat_tag", "sodium_density"),
                "Processed meat x Sodium: +0.20", 0.20, "Common high-burden combination"),
    Interaction("bp_int_wholegrain_fiber", "blood_pressure", ("whole_grain_tag", "fiber_density"),
                "Whole grain x Fiber: -0.10", -0.10, "Synergistic favorable pattern"),
    Interaction("bp_int_addedsugar_upf", "blood_pressure", ("added_sugar_density", "ultra_processed_tag"),
                "Added sugar x Ultra-processed: +0.10", 0.10, "Worse cardiometabolic pattern"),
]


# -------------------------------------------------------------------
# 3. HEART - SUPPORT oriented
# -------------------------------------------------------------------

HEART_RULES: List[Rule] = [
    Rule(
        rule_id="heart_fiber", domain="heart", feature="fiber_density",
        display_name="Fiber density", coefficient=0.85,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Fiber binds bile acids to lower LDL and supports glycemic and cardiometabolic health",
        pathway="Lipid / glycemic regulation", organ="Liver / blood vessels",
        confidence_label="High",
    ),
    Rule(
        rule_id="heart_unsaturated_fat", domain="heart", feature="unsaturated_fat_quality",
        display_name="Unsaturated fat quality", coefficient=0.80,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Replacing saturated fat with unsaturated fat improves the LDL/HDL lipid profile",
        pathway="Lipid profile / substitution effect", organ="Blood vessels",
        confidence_label="High",
    ),
    Rule(
        rule_id="heart_omega3", domain="heart", feature="omega3_density",
        display_name="Omega-3 density", coefficient=0.55,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 0.3},
        mechanism="Omega-3 fatty acids lower triglycerides and support overall heart-pattern quality",
        pathway="Triglyceride metabolism / anti-inflammatory tone", organ="Liver / blood vessels",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="heart_sodium", domain="heart", feature="sodium_density",
        display_name="Sodium burden", coefficient=-0.80,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 100.0},
        mechanism="Sodium is one of the strongest dietary drivers of blood pressure",
        pathway="Fluid balance / vascular resistance", organ="Blood vessels / kidneys",
        confidence_label="High",
    ),
    Rule(
        rule_id="heart_ultra_processed", domain="heart", feature="ultra_processed_tag",
        display_name="Ultra-processed indicator", coefficient=-0.65,
        curve=CurveType.BINARY_INTENSITY, curve_params={},
        mechanism="Ultra-processed foods typically co-track with high sodium, added sugar, poor fat quality, and low fiber",
        pathway="Sodium / sugar / fat-quality co-pattern", organ="Blood vessels",
        confidence_label="High",
    ),
    Rule(
        rule_id="heart_added_sugar", domain="heart", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=-0.45,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 2.0, "scale": 0.2, "steepness_above": 1.5, "cap": 1.5},
        mechanism="Added sugar worsens triglycerides, weight, and metabolic risk",
        pathway="Triglyceride metabolism / adiposity", organ="Liver / adipose tissue",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="heart_saturated_fat", domain="heart", feature="saturated_fat_density",
        display_name="Saturated fat", coefficient=-0.50,
        curve=CurveType.LINEAR, curve_params={"scale": 0.05, "cap": 1.5},
        mechanism="Saturated fat is important chiefly when it displaces unsaturated fat in the diet",
        pathway="Lipid profile / substitution effect", organ="Blood vessels",
        confidence_label="High",
    ),
    Rule(
        rule_id="heart_trans_fat", domain="heart", feature="trans_fat_density",
        display_name="Trans fat", coefficient=-0.90,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.05},
        mechanism="Trans fat has a major adverse effect on lipid profile and vascular function",
        pathway="Lipid profile / endothelial function", organ="Blood vessel endothelium",
        confidence_label="High",
    ),
    Rule(
        rule_id="heart_potassium", domain="heart", feature="potassium_density",
        display_name="Potassium-rich foods", coefficient=0.40,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 200.0},
        mechanism="Potassium supports blood-pressure control when overall dietary pattern is adequate",
        pathway="Renal sodium handling / vascular tone", organ="Kidneys / blood vessels",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="heart_whole_grain", domain="heart", feature="whole_grain_tag",
        display_name="Whole grain tag", coefficient=0.35,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Whole grains benefit lipids, glycemia, and overall dietary pattern quality",
        pathway="Lipid / glycemic regulation", organ="Blood vessels",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="heart_legume", domain="heart", feature="legume_tag",
        display_name="Legume tag", coefficient=0.30,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Legumes provide fiber and potassium with a favorable cardiometabolic effect",
        pathway="Lipid / glycemic regulation", organ="Blood vessels",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="heart_fruit_vegetable", domain="heart", feature="fruit_vegetable_tag",
        display_name="Fruit / vegetable tag", coefficient=0.30,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Fruits and vegetables supply micronutrients and fiber that support blood pressure",
        pathway="Micronutrient / fiber support", organ="Blood vessels",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="heart_nut_seed", domain="heart", feature="nut_seed_tag",
        display_name="Nut / seed tag", coefficient=0.25,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Nuts and seeds carry a favorable fat profile that supports cardiometabolic health",
        pathway="Lipid profile", organ="Blood vessels",
        confidence_label="Low-medium",
    ),
    Rule(
        rule_id="heart_alcohol", domain="heart", feature="alcohol_density",
        display_name="Alcohol burden", coefficient=-0.30,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.5},
        mechanism="Alcohol is particularly relevant to blood pressure and triglyceride elevation",
        pathway="Blood pressure / triglyceride metabolism", organ="Blood vessels / liver",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="heart_energy_density", domain="heart", feature="energy_density",
        display_name="Energy density", coefficient=-0.25,
        curve=CurveType.LINEAR, curve_params={"scale": 0.002, "cap": 1.0},
        mechanism="High energy density promotes excess weight and cardiometabolic strain",
        pathway="Weight regulation", organ="Adipose tissue",
        confidence_label="Low-medium",
    ),
    Rule(
        rule_id="heart_refined_grain", domain="heart", feature="refined_grain_tag",
        display_name="Refined grain burden", coefficient=-0.20,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Refined grains carry lower fiber and a poorer metabolic impact than whole grains",
        pathway="Lipid / glycemic regulation", organ="Blood vessels",
        confidence_label="Low-medium",
    ),
]

HEART_INTERACTIONS: List[Interaction] = [
    Interaction("heart_int_sodium_potassium", "heart", ("sodium_density", "potassium_density"),
                "Sodium x Potassium: stronger benefit when potassium is high", None,
                "Better blood-pressure support"),
    Interaction("heart_int_fiber_upf", "heart", ("fiber_density", "ultra_processed_tag"),
                "Fiber x Ultra-processed: stronger penalty when fiber is low", None,
                "Low-fiber UPF patterns are especially unfavorable"),
    Interaction("heart_int_satfat_unsatfat", "heart", ("saturated_fat_density", "unsaturated_fat_quality"),
                "Saturated fat x Unsaturated fat: reward replacement, not just absolute intake", None,
                "Heart benefit is mostly substitution-based"),
    Interaction("heart_int_addedsugar_upf", "heart", ("added_sugar_density", "ultra_processed_tag"),
                "Added sugar x Ultra-processed: stronger penalty", None,
                "More adverse triglyceride and weight pattern"),
    Interaction("heart_int_omega3_triglycerides", "heart", ("omega3_density",),
                "Omega-3 x High triglycerides: increase omega-3 benefit", None,
                "Most relevant when triglycerides are elevated", modifier_gate="high_triglycerides"),
    Interaction("heart_int_alcohol_hypertension", "heart", ("alcohol_density",),
                "Alcohol x Hypertension: amplify penalty", None,
                "Blood pressure sensitivity rises", modifier_gate="hypertension"),
]


# -------------------------------------------------------------------
# 4. METABOLIC SYNDROME / INSULIN RESISTANCE - RISK oriented
# -------------------------------------------------------------------
#
# The source document explicitly notes that waist circumference,
# triglycerides, HDL, blood pressure, fasting glucose/insulin are "better
# treated as optional user-specific inputs rather than food features" -
# these rules are still fully registered (feature/coefficient/mechanism
# all extracted) but their resolvers always return None at the
# ingredient level, exactly matching the source's own stated guidance.

METABOLIC_SYNDROME_RULES: List[Rule] = [
    Rule(
        rule_id="ms_central_adiposity", domain="metabolic_syndrome", feature="central_adiposity_proxy",
        display_name="Waist / central adiposity proxy", coefficient=0.30,
        curve=CurveType.PIECEWISE_LINEAR, curve_params={"threshold": 0.5, "scale": 1.0, "steepness_above": 2.0, "cap": 1.5},
        mechanism="Central adiposity is a core driver of metabolic syndrome and insulin resistance",
        pathway="Visceral adiposity / insulin signaling", organ="Adipose tissue / liver",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="ms_triglycerides", domain="metabolic_syndrome", feature="triglyceride_burden",
        display_name="Triglyceride burden", coefficient=0.25,
        curve=CurveType.LINEAR, curve_params={"scale": 1.0, "cap": 1.5},
        mechanism="Atherogenic dyslipidemia (elevated triglycerides) is central to metabolic syndrome",
        pathway="Lipid metabolism", organ="Liver / blood vessels",
        confidence_label="N/A",
    ),
    Rule(
        rule_id="ms_low_hdl", domain="metabolic_syndrome", feature="hdl_burden",
        display_name="Low HDL burden", coefficient=0.25,
        curve=CurveType.INVERSE, curve_params={"reference": 1.0},
        mechanism="Low HDL cholesterol is a defining feature of metabolic syndrome",
        pathway="Lipid metabolism", organ="Liver / blood vessels",
        confidence_label="N/A",
    ),
    Rule(
        rule_id="ms_blood_pressure", domain="metabolic_syndrome", feature="blood_pressure_biomarker",
        display_name="Blood pressure burden", coefficient=0.30,
        curve=CurveType.LINEAR, curve_params={"scale": 1.0, "cap": 1.5},
        mechanism="Elevated blood pressure is one of the canonical metabolic syndrome components",
        pathway="Vascular tone", organ="Blood vessels",
        confidence_label="N/A",
    ),
    Rule(
        rule_id="ms_glycemic_load", domain="metabolic_syndrome", feature="glycemic_load",
        display_name="Glycemic load", coefficient=0.35,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 15.0, "scale": 0.05, "steepness_above": 2.0, "cap": 1.5},
        mechanism="Higher glycemic burden worsens insulin demand and drives insulin resistance",
        pathway="Postprandial glycemic response / insulin signaling", organ="Pancreas / liver",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="ms_added_sugar", domain="metabolic_syndrome", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=0.30,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 2.0, "scale": 0.2, "steepness_above": 1.5, "cap": 1.5},
        mechanism="Added sugar is a strong driver of metabolic burden and hepatic fat accumulation",
        pathway="Hepatic lipogenesis / insulin signaling", organ="Liver",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="ms_ultra_processed", domain="metabolic_syndrome", feature="ultra_processed_tag",
        display_name="Ultra-processed indicator", coefficient=0.20,
        curve=CurveType.BINARY_INTENSITY, curve_params={},
        mechanism="Ultra-processed foods track with poor metabolic pattern quality",
        pathway="Metabolic pattern proxy", organ="Liver / adipose tissue",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="ms_fiber", domain="metabolic_syndrome", feature="fiber_density",
        display_name="Fiber density", coefficient=-0.30,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Fiber improves insulin sensitivity and postprandial metabolism",
        pathway="Carbohydrate absorption kinetics / insulin sensitivity", organ="Small intestine / liver",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="ms_whole_grain", domain="metabolic_syndrome", feature="whole_grain_tag",
        display_name="Whole grain tag", coefficient=-0.20,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Whole grains support better glycemic and metabolic pattern quality",
        pathway="Carbohydrate absorption kinetics", organ="Small intestine",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="ms_protein", domain="metabolic_syndrome", feature="protein_density",
        display_name="Protein density", coefficient=-0.15,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 6.0},
        mechanism="Protein supports satiety and lean mass, indirectly improving insulin-resistance burden",
        pathway="Satiety signaling / lean mass preservation", organ="Skeletal muscle",
        confidence_label="Medium",
    ),
]

METABOLIC_SYNDROME_INTERACTIONS: List[Interaction] = [
    Interaction("ms_int_gl_low_fiber", "metabolic_syndrome", ("glycemic_load", "fiber_density"),
                "Glycemic load x low fiber: stronger positive penalty", None, "Compounding glycemic/insulin burden"),
    Interaction("ms_int_addedsugar_upf", "metabolic_syndrome", ("added_sugar_density", "ultra_processed_tag"),
                "Added sugar x Ultra-processed: stronger positive penalty", None, "Worse metabolic pattern"),
    Interaction("ms_int_adiposity_gl", "metabolic_syndrome", ("central_adiposity_proxy", "glycemic_load"),
                "Central adiposity x Glycemic load: synergistic worsening", None,
                "Central adiposity amplifies glycemic burden"),
    Interaction("ms_int_fiber_gl", "metabolic_syndrome", ("fiber_density", "glycemic_load"),
                "Fiber x Glycemic load: buffering effect", None, "Fiber blunts glycemic impact"),
    Interaction("ms_int_wholegrain_fiber", "metabolic_syndrome", ("whole_grain_tag", "fiber_density"),
                "Whole grain x Fiber: extra protective effect", None, "Synergistic protective pattern"),
    Interaction("ms_int_upf_low_protein", "metabolic_syndrome", ("ultra_processed_tag", "protein_density"),
                "Ultra-processed x Low protein: worse satiety/metabolic pattern", None,
                "Low-protein UPF is especially unfavorable for satiety"),
]


# -------------------------------------------------------------------
# 5. KIDNEY - RISK oriented
# -------------------------------------------------------------------

KIDNEY_RULES: List[Rule] = [
    Rule(
        rule_id="kidney_sodium", domain="kidney", feature="sodium_density",
        display_name="Sodium density", coefficient=1.00,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 100.0, "scale": 0.005, "steepness_above": 2.5, "cap": 1.5},
        mechanism="Sodium raises blood pressure and disrupts fluid balance, both of which drive kidney injury",
        pathway="Fluid balance / vascular resistance", organ="Kidneys / blood vessels",
        confidence_label="High",
        citation="https://www.kidney.org/kidney-topics/6-step-guide-to-protecting-kidney-health",
    ),
    Rule(
        rule_id="kidney_potassium", domain="kidney", feature="potassium_density",
        display_name="Potassium density (general population default; CKD-gated via interaction)",
        coefficient=-0.35,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 200.0},
        mechanism="Potassium supports vascular tone and blood-pressure control; must be restricted instead in CKD/hyperkalemia risk (see kidney_int_potassium_ckd interaction)",
        pathway="Vascular tone / electrolyte balance", organ="Kidneys / blood vessels",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="kidney_blood_pressure", domain="kidney", feature="blood_pressure_biomarker",
        display_name="Blood pressure burden", coefficient=0.85,
        curve=CurveType.LINEAR, curve_params={"scale": 1.0, "cap": 1.5},
        mechanism="Blood pressure is a major driver of kidney injury",
        pathway="Vascular / glomerular pressure", organ="Kidneys",
        confidence_label="High",
        citation="https://www.kidney.org/kidney-topics/6-step-guide-to-protecting-kidney-health",
    ),
    Rule(
        rule_id="kidney_glycemic_load", domain="kidney", feature="glycemic_load",
        display_name="Glycemic load", coefficient=0.60,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 15.0, "scale": 0.05, "steepness_above": 2.0, "cap": 1.5},
        mechanism="Diabetes and hyperglycemia are major drivers of chronic kidney disease",
        pathway="Glomerular hyperfiltration / glycation", organ="Kidneys",
        confidence_label="High",
        citation="https://www.kidney.org/kidney-topics/6-step-guide-to-protecting-kidney-health",
    ),
    Rule(
        rule_id="kidney_added_sugar", domain="kidney", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=0.35,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 2.0, "scale": 0.2, "steepness_above": 1.5, "cap": 1.5},
        mechanism="Added sugar contributes indirect metabolic and renal burden",
        pathway="Metabolic burden", organ="Kidneys",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="kidney_ultra_processed", domain="kidney", feature="ultra_processed_tag",
        display_name="Ultra-processed indicator", coefficient=0.35,
        curve=CurveType.BINARY_INTENSITY, curve_params={},
        mechanism="Ultra-processed foods track with high sodium, low fiber, and poor metabolic quality",
        pathway="Sodium / metabolic co-pattern", organ="Kidneys",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="kidney_fiber", domain="kidney", feature="fiber_density",
        display_name="Fiber density", coefficient=-0.20,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Fiber supports metabolic and blood-pressure control, indirectly favorable for kidney health",
        pathway="Metabolic / BP support", organ="Kidneys",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="kidney_protein", domain="kidney", feature="protein_density",
        display_name="Protein density (general-population default; CKD context multiplier via interaction)",
        coefficient=0.20,
        curve=CurveType.LINEAR, curve_params={"scale": 0.1, "cap": 1.0},
        mechanism="Moderate protein is generally fine, but higher protein burden matters more when kidney function is impaired",
        pathway="Renal protein filtration load", organ="Kidneys",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="kidney_processed_meat", domain="kidney", feature="processed_meat_tag",
        display_name="Processed meat tag", coefficient=0.40,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Processed meats add sodium, phosphorus additives, and overall dietary burden",
        pathway="Sodium / phosphorus burden", organ="Kidneys",
        confidence_label="High",
    ),
    Rule(
        rule_id="kidney_phosphorus", domain="kidney", feature="phosphorus_density",
        display_name="Phosphorus load", coefficient=0.35,
        curve=CurveType.LINEAR, curve_params={"scale": 0.005, "cap": 1.5},
        mechanism="Phosphate burden is especially relevant when kidney function is impaired",
        pathway="Mineral / bone-kidney axis", organ="Kidneys",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="kidney_whole_grain", domain="kidney", feature="whole_grain_tag",
        display_name="Whole grain tag", coefficient=-0.15,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Whole grains support better metabolic pattern quality",
        pathway="Metabolic pattern proxy", organ="Kidneys",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="kidney_energy_density", domain="kidney", feature="energy_density",
        display_name="Obesity / energy density proxy", coefficient=0.20,
        curve=CurveType.LINEAR, curve_params={"scale": 0.002, "cap": 1.0},
        mechanism="Energy density contributes indirect kidney risk via metabolic syndrome and obesity",
        pathway="Adiposity / metabolic syndrome", organ="Adipose tissue / kidneys",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="kidney_albuminuria", domain="kidney", feature="albuminuria_proxy",
        display_name="Albuminuria proxy", coefficient=0.90,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Albuminuria is a strong direct marker of existing kidney damage",
        pathway="Glomerular filtration barrier integrity", organ="Kidneys",
        confidence_label="High",
    ),
    Rule(
        rule_id="kidney_egfr", domain="kidney", feature="egfr_burden",
        display_name="eGFR burden", coefficient=1.00,
        curve=CurveType.INVERSE, curve_params={"reference": 90.0},
        mechanism="Lower estimated glomerular filtration rate directly reflects worse kidney status",
        pathway="Glomerular filtration", organ="Kidneys",
        confidence_label="High",
    ),
]

KIDNEY_INTERACTIONS: List[Interaction] = [
    Interaction("kidney_int_sodium_bp", "kidney", ("sodium_density", "blood_pressure_biomarker"),
                "Sodium x BP: +0.25", 0.25, "High BP amplifies kidney injury risk"),
    Interaction("kidney_int_sodium_ckd", "kidney", ("sodium_density",),
                "Sodium x CKD: multiply sodium term by a CKD factor", None,
                "Salt sensitivity rises in CKD", modifier_gate="ckd"),
    Interaction("kidney_int_potassium_ckd", "kidney", ("potassium_density",),
                "Potassium x CKD: gate or penalize depending on hyperkalemia risk", None,
                "Potassium must not be treated as universally beneficial in CKD", modifier_gate="ckd"),
    Interaction("kidney_int_gl_diabetes", "kidney", ("glycemic_load",),
                "Glycemic load x Diabetes: multiply GL term upward", None,
                "Diabetes is a leading cause of chronic kidney disease", modifier_gate="diabetes"),
    Interaction("kidney_int_protein_ckd", "kidney", ("protein_density",),
                "Protein x CKD: multiply protein term upward", None,
                "Higher protein load matters more when kidney function is impaired", modifier_gate="ckd"),
    Interaction("kidney_int_phosphorus_ckd", "kidney", ("phosphorus_density",),
                "Phosphorus x CKD: multiply phosphorus term upward", None,
                "Phosphate burden is more relevant in CKD", modifier_gate="ckd"),
    Interaction("kidney_int_upf_sodium", "kidney", ("ultra_processed_tag", "sodium_density"),
                "Ultra-processed x Sodium: extra positive penalty", None, "Common hidden sodium burden"),
    Interaction("kidney_int_addedsugar_obesity", "kidney", ("added_sugar_density",),
                "Added sugar x Obesity: extra positive penalty", None,
                "Metabolic syndrome worsens kidney risk", modifier_gate="obesity"),
    Interaction("kidney_int_albuminuria_bp", "kidney", ("albuminuria_proxy", "blood_pressure_biomarker"),
                "Albuminuria x BP: extra positive penalty", None, "Strong marker of renal damage"),
]


# -------------------------------------------------------------------
# 6. LIVER / NAFLD - RISK oriented
# -------------------------------------------------------------------

LIVER_RULES: List[Rule] = [
    Rule(
        rule_id="liver_added_sugar", domain="liver", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=0.70,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 2.0, "scale": 0.2, "steepness_above": 2.0, "cap": 1.5},
        mechanism="Added sugar (especially fructose) strongly promotes hepatic fat accumulation and NAFLD risk",
        pathway="Hepatic de novo lipogenesis", organ="Liver",
        confidence_label="High",
        citation="https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash/symptoms-causes",
    ),
    Rule(
        rule_id="liver_liquid_sugar", domain="liver", feature="liquid_sugar_tag",
        display_name="Liquid sugar tag", coefficient=0.80,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Rapid absorption and high fructose exposure make sugary beverages especially adverse for NAFLD risk",
        pathway="Hepatic de novo lipogenesis", organ="Liver",
        confidence_label="High",
        citation="https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash/symptoms-causes",
    ),
    Rule(
        rule_id="liver_glycemic_load", domain="liver", feature="glycemic_load",
        display_name="Glycemic load estimate", coefficient=0.55,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 15.0, "scale": 0.05, "steepness_above": 2.0, "cap": 1.5},
        mechanism="Higher glycemic burden promotes de novo lipogenesis and insulin resistance",
        pathway="Hepatic de novo lipogenesis / insulin signaling", organ="Liver",
        confidence_label="High",
        citation="https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash/symptoms-causes",
    ),
    Rule(
        rule_id="liver_ultra_processed", domain="liver", feature="ultra_processed_tag",
        display_name="Ultra-processed indicator", coefficient=0.40,
        curve=CurveType.BINARY_INTENSITY, curve_params={},
        mechanism="Ultra-processed foods track with refined carbs, added sugars, poor fat quality, and low fiber",
        pathway="Refined-carbohydrate / fat-quality co-pattern", organ="Liver",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="liver_energy_density", domain="liver", feature="energy_density",
        display_name="Energy density", coefficient=0.35,
        curve=CurveType.LINEAR, curve_params={"scale": 0.002, "cap": 1.0},
        mechanism="High energy density promotes adiposity, a major driver of NAFLD",
        pathway="Adiposity", organ="Adipose tissue / liver",
        confidence_label="High",
        citation="https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash/symptoms-causes",
    ),
    Rule(
        rule_id="liver_fiber", domain="liver", feature="fiber_density",
        display_name="Fiber density", coefficient=-0.45,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Fiber improves insulin sensitivity, satiety, and overall metabolic health",
        pathway="Insulin sensitivity / satiety signaling", organ="Liver / small intestine",
        confidence_label="High",
        citation="https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash/symptoms-causes",
    ),
    Rule(
        rule_id="liver_whole_grain", domain="liver", feature="whole_grain_tag",
        display_name="Whole grain tag", coefficient=-0.25,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Whole grains support better carbohydrate quality and metabolic profile",
        pathway="Carbohydrate quality", organ="Liver",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="liver_protein", domain="liver", feature="protein_density",
        display_name="Protein density", coefficient=-0.20,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 6.0},
        mechanism="Protein supports lean mass and weight-loss preservation, indirectly beneficial for hepatic fat",
        pathway="Lean mass preservation", organ="Skeletal muscle / liver",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="liver_saturated_fat", domain="liver", feature="saturated_fat_density",
        display_name="Saturated fat", coefficient=0.30,
        curve=CurveType.LINEAR, curve_params={"scale": 0.05, "cap": 1.5},
        mechanism="Saturated fat can worsen hepatic fat and lipid handling, especially in poor metabolic contexts",
        pathway="Hepatic lipid handling", organ="Liver",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="liver_trans_fat", domain="liver", feature="trans_fat_density",
        display_name="Trans fat", coefficient=0.60,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.05},
        mechanism="Trans fat carries strongly adverse cardiometabolic lipid quality",
        pathway="Lipid handling", organ="Liver",
        confidence_label="High",
    ),
    Rule(
        rule_id="liver_alcohol", domain="liver", feature="alcohol_density",
        display_name="Alcohol tag / alcohol grams", coefficient=1.00,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.1},
        mechanism="Alcohol is directly hepatotoxic at meaningful levels and drives alcohol-associated liver injury",
        pathway="Direct hepatotoxicity", organ="Liver",
        confidence_label="High",
    ),
    Rule(
        rule_id="liver_added_fructose", domain="liver", feature="fructose_density",
        display_name="Added fructose proxy", coefficient=0.50,
        curve=CurveType.LINEAR, curve_params={"scale": 0.2, "cap": 1.5},
        mechanism="Fructose-heavy diets are specifically implicated in liver fat accumulation",
        pathway="Hepatic de novo lipogenesis", organ="Liver",
        confidence_label="Medium",
        citation="https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash/symptoms-causes",
    ),
    Rule(
        rule_id="liver_omega3", domain="liver", feature="omega3_density",
        display_name="Omega-3 density", coefficient=-0.20,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 0.3},
        mechanism="Omega-3 fatty acids support triglyceride handling and inflammation balance",
        pathway="Lipid handling / inflammatory tone", organ="Liver",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="liver_processed_meat", domain="liver", feature="processed_meat_tag",
        display_name="Processed meat tag", coefficient=0.20,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Processed meats add indirect metabolic burden, sodium, and poor fat quality",
        pathway="Metabolic burden", organ="Liver",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="liver_central_adiposity", domain="liver", feature="central_adiposity_proxy",
        display_name="Central adiposity proxy", coefficient=0.80,
        curve=CurveType.LINEAR, curve_params={"scale": 1.0, "cap": 1.5},
        mechanism="Obesity and abdominal adiposity are among the strongest NAFLD risk factors",
        pathway="Visceral adiposity / hepatic fat", organ="Adipose tissue / liver",
        confidence_label="High",
        citation="https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash/symptoms-causes",
    ),
    Rule(
        rule_id="liver_insulin_resistance", domain="liver", feature="insulin_resistance_biomarker",
        display_name="Insulin resistance / glycemia burden", coefficient=0.70,
        curve=CurveType.LINEAR, curve_params={"scale": 1.0, "cap": 1.5},
        mechanism="Insulin resistance is a core driver of NAFLD",
        pathway="Insulin signaling / hepatic lipogenesis", organ="Liver",
        confidence_label="High",
        citation="https://www.niddk.nih.gov/health-information/liver-disease/nafld-nash/symptoms-causes",
    ),
]

LIVER_INTERACTIONS: List[Interaction] = [
    Interaction("liver_int_addedsugar_liquidsugar", "liver", ("added_sugar_density", "liquid_sugar_tag"),
                "Added sugar x Liquid sugar: +0.25", 0.25, "Beverage sugars are especially adverse"),
    Interaction("liver_int_gl_low_fiber", "liver", ("glycemic_load", "fiber_density"),
                "Glycemic load x Low fiber: +0.20", 0.20, "Low fiber amplifies lipogenesis burden"),
    Interaction("liver_int_energy_adiposity", "liver", ("energy_density", "central_adiposity_proxy"),
                "Energy density x Central adiposity: +0.20", 0.20, "Strong obesity-mediated NAFLD risk"),
    Interaction("liver_int_addedsugar_upf", "liver", ("added_sugar_density", "ultra_processed_tag"),
                "Added sugar x Ultra-processed: +0.15", 0.15, "Worse formulation pattern"),
    Interaction("liver_int_alcohol_addedsugar", "liver", ("alcohol_density", "added_sugar_density"),
                "Alcohol x Added sugar: +0.30", 0.30, "Synergistically worsens hepatic stress"),
    Interaction("liver_int_satfat_low_fiber", "liver", ("saturated_fat_density", "fiber_density"),
                "Saturated fat x Low fiber: +0.10", 0.10, "Poor dietary matrix worsens lipid handling"),
    Interaction("liver_int_protein_weightloss", "liver", ("protein_density",),
                "Protein x Weight-loss context: -0.10 (protective)", -0.10,
                "Protein helps preserve lean mass during weight loss", modifier_gate="weight_loss"),
    Interaction("liver_int_omega3_low_transfat", "liver", ("omega3_density", "trans_fat_density"),
                "Omega-3 x Low trans fat: -0.05 (protective)", -0.05, "Better hepatic/lipid environment"),
]


# -------------------------------------------------------------------
# 7. BONE HEALTH - SUPPORT oriented
# -------------------------------------------------------------------

BONE_RULES: List[Rule] = [
    Rule(
        rule_id="bone_calcium", domain="bone", feature="calcium_density",
        display_name="Calcium density", coefficient=0.90,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 80.0},
        mechanism="Calcium is the primary mineral substrate for bone mineralization",
        pathway="Bone mineralization", organ="Bone",
        confidence_label="High",
    ),
    Rule(
        rule_id="bone_vitamin_d", domain="bone", feature="vitamin_d_density",
        display_name="Vitamin D density", coefficient=0.75,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 1.0},
        mechanism="Vitamin D supports intestinal calcium absorption and bone metabolism",
        pathway="Calcium absorption / bone metabolism", organ="Small intestine / bone",
        confidence_label="High",
    ),
    Rule(
        rule_id="bone_protein_adequacy", domain="bone", feature="protein_density",
        display_name="Protein adequacy", coefficient=0.45,
        curve=CurveType.U_SHAPED,
        curve_params={"low_threshold": 4.0, "high_threshold": 6.0, "saturation_point": 4.0},
        mechanism="Protein supports the organic bone matrix and skeletal muscle, which protects against falls",
        pathway="Bone matrix synthesis / fall prevention", organ="Bone / skeletal muscle",
        confidence_label="High",
    ),
    Rule(
        rule_id="bone_vitamin_k", domain="bone", feature="vitamin_k_density",
        display_name="Vitamin K density", coefficient=0.35,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 15.0},
        mechanism="Vitamin K is required for carboxylation of bone matrix proteins (e.g. osteocalcin)",
        pathway="Bone protein carboxylation", organ="Bone",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="bone_magnesium", domain="bone", feature="magnesium_density",
        display_name="Magnesium density", coefficient=0.30,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 15.0},
        mechanism="Magnesium contributes to bone structure and mineral metabolism",
        pathway="Bone mineral metabolism", organ="Bone",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="bone_potassium", domain="bone", feature="potassium_density",
        display_name="Potassium-rich plant foods", coefficient=0.20,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 200.0},
        mechanism="Potassium-rich plant foods help buffer dietary acid load, protecting bone mineral",
        pathway="Acid-base buffering", organ="Bone / kidneys",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bone_fruit_vegetable", domain="bone", feature="fruit_vegetable_tag",
        display_name="Fruit / vegetable density", coefficient=0.15,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Fruits and vegetables support micronutrient intake and lower dietary acid load",
        pathway="Micronutrient support / acid-base buffering", organ="Bone",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bone_dairy_fortified", domain="bone", feature="dairy_or_fortified_tag",
        display_name="Dairy / fortified alternative tag", coefficient=0.25,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Dairy (or fortified alternatives) is a practical, concentrated carrier of calcium and vitamin D",
        pathway="Calcium / vitamin D delivery", organ="Bone",
        confidence_label="High",
    ),
    Rule(
        rule_id="bone_legume", domain="bone", feature="legume_tag",
        display_name="Legume tag", coefficient=0.10,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Legumes provide a helpful protein and magnesium source for bone",
        pathway="Bone matrix / mineral metabolism", organ="Bone",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bone_whole_grain", domain="bone", feature="whole_grain_tag",
        display_name="Whole grain tag", coefficient=0.10,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Whole grains play a minor supportive role via magnesium and overall pattern quality",
        pathway="Mineral metabolism / pattern quality", organ="Bone",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bone_alcohol", domain="bone", feature="alcohol_density",
        display_name="Alcohol burden", coefficient=-0.45,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.5},
        mechanism="Excess alcohol worsens bone metabolism and increases fall risk",
        pathway="Osteoblast function / fall risk", organ="Bone",
        confidence_label="High",
    ),
    Rule(
        rule_id="bone_soda_cola", domain="bone", feature="soda_cola_burden",
        display_name="Soda / cola burden", coefficient=-0.25,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.5},
        mechanism="Soda/cola often displaces calcium-rich beverages and associates with poorer bone patterns",
        pathway="Dietary displacement", organ="Bone",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="bone_ultra_processed", domain="bone", feature="ultra_processed_tag",
        display_name="Ultra-processed indicator", coefficient=-0.30,
        curve=CurveType.BINARY_INTENSITY, curve_params={},
        mechanism="Ultra-processed foods have low nutrient density and worse overall pattern quality for bone nutrients",
        pathway="Nutrient density proxy", organ="Bone",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="bone_added_sugar", domain="bone", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=-0.15,
        curve=CurveType.LINEAR, curve_params={"scale": 0.15, "cap": 1.0},
        mechanism="Added sugar displaces nutrient-rich foods and worsens overall diet quality",
        pathway="Dietary displacement", organ="Bone",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bone_sodium", domain="bone", feature="sodium_density",
        display_name="Sodium burden", coefficient=-0.10,
        curve=CurveType.LINEAR, curve_params={"scale": 0.003, "cap": 1.0},
        mechanism="High sodium intake may increase urinary calcium loss in some contexts",
        pathway="Renal calcium handling", organ="Kidneys / bone",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="bone_caffeine", domain="bone", feature="caffeine_density",
        display_name="Caffeine burden", coefficient=-0.10,
        curve=CurveType.LINEAR, curve_params={"scale": 0.05, "cap": 0.6},
        mechanism="Caffeine is only meaningfully bone-adverse at higher intakes or with low calcium intake",
        pathway="Renal calcium handling", organ="Kidneys / bone",
        confidence_label="Medium",
    ),
]

BONE_INTERACTIONS: List[Interaction] = [
    Interaction("bone_int_calcium_vitamind", "bone", ("calcium_density", "vitamin_d_density"),
                "Calcium x Vitamin D: extra protective bonus", None, "Vitamin D improves calcium absorption"),
    Interaction("bone_int_calcium_protein", "bone", ("calcium_density", "protein_density"),
                "Calcium x Protein: extra protective bonus", None, "Adequate protein supports bone matrix"),
    Interaction("bone_int_vitamind_low_sun", "bone", ("vitamin_d_density",),
                "Vitamin D x Low sun exposure: increase vitamin D weight", None,
                "Supplementary dietary support matters more", modifier_gate="low_sun_exposure"),
    Interaction("bone_int_alcohol_low_calcium", "bone", ("alcohol_density", "calcium_density"),
                "Alcohol x Low calcium: stronger penalty", None, "Combined bone-risk pattern"),
    Interaction("bone_int_upf_low_dairy", "bone", ("ultra_processed_tag", "dairy_or_fortified_tag"),
                "Ultra-processed x Low dairy/fortification: stronger penalty", None,
                "Lower calcium and vitamin D density"),
    Interaction("bone_int_protein_older_age", "bone", ("protein_density",),
                "Protein x Older age: increase benefit", None,
                "Older adults need adequate protein more", modifier_gate="older_adult"),
    Interaction("bone_int_magnesium_potassium", "bone", ("magnesium_density", "potassium_density"),
                "Magnesium x Potassium-rich foods: small synergy", None, "Better overall mineral pattern"),
]


# -------------------------------------------------------------------
# 8. BRAIN / COGNITIVE / MOOD - SUPPORT oriented
# -------------------------------------------------------------------

BRAIN_RULES: List[Rule] = [
    Rule(
        rule_id="brain_omega3", domain="brain", feature="omega3_density",
        display_name="Omega-3 density", coefficient=0.80,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 0.3},
        mechanism="Marine omega-3s support neuronal membrane structure and neurotransmission - the best-supported nutrient-level brain/mood signal",
        pathway="Neuronal membrane biology / neurotransmission", organ="Brain",
        confidence_label="High",
    ),
    Rule(
        rule_id="brain_fiber", domain="brain", feature="fiber_density",
        display_name="Fiber density", coefficient=0.40,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Fiber supports glycemic stability and the gut-brain axis",
        pathway="Glycemic stability / gut-brain axis", organ="Gut / brain",
        confidence_label="High",
    ),
    Rule(
        rule_id="brain_glycemic_load", domain="brain", feature="glycemic_load",
        display_name="Glycemic load estimate", coefficient=-0.35,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 15.0, "scale": 0.05, "steepness_above": 2.0, "cap": 1.5},
        mechanism="Large glucose swings can worsen fatigue and cognitive steadiness",
        pathway="Postprandial glycemic response", organ="Brain",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="brain_ultra_processed", domain="brain", feature="ultra_processed_tag",
        display_name="Ultra-processed indicator", coefficient=-0.45,
        curve=CurveType.BINARY_INTENSITY, curve_params={},
        mechanism="Ultra-processed foods track with lower diet quality and less micronutrient density",
        pathway="Micronutrient density proxy", organ="Brain",
        confidence_label="High",
    ),
    Rule(
        rule_id="brain_added_sugar", domain="brain", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=-0.30,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 2.0, "scale": 0.2, "steepness_above": 1.5, "cap": 1.5},
        mechanism="Added sugar worsens glycemic stability and displaces nutrient-dense foods",
        pathway="Glycemic stability / nutrient displacement", organ="Brain",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="brain_alcohol", domain="brain", feature="alcohol_density",
        display_name="Alcohol burden", coefficient=-0.60,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.5},
        mechanism="Alcohol is a strong negative for sleep, mood, and cognition",
        pathway="Sleep architecture / neurotransmitter balance", organ="Brain",
        confidence_label="High",
    ),
    Rule(
        rule_id="brain_b_vitamins", domain="brain", feature="b_vitamin_density_index",
        display_name="B-vitamin density index", coefficient=0.45,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 10.0},
        mechanism="B vitamins support cellular energy metabolism and are relevant to mood/cognition, especially at suboptimal intake",
        pathway="Cellular energy metabolism", organ="Brain",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="brain_magnesium", domain="brain", feature="magnesium_density",
        display_name="Magnesium density", coefficient=0.20,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 15.0},
        mechanism="Magnesium supports neurometabolic function and stress regulation",
        pathway="Neurometabolic function / stress regulation", organ="Brain",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="brain_choline", domain="brain", feature="choline_density",
        display_name="Choline density", coefficient=0.30,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 20.0},
        mechanism="Choline is important for neurotransmission (acetylcholine synthesis) and neuronal membrane biology",
        pathway="Neurotransmitter synthesis / membrane biology", organ="Brain",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="brain_iron", domain="brain", feature="iron_density",
        display_name="Iron adequacy", coefficient=0.20,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 1.0},
        mechanism="Iron is relevant to fatigue and cognition, especially in at-risk groups",
        pathway="Oxygen transport / cellular energy metabolism", organ="Brain",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="brain_vitamin_d", domain="brain", feature="vitamin_d_density",
        display_name="Vitamin D density", coefficient=0.20,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 1.0},
        mechanism="Vitamin D is supportive for brain function, though less directly than omega-3 or B vitamins",
        pathway="Neurosteroid signaling", organ="Brain",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="brain_whole_grain", domain="brain", feature="whole_grain_tag",
        display_name="Whole grain tag", coefficient=0.15,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Whole grains support steady energy delivery and nutrient density",
        pathway="Glycemic stability", organ="Brain",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="brain_fruit_vegetable", domain="brain", feature="fruit_vegetable_tag",
        display_name="Fruit / vegetable tag", coefficient=0.20,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Polyphenols and micronutrient density from fruit/vegetables support brain health",
        pathway="Polyphenol / micronutrient support", organ="Brain",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="brain_caffeine", domain="brain", feature="caffeine_density",
        display_name="Caffeine burden", coefficient=-0.10,
        curve=CurveType.LINEAR, curve_params={"scale": 0.05, "cap": 0.6},
        mechanism="Caffeine can help alertness but hurt sleep and anxiety in sensitive users",
        pathway="Sleep architecture / anxiety", organ="Brain",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="brain_saturated_fat", domain="brain", feature="saturated_fat_density",
        display_name="Saturated fat", coefficient=-0.10,
        curve=CurveType.LINEAR, curve_params={"scale": 0.05, "cap": 1.0},
        mechanism="Saturated fat has a secondary, pattern-quality effect on brain health",
        pathway="Vascular / pattern quality", organ="Brain",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="brain_protein", domain="brain", feature="protein_density",
        display_name="Protein density", coefficient=0.10,
        curve=CurveType.LINEAR, curve_params={"scale": 0.05, "cap": 0.8},
        mechanism="Protein supports satiety and stable intake patterns, benefiting steady cognitive energy",
        pathway="Satiety / stable glycemic supply", organ="Brain",
        confidence_label="Medium",
    ),
]

BRAIN_INTERACTIONS: List[Interaction] = [
    Interaction("brain_int_omega3_bvitamins", "brain", ("omega3_density", "b_vitamin_density_index"),
                "Omega-3 x B vitamins: extra protective bonus", None,
                "Synergistic cognition support is plausible, especially in at-risk contexts"),
    Interaction("brain_int_gl_upf", "brain", ("glycemic_load", "ultra_processed_tag"),
                "Glycemic load x Ultra-processed: stronger penalty", None,
                "Steadier glucose matters more in poor-quality diets"),
    Interaction("brain_int_alcohol_low_fiber", "brain", ("alcohol_density", "fiber_density"),
                "Alcohol x Low fiber: stronger penalty", None, "Worse sleep/mood/gut-brain pattern"),
    Interaction("brain_int_caffeine_sleep", "brain", ("caffeine_density",),
                "Caffeine x Sleep sensitivity: amplify caffeine penalty", None,
                "Sleep disruption harms cognition and mood", modifier_gate="low_sleep"),
    Interaction("brain_int_bvitamins_low_status", "brain", ("b_vitamin_density_index",),
                "B vitamins x Low status: larger benefit", None,
                "Benefits are strongest when deficiency or suboptimal intake exists", modifier_gate="low_b_vitamin_status"),
    Interaction("brain_int_fv_fiber", "brain", ("fruit_vegetable_tag", "fiber_density"),
                "Fruit/veg x Fiber: extra protective bonus", None, "Combined nutrient and polyphenol support"),
]


# -------------------------------------------------------------------
# 9. INFLAMMATION (+ ARTHRITIS sub-layer) - SUPPORT oriented
# -------------------------------------------------------------------
#
# NOTE ON ORIENTATION: this module's "Recommended equation" -
#   I = I0 + 0.80*Omega3 + 0.45*F - 0.55*UPF - 0.40*AS - 0.50*Alc
#         - 0.25*ED - 0.25*Sat - 0.70*Trans + 0.25*WG + 0.25*FV
#         + 0.20*Leg + 0.10*P + 0.15*Mg - 0.30*Add
# - applies POSITIVE signs to every protective factor (omega-3, fiber,
# whole grain, fruit/veg, legume, protein, magnesium) and NEGATIVE signs
# to every adverse factor (UPF, added sugar, alcohol, energy density,
# saturated fat, trans fat, processing/additive burden). That makes I a
# SUPPORT score (higher = better/more anti-inflammatory), matching Heart/
# Bone/Brain/Muscle's convention - not a RISK score as the domain's
# narrative description initially suggested. Coefficients below are taken
# directly from this equation.

INFLAMMATION_RULES: List[Rule] = [
    Rule(
        rule_id="infl_omega3", domain="inflammation", feature="omega3_density",
        display_name="Omega-3 density", coefficient=0.80,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 0.3},
        mechanism="Omega-3s are the best-supported anti-inflammatory nutrient signal, including for rheumatoid-arthritis symptom support",
        pathway="Eicosanoid balance / anti-inflammatory signaling", organ="Joints / systemic immune system",
        confidence_label="High",
    ),
    Rule(
        rule_id="infl_fiber", domain="inflammation", feature="fiber_density",
        display_name="Fiber density", coefficient=0.45,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Fiber supports gut-derived anti-inflammatory effects (SCFA production) and better overall diet quality",
        pathway="Microbiome / SCFA production", organ="Gut / systemic immune system",
        confidence_label="High",
    ),
    Rule(
        rule_id="infl_ultra_processed", domain="inflammation", feature="ultra_processed_tag",
        display_name="Ultra-processed indicator", coefficient=-0.55,
        curve=CurveType.BINARY_INTENSITY, curve_params={},
        mechanism="Ultra-processed foods are a strong proxy for pro-inflammatory pattern quality",
        pathway="Dietary pattern / metabolic inflammation", organ="Systemic immune system",
        confidence_label="High",
    ),
    Rule(
        rule_id="infl_added_sugar", domain="inflammation", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=-0.40,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 2.0, "scale": 0.2, "steepness_above": 1.5, "cap": 1.5},
        mechanism="Added sugar is pro-inflammatory and metabolically unfavorable",
        pathway="Metabolic inflammation", organ="Systemic immune system",
        confidence_label="High",
    ),
    Rule(
        rule_id="infl_alcohol", domain="inflammation", feature="alcohol_density",
        display_name="Alcohol burden", coefficient=-0.50,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.5},
        mechanism="Alcohol worsens systemic inflammation and joint outcomes",
        pathway="Systemic inflammatory tone", organ="Joints / liver",
        confidence_label="High",
    ),
    Rule(
        rule_id="infl_energy_density", domain="inflammation", feature="energy_density",
        display_name="Energy density", coefficient=-0.25,
        curve=CurveType.LINEAR, curve_params={"scale": 0.002, "cap": 1.0},
        mechanism="High energy density supports weight gain, which worsens osteoarthritis and inflammatory burden",
        pathway="Adiposity / joint load", organ="Adipose tissue / joints",
        confidence_label="High",
    ),
    Rule(
        rule_id="infl_saturated_fat", domain="inflammation", feature="saturated_fat_density",
        display_name="Saturated fat", coefficient=-0.25,
        curve=CurveType.LINEAR, curve_params={"scale": 0.05, "cap": 1.5},
        mechanism="Saturated fat contributes to pattern-level inflammatory burden",
        pathway="Metabolic inflammation", organ="Systemic immune system",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="infl_trans_fat", domain="inflammation", feature="trans_fat_density",
        display_name="Trans fat", coefficient=-0.70,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.05},
        mechanism="Trans fat is strongly pro-inflammatory and cardiometabolically adverse",
        pathway="Metabolic inflammation / vascular function", organ="Systemic immune system / blood vessels",
        confidence_label="High",
    ),
    Rule(
        rule_id="infl_whole_grain", domain="inflammation", feature="whole_grain_tag",
        display_name="Whole grain tag", coefficient=0.25,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Whole grains mark a better inflammatory dietary pattern quality",
        pathway="Dietary pattern quality", organ="Systemic immune system",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="infl_fruit_vegetable", domain="inflammation", feature="fruit_vegetable_tag",
        display_name="Fruit / vegetable tag", coefficient=0.25,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Polyphenols and micronutrient density from fruit/vegetables support anti-inflammatory pattern quality",
        pathway="Polyphenol / antioxidant support", organ="Systemic immune system",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="infl_legume", domain="inflammation", feature="legume_tag",
        display_name="Legume tag", coefficient=0.20,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Legumes are a fiber-rich anti-inflammatory dietary pattern marker",
        pathway="Microbiome / SCFA production", organ="Gut / systemic immune system",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="infl_protein", domain="inflammation", feature="protein_density",
        display_name="Protein density", coefficient=0.10,
        curve=CurveType.LINEAR, curve_params={"scale": 0.05, "cap": 0.8},
        mechanism="Protein supports weight control and tissue repair; the effect on inflammation is secondary",
        pathway="Weight control / tissue repair", organ="Systemic",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="infl_magnesium", domain="inflammation", feature="magnesium_density",
        display_name="Magnesium density", coefficient=0.15,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 15.0},
        mechanism="Magnesium may support inflammatory balance and metabolic health",
        pathway="Metabolic / inflammatory balance", organ="Systemic",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="infl_processing_additive", domain="inflammation", feature="processing_score",
        display_name="Processing / additive burden", coefficient=-0.30,
        curve=CurveType.LINEAR, curve_params={"scale": 0.5, "cap": 1.5},
        mechanism="Processing/additive burden is a proxy for low-quality, pro-inflammatory formulation",
        pathway="Dietary pattern / formulation quality", organ="Systemic immune system",
        confidence_label="Medium-high",
    ),
]

INFLAMMATION_INTERACTIONS: List[Interaction] = [
    Interaction("infl_int_omega3_low_transfat", "inflammation", ("omega3_density", "trans_fat_density"),
                "Omega-3 x Low trans fat: extra protective bonus", None,
                "Anti-inflammatory benefit is cleaner in a low-trans-fat context"),
    Interaction("infl_int_fiber_upf", "inflammation", ("fiber_density", "ultra_processed_tag"),
                "Fiber x Ultra-processed: stronger negative effect if fiber is low", None,
                "Low-fiber UPF patterns are especially pro-inflammatory"),
    Interaction("infl_int_addedsugar_upf", "inflammation", ("added_sugar_density", "ultra_processed_tag"),
                "Added sugar x Ultra-processed: stronger negative effect", None,
                "Synergistic inflammatory/metabolic burden"),
    Interaction("infl_int_energy_weight", "inflammation", ("energy_density",),
                "Energy density x Weight burden: stronger arthritis penalty", None,
                "Weight loss improves OA symptoms", modifier_gate="osteoarthritis"),
    Interaction("infl_int_omega3_ra", "inflammation", ("omega3_density",),
                "Omega-3 x Arthritis subtype: increase benefit in RA more than OA", None,
                "RA is more inflammation-driven", modifier_gate="rheumatoid_arthritis"),
    Interaction("infl_int_fiber_legume_wholegrain", "inflammation", ("fiber_density", "legume_tag"),
                "Fiber x Legume/whole grain: extra protective bonus", None,
                "Fermentable substrate plus diet quality"),
]

# --- Arthritis symptom-burden sub-layer (a distinct second output per
# the source document, sharing the same RISK orientation) ---

ARTHRITIS_RULES: List[Rule] = [
    Rule(
        rule_id="arth_weight_adiposity", domain="arthritis", feature="central_adiposity_proxy",
        display_name="Weight / central adiposity burden", coefficient=-0.70,
        curve=CurveType.LINEAR, curve_params={"scale": 1.0, "cap": 1.5},
        mechanism="Weight loss meaningfully improves osteoarthritis pain and joint function",
        pathway="Joint mechanical load / adiposity-driven inflammation", organ="Joints / adipose tissue",
        confidence_label="High",
    ),
    Rule(
        rule_id="arth_omega3", domain="arthritis", feature="omega3_density",
        display_name="Omega-3 density", coefficient=0.50,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 0.3},
        mechanism="Omega-3 density is the most relevant nutrient-level anti-inflammatory support for joint symptoms",
        pathway="Eicosanoid balance / anti-inflammatory signaling", organ="Joints",
        confidence_label="High",
    ),
    Rule(
        rule_id="arth_energy_density", domain="arthritis", feature="energy_density",
        display_name="Energy density", coefficient=-0.35,
        curve=CurveType.LINEAR, curve_params={"scale": 0.002, "cap": 1.0},
        mechanism="Energy density drives weight gain and joint load",
        pathway="Adiposity / joint mechanical load", organ="Joints / adipose tissue",
        confidence_label="High",
    ),
    Rule(
        rule_id="arth_ultra_processed", domain="arthritis", feature="ultra_processed_tag",
        display_name="Ultra-processed indicator", coefficient=-0.35,
        curve=CurveType.BINARY_INTENSITY, curve_params={},
        mechanism="Ultra-processed foods track with an inflammatory and weight-promoting dietary pattern",
        pathway="Dietary pattern / adiposity", organ="Joints",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="arth_fiber", domain="arthritis", feature="fiber_density",
        display_name="Fiber density", coefficient=0.25,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Fiber supports metabolic and inflammatory control relevant to joint symptoms",
        pathway="Microbiome / metabolic control", organ="Gut / joints",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="arth_added_sugar", domain="arthritis", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=-0.25,
        curve=CurveType.LINEAR, curve_params={"scale": 0.2, "cap": 1.2},
        mechanism="Added sugar worsens inflammatory burden and weight regulation",
        pathway="Metabolic inflammation / adiposity", organ="Joints",
        confidence_label="High",
    ),
    Rule(
        rule_id="arth_alcohol", domain="arthritis", feature="alcohol_density",
        display_name="Alcohol burden", coefficient=-0.30,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.5},
        mechanism="Alcohol can worsen joint symptoms and inflammatory control",
        pathway="Systemic inflammatory tone", organ="Joints",
        confidence_label="High",
    ),
]

ARTHRITIS_INTERACTIONS: List[Interaction] = []


# -------------------------------------------------------------------
# 10. CANCER-PREVENTIVE DIETARY PATTERN - RISK oriented
# -------------------------------------------------------------------
#
# NOTE ON SIGN RESOLUTION: this domain's source coefficient TABLE lists
# every protective factor (fiber, fruit/veg, whole grain, legume, nut)
# with a POSITIVE magnitude and every adverse factor (UPF, added sugar,
# alcohol, energy density, processed meat, red meat, saturated fat, fried
# food) with a NEGATIVE magnitude - but the document's own "Recommended
# equation" for this RISK-oriented score (C, higher = worse) applies
# EXACTLY the opposite sign convention to every one of those same terms
# (protective terms subtracted, adverse terms added), which is the only
# internally consistent reading given the stated "higher C = worse
# cancer-promoting pattern" framing and each row's own evidence-basis
# text. The equation's signs are used here as authoritative; the table's
# raw magnitudes were still used for the coefficient's absolute value.

CANCER_RULES: List[Rule] = [
    Rule(
        rule_id="cancer_fiber", domain="cancer", feature="fiber_density",
        display_name="Fiber density", coefficient=-0.80,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Fiber is the strongest, most consistent dietary protective signal for cancer-preventive patterns",
        pathway="Microbiome / SCFA production / bowel transit time", organ="Colon",
        confidence_label="High",
        citation="https://www.wcrf.org",
    ),
    Rule(
        rule_id="cancer_fruit_vegetable", domain="cancer", feature="fruit_vegetable_tag",
        display_name="Fruit / vegetable density", coefficient=-0.70,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Plant-rich patterns are repeatedly recommended for cancer prevention (phytochemicals, fiber, antioxidants)",
        pathway="Phytochemical / antioxidant exposure", organ="Systemic",
        confidence_label="High",
    ),
    Rule(
        rule_id="cancer_whole_grain", domain="cancer", feature="whole_grain_tag",
        display_name="Whole grain tag", coefficient=-0.55,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Whole grains provide more fiber and a lower glycemic load, a more protective pattern quality",
        pathway="Fiber / glycemic load", organ="Colon",
        confidence_label="High",
        citation="https://www.aafp.org/pubs/afp/issues/2000/1001/p1697.html",
    ),
    Rule(
        rule_id="cancer_legume", domain="cancer", feature="legume_tag",
        display_name="Legume tag", coefficient=-0.55,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Legumes are a fiber-rich, plant-forward protein source with a protective pattern signal",
        pathway="Fiber / plant-protein pattern", organ="Colon",
        confidence_label="High",
    ),
    Rule(
        rule_id="cancer_nut_seed", domain="cancer", feature="nut_seed_tag",
        display_name="Nut / seed tag", coefficient=-0.25,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Nuts and seeds are helpful as part of an overall plant-forward dietary pattern",
        pathway="Plant-forward pattern quality", organ="Systemic",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="cancer_ultra_processed", domain="cancer", feature="ultra_processed_tag",
        display_name="Ultra-processed indicator", coefficient=0.70,
        curve=CurveType.BINARY_INTENSITY, curve_params={},
        mechanism="Ultra-processed foods track with poor dietary quality, high energy density, and fewer protective nutrients",
        pathway="Dietary pattern quality", organ="Systemic",
        confidence_label="High",
    ),
    Rule(
        rule_id="cancer_added_sugar", domain="cancer", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=0.45,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 2.0, "scale": 0.2, "steepness_above": 1.5, "cap": 1.5},
        mechanism="Added sugar has an energy-dense, nutrient-poor displacement effect on the overall dietary pattern",
        pathway="Nutrient displacement / energy density", organ="Systemic",
        confidence_label="High",
    ),
    Rule(
        rule_id="cancer_alcohol", domain="cancer", feature="alcohol_density",
        display_name="Alcohol burden", coefficient=0.80,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.1},
        mechanism="Alcohol is one of the clearest diet-related cancer risk drivers",
        pathway="Direct carcinogenicity (acetaldehyde) / hormonal effects", organ="Liver / breast / GI tract",
        confidence_label="High",
        citation="https://www.cancer.org/cancer/risk-prevention/diet-physical-activity/acs-guidelines-nutrition-physical-activity-cancer-prevention.html",
    ),
    Rule(
        rule_id="cancer_energy_density", domain="cancer", feature="energy_density",
        display_name="Energy density", coefficient=0.35,
        curve=CurveType.LINEAR, curve_params={"scale": 0.002, "cap": 1.0},
        mechanism="High energy density supports excess weight, a major preventable cancer risk factor",
        pathway="Adiposity", organ="Adipose tissue / systemic",
        confidence_label="High",
    ),
    Rule(
        rule_id="cancer_processed_meat", domain="cancer", feature="processed_meat_tag",
        display_name="Processed meat burden", coefficient=0.60,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.0},
        mechanism="Processed meat carries a strongly unfavorable cancer-prevention pattern (nitrosamines, heme iron)",
        pathway="Nitrosamine / heme-iron exposure", organ="Colon",
        confidence_label="High",
    ),
    Rule(
        rule_id="cancer_red_meat", domain="cancer", feature="red_meat_tag",
        display_name="Red meat burden", coefficient=0.25,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Red meat carries a modest unfavorable cancer-prevention signal, smaller than processed meat",
        pathway="Heme-iron exposure", organ="Colon",
        confidence_label="Medium-high",
    ),
    Rule(
        rule_id="cancer_saturated_fat", domain="cancer", feature="saturated_fat_density",
        display_name="Saturated fat", coefficient=0.15,
        curve=CurveType.LINEAR, curve_params={"scale": 0.05, "cap": 1.0},
        mechanism="Saturated fat is mostly a pattern-quality proxy for cancer-preventive dietary patterns",
        pathway="Dietary pattern quality", organ="Systemic",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="cancer_fried_food", domain="cancer", feature="fried_food_tag",
        display_name="Fried food burden", coefficient=0.20,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Fried food often co-travels with energy-dense, low-fiber dietary patterns",
        pathway="Dietary pattern quality", organ="Systemic",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="cancer_dairy_quality", domain="cancer", feature="dairy_or_fortified_tag",
        display_name="Dairy quality", coefficient=-0.05,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Dairy's cancer-prevention relevance is kept neutral-to-small absent a specific cancer-subtype model",
        pathway="Pattern-quality proxy", organ="Systemic",
        confidence_label="Low-medium",
    ),
    Rule(
        rule_id="cancer_physical_activity", domain="cancer", feature="physical_activity_proxy",
        display_name="Physical-activity proxy in diet score", coefficient=0.0,
        curve=CurveType.LINEAR, curve_params={"scale": 0.0, "cap": 0.0},
        mechanism="Physical activity is important for cancer prevention but is explicitly excluded from the diet score and better modeled elsewhere",
        pathway="Not modeled in this diet-only module", organ="N/A",
        confidence_label="N/A",
        citation="https://www.cancer.org/cancer/risk-prevention/diet-physical-activity/acs-guidelines-nutrition-physical-activity-cancer-prevention.html",
    ),
]

CANCER_INTERACTIONS: List[Interaction] = [
    Interaction("cancer_int_fiber_upf", "cancer", ("fiber_density", "ultra_processed_tag"),
                "Fiber x Ultra-processed: stronger penalty when fiber is low", None,
                "Low-fiber UPF patterns are especially poor"),
    Interaction("cancer_int_alcohol_upf", "cancer", ("alcohol_density", "ultra_processed_tag"),
                "Alcohol x Ultra-processed: stronger penalty", None,
                "Pattern of low diet quality and higher cancer risk"),
    Interaction("cancer_int_energy_weight", "cancer", ("energy_density",),
                "Energy density x Weight burden: amplify risk", None,
                "Excess body weight is a major preventable cancer risk factor", modifier_gate="high_bmi"),
    Interaction("cancer_int_procmeat_low_fiber", "cancer", ("processed_meat_tag", "fiber_density"),
                "Processed meat x Low fiber: stronger penalty", None, "Poor overall pattern quality"),
    Interaction("cancer_int_fv_wholegrain", "cancer", ("fruit_vegetable_tag", "whole_grain_tag"),
                "Fruit/veg x Whole grains: extra protective bonus", None, "Plant diversity and fiber synergy"),
    Interaction("cancer_int_legume_wholegrain", "cancer", ("legume_tag", "whole_grain_tag"),
                "Legume x Whole grain: extra protective bonus", None, "Strong plant-protein pattern"),
    Interaction("cancer_int_alcohol_addedsugar", "cancer", ("alcohol_density", "added_sugar_density"),
                "Alcohol x Added sugar: stronger penalty", None, "Sugary alcoholic patterns are especially unfavorable"),
]


# -------------------------------------------------------------------
# 11. WEIGHT MANAGEMENT - RISK oriented
# -------------------------------------------------------------------
#
# Same table-vs-equation sign inversion pattern as the Cancer domain (see
# note there) - the equation's signs are used as authoritative here too,
# for the same reasons (internal consistency with the stated "higher W =
# worse weight-management support" framing).

WEIGHT_RULES: List[Rule] = [
    Rule(
        rule_id="weight_fiber", domain="weight", feature="fiber_density",
        display_name="Fiber density", coefficient=-0.90,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 2.0},
        mechanism="Fiber is the strongest satiety and energy-intake support signal",
        pathway="Satiety signaling / gastric distension", organ="Gastrointestinal tract",
        confidence_label="High",
    ),
    Rule(
        rule_id="weight_protein_adequacy", domain="weight", feature="protein_density",
        display_name="Protein adequacy", coefficient=-0.70,
        curve=CurveType.U_SHAPED,
        curve_params={"low_threshold": 4.0, "high_threshold": 6.0, "saturation_point": 4.0},
        mechanism="Protein supports satiety and lean-mass retention during weight management",
        pathway="Satiety signaling / lean mass preservation", organ="Skeletal muscle",
        confidence_label="High",
    ),
    Rule(
        rule_id="weight_ultra_processed", domain="weight", feature="ultra_processed_tag",
        display_name="Ultra-processed indicator", coefficient=0.80,
        curve=CurveType.BINARY_INTENSITY, curve_params={},
        mechanism="Ultra-processed foods are strongly associated with overeating and weight gain",
        pathway="Passive overconsumption", organ="Adipose tissue",
        confidence_label="High",
    ),
    Rule(
        rule_id="weight_energy_density", domain="weight", feature="energy_density",
        display_name="Energy density", coefficient=0.75,
        curve=CurveType.LINEAR, curve_params={"scale": 0.002, "cap": 1.5},
        mechanism="High-energy-density foods promote passive overconsumption",
        pathway="Passive overconsumption", organ="Adipose tissue",
        confidence_label="High",
    ),
    Rule(
        rule_id="weight_liquid_calories", domain="weight", feature="liquid_calories_tag",
        display_name="Liquid calories", coefficient=0.70,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.0},
        mechanism="Liquid calories have poor satiety per calorie and are easy to overconsume",
        pathway="Satiety signaling", organ="Gastrointestinal tract",
        confidence_label="High",
    ),
    Rule(
        rule_id="weight_added_sugar", domain="weight", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=0.55,
        curve=CurveType.PIECEWISE_LINEAR,
        curve_params={"threshold": 2.0, "scale": 0.2, "steepness_above": 1.5, "cap": 1.5},
        mechanism="Added sugar promotes calorie excess and weaker satiety",
        pathway="Satiety signaling / calorie excess", organ="Adipose tissue",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="weight_refined_grain", domain="weight", feature="refined_grain_tag",
        display_name="Refined grain burden", coefficient=0.35,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Refined grains provide lower satiety than intact whole grains",
        pathway="Satiety signaling", organ="Gastrointestinal tract",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="weight_saturated_fat", domain="weight", feature="saturated_fat_density",
        display_name="Saturated fat", coefficient=0.20,
        curve=CurveType.LINEAR, curve_params={"scale": 0.05, "cap": 1.0},
        mechanism="Saturated fat often co-travels with energy-dense foods",
        pathway="Energy-density proxy", organ="Adipose tissue",
        confidence_label="Low-medium",
    ),
    Rule(
        rule_id="weight_nut_seed", domain="weight", feature="nut_seed_tag",
        display_name="Nut / seed tag", coefficient=-0.20,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Nuts and seeds help satiety in some dietary patterns despite their calorie density",
        pathway="Satiety signaling", organ="Gastrointestinal tract",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="weight_whole_grain", domain="weight", feature="whole_grain_tag",
        display_name="Whole grain tag", coefficient=-0.35,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Whole grains provide better fiber content and fullness than refined grains",
        pathway="Satiety signaling", organ="Gastrointestinal tract",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="weight_legume", domain="weight", feature="legume_tag",
        display_name="Legume tag", coefficient=-0.40,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Legumes offer high satiety through combined fiber and protein",
        pathway="Satiety signaling", organ="Gastrointestinal tract",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="weight_fruit_vegetable", domain="weight", feature="fruit_vegetable_tag",
        display_name="Fruit / vegetable tag", coefficient=-0.30,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Fruits and vegetables have low energy density and high volume, supporting satiety",
        pathway="Satiety signaling / gastric volume", organ="Gastrointestinal tract",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="weight_meal_regularity", domain="weight", feature="meal_regularity",
        display_name="Meal regularity / structure", coefficient=-0.25,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Regular meal structure helps reduce random overeating",
        pathway="Eating-pattern regulation", organ="Systemic",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="weight_alcohol", domain="weight", feature="alcohol_density",
        display_name="Alcohol burden", coefficient=0.25,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.5},
        mechanism="Alcohol adds calories and often weakens dietary self-control",
        pathway="Calorie addition / self-control", organ="Adipose tissue / brain",
        confidence_label="Medium",
    ),
]

WEIGHT_INTERACTIONS: List[Interaction] = [
    Interaction("weight_int_fiber_upf", "weight", ("fiber_density", "ultra_processed_tag"),
                "Fiber x Ultra-processed: stronger penalty when fiber is low", None,
                "Low-fiber UPF patterns are especially overeating-prone"),
    Interaction("weight_int_protein_fiber", "weight", ("protein_density", "fiber_density"),
                "Protein x Fiber: extra satiety bonus", None, "Better fullness than either alone"),
    Interaction("weight_int_liquidcal_addedsugar", "weight", ("liquid_calories_tag", "added_sugar_density"),
                "Liquid calories x Added sugar: stronger penalty", None,
                "Sugary drinks are hard to compensate for"),
    Interaction("weight_int_energy_portion", "weight", ("energy_density",),
                "Energy density x Portion size: amplify risk", None,
                "Large portions of dense food are most problematic"),
    Interaction("weight_int_upf_liquidcal", "weight", ("ultra_processed_tag", "liquid_calories_tag"),
                "Ultra-processed x Liquid calories: strongest penalty", None,
                "Common high-overconsumption pattern"),
    Interaction("weight_int_protein_resistance_training", "weight", ("protein_density",),
                "Protein x Resistance training context: increase benefit", None,
                "Lean mass retention matters more", modifier_gate="resistance_training"),
]


# -------------------------------------------------------------------
# 12. MUSCLE / PHYSICAL PERFORMANCE / HEALTHY AGING - SUPPORT oriented
# -------------------------------------------------------------------

MUSCLE_RULES: List[Rule] = [
    Rule(
        rule_id="muscle_protein_adequacy", domain="muscle", feature="protein_density",
        display_name="Protein adequacy", coefficient=0.95,
        curve=CurveType.U_SHAPED,
        curve_params={"low_threshold": 4.0, "high_threshold": 6.0, "saturation_point": 4.0},
        mechanism="Adequate protein is the central driver of muscle maintenance and function",
        pathway="Muscle protein synthesis", organ="Skeletal muscle",
        confidence_label="High",
    ),
    Rule(
        rule_id="muscle_protein_quality", domain="muscle", feature="protein_quality_leucine_proxy",
        display_name="Protein quality / leucine proxy", coefficient=0.70,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 0.08},
        mechanism="Higher leucine content per gram of protein more effectively triggers muscle protein synthesis",
        pathway="mTOR pathway activation / muscle protein synthesis", organ="Skeletal muscle",
        confidence_label="High",
    ),
    Rule(
        rule_id="muscle_vitamin_d", domain="muscle", feature="vitamin_d_density",
        display_name="Vitamin D density", coefficient=0.50,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 1.0},
        mechanism="Vitamin D is relevant for muscle strength, myopathy prevention, and fall risk",
        pathway="Muscle fiber function / neuromuscular signaling", organ="Skeletal muscle",
        confidence_label="High",
    ),
    Rule(
        rule_id="muscle_omega3", domain="muscle", feature="omega3_density",
        display_name="Omega-3 density", coefficient=0.35,
        curve=CurveType.SATURATING, curve_params={"saturation_point": 0.3},
        mechanism="Omega-3 fatty acids support muscle function and aging resilience",
        pathway="Anti-inflammatory / anabolic support", organ="Skeletal muscle",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="muscle_energy_adequacy", domain="muscle", feature="energy_adequacy",
        display_name="Energy adequacy", coefficient=0.25,
        curve=CurveType.U_SHAPED,
        curve_params={"low_threshold": 0.9, "high_threshold": 1.0, "saturation_point": 0.3},
        mechanism="Too little energy undermines protein utilization and physical performance",
        pathway="Energy availability / protein-sparing", organ="Skeletal muscle",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="muscle_resistance_training_pattern", domain="muscle", feature="resistance_training_context",
        display_name="Resistance-training compatible pattern", coefficient=0.25,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Diet works best to support muscle adaptation when paired with resistance training",
        pathway="Muscle protein synthesis / training adaptation", organ="Skeletal muscle",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="muscle_whole_grain", domain="muscle", feature="whole_grain_tag",
        display_name="Whole grain tag", coefficient=0.15,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Whole grains support steady energy availability and overall diet quality",
        pathway="Energy availability", organ="Skeletal muscle",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="muscle_fruit_vegetable", domain="muscle", feature="fruit_vegetable_tag",
        display_name="Fruit / vegetable tag", coefficient=0.15,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Fruits and vegetables provide micronutrients and overall health support relevant to aging resilience",
        pathway="Micronutrient support", organ="Skeletal muscle",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="muscle_legume", domain="muscle", feature="legume_tag",
        display_name="Legume tag", coefficient=0.20,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Legumes provide protein plus fiber, useful in healthy-aging dietary patterns",
        pathway="Protein / fiber support", organ="Skeletal muscle",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="muscle_nut_seed", domain="muscle", feature="nut_seed_tag",
        display_name="Nut / seed tag", coefficient=0.10,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Nuts and seeds provide helpful fats and minerals for muscle and bone support",
        pathway="Mineral / fat support", organ="Skeletal muscle",
        confidence_label="Low-medium",
    ),
    Rule(
        rule_id="muscle_ultra_processed", domain="muscle", feature="ultra_processed_tag",
        display_name="Ultra-processed indicator", coefficient=-0.35,
        curve=CurveType.BINARY_INTENSITY, curve_params={},
        mechanism="Ultra-processed foods have lower nutrient density and worse pattern quality for muscle support",
        pathway="Nutrient density proxy", organ="Skeletal muscle",
        confidence_label="High",
    ),
    Rule(
        rule_id="muscle_alcohol", domain="muscle", feature="alcohol_density",
        display_name="Alcohol burden", coefficient=-0.30,
        curve=CurveType.THRESHOLD, curve_params={"threshold": 0.5},
        mechanism="Alcohol can impair recovery, appetite quality, and overall muscle health",
        pathway="Recovery / appetite regulation", organ="Skeletal muscle",
        confidence_label="High",
    ),
    Rule(
        rule_id="muscle_added_sugar", domain="muscle", feature="added_sugar_density",
        display_name="Added sugar density", coefficient=-0.20,
        curve=CurveType.LINEAR, curve_params={"scale": 0.15, "cap": 1.0},
        mechanism="Added sugar displaces nutrient-dense foods and supports poorer metabolic health",
        pathway="Nutrient displacement", organ="Skeletal muscle",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="muscle_low_meal_regularity", domain="muscle", feature="meal_regularity",
        display_name="Low meal regularity", coefficient=-0.20,
        curve=CurveType.BINARY, curve_params={},
        mechanism="Inconsistent intake can impair adequate protein distribution across the day",
        pathway="Protein distribution / muscle protein synthesis timing", organ="Skeletal muscle",
        confidence_label="Medium",
    ),
    Rule(
        rule_id="muscle_low_calcium_pattern", domain="muscle", feature="calcium_density",
        display_name="Low calcium / bone-support pattern", coefficient=-0.10,
        curve=CurveType.INVERSE, curve_params={"reference": 80.0},
        mechanism="Bone and muscle health are linked, especially in older adults",
        pathway="Bone-muscle axis", organ="Bone / skeletal muscle",
        confidence_label="Low-medium",
    ),
]

MUSCLE_INTERACTIONS: List[Interaction] = [
    Interaction("muscle_int_protein_resistance_training", "muscle", ("protein_density",),
                "Protein x Resistance training: extra protective bonus", None,
                "Muscle adaptation is strongest with training", modifier_gate="resistance_training"),
    Interaction("muscle_int_protein_energy_adequacy", "muscle", ("protein_density", "energy_adequacy"),
                "Protein x Energy adequacy: extra protective bonus", None,
                "Protein works better when energy is sufficient"),
    Interaction("muscle_int_proteinquality_olderage", "muscle", ("protein_quality_leucine_proxy",),
                "Protein quality x Older age: increase weight", None,
                "Older adults benefit more from high-quality protein distribution", modifier_gate="older_adult"),
    Interaction("muscle_int_vitamind_protein", "muscle", ("vitamin_d_density", "protein_density"),
                "Vitamin D x Protein: extra protective bonus", None, "Common sarcopenia support pairing"),
    Interaction("muscle_int_omega3_low_activity", "muscle", ("omega3_density",),
                "Omega-3 x Low activity: smaller benefit", None,
                "Still helpful, but less than with training", modifier_gate="low_activity"),
    Interaction("muscle_int_upf_low_protein", "muscle", ("ultra_processed_tag", "protein_density"),
                "Ultra-processed x Low protein: stronger penalty", None, "Nutrient-poor, low-anabolic pattern"),
    Interaction("muscle_int_alcohol_low_protein", "muscle", ("alcohol_density", "protein_density"),
                "Alcohol x Low protein: stronger penalty", None, "Recovery and intake quality worsen"),
]


# -------------------------------------------------------------------
# 13. GUT HEALTH - intentionally empty (no dedicated module in source)
# -------------------------------------------------------------------
#
# The coefficient reference document has no dedicated "Gut Health"
# section - it is referenced in passing once ("IBD-associated arthritis:
# reuse gut-health penalties and benefits", in the Inflammation domain's
# population-modifier notes) but never actually elaborated with its own
# coefficient table. Rather than fabricate gut-specific coefficients that
# aren't in the source, this is left empty. Gut-relevant mechanisms
# (fiber -> SCFA production -> microbiome, already the FIBER example
# given in the original task spec) are captured through the existing
# fiber_density rules across Blood Sugar, Heart, Liver, Bone,
# Inflammation, and Cancer, which is where the source document itself
# places gut/microbiome-mediated effects.

GUT_RULES: List[Rule] = []
GUT_INTERACTIONS: List[Interaction] = []


# =========================================================================
# POPULATION MODIFIERS
# =========================================================================
#
# Every modifier referenced by an Interaction's modifier_gate above (ckd,
# hypertension, diabetes, obesity, high_triglycerides, weight_loss,
# osteoarthritis, rheumatoid_arthritis, high_bmi, resistance_training,
# older_adult, low_sun_exposure, low_sleep, low_b_vitamin_status,
# low_activity) is registered here, PLUS every population modifier the
# source document names even where it doesn't tie to a specific
# interaction line (PCOS, athlete/high-energy-demand, children/
# adolescents, heart failure, dyslipidemia, postmenopausal,
# lactose-intolerant/low-dairy, vegetarian/vegan, steroid use, frailty,
# low appetite, depression/anxiety, low fish intake, pregnancy/lactation,
# colon-cancer focus, breast-cancer focus, low plant intake, heavy
# alcohol use, smoking, active weight loss, weight maintenance,
# binge-eating tendency).
#
# ALL enabled_by_default=False per spec - population modifiers exist so a
# future caller can pass active_modifiers=(...) to attach_evidence(), but
# none are ever applied automatically.
#
# MULTIPLIER VALUES: the source document describes every one of these
# qualitatively ("increases X importance", "sharply increases", "reduces
# (but does not eliminate)") rather than with an exact number - it never
# gives a numeric multiplier for a population modifier the way it does for
# many interaction coefficients. Each multiplier below is therefore an
# engineering default consistent with that qualitative direction and
# intensity, on a fixed three-tier scale so the mapping stays auditable:
#   1.25x - the default "increases importance/relevance/penalty" tier
#   1.4x  / 1.6x - used only where the source uses stronger language
#                   ("further", "sharply") for that specific modifier
#   0.75x / 0.80x - "reduces" / "lowers the magnitude of" tier
#   1.0x  (no-op) - modifiers with no affected_features (e.g. "smoking",
#                   which the source explicitly handles outside the diet
#                   module) - multiplying nothing is a no-op regardless
# These affect a rule's effective_weight only (coefficient x confidence),
# never the raw feature_value or the curve-evaluated magnitude - see
# process_feature()/process_ingredient() below.

POPULATION_MODIFIERS: List[PopulationModifier] = [
    PopulationModifier("ckd", "kidney", "Chronic kidney disease",
                        "Increases sodium/phosphorus/protein sensitivity; gates potassium benefit",
                        affected_features=("sodium_density", "potassium_density", "protein_density", "phosphorus_density"),
                        multiplier=1.3),
    PopulationModifier("hypertension", "blood_pressure", "Hypertension",
                        "Increases sodium penalty and sodium-potassium interaction weight",
                        affected_features=("sodium_density", "potassium_density", "alcohol_density"),
                        multiplier=1.3),
    PopulationModifier("diabetes", "kidney", "Diabetes / prediabetes",
                        "Increases glycemic load and added sugar importance across glycemia-linked domains",
                        affected_features=("glycemic_load", "added_sugar_density"),
                        multiplier=1.3),
    PopulationModifier("pcos", "blood_sugar", "PCOS", "Treated similarly to prediabetes",
                        affected_features=("glycemic_load", "added_sugar_density", "liquid_sugar_tag"),
                        multiplier=1.3),
    PopulationModifier("obesity", "kidney", "Obesity / weight-loss context",
                        "Increases ultra-processed, energy-density, and added-sugar penalties",
                        affected_features=("energy_density", "ultra_processed_tag", "added_sugar_density"),
                        multiplier=1.3),
    PopulationModifier("athlete_high_energy_demand", "blood_sugar", "Athlete / high energy demand",
                        "Reduces the carbohydrate-density penalty when the food is otherwise low-sugar, high-fiber",
                        affected_features=("carbohydrate_density",),
                        multiplier=0.75),
    PopulationModifier("older_adult", "bone", "Older adult",
                        "Increases protein, calcium, vitamin D, protein-quality, and fall-risk relevance",
                        affected_features=("protein_density", "calcium_density", "vitamin_d_density", "protein_quality_leucine_proxy"),
                        multiplier=1.25),
    PopulationModifier("children_adolescents", "blood_sugar", "Children / adolescents",
                        "Increases liquid-sugar and added-sugar penalties",
                        affected_features=("liquid_sugar_tag", "added_sugar_density"),
                        multiplier=1.25),
    PopulationModifier("heart_failure", "blood_pressure", "Heart failure", "Increases sodium importance further",
                        affected_features=("sodium_density",),
                        multiplier=1.4),
    PopulationModifier("dyslipidemia", "blood_pressure", "Dyslipidemia",
                        "Increases saturated fat and trans fat weights",
                        affected_features=("saturated_fat_density", "trans_fat_density"),
                        multiplier=1.3),
    PopulationModifier("high_triglycerides", "heart", "High triglycerides",
                        "Increases omega-3, added sugar, and alcohol relevance",
                        affected_features=("omega3_density", "added_sugar_density", "alcohol_density"),
                        multiplier=1.3),
    PopulationModifier("weight_loss", "liver", "Rapid / active weight loss",
                        "Reduces over-penalization of protein and energy-restriction patterns; increases protein/fiber/energy-density relevance",
                        affected_features=("protein_density", "fiber_density", "energy_density"),
                        multiplier=1.2),
    PopulationModifier("postmenopausal", "bone", "Postmenopausal women",
                        "Increases calcium and vitamin D importance",
                        affected_features=("calcium_density", "vitamin_d_density"),
                        multiplier=1.3),
    PopulationModifier("low_sun_exposure", "bone", "Low sun exposure", "Increases vitamin D relevance",
                        affected_features=("vitamin_d_density",),
                        multiplier=1.4),
    PopulationModifier("low_dairy_lactose_intolerant", "bone", "Lactose intolerance / low dairy intake",
                        "Increases fortified-alternative tag importance",
                        affected_features=("dairy_or_fortified_tag",),
                        multiplier=1.25),
    PopulationModifier("vegetarian_vegan", "bone", "Vegetarian / vegan pattern",
                        "Increases attention to calcium, vitamin D, protein, B12, iron, choline, and fortified foods",
                        affected_features=("calcium_density", "vitamin_d_density", "protein_density", "protein_quality_leucine_proxy", "iron_density", "choline_density"),
                        multiplier=1.25),
    PopulationModifier("steroid_use", "bone", "Steroid use", "Increases all bone-supportive nutrient weights",
                        affected_features=("calcium_density", "vitamin_d_density", "vitamin_k_density", "magnesium_density"),
                        multiplier=1.3),
    PopulationModifier("low_sleep", "brain", "Low sleep / shift work",
                        "Increases caffeine sensitivity and glycemic-stability importance",
                        affected_features=("caffeine_density", "glycemic_load"),
                        multiplier=1.25),
    PopulationModifier("low_b_vitamin_status", "brain", "Suboptimal / deficient B-vitamin status",
                        "B-vitamin density's cognitive/mood benefit is strongest when intake is currently "
                        "low or borderline-deficient; increases the weight of the B-vitamin density index",
                        affected_features=("b_vitamin_density_index",),
                        multiplier=1.3),
    PopulationModifier("depression_anxiety", "brain", "Depression / anxiety",
                        "Increases alcohol and caffeine penalties",
                        affected_features=("alcohol_density", "caffeine_density"),
                        multiplier=1.25),
    PopulationModifier("low_fish_intake", "brain", "Low fish intake", "Increases omega-3 relevance",
                        affected_features=("omega3_density",),
                        multiplier=1.3),
    PopulationModifier("pregnancy_lactation", "brain", "Pregnancy / lactation",
                        "Increases choline, iron, omega-3, and folate relevance",
                        affected_features=("choline_density", "iron_density", "omega3_density"),
                        multiplier=1.3),
    PopulationModifier("rheumatoid_arthritis", "arthritis", "Rheumatoid / psoriatic arthritis / spondyloarthritis",
                        "Increases omega-3 and anti-inflammatory pattern weighting",
                        affected_features=("omega3_density",),
                        multiplier=1.3),
    PopulationModifier("osteoarthritis", "arthritis", "Osteoarthritis",
                        "Increases weight/energy-density and calorie-restriction relevance",
                        affected_features=("energy_density", "central_adiposity_proxy"),
                        multiplier=1.25),
    PopulationModifier("ibd_associated_arthritis", "arthritis", "IBD-associated arthritis",
                        "Reuses gut-health penalties and benefits (fiber-centric)",
                        affected_features=("fiber_density",),
                        multiplier=1.2),
    PopulationModifier("heavy_alcohol_use", "liver", "Heavy alcohol use",
                        "Sharply increases alcohol penalty across all alcohol-sensitive domains",
                        affected_features=("alcohol_density",),
                        multiplier=1.6),
    PopulationModifier("colon_cancer_focus", "cancer", "Colon cancer risk focus",
                        "Increases fiber, whole grain, legume, and red/processed meat penalties",
                        affected_features=("fiber_density", "whole_grain_tag", "legume_tag", "red_meat_tag", "processed_meat_tag"),
                        multiplier=1.3),
    PopulationModifier("breast_cancer_focus", "cancer", "Breast cancer risk focus",
                        "Increases alcohol and energy-density relevance",
                        affected_features=("alcohol_density", "energy_density"),
                        multiplier=1.25),
    PopulationModifier("high_bmi", "cancer", "High BMI", "Increases energy density and ultra-processing penalties",
                        affected_features=("energy_density", "ultra_processed_tag"),
                        multiplier=1.25),
    PopulationModifier("low_plant_intake", "cancer", "Low plant intake",
                        "Increases fruit, vegetable, legume, and whole-grain benefits",
                        affected_features=("fruit_vegetable_tag", "legume_tag", "whole_grain_tag"),
                        multiplier=1.3),
    PopulationModifier("smoking", "cancer", "Smoking",
                        "Handled outside the diet module, but amplifies overall prevention risk", affected_features=(),
                        multiplier=1.0),
    PopulationModifier("active_weight_loss", "weight", "Active weight loss",
                        "Increases protein, fiber, and energy-density relevance",
                        affected_features=("protein_density", "fiber_density", "energy_density"),
                        multiplier=1.25),
    PopulationModifier("weight_maintenance", "weight", "Weight maintenance",
                        "Keeps the same weights but lowers the magnitude of energy-deficit assumptions",
                        affected_features=("energy_density",),
                        multiplier=0.8),
    PopulationModifier("binge_eating_tendency", "weight", "Binge-eating tendency",
                        "Increases ultra-processed and liquid-calorie penalties",
                        affected_features=("ultra_processed_tag", "liquid_calories_tag"),
                        multiplier=1.3),
    PopulationModifier("resistance_training", "muscle", "Resistance training",
                        "Increases protein-quality and timing relevance",
                        affected_features=("protein_density", "protein_quality_leucine_proxy"),
                        multiplier=1.25),
    PopulationModifier("frailty_risk", "muscle", "Frailty risk", "Increases protein and energy-adequacy importance",
                        affected_features=("protein_density", "energy_adequacy"),
                        multiplier=1.3),
    PopulationModifier("low_appetite", "muscle", "Low appetite",
                        "Increases nutrient-density and meal-regularity relevance",
                        affected_features=("meal_regularity",),
                        multiplier=1.2),
    PopulationModifier("low_activity", "muscle", "Low physical activity",
                        "Reduces (but does not eliminate) the omega-3 muscle-support benefit",
                        affected_features=("omega3_density",),
                        multiplier=0.75),
]

_POPULATION_MODIFIER_INDEX: Dict[str, PopulationModifier] = {m.modifier_id: m for m in POPULATION_MODIFIERS}

# feature_key -> [PopulationModifier, ...] whose affected_features includes
# that key - lets process_feature()/process_ingredient() find, in O(1),
# every modifier that could amplify/dampen a given feature's evidence,
# without scanning the full POPULATION_MODIFIERS list per feature per
# ingredient.
_POPULATION_MODIFIER_BY_FEATURE: Dict[str, List[PopulationModifier]] = {}
for _pm in POPULATION_MODIFIERS:
    for _feat in _pm.affected_features:
        _POPULATION_MODIFIER_BY_FEATURE.setdefault(_feat, []).append(_pm)


ALL_DOMAIN_RULES: List[List[Rule]] = [
    BLOOD_SUGAR_RULES, BLOOD_PRESSURE_RULES, HEART_RULES, METABOLIC_SYNDROME_RULES,
    KIDNEY_RULES, LIVER_RULES, BONE_RULES, BRAIN_RULES, INFLAMMATION_RULES,
    ARTHRITIS_RULES, CANCER_RULES, WEIGHT_RULES, MUSCLE_RULES, GUT_RULES,
]

ALL_DOMAIN_INTERACTIONS: List[List[Interaction]] = [
    BLOOD_SUGAR_INTERACTIONS, BLOOD_PRESSURE_INTERACTIONS, HEART_INTERACTIONS,
    METABOLIC_SYNDROME_INTERACTIONS, KIDNEY_INTERACTIONS, LIVER_INTERACTIONS,
    BONE_INTERACTIONS, BRAIN_INTERACTIONS, INFLAMMATION_INTERACTIONS,
    ARTHRITIS_INTERACTIONS, CANCER_INTERACTIONS, WEIGHT_INTERACTIONS,
    MUSCLE_INTERACTIONS, GUT_INTERACTIONS,
]


# =========================================================================
# RULE DATABASE ASSEMBLY + INDEXING
# =========================================================================

_RULE_DATABASE_CACHE: Optional[List[Rule]] = None
_INTERACTION_DATABASE_CACHE: Optional[List[Interaction]] = None
_RULE_INDEX_CACHE: Optional[Dict[str, List[Rule]]] = None
_INTERACTION_INDEX_CACHE: Optional[Dict[str, List[Interaction]]] = None


def load_rule_database(force_reload: bool = False) -> Tuple[List[Rule], List[Interaction]]:
    """
    Assemble every Rule and Interaction across all twelve domains into two
    flat lists. Cached after the first call (the database is static,
    module-level data - there is nothing to invalidate between calls
    within one process).
    """
    global _RULE_DATABASE_CACHE, _INTERACTION_DATABASE_CACHE

    if _RULE_DATABASE_CACHE is not None and not force_reload:
        return _RULE_DATABASE_CACHE, _INTERACTION_DATABASE_CACHE

    all_rules: List[Rule] = []
    all_interactions: List[Interaction] = []
    for domain_rules in ALL_DOMAIN_RULES:
        all_rules.extend(domain_rules)
    for domain_interactions in ALL_DOMAIN_INTERACTIONS:
        all_interactions.extend(domain_interactions)

    # Fail fast (at load time, not mid-traversal) if a rule references a
    # feature key with no registered resolver - a data-entry error, not a
    # runtime data-availability gap.
    unresolved = sorted({r.feature for r in all_rules} - set(FEATURE_RESOLVERS.keys()))
    if unresolved:
        raise RuntimeError(
            f"{len(unresolved)} rule feature key(s) have no registered resolver: {unresolved}"
        )

    _RULE_DATABASE_CACHE = all_rules
    _INTERACTION_DATABASE_CACHE = all_interactions
    logger.info(
        "Loaded evidence rule database: %d rules, %d interactions across %d domains",
        len(all_rules), len(all_interactions), len(ALL_DOMAIN_RULES),
    )
    return all_rules, all_interactions


def initialize_rule_index(force_reload: bool = False) -> Tuple[Dict[str, List[Rule]], Dict[str, List[Interaction]]]:
    """
    Build (once, cached) a feature_key -> [Rule, ...] index and a
    feature_key -> [Interaction, ...] index (indexed by each of an
    interaction's constituent features), so process_feature() never has
    to scan the full rule list - O(1) dict lookup per feature regardless
    of how many hundreds of ingredients are processed.
    """
    global _RULE_INDEX_CACHE, _INTERACTION_INDEX_CACHE

    if _RULE_INDEX_CACHE is not None and not force_reload:
        return _RULE_INDEX_CACHE, _INTERACTION_INDEX_CACHE

    rules, interactions = load_rule_database(force_reload=force_reload)

    rule_index: Dict[str, List[Rule]] = {}
    for rule in rules:
        rule_index.setdefault(rule.feature, []).append(rule)

    interaction_index: Dict[str, List[Interaction]] = {}
    for interaction in interactions:
        for feat in interaction.features:
            interaction_index.setdefault(feat, []).append(interaction)

    _RULE_INDEX_CACHE = rule_index
    _INTERACTION_INDEX_CACHE = interaction_index
    return rule_index, interaction_index


def find_matching_rules(feature_key: str, rule_index: Dict[str, List[Rule]]) -> List[Rule]:
    """O(1) lookup of every rule keyed to `feature_key`."""
    return rule_index.get(feature_key, [])


# =========================================================================
# INTERACTIONS
# =========================================================================

def _interaction_feature_available(value: Any) -> bool:
    """Boolean conditions must be true; numeric conditions may include zero.

    Numeric interaction semantics such as "low fiber" are defined by the
    interaction text/rules and therefore cannot be inferred merely from
    truthiness. This guard primarily prevents False food tags from firing.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return bool(value)

def evaluate_interactions(
    entity: Dict[str, Any],
    feature_values: Dict[str, Any],
    interaction_index: Dict[str, List[Interaction]],
    active_modifiers: Tuple[str, ...] = (),
) -> List[Dict[str, Any]]:
    """
    For every Interaction whose constituent features are all present
    (non-None) on this entity, and whose modifier_gate (if any) is active,
    emit an interaction evidence record. Interactions never fire on their
    own steam - they only annotate/co-occur alongside the base rules for
    their constituent features, so an interaction with any missing
    feature simply produces nothing (never a fabricated partial result).
    """
    seen_ids = set()
    results: List[Dict[str, Any]] = []

    for feat, candidates in interaction_index.items():
        if feat not in feature_values:
            continue
        for interaction in candidates:
            if interaction.interaction_id in seen_ids:
                continue
            if not all(_interaction_feature_available(feature_values.get(f)) for f in interaction.features):
                continue
            if interaction.modifier_gate is not None and interaction.modifier_gate not in active_modifiers:
                continue
            seen_ids.add(interaction.interaction_id)
            results.append({
                "interaction_id": interaction.interaction_id,
                "domain": interaction.domain,
                "health_domain": DOMAIN_HEALTH_LABEL.get(interaction.domain, interaction.domain),
                "features": list(interaction.features),
                "feature_values": {f: feature_values.get(f) for f in interaction.features},
                "rule_text": interaction.rule_text,
                "coefficient": interaction.coefficient,
                "mechanism": interaction.mechanism,
                "modifier_gate": interaction.modifier_gate,
                "modifier_active": interaction.modifier_gate in active_modifiers if interaction.modifier_gate else None,
            })

    return results


# =========================================================================
# PER-FEATURE / PER-ENTITY PROCESSING
# =========================================================================

def process_feature(
    feature_key: str,
    entity: Dict[str, Any],
    rule_index: Dict[str, List[Rule]],
    active_modifiers: Tuple[str, ...] = (),
    interaction_records: Sequence[Dict[str, Any]] = (),
) -> List[Dict[str, Any]]:
    """
    Resolve `feature_key` on `entity` once, then build zero, one, or many
    evidence objects - one per matching Rule whose curve evaluates to a
    non-zero magnitude at the observed value.

    `interaction_records` is the full set of interaction records already
    computed for this entity by evaluate_interactions() (empty by
    default, e.g. when calling process_feature() standalone without
    interaction context) - build_evidence() filters it down to just the
    records naming this feature, so each evidence object's
    interaction_multiplier/applied_interactions reflect only the
    interactions actually relevant to it.

    If any modifier in `active_modifiers` lists `feature_key` in its
    `affected_features` (see POPULATION_MODIFIERS), that modifier's
    `multiplier` is applied on top of build_evidence()'s own
    effective_weight, and the modifier's id is recorded in the evidence
    object's "population_modifiers_applied" list for full traceability.
    With no active_modifiers (the default), this list is always empty.
    """
    rules = find_matching_rules(feature_key, rule_index)
    if not rules:
        return []

    value = resolve_feature_value(feature_key, entity)
    if value is None:
        return []

    applicable_modifiers = [
        m for m in _POPULATION_MODIFIER_BY_FEATURE.get(feature_key, [])
        if m.modifier_id in active_modifiers
    ]

    evidence_objects = []
    for rule in rules:
        magnitude = evaluate_threshold(rule, value)
        if magnitude <= 0.0:
            continue
        evidence = build_evidence(rule, value, magnitude, interaction_records)
        if applicable_modifiers:
            combined_multiplier = 1.0
            for m in applicable_modifiers:
                combined_multiplier *= m.multiplier
            evidence["effective_weight"] = round(evidence["effective_weight"] * combined_multiplier, 4)
            if evidence["direction"] == "positive":
                evidence["raw_effect"] = round(evidence["effective_weight"], 6)
            elif evidence["direction"] == "negative":
                evidence["raw_effect"] = round(-evidence["effective_weight"], 6)
            else:
                evidence["raw_effect"] = 0.0
            evidence["population_modifiers_applied"] = [m.modifier_id for m in applicable_modifiers]
        else:
            evidence["population_modifiers_applied"] = []
        evidence_objects.append(evidence)
    return evidence_objects


def process_ingredient(
    entity: Dict[str, Any],
    rule_index: Optional[Dict[str, List[Rule]]] = None,
    interaction_index: Optional[Dict[str, List[Interaction]]] = None,
    active_modifiers: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    """
    Mutates and returns `entity` (a food, ingredient, or spice - the logic
    is identical regardless) with an "evidence" key attached:

        entity["evidence"] = {
            "items": [ <evidence object>, ... ],
            "interactions": [ <interaction record>, ... ],
        }

    The entity itself (name, features, nutrients, etc.) is left fully
    intact - evidence is additive. Feature values are resolved once for
    every indexed feature key, interactions are evaluated from that
    complete set (an interaction can't be evaluated until every one of
    its constituent features has been resolved), and only then are
    evidence objects built - via process_feature(), so there is exactly
    one place that turns a resolved value into evidence objects - with
    each rule's own relevant interaction records already available to
    feed its interaction_multiplier / applied_interactions.
    """
    if rule_index is None or interaction_index is None:
        rule_index, interaction_index = initialize_rule_index()

    feature_values: Dict[str, Any] = {
        feature_key: resolve_feature_value(feature_key, entity) for feature_key in rule_index.keys()
    }

    interaction_records = evaluate_interactions(entity, feature_values, interaction_index, active_modifiers)

    evidence_items: List[Dict[str, Any]] = []
    for feature_key in rule_index.keys():
        evidence_items.extend(
            process_feature(feature_key, entity, rule_index, active_modifiers, interaction_records)
        )

    entity["evidence"] = {
        "items": evidence_items,
        "interactions": interaction_records,
    }
    return entity


def process_food(
    food: Dict[str, Any],
    rule_index: Optional[Dict[str, List[Rule]]] = None,
    interaction_index: Optional[Dict[str, List[Interaction]]] = None,
    active_modifiers: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    """Attach evidence to a top-level food and recurse into its
    ingredients and spices, at whatever depth they actually appear.

    In the current Nutrica pipeline, DECOMPOSE foods carry exactly one
    level of ingredients/spices (DIRECT_USDA / NUTRITION_LABEL foods
    simply have empty ingredients/spices lists, so this is a no-op for
    them) - matching feature_engineering.py's own traversal. This
    function doesn't assume that shape, though: it recurses into an
    ingredient's or spice's own "ingredients"/"spices" fields too, so a
    future or malformed payload with deeper nesting still gets
    "evidence" attached at every level rather than silently stopping
    after one level.
    """
    if rule_index is None or interaction_index is None:
        rule_index, interaction_index = initialize_rule_index()

    process_ingredient(food, rule_index, interaction_index, active_modifiers)

    for ingredient in food.get("ingredients") or []:
        process_food(ingredient, rule_index, interaction_index, active_modifiers)

    for spice in food.get("spices") or []:
        process_food(spice, rule_index, interaction_index, active_modifiers)

    return food


def process_meal(
    meal_json: Dict[str, Any],
    active_modifiers: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    """
    Deep-copies `meal_json`, attaches "evidence" to every food, ingredient,
    and spice, and returns the enriched copy. The input is never mutated.
    """
    if not isinstance(meal_json, dict) or "meal" not in meal_json:
        raise ValueError("Input must be a dict with a top-level 'meal' key")

    result = copy.deepcopy(meal_json)
    rule_index, interaction_index = initialize_rule_index()

    foods = result.get("meal", {}).get("foods", []) or []
    for food in foods:
        process_food(food, rule_index, interaction_index, active_modifiers)

    return result


# =========================================================================
# PUBLIC ENTRY POINTS
# =========================================================================

async def attach_evidence(
    meal_json: Dict[str, Any],
    active_modifiers: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    """
    Main entry point. Takes a meal JSON that has already been through
    feature_engineering.compute_features() (every food/ingredient/spice
    already carries a "features" dict) and returns a deep copy where every
    food, ingredient, and spice also carries an "evidence" dict.

    `active_modifiers` activates population modifiers by their
    modifier_id (see POPULATION_MODIFIERS) - empty by default, matching
    the spec's "disabled by default" requirement.

    This function performs no I/O and needs nothing awaited internally -
    it's async purely so this phase composes naturally with the other
    three async pipeline phases.
    """
    return process_meal(meal_json, active_modifiers=active_modifiers)


def attach_evidence_sync(
    meal_json: Dict[str, Any],
    active_modifiers: Tuple[str, ...] = (),
) -> Dict[str, Any]:
    """
    Synchronous convenience wrapper around attach_evidence().

    Works out of the box in plain scripts, FastAPI background tasks, and
    Celery workers. In notebook environments (Colab/Jupyter) where a loop
    is already running per cell, this detects that automatically and uses
    nest_asyncio if installed, or raises a clear error pointing you at
    `await attach_evidence(...)` if it isn't - same behavior as the rest
    of the Nutrica pipeline (resolve_meal_sync, attach_nutrients_sync,
    compute_features_sync).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(attach_evidence(meal_json, active_modifiers=active_modifiers))

    try:
        import nest_asyncio  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "attach_evidence_sync() was called from inside a running event "
            "loop (this is normal in Colab/Jupyter). Either:\n"
            "  1) use `await attach_evidence(meal_json)` directly, or\n"
            "  2) `pip install nest_asyncio`, then `import nest_asyncio; "
            "nest_asyncio.apply()` before calling attach_evidence_sync()."
        ) from exc

    nest_asyncio.apply()
    return asyncio.run(attach_evidence(meal_json, active_modifiers=active_modifiers))
