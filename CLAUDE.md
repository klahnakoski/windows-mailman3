# CLAUDE.md -- Development Guide
## Running Tests
### Important: IntelliJ Copilot Terminal Limitation
The IntelliJ Copilot terminal tool does **not** reliably capture stdout/stderr.
Always use the `run_tests.py` wrapper which writes output to a file:
```
.\.venv\Scripts\python.exe run_tests.py test_output.txt [nose2 args...]
```
Then read `test_output.txt` to see results.
### Run a single test
```
.\.venv\Scripts\python.exe run_tests.py test_output.txt -v mailman.app.tests.test_bounces.TestSendProbeNonEnglish.test_probe_notice_with_member_nonenglish
```
### Run a single test module
```
.\.venv\Scripts\python.exe run_tests.py test_output.txt -v mailman.utilities.lazr.config.tests.test_config
```
### Run a test class
```
.\.venv\Scripts\python.exe run_tests.py test_output.txt -v mailman.chains.tests.test_base.TestMiscellaneous
```
### Run all tests (fail-fast)
```
.\.venv\Scripts\python.exe run_tests.py test_output.txt -v -F
```
### Using tox (full suite, creates its own venv)
```
.\.venv\Scripts\tox.exe -e py312-nocov
```
### Test naming convention
Tests use **dotted module paths**, not file paths:
- OK `mailman.app.tests.test_bounces.TestSendProbeNonEnglish.test_probe_notice_with_member_nonenglish`
- OK `mailman.utilities.lazr.config.tests.test_config`
- NO `src/mailman/app/tests/test_bounces.py`
The test runner is **nose2** (configured in `unittest.cfg`), not pytest.
Nose2 uses `flufl.testing` and `nose2.plugins.layers` for test setup/teardown.
### Reading test output
After running, always read the output file:
```
read test_output.txt
```
Look for:
- `ok` -- test passed
- `FAIL` -- assertion failed
- `ERROR` -- exception during test
- `RETURN CODE: 0` -- all tests passed
- `LayerSuite` errors in tearDown are often flufl.lock issues on Windows (not test failures)
- `flufl.lock` uses `^` in claim filenames (e.g. `.lock^hostname^pid^rand`) which is valid on Windows, but the lock's parent temp directory may get deleted before tearDown runs -- this is a known issue
## Known Windows Issues
- **flufl.lock claim file errors**: `FileNotFoundError` for `.uid.token.lock^...` files. The temp `var_dir` gets cleaned up before `uid.reset()` runs in tearDown. The test itself passes; the error is in layer teardown.
## Windows Notes
- The project has been ported to run on Windows natively.
- `lazr.config` has been replaced with a local shim at `src/mailman/utilities/lazr/config/`.
  All imports use `from mailman.utilities.lazr.config import ...`.
- Tests using Unix-only APIs (`os.getuid`, `/dev/stdout`) are skipped on Windows.
- The `postmap_command` in test config uses a cross-platform Python script instead of `sh -c`.
- Template filenames containing `:` are converted to `_` on Windows (colons are invalid in Windows filenames).
- File rename operations (`os.rename`) must happen after file handles are closed (Windows locks open files).
## Project Layout
- `src/mailman/` -- main package
- `src/mailman/utilities/lazr/config/` -- local lazr.config shim (cross-platform, no `grp`/`pwd` dependency)
- Each subpackage (e.g. `runners/`, `rest/`, `rules/`) has its own `tests/` directory
- `var/` -- runtime data directory (db, logs, queues)
- `run_tests.py` -- test runner wrapper that captures output to a file
- `unittest.cfg` -- nose2 configuration (plugins, layers, default test layer)
- `test_output.txt` -- output from last test run (gitignored)
## Python Coding Standards
The goal is to **minimise the diff against upstream `master`**. Every unnecessary
change makes future merges harder. Follow these rules.
### Import ordering (isort)
Imports are sorted by the project's `[isort]` config in `tox.ini`:
- **One block** -- no stdlib / third-party / first-party separation (`no_sections = True`)
- **Bare `import x` lines first**, sorted by line length (`length_sort_straight = True`)
- **Blank line** between bare imports and `from x import y` lines (`lines_between_types = 1`)
- **All `from` imports** sorted alphabetically with no blank lines between them
- **Two blank lines** after the last import (`lines_after_imports = 2`)
- Multi-line imports use Vertical Hanging Indent with trailing comma (`multi_line_output = 3`, `include_trailing_comma = True`)
- `from x import y as z` combined on the same line as plain `from x import y` (`combine_as_imports = True`)
Run the fixer at any time:
```
.\.venv\Scripts\python.exe -m isort .
```
Check only (what CI does):
```
.\.venv\Scripts\python.exe -m isort --check-only .
```
### RST doctest files
RST doctests execute in a **single shared namespace** from top to bottom.
- Import each name **once only** -- redundant re-imports in later sections must be removed.
- Use `from mailman.utilities.filesystem import open` (not `File`) unless `File` itself is
  referenced somewhere in that file.
### General style (flake8)
- Max line length **79 characters** (`max-line-length = 79` in `[flake8]`)
- `src/mailman/compat/*.py` is excluded from flake8
Check only:
```
.\.venv\Scripts\python.exe -m flake8 src
```
### Minimise diff discipline
- **Do not reformat** lines that are not otherwise being changed -- even if style is imperfect.
- **Do not rename** variables, parameters, or methods unless there is a functional reason.
- **Do not reorder** class members, test methods, or dict keys unless required.
- **Do not add or remove** blank lines beyond what isort/flake8 require.
- When adding Windows-compatibility code, wrap it in `if sys.platform == 'win32':` guards
  so the upstream POSIX path is unchanged.
- Prefer **targeted, minimal patches** -- change only the lines that need to change.

---

## Branch Topology

```
upstream/main  ──┬── pr/safe-rename     (PR branch, colon files, no renames)
                 ├── pr/skip-windows    (another PR branch)
                 └── rename             (personal: just the : → _ renames on top of upstream)
                          │
                          └── windows/safe-rename   ← built by make_windows_branch.py
                          └── windows               ← built from upstream/main + rename
```

### Branch purposes

| Branch | Colon files? | Purpose |
|---|---|---|
| `upstream/main` | yes | Tracks the real GitLab repo |
| `pr/*` | yes | Individual PRs — branch off upstream, no renames |
| `rename` | no | Personal only — just the `:` → `_` renames on top of upstream |
| `windows/*` | no | `pr/*` + `rename` merged — works on Windows |
| `tooling` (orphan) | — | `make_windows_branch.py` + `CLAUDE.md` only |

### `tooling` orphan branch
An orphan branch (no parent, no code history) that holds `make_windows_branch.py`
and this `CLAUDE.md`.  Check it out on any machine and run the script to
produce a working `windows` branch from scratch.

**Create the tooling branch (one-time setup):**
```powershell
# Save a copy of the two files first
Copy-Item CLAUDE.md, make_windows_branch.py $env:TEMP\

git checkout --orphan tooling
git rm -rf .

Copy-Item $env:TEMP\CLAUDE.md .
Copy-Item $env:TEMP\make_windows_branch.py .
git add CLAUDE.md make_windows_branch.py
git commit -m "tooling: bootstrap script + dev guide"
```

### Building / refreshing a windows branch
```powershell
# From any state, check out the tooling branch and run:
python make_windows_branch.py
# Produces: 'windows' branch = upstream/main + : -> _ renames + rename branch merged

# For a specific PR branch:
python make_windows_branch.py --source pr/safe-rename --output windows/safe-rename

# Skip re-fetching upstream if already up to date:
python make_windows_branch.py --no-fetch
```

### Periodic rebase workflow
When upstream advances and you want to refresh:
1. Rebase `rename` branch onto new `upstream/main`
2. Run `python make_windows_branch.py` to rebuild `windows`

---

## Upstream PR Plan

This branch is a full Windows port. To maximise the chance of upstreaming, send
PRs in small, independent slices, ordered by risk:

### PR 1 — `safe_rename` utility (easy win)
**File**: `src/mailman/utilities/filesystem.py`
**What**: Add `safe_rename(src, dst)` that wraps `os.rename` to handle
Windows' `FileExistsError` semantics (POSIX `os.rename` atomically
replaces; Windows raises if dst exists).
**Why upstream will accept**: Pure POSIX behaviour is preserved; the Windows
path is guarded by `except FileExistsError`.  Callers already exist
(`switchboard.py`, `digests.py`, `dmarc.py`, alembic migration).

### PR 2 — `skipWindows` test helper + Unix-only test guards (easy win)
**Files**: `src/mailman/testing/helpers.py`, `src/mailman/testing/documentation.py`,
and test files that use `os.getuid` / `/dev/stdout`.
**What**: One-liner `skipWindows = skipIf(sys.platform == 'win32', ...)` plus
`.. unix-only` RST marker and `@skipWindows` on the handful of test classes
that would fail on Windows.
**Why upstream will accept**: Zero functional change, improves CI portability.

### PR 3 — Template filename `:` → `_` (medium, needs migration note)
See the dedicated section below for the full strategy options.

### PR 4 — File upstream issues for `lazr.config` and `flufl.lock`
Before submitting code, open issues on
- https://gitlab.com/lazr/lazr.config — Windows failure due to `grp`/`pwd`
- https://github.com/smontanaro/flufl.lock — Windows `os.kill(pid, 0)` sends CTRL_C_EVENT
Link the shims in this repo as reference implementations.  Only send the shim
as a PR if upstream declines to fix the root dependency.

### Hold back for later
- `src/mailman/windows/` services harness
- The full `File` class rewrite in `filesystem.py`
- Import redirects from `lazr.config` → `mailman.utilities.lazr.config` (20 files)

---

## Template Filename Strategy (`:` vs `_`)

### Current state — nothing to do for day-to-day dev
This repo was seeded by a Python import script that cloned the upstream
project and renamed all `:` filenames to `_` before the first commit.
Both `main` and `windows` branches have `_`-named files from day one.
`git diff main -- src/mailman/templates/` is empty — **no template content
was changed** in the `windows` branch.  Regular `git add / git commit`
just works; no special tooling is needed.

### The problem only matters for contributing upstream
Upstream (`https://gitlab.com/mailman/mailman`) ships template files named
with colons, e.g. `src/mailman/templates/en/list:admin:action:post.txt`.
This repo has no remote link to upstream.  To send a PR you would need to
either:

### Option A — keep upstream filenames; sanitize at Python search time
1. In `src/mailman/utilities/i18n.py::find()`, call
   `File.sanitize_name(template_file)` on Windows before the filesystem
   search, so the code looks for `list_admin_action_post.txt` at runtime.
2. Revert `ALL_TEMPLATES` in `interfaces/template.py` back to
   `'{}.txt'.format(key)` (keep the colons in its output).
3. The Windows dev checkout is solved separately by a git wrapper (see B).

**Separator choice**: `_` is correct and unambiguous.  `|` looks distinctive
but is *also* in `_WINDOWS_UNSAFE_CHARS = ':*?"<>|'` — illegal on Windows.
The template key components (`list`, `admin`, `action`, `post`, etc.) never
contain underscores themselves, so `:` → `_` is a lossless 1-to-1 mapping.

### Option B — `mailman3-git` wrapper tool (new repo)
A standalone Python CLI repo (`mailman3-git`) that wraps the git plumbing
commands needed to check out, pull and commit files whose names are
illegal on Windows.

**Why a smudge/clean filter or post-checkout hook won't work**: git filters
operate on file *content*, not filenames.  `git checkout` on Windows fails
*before* any hook runs when it tries to write `list:admin:action:post.txt`
to disk — the OS rejects the `open()` call.  The rename must happen
*inside the checkout step* via git plumbing.

**What `mailman3-git` does:**
```
mailman3-git clone <url>   # git clone --no-checkout, then writes : files
                            # as _ files using git cat-file + git update-index
mailman3-git pull           # git fetch, then merge with same rename logic
mailman3-git send-pr        # stage _ files under their : index names,
                            # produce a patch/branch suitable for upstream
```
Implemented with pure Python + subprocess (no C deps).  Uses
`git ls-tree`, `git cat-file blob`, `git update-index --cacheinfo`, and
`git update-index --assume-unchanged` to keep the working-tree names (`_`)
decoupled from the index names (`:`).

### Option C — rename files + POSIX backward-compat fallback (current branch)
Keep the `_` renames (what we already have) AND add a fallback in `find()`
that, after failing to locate `list_admin_action_post.txt` on POSIX, also
tries `list:admin:action:post.txt`.  This maximises compat for existing
POSIX deployments that have custom templates with the old colon names.

### Recommended path
**For personal dev (current branch)**: Already done — `_` names work,
tests pass, no friction.  Optionally add the POSIX fallback (Option C).

**For a zero-diff upstream PR**: Implement `mailman3-git` (Option B), revert
template renames in this repo, revert `ALL_TEMPLATES`, and add runtime
sanitization in `i18n.py::find()` (Option A).  This is the highest-value
combination but requires `mailman3-git` to be built first.

