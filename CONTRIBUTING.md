# Contributing

Thanks for helping improve ESTOFEX for Home Assistant.

## Development

1. Fork the repository.
2. Create a branch for a focused change.
3. Keep API access, parsing, coordinator logic, entities, and diagnostics separated.
4. Avoid live ESTOFEX requests in tests; mock external responses.
5. Run the local checks before opening a pull request:

   ```bash
   ruff check .
   ruff format --check .
   pytest
   python3 -m compileall custom_components/estofex
   ```

Run the real Home Assistant integration tests in a separate Python 3.12
environment and process. The fast unit tests install module stubs and must not
be collected together with the real framework tests:

```bash
python3.12 -m venv /tmp/estofex-ha-tests
/tmp/estofex-ha-tests/bin/python -m pip install -r requirements-test-ha.txt
/tmp/estofex-ha-tests/bin/python -m pytest -c tests_ha/pytest.ini tests_ha
```

This suite pins Home Assistant 2024.11.3 and exercises config flow, platform
setup, entity state, warning events, refresh and unload. Only ESTOFEX network
responses are mocked; it makes no live ESTOFEX requests. CI runs both suites
in separate jobs. Update the Home Assistant test dependency pin deliberately
alongside its Python version and compatibility constraints.

## Scope

Version `0.4.x` is focused on release quality and bug fixes. Larger features such as AI summaries, Mesoscale Discussions, LightningMaps, KNMI, DWD, ESWD, and a custom Lovelace card should target a later release.

## Privacy

Do not add diagnostics, logs, or attributes that expose credentials, tokens, precise Home Assistant location, private URLs, or local filesystem paths.
