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

```
Run specific test module:

```-- -v mailman.commands.tests
```
