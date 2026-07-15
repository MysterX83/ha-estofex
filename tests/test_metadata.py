"""Release metadata tests for ESTOFEX."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "estofex"
REPOSITORY_URL = "https://github.com/MysterX83/ha-estofex"
OLD_REPOSITORY_OWNER = "dvo" + "laart"
OLD_REFERENCES = (f"{OLD_REPOSITORY_OWNER}/ha-estofex", f"@{OLD_REPOSITORY_OWNER}")


def _load_json(path: str):
    """Load a JSON file from the repository."""
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_manifest_release_metadata() -> None:
    """Manifest metadata should point at the public release repository."""
    manifest = _load_json("custom_components/estofex/manifest.json")

    assert manifest["domain"] == DOMAIN
    assert manifest["name"] == "ESTOFEX"
    assert manifest["version"] == "0.5.0"
    assert manifest["documentation"] == REPOSITORY_URL
    assert manifest["issue_tracker"] == f"{REPOSITORY_URL}/issues"
    assert manifest["codeowners"] == ["@MysterX83"]
    assert manifest["config_flow"] is True
    assert manifest["single_config_entry"] is True
    assert manifest["integration_type"] == "service"
    assert manifest["iot_class"] == "cloud_polling"
    assert manifest["requirements"] == []


def test_hacs_metadata() -> None:
    """HACS metadata should describe one integration repository."""
    hacs = _load_json("hacs.json")

    assert hacs["name"] == "ESTOFEX"
    assert hacs["render_readme"] is True
    assert hacs["homeassistant"] == "2024.6.0"
    assert hacs["domains"] == ["binary_sensor", "button", "camera", "sensor"]


def test_translation_keys_match_entities() -> None:
    """Translation files should cover every entity translation key."""
    expected = {
        "binary_sensor": {
            "local_warning",
            "thunderstorm_risk",
            "forecast_changed",
            "large_hail",
            "severe_wind",
            "excessive_rain",
            "tornado",
            "flash_flood",
        },
        "button": {"update_now"},
        "camera": {"map"},
        "sensor": {
            "forecast_id",
            "active_forecasts",
            "issued_at",
            "valid_until",
            "forecast_number",
            "map_url",
            "local_level",
            "local_summary",
            "discussion",
            "summary_nl",
            "discussion_nl",
            "last_checked",
            "last_successful_update",
            "last_changed",
            "image_downloaded",
            "http_status",
            "status",
        },
    }

    for language in ("en", "nl"):
        translations = _load_json(
            f"custom_components/estofex/translations/{language}.json"
        )
        entities = translations["entity"]
        for platform, keys in expected.items():
            assert set(entities[platform]) == keys
            assert all("name" in entities[platform][key] for key in keys)


def test_tracked_files_do_not_reference_previous_repository() -> None:
    """Release files should not point users to the previous repository owner."""
    tracked_files = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
    ).splitlines()

    for relative_path in tracked_files:
        path = ROOT / relative_path
        if path.suffix.lower() == ".png":
            continue
        text = path.read_text(encoding="utf-8")
        assert not any(old_reference in text for old_reference in OLD_REFERENCES), (
            f"old repository reference found in {relative_path}"
        )


def test_public_attributes_do_not_expose_local_map_path() -> None:
    """Entity attributes should not expose Home Assistant local filesystem paths."""
    sensor_source = (ROOT / "custom_components/estofex/sensor.py").read_text(
        encoding="utf-8"
    )

    assert '"local_map_path"' not in sensor_source
