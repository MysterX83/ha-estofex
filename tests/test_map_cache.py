"""Tests for safe ESTOFEX map-cache helpers."""

from __future__ import annotations

from .helpers import load_estofex_module

map_cache = load_estofex_module("map_cache")


def test_unsafe_forecast_id_cannot_escape_cache_directory(tmp_path) -> None:
    """Unsafe path characters are sanitized into one deterministic filename."""
    filename = map_cache.forecast_image_filename("../../bad/id?<forecast>.xml")
    path = tmp_path / filename

    assert path.parent == tmp_path
    assert filename.startswith("forecast_")
    assert filename.endswith(".png")
    assert "/" not in filename
    assert ".." not in filename
    assert filename == map_cache.forecast_image_filename("../../bad/id?<forecast>.xml")


def test_cache_cleanup_removes_only_owned_inactive_maps(tmp_path) -> None:
    """Cleanup preserves the active map, latest alias, and unrelated files."""
    active = tmp_path / "forecast_active.png"
    expired = tmp_path / "forecast_expired.png"
    latest = tmp_path / "latest.png"
    unrelated = tmp_path / "family_photo.png"
    for path in (active, expired, latest, unrelated):
        path.write_bytes(b"image")

    map_cache.remove_inactive_forecast_maps(tmp_path, {active})

    assert active.exists()
    assert not expired.exists()
    assert latest.exists()
    assert unrelated.exists()
