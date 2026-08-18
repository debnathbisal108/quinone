from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from threading import BoundedSemaphore, RLock
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from analysis_engine import (
    ModelJSONResponseError,
    analyze_meal,
    analyze_label_only,
    continue_with_back_label,
)
from evidence_engine import attach_evidence
from feature_engineering import compute_features
from health_domain_scoring import attach_domain_scores
from food_resolver import resolve_meal
from nutrient_profile import attach_nutrients
from usda_recipe_service import (
    search_usda_foods,
    validate_or_recover_usda_food,
)

from personalization_engine import (
    attach_personalization,
    determine_active_modifiers,
    load_modifier_database,
    normalize_user_profile,
)
from nutrient_target_engine import (
    attach_nutrient_targets,
)
from draft_meal_guidance import build_draft_meal_guidance, apply_personalized_guidance_safety
from recommendation_engine import apply_recommendation, recommend_after_analysis


APP_NAME = "Quinone API"

BASE_DIR = Path(__file__).resolve().parent
SESSION_DIR = BASE_DIR / "storage" / "sessions"
JOB_DIR = BASE_DIR / "storage" / "analysis_jobs"

SESSION_DIR.mkdir(parents=True, exist_ok=True)
JOB_DIR.mkdir(parents=True, exist_ok=True)

JOB_RETENTION_SECONDS = 60 * 60

_analysis_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = RLock()

# Only small JSON continuation sessions are retained.
# Uploaded images are stored in temporary request-scoped directories and
# deleted automatically after each request.
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

logger = logging.getLogger("quinone.server")


def _public_job_error(error: Exception) -> str:
    """Keep parser internals out of mobile UI while retaining useful errors."""
    if isinstance(error, ModelJSONResponseError):
        # These messages are sanitized by analysis_engine and identify the
        # failed operation. Preserve that distinction for the mobile app.
        return str(error).strip() or "The AI analysis could not be completed."

    if isinstance(error, json.JSONDecodeError):
        return (
            "The AI returned an incomplete analysis response. "
            "Please retry the same image."
        )

    message = str(error).strip()
    lowered = message.lower()
    if any(
        marker in lowered
        for marker in (
            "unterminated string",
            "expecting property name",
            "expecting value: line",
            "json object",
        )
    ):
        return (
            "The AI returned an incomplete analysis response. "
            "Please retry the same image."
        )

    return message or "The analysis could not be completed."

# A global Lock serialized every Gemini request across all users. Keep a small
# bounded limit for quota safety while allowing independent requests to run.
MAX_CONCURRENT_ANALYSES = max(
    1,
    int(os.environ.get("MAX_CONCURRENT_ANALYSES", "2")),
)
analysis_lock = BoundedSemaphore(MAX_CONCURRENT_ANALYSES)


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




class LabelServingItemRequest(BaseModel):
    food_id: str
    quantity: float = Field(gt=0, le=100000)
    unit: str


class LabelServingConfirmationRequest(BaseModel):
    analysis_id: str
    items: list[LabelServingItemRequest]


class ManualRecipeIngredientRequest(BaseModel):
    fdc_id: int
    name: str
    description: str
    data_type: str | None = None
    food_category: str | None = None
    preparation: str | None = None
    quantity_basis: str | None = None
    grams: float = Field(gt=0, le=100000)


class MixedMealConfirmationRequest(BaseModel):
    analysis_id: str
    recipe_name: str = "Detected meal"
    ingredients: list[ManualRecipeIngredientRequest]
    label_items: list[LabelServingItemRequest]
    servings_made: float = Field(default=1.0, gt=0, le=1000)
    servings_eaten: float = Field(default=1.0, gt=0, le=1000)


class ManualRecipeRequest(BaseModel):
    recipe_name: str = "Manual recipe"
    ingredients: list[ManualRecipeIngredientRequest]
    servings_made: float = Field(default=1.0, gt=0, le=10000)
    servings_eaten: float = Field(default=1.0, gt=0, le=10000)
    profile: dict[str, Any] | None = None


class PostAnalysisRecommendationRequest(BaseModel):
    current_result: dict[str, Any]
    today_results: list[dict[str, Any]] = Field(default_factory=list)
    profile: dict[str, Any] | None = None
    local_hour: int = Field(default=12, ge=0, le=23)
    maximum_results: int = Field(default=5, ge=1, le=8)
    preferred_domain_keys: list[str] = Field(default_factory=list)


class ApplyPostAnalysisRecommendationRequest(BaseModel):
    current_result: dict[str, Any]
    today_results: list[dict[str, Any]] = Field(default_factory=list)
    profile: dict[str, Any] | None = None
    local_hour: int = Field(default=12, ge=0, le=23)
    recommendation_id: str = Field(min_length=1, max_length=100)


class DraftMealGuidanceRequest(ManualRecipeRequest):
    analysis_id: str | None = None
    label_items: list[LabelServingItemRequest] = Field(default_factory=list)
    today_results: list[dict[str, Any]] = Field(default_factory=list)
    include_shortfalls: bool = True
    local_hour: int = Field(default=12, ge=0, le=23)


@app.post("/recommendations/after-analysis")
@app.post("/api/v1/recommendations/after-analysis", include_in_schema=False)
async def post_analysis_recommendations(
    request: PostAnalysisRecommendationRequest,
) -> dict[str, Any]:
    """Recommend a safe change targeted to this meal's weakest domain."""
    try:
        return await recommend_after_analysis(
            current_result=request.current_result,
            today_results=request.today_results,
            profile=request.profile,
            local_hour=request.local_hour,
            maximum_results=request.maximum_results,
            preferred_domain_keys=request.preferred_domain_keys,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("Post-analysis recommendation failed")
        raise HTTPException(
            status_code=500,
            detail="Recommendations could not be calculated for this meal.",
        ) from error


@app.post("/recommendations/apply")
@app.post("/api/v1/recommendations/apply", include_in_schema=False)
async def apply_post_analysis_recommendation(
    request: ApplyPostAnalysisRecommendationRequest,
) -> dict[str, Any]:
    """Merge a revalidated recommendation into the existing meal analysis."""
    try:
        return await apply_recommendation(
            current_result=request.current_result,
            today_results=request.today_results,
            profile=request.profile,
            local_hour=request.local_hour,
            recommendation_id=request.recommendation_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("Applying post-analysis recommendation failed")
        raise HTTPException(
            status_code=500,
            detail="The recommendation could not be applied to this meal.",
        ) from error


async def _draft_guidance_nutrient_result(
    request: DraftMealGuidanceRequest,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    portion_fraction = request.servings_eaten / request.servings_made
    validated = await asyncio.gather(
        *[
            validate_or_recover_usda_food(
                fdc_id=item.fdc_id,
                name=item.name,
                description=item.description,
                data_type=item.data_type,
                food_category=item.food_category,
            )
            for item in request.ingredients
        ]
    )

    foods: list[dict[str, Any]] = []
    effective_profile = request.profile
    if request.analysis_id and request.label_items:
        session = load_session(request.analysis_id)
        if session is None:
            raise ValueError("Analysis session was not found or has expired.")
        base_result = session.get("confirmed_label_result")
        if not isinstance(base_result, dict):
            raise ValueError("The saved detected meal is unavailable.")
        confirmed = _apply_label_serving_confirmation(
            base_result,
            LabelServingConfirmationRequest(
                analysis_id=request.analysis_id,
                items=request.label_items,
            ),
        )
        foods.extend(
            copy.deepcopy(food)
            for food in confirmed.get("meal", {}).get("foods", [])
            if isinstance(food, dict)
            and food.get("analysis_route") == "NUTRITION_LABEL"
        )
        if effective_profile is None:
            effective_profile = session.get("profile")

    total_weight = 0.0
    for index, (item, resolved) in enumerate(zip(request.ingredients, validated), start=1):
        grams = float(item.grams) * portion_fraction
        total_weight += grams
        foods.append({
            "id": f"guidance_{index:04d}",
            "name": item.name.strip() or item.description,
            "display_name": item.name.strip() or item.description,
            "canonical_name": item.description,
            "category": item.food_category or "Unknown",
            "food_source": "draft_guidance",
            "analysis_route": "DIRECT_USDA",
            "quantity": grams,
            "unit": "g",
            "estimated_weight_g": grams,
            "preparation": item.preparation or "unknown",
            "quantity_basis": item.quantity_basis or "as_served",
            "resolver": {
                "status": "resolved",
                "fdc_id": resolved["fdc_id"],
                "matched_description": resolved["description"],
                "data_type": resolved.get("data_type"),
                "confidence": 1.0,
                "source": "user_selected_usda",
            },
            "ingredients": [],
            "spices": [],
        })
    prepared = {
        "status": "completed",
        "input_method": "draft_guidance",
        "meal": {
            "meal_type": request.recipe_name.strip() or "Draft meal",
            "meal_name": request.recipe_name.strip() or "Draft meal",
            "estimated_visible_food_weight_g": round(total_weight, 3),
            "foods": foods,
        },
    }
    return await attach_nutrients(prepared), effective_profile


@app.post("/meal-guidance/evaluate")
@app.post("/api/v1/meal-guidance/evaluate", include_in_schema=False)
async def evaluate_draft_meal_guidance(
    request: DraftMealGuidanceRequest,
) -> dict[str, Any]:
    """Return optional pre-analysis nutrient alerts for an editable draft."""
    if request.servings_eaten > request.servings_made:
        raise HTTPException(
            status_code=422,
            detail="servings_eaten cannot exceed servings_made",
        )
    try:
        nutrient_result, effective_profile = await _draft_guidance_nutrient_result(request)
        guidance = build_draft_meal_guidance(
            nutrient_result,
            profile=effective_profile,
            local_hour=request.local_hour,
            today_results=request.today_results,
            include_shortfalls=request.include_shortfalls,
        )
        return await apply_personalized_guidance_safety(guidance, nutrient_result, profile=effective_profile)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("Draft meal guidance failed")
        raise HTTPException(
            status_code=500,
            detail="Meal guidance could not be calculated right now. You can continue without it.",
        ) from error


@app.get("/recipes/usda/search")
@app.get("/api/v1/recipes/usda/search", include_in_schema=False)
async def recipe_usda_search(q: str) -> dict[str, Any]:
    query = q.strip()
    if len(query) < 2:
        return {"query": query, "foods": []}
    try:
        foods = await search_usda_foods(query, limit=8)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"USDA food search is temporarily unavailable: {error}",
        ) from error
    return {"query": query, "foods": foods}


@app.post("/recipes/analyze/start")
@app.post("/api/v1/recipes/analyze/start", include_in_schema=False)
async def start_manual_recipe_job(
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    # Validate inside the endpoint instead of letting FastAPI reject the
    # request with a generic 422 before our code runs. This gives Flutter
    # a concrete, user-readable error when a field is malformed.
    try:
        request = (
            ManualRecipeRequest.model_validate(payload)
            if hasattr(ManualRecipeRequest, "model_validate")
            else ManualRecipeRequest.parse_obj(payload)
        )
    except ValidationError as error:
        problems: list[str] = []
        for item in error.errors():
            location = ".".join(str(part) for part in item.get("loc", ()))
            message = str(item.get("msg") or "Invalid value")
            problems.append(f"{location}: {message}" if location else message)
        detail = "; ".join(problems) or "The recipe request is invalid."
        raise HTTPException(status_code=400, detail=detail) from error

    if not request.ingredients:
        raise HTTPException(
            status_code=400,
            detail="Add at least one recipe ingredient.",
        )
    if request.servings_eaten > request.servings_made:
        raise HTTPException(
            status_code=400,
            detail="Servings eaten cannot be greater than servings made.",
        )

    _cleanup_expired_jobs()
    job_id = str(uuid.uuid4())
    _set_job(
        job_id,
        status="queued",
        stage="recipe_ready",
        message="Recipe ingredients received. Nutrition analysis is starting…",
        progress=0.10,
    )
    asyncio.create_task(_process_manual_recipe_job(job_id=job_id, request=request))
    return {
        "job_id": job_id,
        "status": "queued",
        "stage": "recipe_ready",
        "message": "Recipe ingredients received. Nutrition analysis is starting…",
        "progress": 0.10,
    }


# =========================================================================
# REAL BACKEND-STAGE PROGRESS
# =========================================================================


def _job_snapshot(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        job = _analysis_jobs.get(job_id)
        return copy.deepcopy(job) if job is not None else None


def _set_job(
    job_id: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    message: str | None = None,
    progress: float | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    with _jobs_lock:
        job = _analysis_jobs.setdefault(
            job_id,
            {
                "job_id": job_id,
                "status": "queued",
                "stage": "queued",
                "message": "Waiting to start analysis…",
                "progress": 0.0,
                "created_at": time.time(),
                "updated_at": time.time(),
                "result": None,
                "error": None,
                "cancel_requested": False,
                "timings_ms": {},
            },
        )
        if status is not None:
            job["status"] = status
        if stage is not None:
            job["stage"] = stage
        if message is not None:
            job["message"] = message
        if progress is not None:
            job["progress"] = max(0.0, min(1.0, float(progress)))
        if result is not None:
            job["result"] = result
        if error is not None:
            job["error"] = error
        job["updated_at"] = time.time()


def _record_job_timing(job_id: str, stage: str, started: float) -> None:
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    with _jobs_lock:
        job = _analysis_jobs.get(job_id)
        if job is not None:
            job.setdefault("timings_ms", {})[stage] = elapsed_ms
            job["updated_at"] = time.time()
    logger.info("analysis job=%s stage=%s elapsed_ms=%.1f", job_id, stage, elapsed_ms)


def _job_cancel_requested(job_id: str) -> bool:
    with _jobs_lock:
        return bool(_analysis_jobs.get(job_id, {}).get("cancel_requested"))


def _raise_if_cancelled(job_id: str) -> None:
    if _job_cancel_requested(job_id):
        raise asyncio.CancelledError()


def _cleanup_expired_jobs() -> None:
    cutoff = time.time() - JOB_RETENTION_SECONDS
    with _jobs_lock:
        expired = [
            job_id
            for job_id, job in _analysis_jobs.items()
            if job.get("updated_at", 0) < cutoff
            and job.get("status") in {
                "completed",
                "failed",
                "cancelled",
                "waiting_for_back_label",
                "waiting_for_meal_confirmation",
                "no_food_detected",
            }
        ]
        for job_id in expired:
            _analysis_jobs.pop(job_id, None)


def _run_analysis_engine_locked(
    image_paths: list[str],
    profile_data: dict[str, Any] | None,
) -> dict[str, Any]:
    with analysis_lock:
        return analyze_meal(
            image_paths=image_paths,
            profile=profile_data,
        )


# def _run_back_label_engine_locked(
#     partial_result: dict[str, Any],
#     label_path: str,
#     target_food_id: str | None,
# ) -> dict[str, Any]:
#     with analysis_lock:
#         return continue_with_back_label(
#             partial_result=partial_result,
#             label_image_path=label_path,
#             target_food_id=target_food_id,
#         )


def _run_back_label_engine_locked(
    partial_result: dict[str, Any],
    label_path: str,
    target_food_id: str | None,
) -> dict[str, Any]:
    with analysis_lock:
        return continue_with_back_label(
            partial_result=partial_result,
            label_image_path=label_path,
            target_food_id=target_food_id,
        )


def _run_label_only_engine_locked(
    label_path: str,
) -> dict[str, Any]:
    with analysis_lock:
        return analyze_label_only(
            image_path=label_path,
        )


@app.post("/analyze/start")
async def start_analysis_job(
    images: list[UploadFile] = File(...),
    profile: str | None = Form(default=None),
) -> dict[str, Any]:
    if not images:
        raise HTTPException(
            status_code=400,
            detail="At least one meal image is required.",
        )

    _cleanup_expired_jobs()
    job_id = str(uuid.uuid4())
    profile_data = parse_profile(profile)
    job_directory = JOB_DIR / job_id
    job_directory.mkdir(parents=True, exist_ok=False)

    image_paths: list[str] = []
    try:
        for index, image in enumerate(images):
            saved_path = await save_upload(
                upload=image,
                destination_directory=job_directory,
                fallback_name=f"meal_{index + 1}",
            )
            image_paths.append(str(saved_path))
    except Exception:
        shutil.rmtree(job_directory, ignore_errors=True)
        raise

    _set_job(
        job_id,
        status="queued",
        stage="upload_complete",
        message="Images uploaded. Analysis is starting…",
        progress=0.08,
    )
    asyncio.create_task(
        _process_initial_job(
            job_id=job_id,
            image_paths=image_paths,
            profile_data=profile_data,
            job_directory=job_directory,
        )
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "stage": "upload_complete",
        "message": "Images uploaded. Analysis is starting…",
        "progress": 0.08,
    }


@app.post("/analyze/back-label/start")
async def start_back_label_job(
    analysis_id: str = Form(...),
    label: UploadFile = File(...),
    target_food_id: str | None = Form(default=None),
) -> dict[str, Any]:
    session = load_session(analysis_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis session was not found or has expired.",
        )

    partial_result = session.get("partial_result")
    if not isinstance(partial_result, dict):
        raise HTTPException(
            status_code=500,
            detail="The saved session contains an invalid partial result.",
        )

    _cleanup_expired_jobs()
    job_id = str(uuid.uuid4())
    job_directory = JOB_DIR / job_id
    job_directory.mkdir(parents=True, exist_ok=False)

    try:
        label_path = await save_upload(
            upload=label,
            destination_directory=job_directory,
            fallback_name="nutrition_label",
        )
    except Exception:
        shutil.rmtree(job_directory, ignore_errors=True)
        raise

    _set_job(
        job_id,
        status="queued",
        stage="label_upload_complete",
        message="Nutrition label uploaded. Reading the label…",
        progress=0.08,
    )
    asyncio.create_task(
        _process_back_label_job(
            job_id=job_id,
            analysis_id=analysis_id,
            session=session,
            partial_result=partial_result,
            label_path=str(label_path),
            target_food_id=target_food_id,
            job_directory=job_directory,
        )
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "stage": "label_upload_complete",
        "message": "Nutrition label uploaded. Reading the label…",
        "progress": 0.08,
    }

@app.post("/analyze/label-only/start")
async def start_label_only_job(
    label: UploadFile = File(...),
    profile: str | None = Form(default=None),
) -> dict[str, Any]:
    """Entry point for a back-label image uploaded on its own — no prior
    meal photo and no existing analysis_id. This must never route through
    analyze_meal / _run_analysis_engine_locked, which would misread the
    label as a meal photo and ask for the same label again."""
    _cleanup_expired_jobs()
    job_id = str(uuid.uuid4())
    profile_data = parse_profile(profile)
    job_directory = JOB_DIR / job_id
    job_directory.mkdir(parents=True, exist_ok=False)

    try:
        label_path = await save_upload(
            upload=label,
            destination_directory=job_directory,
            fallback_name="nutrition_label",
        )
    except Exception:
        shutil.rmtree(job_directory, ignore_errors=True)
        raise

    _set_job(
        job_id,
        status="queued",
        stage="label_upload_complete",
        message="Nutrition label uploaded. Reading the label…",
        progress=0.08,
    )
    asyncio.create_task(
        _process_label_only_job(
            job_id=job_id,
            label_path=str(label_path),
            profile_data=profile_data,
            job_directory=job_directory,
        )
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "stage": "label_upload_complete",
        "message": "Nutrition label uploaded. Reading the label…",
        "progress": 0.08,
    }

@app.get("/analyze/jobs/{job_id}")
@app.get("/api/v1/analyze/jobs/{job_id}", include_in_schema=False)
async def get_analysis_job(job_id: str) -> dict[str, Any]:
    job = _job_snapshot(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job was not found.")

    response = {
        "job_id": job_id,
        "status": job["status"],
        "stage": job["stage"],
        "message": job["message"],
        "progress": job["progress"],
        "error": job.get("error"),
        "timings_ms": job.get("timings_ms", {}),
    }
    if job["status"] in {
        "completed",
        "waiting_for_back_label",
        "waiting_for_meal_confirmation",
        "waiting_for_serving_confirmation",
        "no_food_detected",
    }:
        response["result"] = job.get("result")
    return response



async def _process_mixed_meal_confirmation_job(
    *,
    job_id: str,
    request: MixedMealConfirmationRequest,
) -> None:
    try:
        session = load_session(request.analysis_id)
        if session is None:
            raise ValueError("Analysis session was not found or has expired.")
        base_result = session.get("confirmed_label_result")
        if not isinstance(base_result, dict):
            raise ValueError("The saved mixed-meal result is unavailable.")

        _set_job(
            job_id,
            status="running",
            stage="meal_confirmation",
            message="Applying your meal corrections…",
            progress=0.12,
        )

        # First apply the confirmed packaged-food serving(s).
        label_request = LabelServingConfirmationRequest(
            analysis_id=request.analysis_id,
            items=request.label_items,
        )
        updated = _apply_label_serving_confirmation(base_result, label_request)

        portion_fraction = request.servings_eaten / request.servings_made
        validated = await asyncio.gather(
            *[
                validate_or_recover_usda_food(
                    fdc_id=item.fdc_id,
                    name=item.name,
                    description=item.description,
                    data_type=item.data_type,
                    food_category=item.food_category,
                )
                for item in request.ingredients
            ]
        )

        meal = updated.get("meal")
        if not isinstance(meal, dict):
            raise ValueError("The mixed meal is missing meal data.")
        existing_foods = meal.get("foods")
        if not isinstance(existing_foods, list):
            raise ValueError("The mixed meal is missing foods.")

        # Keep only authoritative label-backed foods from the original meal.
        foods: list[dict[str, Any]] = [
            copy.deepcopy(food)
            for food in existing_foods
            if isinstance(food, dict)
            and food.get("analysis_route") == "NUTRITION_LABEL"
        ]

        total_weight = 0.0
        for index, (ingredient, resolved_food) in enumerate(
            zip(request.ingredients, validated),
            start=1,
        ):
            grams = float(ingredient.grams) * portion_fraction
            total_weight += grams
            foods.append(
                {
                    "id": f"confirmed_{index:04d}",
                    "name": ingredient.name.strip() or ingredient.description,
                    "display_name": ingredient.name.strip() or ingredient.description,
                    "canonical_name": ingredient.description,
                    "category": ingredient.food_category or "Unknown",
                    "food_source": "photo_user_confirmed",
                    "analysis_route": "DIRECT_USDA",
                    "quantity": grams,
                    "unit": "g",
                    "estimated_weight_g": grams,
                    "preparation": ingredient.preparation or "unknown",
                    "quantity_basis": ingredient.quantity_basis or "as_served",
                    "resolver": {
                        "status": "resolved",
                        "fdc_id": resolved_food["fdc_id"],
                        "matched_description": resolved_food["description"],
                        "data_type": resolved_food.get("data_type"),
                        "confidence": 1.0,
                        "source": "user_confirmed_usda",
                    },
                    "ingredients": [],
                    "spices": [],
                }
            )

        meal["foods"] = foods
        meal["meal_name"] = request.recipe_name.strip() or meal.get("meal_name") or "Detected meal"
        meal["meal_type"] = request.recipe_name.strip() or meal.get("meal_type") or "Detected meal"
        meal["recipe_servings_made"] = request.servings_made
        meal["recipe_servings_eaten"] = request.servings_eaten
        # Label foods may be ml/serving-based, so this is the confirmed USDA
        # gram mass only rather than inventing a mass for beverages.
        meal["estimated_visible_food_weight_g"] = round(total_weight, 3)
        updated["input_method"] = "photo_confirmed_mixed"
        updated["status"] = "completed"

        final_result = await run_manual_recipe_pipeline(
            updated,
            profile=session.get("profile"),
            progress_callback=lambda stage, message, progress: _set_job(
                job_id,
                status="running",
                stage=stage,
                message=message,
                progress=progress,
            ),
            cancellation_check=lambda: _raise_if_cancelled(job_id),
        )
        final_result["analysis_id"] = request.analysis_id
        delete_session(request.analysis_id)
        _set_job(
            job_id,
            status="completed",
            stage="completed",
            message="Your meal report is ready.",
            progress=1.0,
            result=final_result,
        )
    except asyncio.CancelledError:
        _set_job(
            job_id,
            status="cancelled",
            stage="cancelled",
            message="Analysis cancelled.",
            progress=0.0,
        )
    except Exception as error:
        _set_job(
            job_id,
            status="failed",
            stage="failed",
            message="The confirmed mixed meal could not be analyzed.",
            error=_public_job_error(error),
        )


@app.post("/analyze/mixed-meal-confirmation/start")
@app.post(
    "/api/v1/analyze/mixed-meal-confirmation/start",
    include_in_schema=False,
)
async def start_mixed_meal_confirmation_job(
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    try:
        request = (
            MixedMealConfirmationRequest.model_validate(payload)
            if hasattr(MixedMealConfirmationRequest, "model_validate")
            else MixedMealConfirmationRequest.parse_obj(payload)
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail="The confirmed meal is invalid.",
        ) from error

    if request.servings_eaten > request.servings_made:
        raise HTTPException(
            status_code=422,
            detail="servings_eaten cannot exceed servings_made",
        )

    if load_session(request.analysis_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis session was not found or has expired.",
        )

    _cleanup_expired_jobs()
    job_id = str(uuid.uuid4())
    _set_job(
        job_id,
        status="queued",
        stage="meal_confirmation",
        message="Meal confirmed. Final analysis is starting…",
        progress=0.08,
    )
    asyncio.create_task(
        _process_mixed_meal_confirmation_job(
            job_id=job_id,
            request=request,
        )
    )
    return {
        "job_id": job_id,
        "status": "queued",
        "stage": "meal_confirmation",
        "message": "Meal confirmed. Final analysis is starting…",
        "progress": 0.08,
    }


async def _process_label_serving_confirmation_job(
    *,
    job_id: str,
    analysis_id: str,
    request: LabelServingConfirmationRequest,
) -> None:
    try:
        session = load_session(analysis_id)
        if session is None:
            raise ValueError("Analysis session was not found or has expired.")

        base_result = session.get("confirmed_label_result")
        if not isinstance(base_result, dict):
            raise ValueError(
                "The saved nutrition-label result is unavailable."
            )

        _set_job(
            job_id,
            status="running",
            stage="serving_confirmation",
            message="Applying the confirmed serving…",
            progress=0.12,
        )
        confirmed_result = _apply_label_serving_confirmation(
            base_result,
            request,
        )

        final_result = await run_nutrica_pipeline(
            confirmed_result,
            profile=session.get("profile"),
            progress_callback=lambda stage, message, progress: _set_job(
                job_id,
                status="running",
                stage=stage,
                message=message,
                progress=progress,
            ),
            cancellation_check=lambda: _raise_if_cancelled(job_id),
        )
        final_result["analysis_id"] = analysis_id
        delete_session(analysis_id)
        _set_job(
            job_id,
            status="completed",
            stage="completed",
            message="Your meal report is ready.",
            progress=1.0,
            result=final_result,
        )
    except asyncio.CancelledError:
        _set_job(
            job_id,
            status="cancelled",
            stage="cancelled",
            message="Analysis cancelled.",
            progress=0.0,
        )
    except Exception as error:
        _set_job(
            job_id,
            status="failed",
            stage="failed",
            message="The serving confirmation could not be completed.",
            error=_public_job_error(error),
        )


@app.post("/analyze/serving-confirmation/start")
@app.post(
    "/api/v1/analyze/serving-confirmation/start",
    include_in_schema=False,
)
async def start_label_serving_confirmation_job(
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    try:
        request = (
            LabelServingConfirmationRequest.model_validate(payload)
            if hasattr(LabelServingConfirmationRequest, "model_validate")
            else LabelServingConfirmationRequest.parse_obj(payload)
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail="Serving confirmation is invalid.",
        ) from error

    if load_session(request.analysis_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Analysis session was not found or has expired.",
        )

    _cleanup_expired_jobs()
    job_id = str(uuid.uuid4())
    _set_job(
        job_id,
        status="queued",
        stage="serving_confirmation",
        message="Serving confirmed. Final analysis is starting…",
        progress=0.08,
    )
    asyncio.create_task(
        _process_label_serving_confirmation_job(
            job_id=job_id,
            analysis_id=request.analysis_id,
            request=request,
        )
    )
    return {
        "job_id": job_id,
        "status": "queued",
        "stage": "serving_confirmation",
        "message": "Serving confirmed. Final analysis is starting…",
        "progress": 0.08,
    }


@app.post("/analyze/jobs/{job_id}/cancel")
@app.post("/api/v1/analyze/jobs/{job_id}/cancel", include_in_schema=False)
async def cancel_analysis_job(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _analysis_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Analysis job was not found.")
        if job.get("status") in {"completed", "failed", "cancelled"}:
            return {"job_id": job_id, "status": job["status"]}
        job["cancel_requested"] = True
        job["message"] = "Cancelling after the current analysis stage…"
        job["updated_at"] = time.time()
    return {"job_id": job_id, "status": "cancellation_requested"}


async def _process_initial_job(
    *,
    job_id: str,
    image_paths: list[str],
    profile_data: dict[str, Any] | None,
    job_directory: Path,
) -> None:
    try:
        _set_job(
            job_id,
            status="running",
            stage="analysis_engine",
            message="Detecting foods and estimating portions…",
            progress=0.14,
        )
        vision_started = time.perf_counter()
        analysis_result = await asyncio.to_thread(
            _run_analysis_engine_locked,
            image_paths,
            profile_data,
        )
        _record_job_timing(job_id, "vision", vision_started)
        _raise_if_cancelled(job_id)
        analysis_result = normalize_result(analysis_result)
        status = analysis_result.get("status")

        if status == "waiting_for_back_label":
            partial_result = analysis_result.get("partial_result")
            if not isinstance(partial_result, dict):
                raise ValueError("The analysis engine returned an invalid partial result.")
            save_session(
                analysis_id=job_id,
                data={
                    "analysis_id": job_id,
                    "profile": profile_data,
                    "partial_result": partial_result,
                },
            )
            analysis_result["analysis_id"] = job_id
            _set_job(
                job_id,
                status="waiting_for_back_label",
                stage="back_label_required",
                message="A branded food needs a nutrition-label photo.",
                progress=1.0,
                result=analysis_result,
            )
            return

        if status == "no_food_detected":
            analysis_result["analysis_id"] = job_id
            _set_job(
                job_id,
                status="no_food_detected",
                stage="no_food_detected",
                message="No food was detected in the uploaded image.",
                progress=1.0,
                result=analysis_result,
            )
            return

        if status != "completed":
            raise ValueError(f"Unsupported analysis status: {status}")

        if _has_attached_nutrition_label_foods(analysis_result):
            next_status, confirmation, session_data = (
                await _confirmation_after_label_analysis(
                    analysis_result,
                    analysis_id=job_id,
                    profile=profile_data,
                )
            )
            save_session(analysis_id=job_id, data=session_data)
            _set_job(
                job_id,
                status=next_status,
                stage=(
                    "meal_confirmation"
                    if next_status == "waiting_for_meal_confirmation"
                    else "serving_confirmation"
                ),
                message=str(confirmation.get("message") or "Review the detected meal."),
                progress=1.0,
                result=confirmation,
            )
            return

        _set_job(
            job_id,
            status="running",
            stage="food_resolution",
            message="Matching detected foods to nutrition database entries…",
            progress=0.72,
        )
        resolution_started = time.perf_counter()
        resolved_result = await resolve_meal(analysis_result)
        _record_job_timing(job_id, "usda_resolution", resolution_started)
        _raise_if_cancelled(job_id)

        review_result = _resolved_meal_to_review_draft(
            resolved_result,
            analysis_id=job_id,
        )
        _set_job(
            job_id,
            status="waiting_for_meal_confirmation",
            stage="meal_confirmation",
            message="Review the detected foods and quantities before final analysis.",
            progress=1.0,
            result=review_result,
        )
    except asyncio.CancelledError:
        _set_job(
            job_id,
            status="cancelled",
            stage="cancelled",
            message="Analysis cancelled.",
            progress=0.0,
        )
    except Exception as error:
        _set_job(
            job_id,
            status="failed",
            stage="failed",
            message="The meal analysis could not be completed.",
            error=_public_job_error(error),
        )
    finally:
        shutil.rmtree(job_directory, ignore_errors=True)


async def _process_label_only_job(
    *,
    job_id: str,
    label_path: str,
    profile_data: dict[str, Any] | None,
    job_directory: Path,
) -> None:
    try:
        _set_job(
            job_id,
            status="running",
            stage="analysis_engine",
            message="Reading the nutrition label…",
            progress=0.30,
        )
        vision_started = time.perf_counter()
        analysis_result = await asyncio.to_thread(
            _run_label_only_engine_locked,
            label_path,
        )
        _record_job_timing(job_id, "label_vision", vision_started)
        _raise_if_cancelled(job_id)
        analysis_result = normalize_result(analysis_result)
        status = analysis_result.get("status")

        if status != "completed":
            raise ValueError(f"Unsupported analysis status: {status}")

        next_status, confirmation, session_data = (
            await _confirmation_after_label_analysis(
                analysis_result,
                analysis_id=job_id,
                profile=profile_data,
            )
        )
        save_session(analysis_id=job_id, data=session_data)
        _set_job(
            job_id,
            status=next_status,
            stage=(
                "meal_confirmation"
                if next_status == "waiting_for_meal_confirmation"
                else "serving_confirmation"
            ),
            message=str(confirmation.get("message") or "Review the detected label."),
            progress=1.0,
            result=confirmation,
        )
    except asyncio.CancelledError:
        _set_job(
            job_id,
            status="cancelled",
            stage="cancelled",
            message="Analysis cancelled.",
            progress=0.0,
        )
    except Exception as error:
        _set_job(
            job_id,
            status="failed",
            stage="failed",
            message="The label analysis could not be completed.",
            error=str(error),
        )
    finally:
        shutil.rmtree(job_directory, ignore_errors=True)

async def _process_manual_recipe_job(
    *,
    job_id: str,
    request: ManualRecipeRequest,
) -> None:
    try:
        _set_job(
            job_id,
            status="running",
            stage="recipe_normalization",
            message="Preparing your selected ingredients and portion…",
            progress=0.18,
        )
        _raise_if_cancelled(job_id)
        portion_fraction = request.servings_eaten / request.servings_made
        foods: list[dict[str, Any]] = []
        total_weight = 0.0

        # Revalidate IDs at Analyze time, not just at search time. This also
        # repairs saved recipes/photo drafts that still contain a stale FDC ID.
        validated_ingredients = await asyncio.gather(
            *[
                validate_or_recover_usda_food(
                    fdc_id=ingredient.fdc_id,
                    name=ingredient.name,
                    description=ingredient.description,
                    data_type=ingredient.data_type,
                    food_category=ingredient.food_category,
                )
                for ingredient in request.ingredients
            ]
        )

        for index, (ingredient, resolved_food) in enumerate(
            zip(request.ingredients, validated_ingredients),
            start=1,
        ):
            grams = float(ingredient.grams) * portion_fraction
            total_weight += grams
            foods.append(
                {
                    "id": f"manual_{index:04d}",
                    "name": ingredient.name.strip() or ingredient.description,
                    "display_name": ingredient.name.strip() or ingredient.description,
                    "canonical_name": ingredient.description,
                    "category": ingredient.food_category or "Unknown",
                    "food_source": "manual_recipe",
                    "analysis_route": "DIRECT_USDA",
                    "quantity": grams,
                    "unit": "g",
                    "estimated_weight_g": grams,
                    "preparation": ingredient.preparation or "unknown",
                    "quantity_basis": ingredient.quantity_basis or "as_served",
                    "resolver": {
                        "status": "resolved",
                        "fdc_id": resolved_food["fdc_id"],
                        "matched_description": resolved_food["description"],
                        "data_type": resolved_food.get("data_type"),
                        "confidence": 1.0,
                        "source": "user_selected_usda",
                    },
                    "ingredients": [],
                    "spices": [],
                }
            )

        prepared = {
            "status": "completed",
            "input_method": "manual_recipe",
            "meal": {
                "meal_type": request.recipe_name.strip() or "Manual recipe",
                "meal_name": request.recipe_name.strip() or "Manual recipe",
                "estimated_visible_food_weight_g": round(total_weight, 3),
                "recipe_servings_made": request.servings_made,
                "recipe_servings_eaten": request.servings_eaten,
                "foods": foods,
            },
        }

        final_result = await run_manual_recipe_pipeline(
            prepared,
            profile=request.profile,
            progress_callback=lambda stage, message, progress: _set_job(
                job_id,
                status="running",
                stage=stage,
                message=message,
                progress=progress,
            ),
            cancellation_check=lambda: _raise_if_cancelled(job_id),
        )
        final_result["analysis_id"] = job_id
        _set_job(
            job_id,
            status="completed",
            stage="completed",
            message="Your recipe report is ready.",
            progress=1.0,
            result=final_result,
        )
    except asyncio.CancelledError:
        _set_job(
            job_id,
            status="cancelled",
            stage="cancelled",
            message="Recipe analysis cancelled.",
            progress=0.0,
        )
    except Exception as error:
        _set_job(
            job_id,
            status="failed",
            stage="failed",
            message="The recipe analysis could not be completed.",
            error=_public_job_error(error),
        )


async def _process_back_label_job(
    *,
    job_id: str,
    analysis_id: str,
    session: dict[str, Any],
    partial_result: dict[str, Any],
    label_path: str,
    target_food_id: str | None,
    job_directory: Path,
) -> None:
    try:
        _set_job(
            job_id,
            status="running",
            stage="nutrition_label_analysis",
            message="Reading ingredients and nutrition from the label…",
            progress=0.14,
        )
        label_started = time.perf_counter()
        continued_result = await asyncio.to_thread(
            _run_back_label_engine_locked,
            partial_result,
            label_path,
            target_food_id,
        )
        _record_job_timing(job_id, "back_label_vision", label_started)
        _raise_if_cancelled(job_id)
        continued_result = normalize_result(continued_result)
        status = continued_result.get("status")

        if status == "waiting_for_back_label":
            updated_partial = continued_result.get("partial_result")
            if not isinstance(updated_partial, dict):
                raise ValueError("The continuation engine returned an invalid partial result.")
            session["partial_result"] = updated_partial
            save_session(analysis_id=analysis_id, data=session)
            continued_result["analysis_id"] = analysis_id
            _set_job(
                job_id,
                status="waiting_for_back_label",
                stage="back_label_required",
                message="Another branded food needs a nutrition-label photo.",
                progress=1.0,
                result=continued_result,
            )
            return

        if status != "completed":
            raise ValueError(f"Unsupported continuation status: {status}")

        next_status, confirmation, session_data = (
            await _confirmation_after_label_analysis(
                continued_result,
                analysis_id=analysis_id,
                profile=session.get("profile"),
            )
        )
        # Preserve any session fields used by the back-label flow while
        # replacing the stored final meal with its resolved version.
        session.update(session_data)
        save_session(analysis_id=analysis_id, data=session)

        _set_job(
            job_id,
            status=next_status,
            stage=(
                "meal_confirmation"
                if next_status == "waiting_for_meal_confirmation"
                else "serving_confirmation"
            ),
            message=str(confirmation.get("message") or "Review the detected meal."),
            progress=1.0,
            result=confirmation,
        )
    except asyncio.CancelledError:
        _set_job(job_id, status="cancelled", stage="cancelled", message="Analysis cancelled.", progress=0.0)
    except Exception as error:
        _set_job(
            job_id,
            status="failed",
            stage="failed",
            message="The nutrition-label analysis could not be completed.",
            error=_public_job_error(error),
        )
    finally:
        shutil.rmtree(job_directory, ignore_errors=True)


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

            analysis_result = await asyncio.to_thread(
                _run_analysis_engine_locked,
                image_paths,
                profile_data,
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

            continued_result = await asyncio.to_thread(
                _run_back_label_engine_locked,
                partial_result,
                str(label_path),
                target_food_id,
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




async def _confirmation_after_label_analysis(
    result: dict[str, Any],
    *,
    analysis_id: str,
    profile: dict[str, Any] | None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Resolve the non-label portion of a meal and choose the correct review UI.

    Mixed meals must not lose their ordinary foods simply because one item
    required a nutrition label. The returned session data preserves the full
    resolved meal so final confirmation can merge USDA-backed foods and
    label-backed foods into one nutrient/scoring run.
    """
    resolved = await resolve_meal(result)
    session_data = {
        "analysis_id": analysis_id,
        "profile": profile,
        "confirmed_label_result": resolved,
    }

    label_payload = _label_serving_confirmation_payload(
        resolved,
        analysis_id=analysis_id,
    )

    try:
        draft_payload = _resolved_meal_to_review_draft(
            resolved,
            analysis_id=analysis_id,
        )
    except ValueError:
        # A label-only upload has no USDA-backed foods to review.
        return "waiting_for_serving_confirmation", label_payload, session_data

    draft_payload["label_items"] = label_payload.get("items", [])
    draft_payload["message"] = (
        "Review the detected foods, ingredients, quantities, and packaged-food serving before final analysis."
    )
    return "waiting_for_meal_confirmation", draft_payload, session_data


def _has_attached_nutrition_label_foods(result: dict[str, Any]) -> bool:
    meal = result.get("meal")
    if not isinstance(meal, dict):
        return False
    foods = meal.get("foods")
    if not isinstance(foods, list):
        return False
    return any(
        isinstance(food, dict)
        and food.get("analysis_route") == "NUTRITION_LABEL"
        and isinstance(food.get("nutrition_label"), dict)
        for food in foods
    )



def _normalize_label_quantity_unit(value: Any) -> str:
    unit = str(value or "").strip().lower()
    aliases = {
        "gram": "g",
        "grams": "g",
        "g": "g",
        "millilitre": "ml",
        "millilitres": "ml",
        "milliliter": "ml",
        "milliliters": "ml",
        "ml": "ml",
        "litre": "l",
        "litres": "l",
        "liter": "l",
        "liters": "l",
        "l": "l",
        "servings": "serving",
        "serving": "serving",
        "pieces": "piece",
        "piece": "piece",
        "can": "serving",
        "cans": "serving",
        "bottle": "serving",
        "bottles": "serving",
    }
    return aliases.get(unit, unit)


def _positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _authoritative_label_quantity(
    *,
    food: dict[str, Any],
    label: dict[str, Any],
) -> tuple[float, str, float | None, str]:
    """Choose a confirmation quantity/unit that can actually scale the label.

    The printed label unit is authoritative. A vision estimate such as
    ``250 g`` for a cola bottle must never be paired with a label whose
    nutrition is printed per ``355 ml``; nutrient_profile intentionally rejects
    that mismatch.
    """
    current_quantity = _positive_float(food.get("quantity"))
    current_unit = _normalize_label_quantity_unit(food.get("unit"))

    serving = label.get("serving_size")
    serving = serving if isinstance(serving, dict) else {}
    serving_value = _positive_float(serving.get("value"))
    serving_unit = _normalize_label_quantity_unit(serving.get("unit"))

    basis = label.get("nutrition_basis")
    basis = basis if isinstance(basis, dict) else {}
    basis_value = _positive_float(basis.get("value"))
    basis_unit = _normalize_label_quantity_unit(basis.get("unit"))

    net = label.get("net_weight")
    net = net if isinstance(net, dict) else {}
    net_value = _positive_float(net.get("value"))
    net_unit = _normalize_label_quantity_unit(net.get("unit"))

    # Prefer a printed serving unit because per-serving nutrient panels scale
    # directly from it. If there is no serving unit, use the printed per-100
    # basis, then the package/net unit.
    label_unit = ""
    if serving_unit in {"g", "ml"}:
        label_unit = serving_unit
    elif basis_unit in {"g", "ml"}:
        label_unit = basis_unit
    elif net_unit in {"g", "ml"}:
        label_unit = net_unit

    if label_unit:
        # Keep the vision quantity only when it is already expressed in the
        # exact same physical unit as the printed label.
        if current_quantity is not None and current_unit == label_unit:
            quantity = current_quantity
        elif serving_value is not None and serving_unit == label_unit:
            quantity = serving_value
        elif net_value is not None and net_unit == label_unit:
            quantity = net_value
        elif basis_value is not None and basis_unit == label_unit:
            quantity = basis_value
        else:
            quantity = 1.0
        return quantity, label_unit, serving_value, serving_unit

    # Count-based labels can still be scaled by number of servings/pieces.
    if current_quantity is not None and current_unit in {"serving", "piece"}:
        return current_quantity, current_unit, serving_value, serving_unit
    if serving_value is not None and serving_unit in {"serving", "piece"}:
        return serving_value, serving_unit, serving_value, serving_unit

    # Final fallback is explicitly one serving, not an invented gram amount.
    return 1.0, "serving", serving_value, serving_unit


def _label_serving_confirmation_payload(
    result: dict[str, Any],
    *,
    analysis_id: str,
) -> dict[str, Any]:
    meal = result.get("meal")
    if not isinstance(meal, dict):
        raise ValueError("The label analysis is missing meal data.")

    foods = meal.get("foods")
    if not isinstance(foods, list):
        raise ValueError("The label analysis is missing foods.")

    items: list[dict[str, Any]] = []
    for food in foods:
        if not isinstance(food, dict):
            continue
        if food.get("analysis_route") != "NUTRITION_LABEL":
            continue
        label = food.get("nutrition_label")
        if not isinstance(label, dict):
            continue

        quantity, unit, serving_value, serving_unit = (
            _authoritative_label_quantity(
                food=food,
                label=label,
            )
        )

        servings_per_container = label.get("servings_per_container")
        try:
            servings_per_container = float(servings_per_container)
        except (TypeError, ValueError):
            servings_per_container = None

        items.append(
            {
                "food_id": str(food.get("id") or ""),
                "name": str(
                    food.get("display_name")
                    or food.get("name")
                    or label.get("product_name")
                    or "Packaged food"
                ),
                "brand": food.get("brand") or label.get("brand"),
                "quantity": round(quantity, 3),
                "unit": unit,
                "serving_size_value": serving_value,
                "serving_size_unit": serving_unit or None,
                "servings_per_container": servings_per_container,
                "label_nutrient_source": (
                    "nutrition_per_serving"
                    if isinstance(label.get("nutrition_per_serving"), dict)
                    and any(
                        value is not None
                        for value in label.get("nutrition_per_serving", {}).values()
                    )
                    else "nutrition_per_100"
                ),
            }
        )

    if not items:
        raise ValueError(
            "No nutrition-label food was available for serving confirmation."
        )

    return {
        "status": "waiting_for_serving_confirmation",
        "analysis_id": analysis_id,
        "message": "Confirm how much of the packaged food you consumed.",
        "items": items,
    }


def _apply_label_serving_confirmation(
    result: dict[str, Any],
    request: LabelServingConfirmationRequest,
) -> dict[str, Any]:
    updated = copy.deepcopy(result)
    meal = updated.get("meal")
    if not isinstance(meal, dict):
        raise ValueError("The saved analysis is missing meal data.")
    foods = meal.get("foods")
    if not isinstance(foods, list):
        raise ValueError("The saved analysis is missing foods.")

    by_id = {item.food_id: item for item in request.items}
    matched = 0
    for food in foods:
        if not isinstance(food, dict):
            continue
        food_id = str(food.get("id") or "")
        item = by_id.get(food_id)
        if item is None:
            continue
        if food.get("analysis_route") != "NUTRITION_LABEL":
            continue

        unit = item.unit.strip().lower()
        aliases = {
            "gram": "g",
            "grams": "g",
            "milliliter": "ml",
            "milliliters": "ml",
            "litre": "l",
            "liter": "l",
            "liters": "l",
            "servings": "serving",
            "pieces": "piece",
        }
        unit = aliases.get(unit, unit)
        quantity = float(item.quantity)
        if unit == "l":
            quantity *= 1000.0
            unit = "ml"

        if unit not in {"g", "ml", "serving", "piece"}:
            raise ValueError(
                f"Unsupported serving unit '{item.unit}' for {food_id}."
            )

        food["quantity"] = quantity
        food["unit"] = unit
        if unit == "g":
            food["estimated_weight_g"] = quantity
        else:
            food.pop("estimated_weight_g", None)
        matched += 1

    if matched == 0:
        raise ValueError("No packaged-food serving was updated.")

    # Recalculate visible gram weight only from foods that actually have gram
    # quantities. Do not pretend ml/serving counts are grams.
    visible_g = 0.0
    for food in foods:
        if not isinstance(food, dict):
            continue
        if str(food.get("unit") or "").lower() != "g":
            continue
        try:
            q = float(food.get("quantity"))
        except (TypeError, ValueError):
            continue
        if q > 0:
            visible_g += q
    meal["estimated_visible_food_weight_g"] = round(visible_g, 3)

    return updated


def _resolved_meal_to_review_draft(
    resolved_result: dict[str, Any],
    *,
    analysis_id: str,
) -> dict[str, Any]:
    """Convert resolved vision foods into the same editable USDA recipe contract used by Flutter."""
    meal = resolved_result.get("meal")
    if not isinstance(meal, dict):
        raise ValueError("Resolved analysis is missing meal data.")

    raw_foods = meal.get("foods")
    if not isinstance(raw_foods, list):
        raise ValueError("Resolved analysis is missing foods.")

    ingredients: list[dict[str, Any]] = []
    unresolved: list[str] = []

    for food in raw_foods:
        if not isinstance(food, dict):
            continue
        if food.get("display_in_food_list") is False:
            continue

        if food.get("analysis_route") == "NUTRITION_LABEL":
            # Packaged foods are reviewed using their printed-label serving
            # data, not forced through a USDA ingredient record.
            continue

        resolver = food.get("resolver")
        if not isinstance(resolver, dict):
            resolver = {}

        fdc_id = resolver.get("fdc_id")
        try:
            fdc_id = int(fdc_id)
        except (TypeError, ValueError):
            unresolved.append(str(food.get("display_name") or food.get("name") or "Food"))
            continue

        grams = food.get("estimated_weight_g")
        if grams is None and str(food.get("unit") or "").lower() in {"g", "gram", "grams"}:
            grams = food.get("quantity")
        try:
            grams = float(grams)
        except (TypeError, ValueError):
            grams = 0.0
        if grams <= 0:
            unresolved.append(str(food.get("display_name") or food.get("name") or "Food"))
            continue

        matched = str(
            resolver.get("matched_name")
            or resolver.get("matched_description")
            or resolver.get("description")
            or food.get("canonical_name")
            or food.get("display_name")
            or food.get("name")
            or "Food"
        ).strip()

        display_name = str(
            food.get("display_name")
            or food.get("name")
            or matched
        ).strip()

        preparation = str(food.get("preparation") or "").strip()
        quantity_basis = str(
            food.get("quantity_basis") or "as_served"
        ).strip()

        ingredients.append(
            {
                "food": {
                    "fdc_id": fdc_id,
                    "description": matched,
                    "display_name": display_name,
                    "data_type": str(resolver.get("data_type") or "USDA"),
                    "food_category": food.get("category"),
                    "brand_owner": resolver.get("brand_owner"),
                    "preparation": preparation or None,
                    "quantity_basis": quantity_basis,
                    "match_query": resolver.get("match_query"),
                },
                "grams": round(grams, 3),
            }
        )

    meal_name = str(
        meal.get("meal_name")
        or meal.get("meal_type")
        or "Detected meal"
    ).strip()

    return {
        "status": "waiting_for_meal_confirmation",
        "analysis_id": analysis_id,
        "message": "Review the detected foods and quantities before final analysis.",
        "meal_draft": {
            "id": analysis_id,
            "name": meal_name or "Detected meal",
            "source": "photo",
            "ingredients": ingredients,
            "servings_made": 1.0,
            "servings_eaten": 1.0,
        },
        "unresolved_foods": unresolved,
    }


async def run_nutrica_pipeline(
    analysis_result: dict[str, Any],
    profile: dict[str, Any] | None = None,
    progress_callback: Any | None = None,
    cancellation_check: Any | None = None,
) -> dict[str, Any]:
    """Run the post-vision pipeline while reporting real stage boundaries."""

    def report(stage: str, message: str, progress: float) -> None:
        if cancellation_check is not None:
            cancellation_check()
        if progress_callback is not None:
            progress_callback(stage, message, progress)

    async def timed(stage: str, awaitable: Any) -> Any:
        started = time.perf_counter()
        value = await awaitable
        logger.info(
            "pipeline stage=%s elapsed_ms=%.1f",
            stage,
            (time.perf_counter() - started) * 1000,
        )
        return value

    report("food_resolution", "Matching foods and ingredients to nutrition databases…", 0.28)
    resolved_result = await timed("food_resolution", resolve_meal(analysis_result))

    report("nutrient_calculation", "Calculating calories, macros, vitamins and minerals…", 0.45)
    nutrient_result = await timed("nutrient_calculation", attach_nutrients(resolved_result))

    report("feature_engineering", "Measuring nutrient density and meal-quality features…", 0.60)
    feature_result = await timed("feature_engineering", compute_features(nutrient_result))

    report("evidence_mapping", "Linking meal features to nutrition evidence…", 0.71)
    evidence_result = await timed("evidence_mapping", attach_evidence(feature_result))

    report("health_scoring", "Calculating health-domain scores…", 0.83)
    scored_result = await timed("health_scoring", attach_domain_scores(evidence_result))

    normalized_profile = normalize_user_profile(profile)

    report("personalization", "Applying your health and lifestyle profile…", 0.93)
    personalized_result = await timed(
        "personalization",
        attach_personalization(scored_result, normalized_profile),
    )

    report("nutrient_targets", "Resolving your personalized daily nutrient targets…", 0.98)
    final_result = attach_nutrient_targets(
        personalized_result,
        normalized_profile,
    )

    return final_result


async def run_manual_recipe_pipeline(
    prepared_result: dict[str, Any],
    profile: dict[str, Any] | None = None,
    progress_callback: Any | None = None,
    cancellation_check: Any | None = None,
) -> dict[str, Any]:
    """Run the normal pipeline after USDA resolution has already been chosen by the user."""

    def report(stage: str, message: str, progress: float) -> None:
        if cancellation_check is not None:
            cancellation_check()
        if progress_callback is not None:
            progress_callback(stage, message, progress)

    async def timed(stage: str, awaitable: Any) -> Any:
        started = time.perf_counter()
        value = await awaitable
        logger.info(
            "manual pipeline stage=%s elapsed_ms=%.1f",
            stage,
            (time.perf_counter() - started) * 1000,
        )
        return value

    report("nutrient_calculation", "Loading USDA nutrients for your ingredients…", 0.38)
    nutrient_result = await timed("nutrient_calculation", attach_nutrients(prepared_result))

    report("feature_engineering", "Measuring nutrient density and meal-quality features…", 0.58)
    feature_result = await timed("feature_engineering", compute_features(nutrient_result))

    report("evidence_mapping", "Linking recipe features to nutrition evidence…", 0.70)
    evidence_result = await timed("evidence_mapping", attach_evidence(feature_result))

    report("health_scoring", "Calculating health-domain scores…", 0.82)
    scored_result = await timed("health_scoring", attach_domain_scores(evidence_result))

    normalized_profile = normalize_user_profile(profile)
    report("personalization", "Applying your health and lifestyle profile…", 0.92)
    personalized_result = await timed(
        "personalization",
        attach_personalization(scored_result, normalized_profile),
    )

    report("nutrient_targets", "Resolving your personalized daily nutrient targets…", 0.98)
    return attach_nutrient_targets(personalized_result, normalized_profile)


def normalize_personalization_profile(
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Backward-compatible wrapper.

    New code should call normalize_user_profile() directly. This wrapper is
    retained only so older tests or imports do not break.
    """
    return normalize_user_profile(
        profile
    )


def has_personalization_modifiers(
    profile: dict[str, Any] | None,
) -> bool:
    """Return whether the profile activates any health-score modifier."""
    normalized = normalize_user_profile(
        profile
    )

    return bool(
        determine_active_modifiers(
            normalized,
            load_modifier_database(),
        )
    )


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
