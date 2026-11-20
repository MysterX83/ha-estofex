# Development and testing

[Documentation index](../README.md) · [Contribution guidelines](../../CONTRIBUTING.md)

## Local checks

Run from the repository root using Python 3.12. A separate environment keeps tools
out of the system Python installation:

```bash
python3.12 -m venv /tmp/estofex-unit-tests
/tmp/estofex-unit-tests/bin/python -m pip install pytest ruff==0.15.20
/tmp/estofex-unit-tests/bin/python -m pytest
/tmp/estofex-unit-tests/bin/ruff check .
/tmp/estofex-unit-tests/bin/ruff format --check .
/tmp/estofex-unit-tests/bin/python -m compileall -q custom_components/estofex
```

The default pytest configuration in `pyproject.toml` collects `tests/` only.
The unit helpers provide Home Assistant module stubs; they do not validate the
real framework's lifecycle or API compatibility.

## Real Home Assistant tests

Use a separate environment and process as described in
[CONTRIBUTING.md](../../CONTRIBUTING.md#development):

```bash
python3.12 -m venv /tmp/estofex-ha-tests
/tmp/estofex-ha-tests/bin/python -m pip install -r requirements-test-ha.txt
/tmp/estofex-ha-tests/bin/python -m pytest -c tests_ha/pytest.ini tests_ha
```

Do not collect both suites in one invocation: unit-test stubs modify Python's
module registry. The framework suite pins Home Assistant 2024.11.3 through
`pytest-homeassistant-custom-component`; this establishes coverage for that
version, not compatibility with every newer Home Assistant release. Update the
pin, Python version and compatibility constraints together deliberately.

## Where to add coverage

| Change | Relevant tests |
| --- | --- |
| Source recognition, dates, discussion or hazards | `tests/test_parser.py` |
| Polygon boundaries or longitude handling | `tests/test_geometry.py` |
| Activity, ordering or combined warnings | `tests/test_models.py` |
| Refresh, recovery, expiry or events | `tests/test_coordinator.py` |
| Safe filenames and cache cleanup | `tests/test_map_cache.py` |
| Entity attributes and camera behavior | `tests/test_entities.py`, `tests/test_camera.py` |
| Package metadata and bundled assets | `tests/test_metadata.py`, `tests/test_assets.py` |
| Config flow, setup, refresh button, real states, unload/reload | `tests_ha/test_integration.py` |

Use fixed source responses and deterministic time. Tests must not make live
ESTOFEX requests. Framework fixtures mock the ESTOFEX API methods while retaining
the actual coordinator and Home Assistant framework. Include a failure/recovery
case when changing error policy, and overlapping forecasts when changing warning
aggregation.

## CI and documentation maintenance

GitHub Actions runs separate unit and framework jobs in
[tests.yml](../../.github/workflows/tests.yml), Ruff in
[lint.yml](../../.github/workflows/lint.yml), and integration metadata validation in
[hassfest.yml](../../.github/workflows/hassfest.yml).

For a behavior change, update the affected high- or low-level page and the public
README if its interface changes. Check relative links and `git diff --check` for
documentation edits. Documentation-only edits do not require application tests.
Use the [changelog](../../CHANGELOG.md) for release history rather than embedding
release narratives throughout the design documents.
