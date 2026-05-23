"""Cross-platform substitute for /bin/echo used in mhonarc testing.

Prints its first argument to stdout, mimicking ``/bin/echo "arg"``.
Normalizes backslashes to forward slashes so doctest path patterns
(which use ``/``) match on Windows.
Used in mhonarc.cfg so the mhonarc archiver tests run on Windows.
"""

import sys


if __name__ == '__main__':
    print(sys.argv[1].replace('\\', '/'))

