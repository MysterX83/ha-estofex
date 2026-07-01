# Changelog

All notable changes to this project will be documented in this file.

This project follows [Semantic Versioning](https://semver.org/).

## [0.4.0] - 2026-06-30

### Added

- Public-release README with installation, entities, events, troubleshooting, architecture, and roadmap.
- Home Assistant diagnostics support.
- Domain-specific API client and exception classes.
- GitHub Actions CI for hassfest, Ruff, and pytest.
- Basic pytest structure for parser and geometry behavior.

### Changed

- Prepared project metadata for first public HACS/GitHub release.
- Refined architecture around API, parser, coordinator, models, geometry, and entities.
- Updated manifest version to `0.4.0`.

### Notes

- Dutch translation and summary hooks remain provider-free.
- Mesoscale Discussions are modeled for future support but not fully implemented.

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
