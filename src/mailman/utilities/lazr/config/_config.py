"""Internal implementation module for lazr.config shim.

Provides ``Section`` and other internals so that
``from lazr.config._config import Section`` works the same way it does
with the real lazr.config package.
"""

from __future__ import annotations

import re
import logging
import datetime

from collections import OrderedDict
from configparser import RawConfigParser
from dataclasses import dataclass
from io import StringIO
from mailman.utilities.filesystem import open
from typing import Dict, Iterable, List, MutableMapping, Optional


_MISSING = object()


class Section:
    """Config section with dict-like and attribute-like access."""

    def __init__(self, name: str, options: Optional[MutableMapping[str, str]] = None):
        self.name = name
        self._options: Dict[str, str] = dict(options or {})

    def __iter__(self) -> Iterable[str]:
        return iter(self._options)

    def __contains__(self, key: str) -> bool:
        return key in self._options

    def __getitem__(self, key: str) -> str:
        return self._options[key]

    def __getattr__(self, name: str) -> str:
        if name in self._options:
            return self._options[name]
        raise AttributeError(f"No section key named {name}.")

    @property
    def category_and_section_names(self):
        if "." in self.name:
            return tuple(self.name.split(".", 1))
        return (None, self.name)

    def update(self, options: MutableMapping[str, str]) -> None:
        self._options.update(options)

    def clone(self, name: Optional[str] = None) -> "Section":
        return Section(self.name if name is None else name, self._options.copy())


class Category:
    """Category accessor for dotted section names (for example `logging.root`)."""

    def __init__(self, name: str, sections: List[Section]):
        self.name = name
        self._sections = {section.name: section for section in sections}

    def __iter__(self):
        return iter(self._sections.values())

    def __getattr__(self, name: str) -> Section:
        full_name = f"{self.name}.{name}"
        if full_name in self._sections:
            return self._sections[full_name]
        raise AttributeError(f"No section named {name}.")


@dataclass
class ConfigData:
    name: str
    sections: OrderedDict


class StackableConfig:
    """Small stack-based config model compatible with Mailman's usage."""

    def __init__(self, schema_sections: OrderedDict):
        self._schema_name = "<schema>"
        self._overlays: List[ConfigData] = [
            ConfigData(self._schema_name, schema_sections)
        ]
        self._sections: OrderedDict[str, Section] = OrderedDict()
        self._categories: Dict[str, List[Section]] = {}
        self._rebuild()

    @property
    def overlays(self):
        return self._overlays

    def __iter__(self):
        return iter(self._sections.values())

    def __getattr__(self, name: str):
        section = self._sections.get(name)
        if section is not None:
            return section
        category_sections = self._categories.get(name)
        if category_sections is not None:
            return Category(name, category_sections)
        raise AttributeError(name)

    def getByCategory(self, category: str, default=_MISSING):
        if category in self._categories:
            return list(self._categories[category])
        if category in self._sections:
            return [self._sections[category]]
        if default is _MISSING:
            return []
        return default

    def push(self, conf_name: str, config_data: str):
        parsed = _parse_ini(config_data)
        self._overlays.insert(0, ConfigData(conf_name, parsed))
        self._rebuild()

    def pop(self, conf_name: str):
        schema_index = len(self._overlays) - 1
        for index, overlay in enumerate(self._overlays):
            if index == schema_index and overlay.name == conf_name:
                raise ValueError("Cannot pop the schema default config.")
            if overlay.name == conf_name:
                removed = self._overlays[: index + 1]
                self._overlays = self._overlays[index + 1 :]
                self._rebuild()
                return removed
        raise ValueError(f"No config with name: {conf_name}.")

    def _rebuild(self):
        schema_sections = self._overlays[-1].sections
        merged: OrderedDict[str, Section] = OrderedDict(
            (name, section.clone()) for name, section in schema_sections.items()
        )
        self._apply_template_inheritance(merged)
        for overlay in reversed(self._overlays[:-1]):
            for name, incoming in overlay.sections.items():
                current = merged.get(name)
                if current is None:
                    current = self._make_new_section(name, merged)
                    merged[name] = current
                current.update(incoming._options)
        self._sections = merged
        self._categories = {}
        for section in self._sections.values():
            category, dotted_name = section.category_and_section_names
            if category is None:
                continue
            # Exclude template/master sections from category listings,
            # matching the behaviour of the real lazr.config library where
            # template sections are used for inheritance only and are not
            # returned by getByCategory().
            if dotted_name in ('master', 'template'):
                continue
            self._categories.setdefault(category, []).append(section)

    def _apply_template_inheritance(self, merged: OrderedDict) -> None:
        templates: Dict[str, Section] = {}
        for name, section in merged.items():
            if "." not in name:
                continue
            category, _, suffix = name.partition(".")
            if suffix in ("template", "master"):
                templates[category] = section
        for name, section in merged.items():
            if "." not in name:
                continue
            category, _, suffix = name.partition(".")
            if suffix in ("template", "master"):
                continue
            template = templates.get(category)
            if template is None:
                continue
            inherited = dict(template._options)
            inherited.update(section._options)
            section._options = inherited

    def _make_new_section(self, name: str, merged: OrderedDict[str, Section]) -> Section:
        if "." in name:
            category, _, _ = name.partition(".")
            for suffix in ("master", "template"):
                template_name = f"{category}.{suffix}"
                template_section = merged.get(template_name)
                if template_section is not None:
                    return template_section.clone(name=name)
        return Section(name)


class ConfigSchema:
    """Load schema defaults and build a stackable runtime configuration."""

    def __init__(self, filename: str):
        with open(filename, 'r') as fp:
            schema_data = fp.read()
        self._schema_sections = _parse_ini(schema_data)

    def load(self, filename: Optional[str] = None) -> StackableConfig:
        config = StackableConfig(self._schema_sections)
        if filename:
            with open(filename, 'r') as fp:
                config.push(filename, fp.read())
        return config


def _parse_ini(data: str) -> OrderedDict[str, Section]:
    parser = RawConfigParser(strict=False)
    parser.optionxform = str.lower
    parser.read_file(StringIO(data))
    sections: OrderedDict[str, Section] = OrderedDict()
    for section_name in parser.sections():
        if section_name == "meta":
            continue
        options = OrderedDict()
        for key, value in parser.items(section_name):
            options[key] = value
        sections[section_name] = Section(section_name, options)
    return sections


def as_boolean(value: str) -> bool:
    value = value.lower()
    if value in ("true", "yes", "1", "on", "enabled", "enable"):
        return True
    if value in ("false", "no", "0", "off", "disabled", "disable"):
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _sortkey(item: str):
    order = {"w": 0, "d": 1, "h": 2, "m": 3, "s": 4}
    return order.get(item[-1])


def as_timedelta(value: str) -> datetime.timedelta:
    components = sorted(re.findall(r"([\d.]+[smhdw])", value), key=_sortkey)
    if "".join(components) != value:
        raise ValueError
    keywords = {
        interval[0].lower(): interval
        for interval in ("weeks", "days", "hours", "minutes", "seconds")
    }
    keyword_arguments = {}
    for interval in components:
        if len(interval) == 0:
            raise ValueError
        keyword = keywords.get(interval[-1].lower())
        if keyword is None or keyword in keyword_arguments:
            raise ValueError
        converted = float(interval[:-1]) if "." in interval[:-1] else int(interval[:-1])
        keyword_arguments[keyword] = converted
    if len(keyword_arguments) == 0:
        raise ValueError
    return datetime.timedelta(**keyword_arguments)


def as_log_level(value: str) -> int:
    return getattr(logging, value.upper())

