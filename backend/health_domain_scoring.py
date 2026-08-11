from __future__ import annotations

import asyncio
import copy
import logging
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


# =========================================================================
# LOGGING
# =========================================================================

logger = logging.getLogger("nutrica.health_domain_scoring")

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    )
    logger.addHandler(handler)

logger.setLevel(
    os.environ.get(
        "NUTRICA_LOG_LEVEL",
        "INFO",
    )
)

logger.propagate = False


# =========================================================================
# CONFIG
# =========================================================================

SCORING_VERSION = "1.1"

SCORE_MIN = 0.0
SCORE_MAX = 100.0
SCORE_NEUTRAL = 50.0

DEFAULT_TOP_N = 5
DEFAULT_COVERAGE_SATURATION = 10.0

# A score based on one thin evidence item should not immediately become
# 0 or 100. The directional score is therefore pulled toward neutral in
# proportion to the reliability of the evidence base.
DEFAULT_RELIABILITY_ADJUSTMENT = True

_ROUND_DP = 2
_EPSILON = 1e-12


def _round(
    value: float,
    dp: int = _ROUND_DP,
) -> float:
    return round(value, dp)


def _finite_number(
    value: Any,
    *,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
    default: float = 0.0,
) -> float:
    if value is None or isinstance(value, bool):
        return default

    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(number):
        return default

    if minimum is not None:
        number = max(minimum, number)

    if maximum is not None:
        number = min(maximum, number)

    return number


def _effective_weight(
    evidence_item: Dict[str, Any],
) -> float:
    return _finite_number(
        evidence_item.get("effective_weight"),
        minimum=0.0,
    )


def _confidence_value(
    evidence_item: Dict[str, Any],
) -> float:
    return _finite_number(
        evidence_item.get("confidence"),
        minimum=0.0,
        maximum=1.0,
    )


def _is_signal_item(
    evidence_item: Any,
) -> bool:
    if not isinstance(evidence_item, dict):
        return False

    direction = evidence_item.get("direction")

    if direction not in {
        "positive",
        "negative",
        "neutral",
    }:
        return False

    return _effective_weight(evidence_item) > _EPSILON


# =========================================================================
# DATA STRUCTURES
# =========================================================================

@dataclass
class DomainAccumulator:
    """
    Collects evidence for one canonical domain key.

    The evidence engine emits both:
      - domain: canonical machine key, such as "blood_sugar"
      - health_domain: presentation label, such as "Glycemic Control"

    Scoring groups by the canonical key so labels can change without
    changing API keys or combining unrelated domains.
    """

    domain: str
    health_domain: str
    evidence_items: List[Dict[str, Any]] = field(
        default_factory=list
    )

    def add(
        self,
        evidence_item: Dict[str, Any],
    ) -> None:
        self.evidence_items.append(
            evidence_item
        )

    def __len__(self) -> int:
        return len(self.evidence_items)


@dataclass(frozen=True)
class DomainScore:
    """Complete scoring result for one health domain."""

    domain: str
    health_domain: str
    score: float
    directional_score: float
    confidence: float
    coverage: float
    reliability: float

    positive_evidence: int
    negative_evidence: int
    neutral_evidence: int

    positive_weight: float
    negative_weight: float
    net_effect: float
    total_weight: float

    mechanisms: Tuple[str, ...]
    pathways: Tuple[str, ...]
    top_positive_features: Tuple[str, ...]
    top_negative_features: Tuple[str, ...]

    positive_contributors: Tuple[
        Dict[str, Any],
        ...,
    ]
    negative_contributors: Tuple[
        Dict[str, Any],
        ...,
    ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "health_domain": self.health_domain,
            "score": self.score,
            "directional_score": (
                self.directional_score
            ),
            "confidence": self.confidence,
            "coverage": self.coverage,
            "reliability": self.reliability,
            "positive_evidence": (
                self.positive_evidence
            ),
            "negative_evidence": (
                self.negative_evidence
            ),
            "neutral_evidence": (
                self.neutral_evidence
            ),
            "positive_weight": (
                self.positive_weight
            ),
            "negative_weight": (
                self.negative_weight
            ),
            "net_effect": self.net_effect,
            "total_weight": self.total_weight,
            "mechanisms": list(
                self.mechanisms
            ),
            "pathways": list(
                self.pathways
            ),
            "top_positive_features": list(
                self.top_positive_features
            ),
            "top_negative_features": list(
                self.top_negative_features
            ),
            "positive_contributors": [
                dict(contributor)
                for contributor
                in self.positive_contributors
            ],
            "negative_contributors": [
                dict(contributor)
                for contributor
                in self.negative_contributors
            ],
        }


# =========================================================================
# STRATEGY: NORMALIZATION
# =========================================================================

class DomainNormalizer:
    """Convert positive and negative weight to a 0-100 score."""

    def normalize(
        self,
        positive_weight: float,
        negative_weight: float,
    ) -> float:
        raise NotImplementedError


class LinearRatioNormalizer(
    DomainNormalizer
):
    """
    score = 50 + 50 * (net / total).

    This represents the direction and balance of the available evidence.
    The DomainAggregator optionally adjusts this directional score toward
    neutral according to confidence and coverage.
    """

    def normalize(
        self,
        positive_weight: float,
        negative_weight: float,
    ) -> float:
        total = (
            positive_weight
            + negative_weight
        )

        if total <= _EPSILON:
            return SCORE_NEUTRAL

        ratio = (
            positive_weight
            - negative_weight
        ) / total

        score = (
            SCORE_NEUTRAL
            + SCORE_NEUTRAL * ratio
        )

        return _round(
            max(
                SCORE_MIN,
                min(
                    score,
                    SCORE_MAX,
                ),
            )
        )


class SigmoidNormalizer(
    DomainNormalizer
):
    """
    Alternative magnitude-sensitive normalizer.

    Extreme net values are clipped before exponentiation to avoid
    overflow with unusually large custom coefficients.
    """

    def __init__(
        self,
        steepness: float = 1.0,
    ):
        self.steepness = float(
            steepness
        )

    def normalize(
        self,
        positive_weight: float,
        negative_weight: float,
    ) -> float:
        net = (
            positive_weight
            - negative_weight
        )

        exponent = max(
            -60.0,
            min(
                60.0,
                -self.steepness * net,
            ),
        )

        score = (
            SCORE_MAX
            / (
                1.0
                + math.exp(exponent)
            )
        )

        return _round(
            max(
                SCORE_MIN,
                min(
                    score,
                    SCORE_MAX,
                ),
            )
        )


# =========================================================================
# STRATEGY: COVERAGE
# =========================================================================

class CoverageCalculator:
    """Calculate evidence coverage in [0, 1]."""

    def calculate(
        self,
        evidence_items: List[
            Dict[str, Any]
        ],
    ) -> float:
        raise NotImplementedError


class DefaultCoverageCalculator(
    CoverageCalculator
):
    """
    Combines evidence count with mechanism and pathway diversity.

    Only non-zero signal items are included. A rule with zero effective
    weight must not increase coverage.
    """

    def __init__(
        self,
        saturation: float = (
            DEFAULT_COVERAGE_SATURATION
        ),
    ):
        if saturation <= 0:
            raise ValueError(
                "Coverage saturation must "
                "be greater than zero."
            )

        self.saturation = float(
            saturation
        )

    def calculate(
        self,
        evidence_items: List[
            Dict[str, Any]
        ],
    ) -> float:
        signal_items = [
            item
            for item in evidence_items
            if _is_signal_item(item)
        ]

        if not signal_items:
            return 0.0

        # Repeated instances of the same rule (for example the same
        # nutrient mechanism emitted by several ingredient rows) must not
        # manufacture extra certainty. Coverage measures distinct evidence
        # mechanisms, not row count.
        unique_rules = {
            item.get("rule_id") or (item.get("feature"), item.get("mechanism"))
            for item in signal_items
        }

        mechanisms = {
            item.get("mechanism")
            for item in signal_items
            if item.get("mechanism")
        }

        pathways = {
            item.get("pathway")
            for item in signal_items
            if item.get("pathway")
        }

        signal = (
            len(unique_rules)
            + 0.5 * len(mechanisms)
            + 0.5 * len(pathways)
        )

        coverage = (
            1.0
            - math.exp(
                -signal
                / self.saturation
            )
        )

        return _round(
            max(
                0.0,
                min(
                    coverage,
                    1.0,
                ),
            ),
            4,
        )


# =========================================================================
# STRATEGY: CONFIDENCE
# =========================================================================

class ConfidenceCalculator:
    """Calculate confidence in [0, 1]."""

    def calculate(
        self,
        evidence_items: List[
            Dict[str, Any]
        ],
        coverage: float,
    ) -> float:
        raise NotImplementedError


class DefaultConfidenceCalculator(
    ConfidenceCalculator
):
    """
    Weighted average evidence confidence, gently discounted by coverage.
    """

    def calculate(
        self,
        evidence_items: List[
            Dict[str, Any]
        ],
        coverage: float,
    ) -> float:
        signal_items = [
            item
            for item in evidence_items
            if _is_signal_item(item)
        ]

        if not signal_items:
            return 0.0

        total_weight = sum(
            _effective_weight(item)
            for item in signal_items
        )

        if total_weight > _EPSILON:
            weighted_confidence = (
                sum(
                    _confidence_value(item)
                    * _effective_weight(item)
                    for item
                    in signal_items
                )
                / total_weight
            )
        else:
            weighted_confidence = (
                sum(
                    _confidence_value(item)
                    for item
                    in signal_items
                )
                / len(signal_items)
            )

        bounded_coverage = max(
            0.0,
            min(
                float(coverage),
                1.0,
            ),
        )

        coverage_multiplier = (
            0.5
            + 0.5 * bounded_coverage
        )

        confidence = (
            weighted_confidence
            * coverage_multiplier
        )

        return _round(
            max(
                0.0,
                min(
                    confidence,
                    1.0,
                ),
            ),
            4,
        )


# =========================================================================
# EXPLANATION BUILDER
# =========================================================================

class ExplanationBuilder:
    """Build structured contributor and mechanism summaries."""

    def __init__(
        self,
        top_n: int = DEFAULT_TOP_N,
    ):
        if top_n < 1:
            raise ValueError(
                "top_n must be at least 1."
            )

        self.top_n = int(top_n)

    def build(
        self,
        evidence_items: List[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:
        signal_items = [
            item
            for item in evidence_items
            if _is_signal_item(item)
        ]

        positive = aggregate_positive(
            signal_items
        )
        negative = aggregate_negative(
            signal_items
        )

        return {
            "positive_contributors": (
                self._top_contributors(
                    positive
                )
            ),
            "negative_contributors": (
                self._top_contributors(
                    negative
                )
            ),
            "mechanisms": tuple(
                sorted(
                    {
                        item.get(
                            "mechanism"
                        )
                        for item
                        in signal_items
                        if item.get(
                            "mechanism"
                        )
                    }
                )
            ),
            "pathways": tuple(
                sorted(
                    {
                        item.get(
                            "pathway"
                        )
                        for item
                        in signal_items
                        if item.get(
                            "pathway"
                        )
                    }
                )
            ),
            "top_positive_features": (
                self._top_features(
                    positive
                )
            ),
            "top_negative_features": (
                self._top_features(
                    negative
                )
            ),
        }

    def _top_contributors(
        self,
        evidence_items: List[
            Dict[str, Any]
        ],
    ) -> Tuple[
        Dict[str, Any],
        ...,
    ]:
        ranked = sorted(
            evidence_items,
            key=_effective_weight,
            reverse=True,
        )

        return tuple(
            {
                "rule_id": item.get(
                    "rule_id"
                ),
                "rule_name": item.get(
                    "rule_name"
                ),
                "feature": item.get(
                    "feature"
                ),
                "feature_value": item.get(
                    "feature_value"
                ),
                "direction": item.get(
                    "direction"
                ),
                "effective_weight": (
                    _round(
                        _effective_weight(
                            item
                        ),
                        4,
                    )
                ),
                "confidence": (
                    _confidence_value(
                        item
                    )
                ),
                "mechanism": item.get(
                    "mechanism"
                ),
                "pathway": item.get(
                    "pathway"
                ),
                "citation": item.get(
                    "citation"
                ),
            }
            for item in ranked[
                : self.top_n
            ]
        )

    def _top_features(
        self,
        evidence_items: List[
            Dict[str, Any]
        ],
    ) -> Tuple[str, ...]:
        weight_by_feature: Dict[
            str,
            float,
        ] = {}

        for item in evidence_items:
            feature = item.get(
                "feature"
            )

            if not isinstance(
                feature,
                str,
            ) or not feature:
                continue

            weight_by_feature[
                feature
            ] = (
                weight_by_feature.get(
                    feature,
                    0.0,
                )
                + _effective_weight(
                    item
                )
            )

        ranked = sorted(
            weight_by_feature.items(),
            key=lambda pair: pair[1],
            reverse=True,
        )

        return tuple(
            feature
            for feature, _
            in ranked[
                : self.top_n
            ]
        )


# =========================================================================
# CORE AGGREGATION HELPERS
# =========================================================================

def aggregate_positive(
    evidence_items: Iterable[
        Dict[str, Any]
    ],
) -> List[Dict[str, Any]]:
    return [
        item
        for item in evidence_items
        if (
            item.get("direction")
            == "positive"
            and _effective_weight(
                item
            ) > _EPSILON
        )
    ]


def aggregate_negative(
    evidence_items: Iterable[
        Dict[str, Any]
    ],
) -> List[Dict[str, Any]]:
    return [
        item
        for item in evidence_items
        if (
            item.get("direction")
            == "negative"
            and _effective_weight(
                item
            ) > _EPSILON
        )
    ]


def aggregate_neutral(
    evidence_items: Iterable[
        Dict[str, Any]
    ],
) -> List[Dict[str, Any]]:
    return [
        item
        for item in evidence_items
        if (
            item.get("direction")
            == "neutral"
            and _effective_weight(
                item
            ) > _EPSILON
        )
    ]


def calculate_net_effect(
    positive_weight: float,
    negative_weight: float,
) -> float:
    return (
        positive_weight
        - negative_weight
    )


def calculate_reliability(
    confidence: float,
    coverage: float,
) -> float:
    """
    Geometric blend of confidence and coverage.

    This prevents either high confidence with almost no coverage, or high
    coverage made of weak evidence, from appearing fully reliable.
    """

    bounded_confidence = max(
        0.0,
        min(
            float(confidence),
            1.0,
        ),
    )

    bounded_coverage = max(
        0.0,
        min(
            float(coverage),
            1.0,
        ),
    )

    return _round(
        math.sqrt(
            bounded_confidence
            * bounded_coverage
        ),
        4,
    )


def adjust_score_for_reliability(
    directional_score: float,
    reliability: float,
) -> float:
    adjusted = (
        SCORE_NEUTRAL
        + (
            directional_score
            - SCORE_NEUTRAL
        )
        * reliability
    )

    return _round(
        max(
            SCORE_MIN,
            min(
                adjusted,
                SCORE_MAX,
            ),
        )
    )


_DEFAULT_NORMALIZER = (
    LinearRatioNormalizer()
)

_DEFAULT_COVERAGE_CALCULATOR = (
    DefaultCoverageCalculator()
)

_DEFAULT_CONFIDENCE_CALCULATOR = (
    DefaultConfidenceCalculator()
)

_DEFAULT_EXPLANATION_BUILDER = (
    ExplanationBuilder()
)


def normalize_score(
    positive_weight: float,
    negative_weight: float,
    normalizer: Optional[
        DomainNormalizer
    ] = None,
) -> float:
    return (
        normalizer
        or _DEFAULT_NORMALIZER
    ).normalize(
        positive_weight,
        negative_weight,
    )


def calculate_coverage(
    evidence_items: List[
        Dict[str, Any]
    ],
    coverage_calculator: Optional[
        CoverageCalculator
    ] = None,
) -> float:
    return (
        coverage_calculator
        or _DEFAULT_COVERAGE_CALCULATOR
    ).calculate(
        evidence_items
    )


def calculate_confidence(
    evidence_items: List[
        Dict[str, Any]
    ],
    coverage: float,
    confidence_calculator: Optional[
        ConfidenceCalculator
    ] = None,
) -> float:
    return (
        confidence_calculator
        or _DEFAULT_CONFIDENCE_CALCULATOR
    ).calculate(
        evidence_items,
        coverage,
    )


def build_explanation(
    evidence_items: List[
        Dict[str, Any]
    ],
    explanation_builder: Optional[
        ExplanationBuilder
    ] = None,
) -> Dict[str, Any]:
    return (
        explanation_builder
        or _DEFAULT_EXPLANATION_BUILDER
    ).build(
        evidence_items
    )


# =========================================================================
# DOMAIN AGGREGATOR
# =========================================================================

@dataclass
class DomainAggregator:
    normalizer: DomainNormalizer = (
        field(
            default_factory=(
                SigmoidNormalizer
            )
        )
    )

    coverage_calculator: (
        CoverageCalculator
    ) = field(
        default_factory=(
            DefaultCoverageCalculator
        )
    )

    confidence_calculator: (
        ConfidenceCalculator
    ) = field(
        default_factory=(
            DefaultConfidenceCalculator
        )
    )

    explanation_builder: (
        ExplanationBuilder
    ) = field(
        default_factory=(
            ExplanationBuilder
        )
    )

    reliability_adjustment: bool = (
        DEFAULT_RELIABILITY_ADJUSTMENT
    )

    def score(
        self,
        domain: str,
        health_domain: str,
        evidence_items: List[
            Dict[str, Any]
        ],
    ) -> DomainScore:
        valid_items = [
            item
            for item in evidence_items
            if _is_signal_item(item)
        ]

        positive = aggregate_positive(
            valid_items
        )

        negative = aggregate_negative(
            valid_items
        )

        neutral = aggregate_neutral(
            valid_items
        )

        positive_weight = sum(
            _effective_weight(item)
            for item in positive
        )

        negative_weight = sum(
            _effective_weight(item)
            for item in negative
        )

        total_weight = (
            positive_weight
            + negative_weight
        )

        net_effect = (
            calculate_net_effect(
                positive_weight,
                negative_weight,
            )
        )

        coverage = (
            self.coverage_calculator
            .calculate(
                valid_items
            )
        )

        confidence = (
            self.confidence_calculator
            .calculate(
                valid_items,
                coverage,
            )
        )

        directional_score = (
            self.normalizer.normalize(
                positive_weight,
                negative_weight,
            )
        )

        reliability = (
            calculate_reliability(
                confidence,
                coverage,
            )
        )

        if self.reliability_adjustment:
            score_value = (
                adjust_score_for_reliability(
                    directional_score,
                    reliability,
                )
            )
        else:
            score_value = (
                directional_score
            )

        explanation = (
            self.explanation_builder
            .build(
                valid_items
            )
        )

        return DomainScore(
            domain=domain,
            health_domain=health_domain,
            score=score_value,
            directional_score=(
                directional_score
            ),
            confidence=confidence,
            coverage=coverage,
            reliability=reliability,
            positive_evidence=len(
                positive
            ),
            negative_evidence=len(
                negative
            ),
            neutral_evidence=len(
                neutral
            ),
            positive_weight=_round(
                positive_weight,
                4,
            ),
            negative_weight=_round(
                negative_weight,
                4,
            ),
            net_effect=_round(
                net_effect,
                4,
            ),
            total_weight=_round(
                total_weight,
                4,
            ),
            mechanisms=explanation[
                "mechanisms"
            ],
            pathways=explanation[
                "pathways"
            ],
            top_positive_features=(
                explanation[
                    "top_positive_features"
                ]
            ),
            top_negative_features=(
                explanation[
                    "top_negative_features"
                ]
            ),
            positive_contributors=(
                explanation[
                    "positive_contributors"
                ]
            ),
            negative_contributors=(
                explanation[
                    "negative_contributors"
                ]
            ),
        )


_DEFAULT_AGGREGATOR = (
    DomainAggregator()
)


# =========================================================================
# TRAVERSAL
# =========================================================================

def _collect_entity_evidence(
    entity: Dict[str, Any],
    by_domain: Dict[
        str,
        DomainAccumulator,
    ],
) -> None:
    evidence = entity.get(
        "evidence"
    ) or {}

    items = evidence.get(
        "items"
    ) or []

    if not isinstance(items, list):
        return

    for item in items:
        if not isinstance(
            item,
            dict,
        ):
            continue

        canonical_domain = item.get(
            "domain"
        )

        if not isinstance(
            canonical_domain,
            str,
        ) or not canonical_domain:
            continue

        health_domain = item.get(
            "health_domain"
        )

        if not isinstance(
            health_domain,
            str,
        ) or not health_domain:
            health_domain = (
                canonical_domain
            )

        accumulator = by_domain.get(
            canonical_domain
        )

        if accumulator is None:
            accumulator = (
                DomainAccumulator(
                    domain=canonical_domain,
                    health_domain=(
                        health_domain
                    ),
                )
            )

            by_domain[
                canonical_domain
            ] = accumulator

        accumulator.add(item)


def _walk_food(
    food: Dict[str, Any],
    by_domain: Dict[
        str,
        DomainAccumulator,
    ],
) -> None:
    if not isinstance(food, dict):
        return

    _collect_entity_evidence(
        food,
        by_domain,
    )

    # A DECOMPOSE parent whose nutrients were aggregated from components
    # already represents the complete dish. Walking its ingredients and
    # spices again would count the same nutritional exposure twice and
    # artificially increase coverage/reliability.
    if (
        food.get("analysis_route") == "DECOMPOSE"
        and food.get("nutrient_status")
        == "aggregated_from_components"
    ):
        return

    for ingredient in (
        food.get("ingredients")
        or []
    ):
        _walk_food(
            ingredient,
            by_domain,
        )

    for spice in (
        food.get("spices")
        or []
    ):
        _walk_food(
            spice,
            by_domain,
        )


def collect_domain_evidence(
    root: Dict[str, Any],
    is_meal: bool = True,
) -> Dict[
    str,
    DomainAccumulator,
]:
    by_domain: Dict[
        str,
        DomainAccumulator,
    ] = {}

    if is_meal:
        meal = root.get("meal")

        if not isinstance(meal, dict):
            return by_domain

        foods = (
            meal.get("foods")
            or []
        )

        for food in foods:
            _walk_food(
                food,
                by_domain,
            )
    else:
        _walk_food(
            root,
            by_domain,
        )

    return by_domain


# =========================================================================
# SCORING ENTRY POINTS
# =========================================================================

def score_domain(
    domain: str,
    evidence_items: List[
        Dict[str, Any]
    ],
    health_domain: Optional[
        str
    ] = None,
    aggregator: Optional[
        DomainAggregator
    ] = None,
) -> DomainScore:
    return (
        aggregator
        or _DEFAULT_AGGREGATOR
    ).score(
        domain=domain,
        health_domain=(
            health_domain
            or domain
        ),
        evidence_items=(
            evidence_items
        ),
    )


def score_food(
    food: Dict[str, Any],
    aggregator: Optional[
        DomainAggregator
    ] = None,
) -> Dict[
    str,
    Dict[str, Any],
]:
    by_domain = (
        collect_domain_evidence(
            food,
            is_meal=False,
        )
    )

    selected_aggregator = (
        aggregator
        or _DEFAULT_AGGREGATOR
    )

    return {
        domain: (
            selected_aggregator.score(
                domain=domain,
                health_domain=(
                    accumulator
                    .health_domain
                ),
                evidence_items=(
                    accumulator
                    .evidence_items
                ),
            ).to_dict()
        )
        for domain, accumulator
        in by_domain.items()
    }


def score_meal(
    meal_json: Dict[str, Any],
    aggregator: Optional[
        DomainAggregator
    ] = None,
) -> Dict[
    str,
    Dict[str, Any],
]:
    by_domain = (
        collect_domain_evidence(
            meal_json,
            is_meal=True,
        )
    )

    selected_aggregator = (
        aggregator
        or _DEFAULT_AGGREGATOR
    )

    return {
        domain: (
            selected_aggregator.score(
                domain=domain,
                health_domain=(
                    accumulator
                    .health_domain
                ),
                evidence_items=(
                    accumulator
                    .evidence_items
                ),
            ).to_dict()
        )
        for domain, accumulator
        in by_domain.items()
    }


# =========================================================================
# PUBLIC ENTRY POINTS
# =========================================================================

async def attach_domain_scores(
    meal_json: Dict[str, Any],
    aggregator: Optional[
        DomainAggregator
    ] = None,
) -> Dict[str, Any]:
    """
    Attach canonical-domain keyed scores to meal.health_domain_scores.

    Input must already have passed through evidence_engine.attach_evidence.
    The input dictionary is never mutated.
    """

    if not isinstance(
        meal_json,
        dict,
    ):
        raise ValueError(
            "Input must be a dictionary."
        )

    meal = meal_json.get("meal")

    if not isinstance(meal, dict):
        raise ValueError(
            "Input must contain a "
            "top-level 'meal' object."
        )

    result = copy.deepcopy(
        meal_json
    )

    result["meal"][
        "health_domain_scores"
    ] = score_meal(
        result,
        aggregator,
    )

    result["meal"][
        "health_scoring_metadata"
    ] = {
        "version": SCORING_VERSION,
        "score_min": SCORE_MIN,
        "score_max": SCORE_MAX,
        "neutral_score": (
            SCORE_NEUTRAL
        ),
        "reliability_adjustment": (
            (
                aggregator
                or _DEFAULT_AGGREGATOR
            ).reliability_adjustment
        ),
    }

    return result


def attach_domain_scores_sync(
    meal_json: Dict[str, Any],
    aggregator: Optional[
        DomainAggregator
    ] = None,
) -> Dict[str, Any]:
    try:
        asyncio.get_running_loop()

    except RuntimeError:
        return asyncio.run(
            attach_domain_scores(
                meal_json,
                aggregator,
            )
        )

    try:
        import nest_asyncio  # type: ignore

    except ImportError as error:
        raise RuntimeError(
            "attach_domain_scores_sync() "
            "was called inside a running "
            "event loop. Use "
            "'await attach_domain_scores(...)' "
            "or install and apply nest_asyncio."
        ) from error

    nest_asyncio.apply()

    return asyncio.run(
        attach_domain_scores(
            meal_json,
            aggregator,
        )
    )
