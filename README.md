# GNU Mailman 3 — Windows Port

Fork of [GNU Mailman 3](https://gitlab.com/mailman/mailman). Runs natively on Windows.

---

## Changes from upstream

| Area | Change |
|---|---|
| `lazr.config` | Local shim — no Unix `grp`/`pwd` deps |
| Template filenames | `:` → `_` |
| `safe_rename()` | Handles Windows `FileExistsError` |
| Unix-only tests | Skipped via `@skipWindows` |
| File handles | Closed before rename/delete |

---

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\pip install tox
.\.venv\Scripts\tox.exe -e py312-nocov   # once
```

## Running Tests

Run all tests:

```commandline
tox.exe -e py312-nocov
```

Run specific test module:

```
tox.exe -e py312-nocov -- -v mailman.commands.tests
```

Run tests on Docker:

```
docker build -f dev/Dockerfile.test .
```

Run a single module

```
docker build --build-arg NOSE_ARGS="mailman.app.tests.test_bounces" -f dev/Dockerfile.test .
```
