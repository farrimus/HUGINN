# tests/ -- Test Suite

pytest + pytest-asyncio. Run from project root.

## Running Tests

```bash
.venv/bin/pytest tests/                    # all tests
.venv/bin/pytest tests/test_config.py      # single file
.venv/bin/pytest tests/ --collect-only -q  # list without running
```

## Structure

| Path | What it covers |
|------|---------------|
| tests/test_main.py | Integration -- endpoint tests via ASGI transport |
| tests/test_*.py | Unit -- config, routing, search, galaxy DB, ship profiles, etc. |
| tests/tools/ | AI tool handler tests (threat, memory, route, killmail, alert, structure) |
| tests/conftest.py | Shared fixtures |

28 test files in tests/, 6 in tests/tools/.

## Known Issues

Some tests have collection errors from import dependencies (galaxy DB path, missing python-multipart). These predate the current work and need fixing before adding new tests.

## Conventions

- Test files mirror src/ module names: `test_<module>.py`.
- Use pytest-asyncio for async endpoint tests.
- Endpoint tests use httpx ASGI transport -- no live server needed.
