"""Tests for packaged ESTOFEX assets."""

from __future__ import annotations

from pathlib import Path


def test_no_forecast_image_is_packaged_png() -> None:
    """The camera fallback image should be present in the integration package."""
    image_path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "estofex"
        / "assets"
        / "no_forecast.png"
    )

    assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_brand_icon_is_packaged_png() -> None:
    """The HACS brand icon should be present in the repository."""
    image_path = Path(__file__).resolve().parents[1] / "brand" / "icon.png"

    assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
