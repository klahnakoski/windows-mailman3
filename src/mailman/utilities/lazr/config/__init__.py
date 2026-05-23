"""Mailman-focused subset of :mod:`lazr.config`.

This implementation intentionally supports only the surface Mailman imports:
`ConfigSchema`, `as_boolean`, `as_timedelta`, and `as_log_level`.
"""

from mailman.utilities.lazr.config._config import (  # noqa: F401
    _parse_ini,
    as_boolean,
    as_log_level,
    as_timedelta,
    Category,
    ConfigData,
    ConfigSchema,
    Section,
    StackableConfig,
)


__all__ = [
    "ConfigSchema",
    "as_boolean",
    "as_log_level",
    "as_timedelta",
]

