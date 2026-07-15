"""Safe filesystem helpers for the ESTOFEX map cache."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

FORECAST_IMAGE_PREFIX = "forecast_"
FORECAST_IMAGE_SUFFIX = ".png"
_MAX_SAFE_ID_LENGTH = 120


def safe_forecast_id(forecast_id: str) -> str:
    """Return a deterministic filename-safe representation of a forecast id."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", forecast_id).strip("._")
    safe = safe[:_MAX_SAFE_ID_LENGTH].rstrip("._") or "forecast"
    if safe != forecast_id:
        digest = hashlib.sha256(forecast_id.encode()).hexdigest()[:10]
        safe = f"{safe[: _MAX_SAFE_ID_LENGTH - 11]}_{digest}"
    return safe


def forecast_image_filename(forecast_id: str) -> str:
    """Return the integration-owned map filename for one forecast."""
    return (
        f"{FORECAST_IMAGE_PREFIX}{safe_forecast_id(forecast_id)}{FORECAST_IMAGE_SUFFIX}"
    )


def remove_inactive_forecast_maps(
    cache_dir: Path,
    expected: set[Path],
) -> None:
    """Remove only integration-owned per-forecast maps not in ``expected``."""
    if not cache_dir.exists():
        return
    for path in cache_dir.glob(f"{FORECAST_IMAGE_PREFIX}*{FORECAST_IMAGE_SUFFIX}"):
        if path.is_file() and path not in expected:
            path.unlink()
