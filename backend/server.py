from __future__ import annotations

import asyncio
import copy
import json
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from threading import Lock, RLock
from typing import Any

from pydantic import BaseModel, Field

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
from usda_recipe_service import search_usda_foods

from personalization_engine import (
    attach_personalization,
    determine_active_modifiers,
    load_modifier_database,
    normalize_user_profile,
)
from nutrient_target_engine import (
    attach_nutrient_targets,
)


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



class ManualRecipeIngredientRequest(BaseModel):
    fdc_id: int
    name: str
    description: str
    data_type: str | None = None
    food_category: str | None = None
    grams: float = Field(gt=0, le=100000)


class ManualRecipeRequest(BaseModel):
    recipe_name: str = "Manual recipe"
    ingredients: list[ManualRecipeIngredientRequest]
    servings_made: float = Field(default=1.0, gt=0, le=10000)
    servings_eaten: float = Field(default=1.0, gt=0, le=10000)
    profile: dict[str, Any] | None = None


@app.get("/recipes/usda/search")
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
async def start_manual_recipe_job(request: ManualRecipeRequest) -> dict[str, Any]:
    if not request.ingredients:
        raise HTTPException(status_code=400, detail="Add at least one recipe ingredient.")
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


@app.get("/analyze/jobs/{job_id}")
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
    }
    if job["status"] in {
        "completed",
        "waiting_for_back_label",
        "no_food_detected",
    }:
        response["result"] = job.get("result")
    return response


@app.post("/analyze/jobs/{job_id}/cancel")
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
        analysis_result = await asyncio.to_thread(
            _run_analysis_engine_locked,
            image_paths,
            profile_data,
        )
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

        final_result = await run_nutrica_pipeline(
            analysis_result,
            profile=profile_data,
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
            message="The meal analysis could not be completed.",
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

        for index, ingredient in enumerate(request.ingredients, start=1):
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
                    "resolver": {
                        "status": "resolved",
                        "fdc_id": ingredient.fdc_id,
                        "matched_description": ingredient.description,
                        "data_type": ingredient.data_type,
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
            error=str(error),
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
        continued_result = await asyncio.to_thread(
            _run_back_label_engine_locked,
            partial_result,
            label_path,
            target_food_id,
        )
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

        final_result = await run_nutrica_pipeline(
            continued_result,
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
        _set_job(job_id, status="cancelled", stage="cancelled", message="Analysis cancelled.", progress=0.0)
    except Exception as error:
        _set_job(
            job_id,
            status="failed",
            stage="failed",
            message="The nutrition-label analysis could not be completed.",
            error=str(error),
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
    progress_callback: Any | None = None,
    cancellation_check: Any | None = None,
) -> dict[str, Any]:
    """Run the post-vision pipeline while reporting real stage boundaries."""

    def report(stage: str, message: str, progress: float) -> None:
        if cancellation_check is not None:
            cancellation_check()
        if progress_callback is not None:
            progress_callback(stage, message, progress)

    report("food_resolution", "Matching foods and ingredients to nutrition databases…", 0.28)
    resolved_result = await resolve_meal(analysis_result)

    report("nutrient_calculation", "Calculating calories, macros, vitamins and minerals…", 0.45)
    nutrient_result = await attach_nutrients(resolved_result)

    report("feature_engineering", "Measuring nutrient density and meal-quality features…", 0.60)
    feature_result = await compute_features(nutrient_result)

    report("evidence_mapping", "Linking meal features to nutrition evidence…", 0.71)
    evidence_result = await attach_evidence(feature_result)

    report("health_scoring", "Calculating health-domain scores…", 0.83)
    scored_result = await attach_domain_scores(evidence_result)

    normalized_profile = normalize_user_profile(profile)

    report("personalization", "Applying your health and lifestyle profile…", 0.93)
    personalized_result = await attach_personalization(
        scored_result,
        normalized_profile,
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

    report("nutrient_calculation", "Loading USDA nutrients for your ingredients…", 0.38)
    nutrient_result = await attach_nutrients(prepared_result)

    report("feature_engineering", "Measuring nutrient density and meal-quality features…", 0.58)
    feature_result = await compute_features(nutrient_result)

    report("evidence_mapping", "Linking recipe features to nutrition evidence…", 0.70)
    evidence_result = await attach_evidence(feature_result)

    report("health_scoring", "Calculating health-domain scores…", 0.82)
    scored_result = await attach_domain_scores(evidence_result)

    normalized_profile = normalize_user_profile(profile)
    report("personalization", "Applying your health and lifestyle profile…", 0.92)
    personalized_result = await attach_personalization(scored_result, normalized_profile)

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
