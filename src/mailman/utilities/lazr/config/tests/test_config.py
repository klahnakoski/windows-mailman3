# Copyright 2008-2015 Canonical Ltd.  All rights reserved.
#
# This file is part of lazr.config.
#
# lazr.config is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# lazr.config is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public
# License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with lazr.config.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for the mailman.lazr.config shim."""

import os
import logging
import datetime
import unittest

from mailman.utilities.lazr.config import (
    _parse_ini,
    as_boolean,
    as_log_level,
    as_timedelta,
    Category,
    ConfigSchema,
    Section,
    StackableConfig,
)
from mailman.testing.tempfile import NamedTemporaryFile


class TestAsBoolean(unittest.TestCase):

    def test_true_values(self):
        for val in ('true', 'True', 'yes', 'YES', '1', 'on', 'enabled', 'enable'):
            self.assertTrue(as_boolean(val), f'{val} should be True')

    def test_false_values(self):
        for val in ('false', 'False', 'no', 'NO', '0', 'off', 'disabled', 'disable'):
            self.assertFalse(as_boolean(val), f'{val} should be False')

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            as_boolean('maybe')


class TestAsTimedelta(unittest.TestCase):

    def test_seconds(self):
        self.assertEqual(as_timedelta('30s'), datetime.timedelta(seconds=30))

    def test_minutes(self):
        self.assertEqual(as_timedelta('5m'), datetime.timedelta(minutes=5))

    def test_hours(self):
        self.assertEqual(as_timedelta('2h'), datetime.timedelta(hours=2))

    def test_days(self):
        self.assertEqual(as_timedelta('7d'), datetime.timedelta(days=7))

    def test_weeks(self):
        self.assertEqual(as_timedelta('1w'), datetime.timedelta(weeks=1))

    def test_combined(self):
        self.assertEqual(
            as_timedelta('1d2h3m'),
            datetime.timedelta(days=1, hours=2, minutes=3),
        )

    def test_float(self):
        self.assertEqual(as_timedelta('1.5h'), datetime.timedelta(hours=1.5))

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            as_timedelta('bogus')

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            as_timedelta('')

    def test_duplicate_unit_raises(self):
        with self.assertRaises(ValueError):
            as_timedelta('1s2s')


class TestAsLogLevel(unittest.TestCase):

    def test_debug(self):
        self.assertEqual(as_log_level('debug'), logging.DEBUG)

    def test_info(self):
        self.assertEqual(as_log_level('info'), logging.INFO)

    def test_warning(self):
        self.assertEqual(as_log_level('warning'), logging.WARNING)

    def test_case_insensitive(self):
        self.assertEqual(as_log_level('ERROR'), logging.ERROR)


class TestSection(unittest.TestCase):

    def test_getitem(self):
        s = Section('test', {'key': 'value'})
        self.assertEqual(s['key'], 'value')

    def test_getattr(self):
        s = Section('test', {'key': 'value'})
        self.assertEqual(s.key, 'value')

    def test_contains(self):
        s = Section('test', {'key': 'value'})
        self.assertIn('key', s)
        self.assertNotIn('missing', s)

    def test_iter(self):
        s = Section('test', {'a': '1', 'b': '2'})
        self.assertEqual(sorted(s), ['a', 'b'])

    def test_getattr_missing_raises(self):
        s = Section('test', {})
        with self.assertRaises(AttributeError):
            _ = s.missing

    def test_category_and_section_names_dotted(self):
        s = Section('logging.root')
        self.assertEqual(s.category_and_section_names, ('logging', 'root'))

    def test_category_and_section_names_simple(self):
        s = Section('mailman')
        self.assertEqual(s.category_and_section_names, (None, 'mailman'))

    def test_update(self):
        s = Section('test', {'a': '1'})
        s.update({'a': '2', 'b': '3'})
        self.assertEqual(s['a'], '2')
        self.assertEqual(s['b'], '3')

    def test_clone(self):
        s = Section('test', {'key': 'value'})
        c = s.clone('copy')
        self.assertEqual(c.name, 'copy')
        self.assertEqual(c['key'], 'value')
        c.update({'key': 'changed'})
        self.assertEqual(s['key'], 'value')


class TestCategory(unittest.TestCase):

    def test_getattr(self):
        sections = [Section('logging.root', {'level': 'info'})]
        cat = Category('logging', sections)
        self.assertEqual(cat.root.level, 'info')

    def test_iter(self):
        sections = [
            Section('logging.root', {}),
            Section('logging.debug', {}),
        ]
        cat = Category('logging', sections)
        self.assertEqual(len(list(cat)), 2)

    def test_missing_raises(self):
        cat = Category('logging', [])
        with self.assertRaises(AttributeError):
            _ = cat.missing


class TestParseIni(unittest.TestCase):

    def test_basic(self):
        data = '[mailman]\nkey: value\n'
        sections = _parse_ini(data)
        self.assertIn('mailman', sections)
        self.assertEqual(sections['mailman']['key'], 'value')

    def test_meta_section_skipped(self):
        data = '[meta]\nversion: 1\n[mailman]\nkey: val\n'
        sections = _parse_ini(data)
        self.assertNotIn('meta', sections)
        self.assertIn('mailman', sections)

    def test_duplicate_sections_allowed(self):
        data = '[mailman]\na: 1\n[mailman]\nb: 2\n'
        sections = _parse_ini(data)
        self.assertIn('mailman', sections)
        self.assertIn('a', sections['mailman'])
        self.assertIn('b', sections['mailman'])


class TestStackableConfig(unittest.TestCase):

    def _make_config(self, schema_ini):
        sections = _parse_ini(schema_ini)
        return StackableConfig(sections)

    def test_getattr_section(self):
        cfg = self._make_config('[mailman]\nlayout: testing\n')
        self.assertEqual(cfg.mailman.layout, 'testing')

    def test_push_overrides(self):
        cfg = self._make_config('[mailman]\nlayout: testing\n')
        cfg.push('overlay', '[mailman]\nlayout: production\n')
        self.assertEqual(cfg.mailman.layout, 'production')

    def test_pop_restores(self):
        cfg = self._make_config('[mailman]\nlayout: testing\n')
        cfg.push('overlay', '[mailman]\nlayout: production\n')
        cfg.pop('overlay')
        self.assertEqual(cfg.mailman.layout, 'testing')

    def test_pop_schema_raises(self):
        cfg = self._make_config('[mailman]\nlayout: testing\n')
        with self.assertRaises(ValueError):
            cfg.pop('<schema>')

    def test_pop_missing_raises(self):
        cfg = self._make_config('[mailman]\nlayout: testing\n')
        with self.assertRaises(ValueError):
            cfg.pop('nonexistent')

    def test_getattr_missing_raises(self):
        cfg = self._make_config('[mailman]\nlayout: testing\n')
        with self.assertRaises(AttributeError):
            _ = cfg.nonexistent

    def test_iter(self):
        cfg = self._make_config('[a]\nx: 1\n[b]\ny: 2\n')
        names = [s.name for s in cfg]
        self.assertEqual(names, ['a', 'b'])

    def test_category_access(self):
        cfg = self._make_config('[logging.root]\nlevel: info\n[logging.debug]\nlevel: debug\n')
        cat = cfg.logging
        self.assertIsInstance(cat, Category)

    def test_getByCategory(self):
        cfg = self._make_config('[logging.root]\nlevel: info\n')
        sections = cfg.getByCategory('logging')
        self.assertEqual(len(sections), 1)

    def test_getByCategory_empty(self):
        cfg = self._make_config('[mailman]\nlayout: testing\n')
        self.assertEqual(cfg.getByCategory('nonexistent'), [])

    def test_master_template_cloned(self):
        schema = '[runner.master]\ninterval: 1s\n[runner.archive]\ninterval: 5s\n'
        cfg = self._make_config(schema)
        cfg.push('overlay', '[runner.custom]\n')
        self.assertEqual(cfg.runner.custom.interval, '1s')

    def test_template_inheritance(self):
        schema = (
            '[logging.template]\nformat: default_fmt\nlevel: info\n'
            '[logging.root]\n'
            '[logging.debug]\nlevel: debug\n'
        )
        cfg = self._make_config(schema)
        # Empty section inherits from template.
        self.assertEqual(cfg.logging.root.format, 'default_fmt')
        self.assertEqual(cfg.logging.root.level, 'info')
        # Section with own value overrides template.
        self.assertEqual(cfg.logging.debug.level, 'debug')
        self.assertEqual(cfg.logging.debug.format, 'default_fmt')


class TestConfigSchema(unittest.TestCase):

    def test_load_schema(self):
        schema = '[mailman]\nlayout: testing\n'
        with NamedTemporaryFile(
            mode='w', suffix='.cfg', delete=False, encoding='utf-8'
        ) as fp:
            fp.write(schema)
            schema_path = fp.name
        try:
            cs = ConfigSchema(schema_path)
            cfg = cs.load()
            self.assertEqual(cfg.mailman.layout, 'testing')
        finally:
            os.unlink(schema_path)

    def test_load_with_overlay(self):
        schema = '[mailman]\nlayout: testing\n'
        overlay = '[mailman]\nlayout: production\n'
        with NamedTemporaryFile(
            mode='w', suffix='.cfg', delete=False, encoding='utf-8'
        ) as fp:
            fp.write(schema)
            schema_path = fp.name
        with NamedTemporaryFile(
            mode='w', suffix='.cfg', delete=False, encoding='utf-8'
        ) as fp:
            fp.write(overlay)
            overlay_path = fp.name
        try:
            cs = ConfigSchema(schema_path)
            cfg = cs.load(overlay_path)
            self.assertEqual(cfg.mailman.layout, 'production')
        finally:
            os.unlink(schema_path)
            os.unlink(overlay_path)
