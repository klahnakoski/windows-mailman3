# GNU Mailman 3 — Windows Port

Fork of [GNU Mailman 3](https://gitlab.com/mailman/mailman). Runs natively on Windows. POSIX behaviour is unchanged.

## Setup

**Requirements:** Python 3.12, tox

```
python312 -m venv .venv
.\.venv\Scripts\activate
pip install -e .
tox.exe -e py312-nocov
```

## Running Tests

```
tox.exe -e py312-nocov
```
