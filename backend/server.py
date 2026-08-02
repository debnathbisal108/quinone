from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from analysis_engine import (
    analyze_meal,
    continue_with_back_label,
)
from evidence_engine import attach_evidence
from feature_engineering import compute_features
from health_domain_scoring import attach_domain_scores
from food_resolver import resolve_meal
from nutrient_profile import attach_nutrients

# ENABLE_PERSONALIZATION = True

ENABLE_PERSONALIZATION = False

if ENABLE_PERSONALIZATION:
    from personalization_engine import (
        attach_personalization,
        normalize_profile,
        determine_active_modifiers,
        load_modifier_database
    )


# from personalization_engine import (
#     attach_personalization,
#     determine_active_modifiers,
#     load_modifier_database,
# )


APP_NAME = "Quinone API"

BASE_DIR = Path(__file__).resolve().parent
SESSION_DIR = BASE_DIR / "storage" / "sessions"

# Only small JSON continuation sessions are retained.
# Uploaded images are stored in temporary request-scoped directories and
# deleted automatically after each request.
SESSION_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}

MAX_FILE_SIZE = 15 * 1024 * 1024

app = FastAPI(
    title=APP_NAME,
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

analysis_lock = Lock()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": APP_NAME,
        "status": "running",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
    }


@app.post("/analyze")
async def analyze(
    images: list[UploadFile] = File(...),
    profile: str | None = Form(default=None),
) -> dict[str, Any]:
    if not images:
        raise HTTPException(
            status_code=400,
            detail="At least one meal image is required.",
        )

    analysis_id = str(uuid.uuid4())

    try:
        profile_data = parse_profile(profile)

        # Files exist only while this request is being processed.
        with tempfile.TemporaryDirectory(
            prefix=f"quinone_{analysis_id}_"
        ) as temporary_directory:
            analysis_directory = Path(
                temporary_directory
            )

            image_paths: list[str] = []

            for index, image in enumerate(images):
                saved_path = await save_upload(
                    upload=image,
                    destination_directory=analysis_directory,
                    fallback_name=f"meal_{index + 1}",
                )

                image_paths.append(str(saved_path))

            with analysis_lock:
                analysis_result = analyze_meal(
                    image_paths=image_paths,
                    profile=profile_data,
                )

            analysis_result = normalize_result(
                analysis_result
            )

            status = analysis_result.get("status")

            if status == "waiting_for_back_label":
                partial_result = analysis_result.get(
                    "partial_result"
                )

                if not isinstance(partial_result, dict):
                    raise ValueError(
                        "The analysis engine returned an "
                        "invalid partial result."
                    )

                # Do not save image paths because the temporary files will
                # be deleted when this request exits.
                save_session(
                    analysis_id=analysis_id,
                    data={
                        "analysis_id": analysis_id,
                        "profile": profile_data,
                        "partial_result": partial_result,
                    },
                )

                analysis_result["analysis_id"] = (
                    analysis_id
                )

                return analysis_result

            if status == "no_food_detected":
                analysis_result["analysis_id"] = (
                    analysis_id
                )

                return analysis_result

            if status != "completed":
                raise ValueError(
                    f"Unsupported analysis status: {status}"
                )

            final_result = await run_nutrica_pipeline(
                analysis_result,
                profile=profile_data,
            )

            final_result["analysis_id"] = (
                analysis_id
            )

            return final_result

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Meal analysis failed: {error}",
        ) from error


@app.post("/analyze/back-label")
async def analyze_back_label(
    analysis_id: str = Form(...),
    label: UploadFile = File(...),
    target_food_id: str | None = Form(
        default=None
    ),
) -> dict[str, Any]:
    session = load_session(analysis_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Analysis session was not found "
                "or has expired."
            ),
        )

    partial_result = session.get(
        "partial_result"
    )

    if not isinstance(partial_result, dict):
        raise HTTPException(
            status_code=500,
            detail=(
                "The saved session contains an "
                "invalid partial result."
            ),
        )

    try:
        # The nutrition-label image also exists only for this request.
        with tempfile.TemporaryDirectory(
            prefix=f"quinone_label_{analysis_id}_"
        ) as temporary_directory:
            analysis_directory = Path(
                temporary_directory
            )

            label_path = await save_upload(
                upload=label,
                destination_directory=analysis_directory,
                fallback_name="nutrition_label",
            )

            with analysis_lock:
                continued_result = (
                    continue_with_back_label(
                        partial_result=partial_result,
                        label_image_path=str(
                            label_path
                        ),
                        target_food_id=target_food_id,
                    )
                )

            continued_result = normalize_result(
                continued_result
            )

            status = continued_result.get("status")

            if status == "waiting_for_back_label":
                updated_partial_result = (
                    continued_result.get(
                        "partial_result"
                    )
                )

                if not isinstance(
                    updated_partial_result,
                    dict,
                ):
                    raise ValueError(
                        "The continuation engine returned "
                        "an invalid partial result."
                    )

                session["partial_result"] = (
                    updated_partial_result
                )

                save_session(
                    analysis_id=analysis_id,
                    data=session,
                )

                continued_result["analysis_id"] = (
                    analysis_id
                )

                return continued_result

            if status == "no_food_detected":
                delete_session(analysis_id)

                continued_result["analysis_id"] = (
                    analysis_id
                )

                return continued_result

            if status != "completed":
                raise ValueError(
                    "Unsupported continuation status: "
                    f"{status}"
                )

            final_result = await run_nutrica_pipeline(
                continued_result,
                profile=session.get("profile"),
            )

            final_result["analysis_id"] = (
                analysis_id
            )

            delete_session(analysis_id)

            return final_result

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Back-label analysis failed: {error}"
            ),
        ) from error


async def run_nutrica_pipeline(
    analysis_result: dict[str, Any],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run the complete post-vision pipeline.

    Generic health-domain scores are always calculated first. The separate
    personalization phase runs only when the normalized user profile activates
    at least one supported modifier. This prevents empty/basic profiles from
    changing the generic result and avoids applying modifiers twice.
    """
    resolved_result = await resolve_meal(analysis_result)
    nutrient_result = await attach_nutrients(resolved_result)

    print("\n" + "=" * 100)
    print("NUTRIENT RESULT FROM BACKEND")
    print("=" * 100)
    print(
        json.dumps(
            nutrient_result,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
    print("=" * 100 + "\n")
    
    feature_result = await compute_features(nutrient_result)

    # Evidence remains population-neutral here. Personal reweighting is handled
    # once, after domain scoring, by personalization_engine.py.
    evidence_result = await attach_evidence(feature_result)
    scored_result = await attach_domain_scores(evidence_result)

    # personalization_profile = normalize_personalization_profile(profile)
    # active_modifiers = determine_active_modifiers(
    #     personalization_profile,
    #     load_modifier_database(),
    # )

    # if not active_modifiers:
    return scored_result

    # return await attach_personalization(
    #     scored_result,
    #     personalization_profile,
    # )


def normalize_personalization_profile(
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Convert Quinone's current Flutter profile payload to the engine schema."""
    if not isinstance(profile, dict):
        return {}

    normalized = dict(profile)

    # Flutter currently sends chronic_conditions as a map of booleans.
    raw_conditions = profile.get("chronic_conditions")
    conditions: list[str] = []
    if isinstance(raw_conditions, dict):
        aliases = {
            "diabetes": "diabetes",
            "type_2_diabetes": "type_2_diabetes",
            "prediabetes": "prediabetes",
            "ckd": "ckd",
            "chronic_kidney_disease": "chronic_kidney_disease",
            "hypertension": "hypertension",
            "high_blood_pressure": "high_blood_pressure",
            "hyperlipidemia": "hyperlipidemia",
            "dyslipidemia": "dyslipidemia",
            "ibs": "ibs",
            "ibd": "ibd",
            "osteoporosis": "osteoporosis",
            "osteoarthritis": "osteoarthritis",
            "rheumatoid_arthritis": "rheumatoid_arthritis",
            "heart_failure": "heart_failure",
        }
        for key, enabled in raw_conditions.items():
            if enabled:
                conditions.append(aliases.get(str(key).strip().lower(), str(key).strip().lower()))
    elif isinstance(raw_conditions, (list, tuple, set)):
        conditions.extend(str(value).strip().lower() for value in raw_conditions if str(value).strip())

    # Support older/profile-setup payloads that store conditions as free text.
    health_conditions = profile.get("health_conditions")
    if isinstance(health_conditions, str) and health_conditions.strip():
        text = health_conditions.lower().replace(";", ",")
        keyword_aliases = {
            "diabetes": "diabetes",
            "prediabetes": "prediabetes",
            "kidney": "ckd",
            "ckd": "ckd",
            "hypertension": "hypertension",
            "high blood pressure": "high_blood_pressure",
            "cholesterol": "high_cholesterol",
            "hyperlipidemia": "hyperlipidemia",
            "ibs": "ibs",
            "osteoporosis": "osteoporosis",
            "osteoarthritis": "osteoarthritis",
            "rheumatoid": "rheumatoid_arthritis",
        }
        for keyword, condition_id in keyword_aliases.items():
            if keyword in text:
                conditions.append(condition_id)

    normalized["chronic_conditions"] = list(dict.fromkeys(conditions))

    if profile.get("vegetarian") is True:
        normalized["diet_type"] = "vegetarian"
    elif profile.get("vegan") is True:
        normalized["diet_type"] = "vegan"
    elif not normalized.get("diet_type"):
        preference = profile.get("dietary_preferences")
        if isinstance(preference, str):
            lowered = preference.strip().lower()
            if "vegan" in lowered:
                normalized["diet_type"] = "vegan"
            elif "vegetarian" in lowered:
                normalized["diet_type"] = "vegetarian"

    # Normalize common UI labels to the IDs used by the modifier database.
    goal = normalized.get("goal")
    if isinstance(goal, str):
        normalized_goal = goal.strip().lower().replace(" ", "_").replace("-", "_")
        goal_aliases = {
            "lose_weight": "weight_loss",
            "weight_reduction": "weight_loss",
            "gain_muscle": "muscle_gain",
            "build_muscle": "muscle_gain",
        }
        normalized["goal"] = goal_aliases.get(normalized_goal, normalized_goal)

    activity = normalized.get("activity_level")
    if isinstance(activity, str):
        normalized_activity = activity.strip().lower().replace(" ", "_").replace("-", "_")
        activity_aliases = {
            "lightly_active": "active",
            "moderately_active": "active",
            "highly_active": "very_active",
        }
        normalized["activity_level"] = activity_aliases.get(normalized_activity, normalized_activity)

    return normalized


def has_personalization_modifiers(profile: dict[str, Any] | None) -> bool:
    """Public helper for tests/diagnostics."""
    normalized = normalize_personalization_profile(profile)
    return bool(determine_active_modifiers(normalized, load_modifier_database()))
    # return False


async def save_upload(
    upload: UploadFile,
    destination_directory: Path,
    fallback_name: str,
) -> Path:
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type: "
                f"{upload.content_type}. "
                "Use JPEG, PNG, or WebP."
            ),
        )

    extension = Path(
        upload.filename or ""
    ).suffix.lower()

    if extension not in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }:
        extension = content_type_extension(
            upload.content_type
        )

    destination = (
        destination_directory
        / (
            f"{fallback_name}_"
            f"{uuid.uuid4().hex}"
            f"{extension}"
        )
    )

    size = 0

    try:
        with destination.open("wb") as output:
            while True:
                chunk = await upload.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                size += len(chunk)

                if size > MAX_FILE_SIZE:
                    output.close()
                    destination.unlink(
                        missing_ok=True
                    )

                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "Image exceeds the "
                            "15 MB limit."
                        ),
                    )

                output.write(chunk)

    finally:
        await upload.close()

    return destination


def parse_profile(
    profile: str | None,
) -> dict[str, Any] | None:
    if profile is None or not profile.strip():
        return None

    try:
        decoded = json.loads(profile)

    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail=(
                "The profile field is not "
                "valid JSON."
            ),
        ) from error

    if not isinstance(decoded, dict):
        raise HTTPException(
            status_code=400,
            detail=(
                "The profile field must contain "
                "a JSON object."
            ),
        )

    return decoded


def normalize_result(
    result: Any,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError(
            "The analysis engine must return "
            "a dictionary."
        )

    normalized = dict(result)

    normalized.setdefault(
        "status",
        "completed",
    )

    return normalized


def session_path(
    analysis_id: str,
) -> Path:
    safe_id = Path(analysis_id).name

    if safe_id != analysis_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid analysis ID.",
        )

    return SESSION_DIR / f"{safe_id}.json"


def save_session(
    analysis_id: str,
    data: dict[str, Any],
) -> None:
    path = session_path(analysis_id)
    temporary_path = path.with_suffix(
        ".tmp"
    )

    temporary_path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(path)


def load_session(
    analysis_id: str,
) -> dict[str, Any] | None:
    path = session_path(analysis_id)

    if not path.exists():
        return None

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None

    if not isinstance(data, dict):
        return None

    return data


def delete_session(
    analysis_id: str,
) -> None:
    session_path(analysis_id).unlink(
        missing_ok=True
    )


def content_type_extension(
    content_type: str | None,
) -> str:
    extensions = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    return extensions.get(
        content_type or "",
        ".jpg",
    )
