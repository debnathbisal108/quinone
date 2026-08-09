from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

USDA_API_KEY = os.getenv("USDA_API_KEY", "DEMO_KEY")
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
CACHE_TTL_SECONDS = 15 * 60
MAX_CACHE_ITEMS = 250

_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_cache_lock = asyncio.Lock()

_DATA_TYPE_SCORE = {
    "Foundation": 40,
    "SR Legacy": 34,
    "Survey (FNDDS)": 27,
    "Branded": 8,
}


def _clean_query(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9\s\-']+", " ", value or "")
    return re.sub(r"\s+", " ", value).strip()


def _tokens(value: str) -> list[str]:
    return [token for token in re.split(r"\W+", value.lower()) if token]


def _candidate_score(candidate: dict[str, Any], query: str) -> float:
    description = str(candidate.get("description") or "")
    data_type = str(candidate.get("dataType") or "")
    brand_owner = str(candidate.get("brandOwner") or candidate.get("brandName") or "")
    q = query.lower().strip()
    d = description.lower()
    score = float(_DATA_TYPE_SCORE.get(data_type, 0))

    if d == q:
        score += 60
    elif d.startswith(q):
        score += 38
    elif q in d:
        score += 22

    query_tokens = set(_tokens(query))
    description_tokens = set(_tokens(description))
    if query_tokens:
        score += 24 * len(query_tokens & description_tokens) / len(query_tokens)

    # Generic/manual recipe searches should not be dominated by branded products.
    if data_type == "Branded" and not any(token in brand_owner.lower() for token in query_tokens):
        score -= 14

    # Penalize obviously unrelated long descriptions.
    score -= max(0, len(description_tokens) - len(query_tokens) - 8) * 0.35
    return score


def _display_name(description: str) -> str:
    # USDA descriptions are useful but can be visually noisy. Preserve meaning,
    # normalize whitespace, and sentence-case only when the source is all caps.
    value = re.sub(r"\s+", " ", description).strip()
    if value.isupper():
        value = value.title()
    return value


def _normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
    fdc_id = candidate.get("fdcId")
    description = str(candidate.get("description") or "").strip()
    if not isinstance(fdc_id, int) or not description:
        return None
    return {
        "fdc_id": fdc_id,
        "description": description,
        "display_name": _display_name(description),
        "data_type": str(candidate.get("dataType") or "Unknown"),
        "food_category": str(candidate.get("foodCategory") or "").strip() or None,
        "brand_owner": str(candidate.get("brandOwner") or candidate.get("brandName") or "").strip() or None,
    }


async def search_usda_foods(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    cleaned = _clean_query(query)
    if len(cleaned) < 2:
        return []
    cache_key = cleaned.lower()
    now = time.time()

    async with _cache_lock:
        cached = _cache.get(cache_key)
        if cached is not None and now - cached[0] < CACHE_TTL_SECONDS:
            return cached[1][:limit]

    payload = {
        "query": cleaned,
        "pageSize": 30,
        "pageNumber": 1,
        "dataType": ["Foundation", "SR Legacy", "Survey (FNDDS)", "Branded"],
    }
    params = {"api_key": USDA_API_KEY}

    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0)) as client:
        response = await client.post(USDA_SEARCH_URL, params=params, json=payload)
        response.raise_for_status()
        body = response.json()

    raw_foods = body.get("foods", []) if isinstance(body, dict) else []
    normalized: list[tuple[float, dict[str, Any]]] = []
    seen: set[int] = set()
    for item in raw_foods if isinstance(raw_foods, list) else []:
        if not isinstance(item, dict):
            continue
        candidate = _normalize_candidate(item)
        if candidate is None or candidate["fdc_id"] in seen:
            continue
        seen.add(candidate["fdc_id"])
        normalized.append((_candidate_score(item, cleaned), candidate))

    normalized.sort(key=lambda pair: pair[0], reverse=True)
    results = [candidate for _, candidate in normalized[: max(limit, 12)]]

    async with _cache_lock:
        if len(_cache) >= MAX_CACHE_ITEMS:
            oldest_key = min(_cache, key=lambda key: _cache[key][0])
            _cache.pop(oldest_key, None)
        _cache[cache_key] = (now, results)

    return results[:limit]
