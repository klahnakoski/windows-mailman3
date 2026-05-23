"""Cross-platform fake postmap for testing.

Usage:
    python -m mailman.mta.tests.data.fake_postmap [--fail] [type:]path ...

For each ``path`` argument (optionally prefixed with a Postfix database
type like ``hash:``), writes the raw argument string into
``path.created-db`` so the test can verify what was passed.

If ``--fail`` is given, exits with status 1 without writing anything
(simulates a broken postmap command).
"""

import sys

from pathlib import Path


def _split_type_path(arg):
    """Split a ``[type:]path`` argument into ``(type_prefix, path_str)``.

    Postfix database type prefixes are short alphabetic words (``hash``,
    ``btree``, ``regexp``, …).  On Windows a bare path may start with a
    drive letter like ``C:\\…``, so we only treat a colon as a type
    separator when the part before it is purely alphabetic and short.
    """
    colon = arg.find(':')
    if colon > 0:
        maybe_type = arg[:colon]
        if maybe_type.isalpha() and len(maybe_type) <= 10:
            return maybe_type, arg[colon + 1:]
    return None, arg


def main():
    args = sys.argv[1:]

    if '--fail' in args:
        sys.exit(1)

    for arg in args:
        _type_prefix, path_str = _split_type_path(arg)
        out = Path(f'{path_str}.created-db')
        out.write_text(arg + '\n')


if __name__ == '__main__':
    main()

