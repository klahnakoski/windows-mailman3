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

> Run tests with `.\.tox\py312-nocov\Scripts\python.exe`, not `.\.venv\Scripts\python.exe`.

---

## Running Tests

```powershell
# single test
.\.tox\py312-nocov\Scripts\python.exe run_tests.py test_output.txt -v mailman.handlers.tests.test_replybot.TestReplybot.test_response
# test class
.\.tox\py312-nocov\Scripts\python.exe run_tests.py test_output.txt -v mailman.chains.tests.test_base.TestMiscellaneous
# all (fail-fast)
.\.tox\py312-nocov\Scripts\python.exe run_tests.py test_output.txt -v -F
```

Results in `test_output.txt`. `RETURN CODE: 0` = pass.

---

## Known Issues

- **flufl.lock teardown noise** — `FileNotFoundError` in layer tearDown. Tests pass.

---

This repo: <https://github.com/klahnakoski/windows-mailman3>  
Upstream: <https://gitlab.com/mailman/mailman> — GPLv3+
