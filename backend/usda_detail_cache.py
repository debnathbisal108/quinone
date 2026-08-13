"""Small process-local cache shared by USDA resolution and nutrient loading.

The resolver already downloads Food Details to reject stale search IDs. The
nutrient stage used to download the same record again immediately afterward.
Keeping the successful JSON here removes that duplicate request while retaining
the stale-ID safety check.
"""

from __future__ import annotations

import copy
from threading import RLock
from typing import Any


_lock = RLock()
_details: dict[int, dict[str, Any]] = {}


def get_food_detail(fdc_id: int) -> dict[str, Any] | None:
    with _lock:
        value = _details.get(int(fdc_id))
        return copy.deepcopy(value) if value is not None else None


def set_food_detail(fdc_id: int, detail: dict[str, Any]) -> None:
    if not isinstance(detail, dict):
        return
    with _lock:
        _details[int(fdc_id)] = copy.deepcopy(detail)


def remove_food_detail(fdc_id: int) -> None:
    with _lock:
        _details.pop(int(fdc_id), None)


def cache_size() -> int:
    with _lock:
        return len(_details)
