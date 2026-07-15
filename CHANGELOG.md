# Changelog

All notable changes to this project will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/).

## [0.5.0] - 2026-07-15

### Added

- Support for all simultaneously active ESTOFEX forecasts with deterministic primary selection.
- A compact active-forecast count sensor and dynamic map camera per active forecast.
- Safe per-forecast map caching while retaining `/local/estofex/latest.png` for the primary camera.
- Full sanitized discussion text and Markdown attributes on the discussion sensor.
- A combined local thunderstorm-risk binary sensor for ESTOFEX levels 1, 2, and 3.
- Multi-forecast diagnostics, event metadata, and mocked lifecycle/cache/offline tests.

### Changed

- Existing primary forecast sensors and camera now read the newest active forecast from an immutable collection model.
- Local warning and hazard binary sensors combine matches across every active forecast.
- Forecast-update events now react to additions, removals, and primary changes without polling-cycle event spam.
- Per-forecast source, parsing, discussion, and map failures are isolated where usable data remains.

### Compatibility

- Preserved existing entity unique IDs, config entries, status values, events, update button, and primary map URL.
- Preserved `text` and `original_text` as discussion attribute aliases; `discussion` and `discussion_markdown` are preferred.

## [0.4.0] - 2026-07-10

### Added

- Public-release README with installation, entities, events, troubleshooting, architecture, and roadmap.
- Home Assistant diagnostics support.
- Domain-specific API client and exception classes.
- GitHub Actions CI for hassfest, Ruff, and pytest.
- Basic pytest structure for parser and geometry behavior.
- Built-in no-forecast placeholder image for the map camera.
- Release metadata and documentation for custom HACS installation.

### Changed

- Finalized project metadata for the first public HACS/GitHub release.
- Refined architecture around API, parser, coordinator, models, geometry, and entities.
- Updated manifest version to `0.4.0`.
- Treat expired ESTOFEX forecasts as no active forecast so stale maps are cleared.

### Notes

- Dutch translation and summary hooks remain provider-free.
- Mesoscale Discussions are modeled for future support but not fully implemented.
- `sensor.estofex_image_downloaded` remains a diagnostic string sensor for v0.4.0; a binary sensor migration can be considered in a later release.

## [0.3.0] - 2026-06-30

### Added

- Forecast domain models.
- ESTOFEX XML polygon parsing.
- Local warning detection using Home Assistant latitude/longitude.
- Hazard binary sensors.
- Home Assistant events for forecast updates and local warning transitions.

## [0.2.0] - 2026-06-30

### Added

- Status and diagnostic sensors.
- Improved update/download policy.
- Manual update button using the coordinator refresh path.

## [0.1.0] - 2026-06-30

### Added

- Initial config flow.
- Hourly `DataUpdateCoordinator`.
- ESTOFEX map camera.
- Forecast metadata sensors.
