# Tests Overview

The suite is split into two layers:

- `tests/test_parsers_unit.py`: offline, deterministic unit coverage for the three parsers, downloader path handling, and validation utilities. Uses handcrafted fixtures; no network calls.
- `tests/test_13f_nport_integration.py` and `tests/test_section16_parser.py`: live integration tests that call SEC endpoints to verify real-file parsing. These are marked with `@pytest.mark.integration`.

Running guidance:

- Default unit run: `pytest tests/test_parsers_unit.py`
- Full suite including live calls (slow, requires network): `pytest -m integration`
