This is GNU Mailman, a mailing list management system distributed under the
terms of the GNU General Public License (GPL) version 3 or later. The name of
this software is spelled ‘Mailman’ with a leading capital ‘M’ but with a lower
case second ‘m’. Any other spelling is incorrect.

Useful Links
============

* Documentation is available at https://docs.mailman3.org/en/latest/.
* Report bugs at https://gitlab.com/mailman/mailman/issues.
* Home page is https://www.list.org/.


## Running tests

Tests use **nose2** (configured in `unittest.cfg`).

### Run all tests (fail-fast)

```
.\.venv\Scripts\nose2.exe -v -F
```

### Using tox (full suite, creates its own venv)

```
.\.venv\Scripts\tox.exe -e py312-nocov
```

### Test naming convention

Tests use **dotted module paths**, not file paths:
- ✅ `mailman.app.tests.test_bounces`
- ❌ `src/mailman/app/tests/test_bounces.py`

