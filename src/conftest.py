# Copyright (C) 2025 by the Free Software Foundation, Inc.
#
# This file is part of GNU Mailman.
#
# GNU Mailman is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# GNU Mailman is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# GNU Mailman.  If not, see <https://www.gnu.org/licenses/>.

"""Pytest conftest.py that bridges Mailman's zope.testrunner layer system
into pytest fixtures.

Mailman's test classes declare a ``layer`` class attribute (e.g.
``layer = ConfigLayer`` or ``layer = SMTPLayer``).  The zope.testrunner
knows how to call setUp/tearDown on the full layer hierarchy, but pytest
does not.  This conftest inspects each collected test class and wires the
appropriate layer lifecycle into pytest fixtures so the tests Just Work.
"""

import pytest

from mailman.testing.layers import ConfigLayer, MockAndMonkeyLayer, SMTPLayer


# ---------------------------------------------------------------------------
# Session-scoped fixtures for the layer *class* setUp / tearDown.
# These are called once per test session, mimicking what zope.testrunner
# does when it first encounters a layer.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def config_layer_setup():
    """One-time ConfigLayer (and its base MockAndMonkeyLayer) setup."""
    ConfigLayer.setUp()
    yield
    ConfigLayer.tearDown()


@pytest.fixture(scope="session")
def smtp_layer_setup(config_layer_setup):
    """One-time SMTPLayer setup (depends on ConfigLayer being up)."""
    SMTPLayer.setUp()
    yield
    SMTPLayer.tearDown()


# ---------------------------------------------------------------------------
# Function-scoped fixtures for the per-test setUp / tearDown.
# ---------------------------------------------------------------------------

@pytest.fixture()
def config_layer(config_layer_setup):
    """Per-test ConfigLayer lifecycle."""
    ConfigLayer.testSetUp()
    yield ConfigLayer
    ConfigLayer.testTearDown()
    MockAndMonkeyLayer.testTearDown()


@pytest.fixture()
def smtp_layer(smtp_layer_setup):
    """Per-test SMTPLayer lifecycle."""
    # SMTPLayer.testSetUp is a deliberate no-op (avoids double domain add),
    # but we still need to call ConfigLayer.testSetUp for the domain.
    ConfigLayer.testSetUp()
    yield SMTPLayer
    # Tear down in reverse layer order: SMTP first, then Config (which
    # calls reset_the_world to clean the DB), then MockAndMonkey.
    SMTPLayer.testTearDown()
    ConfigLayer.testTearDown()
    MockAndMonkeyLayer.testTearDown()


# ---------------------------------------------------------------------------
# Automatic fixture selection based on the ``layer`` class attribute.
# ---------------------------------------------------------------------------

def pytest_collection_modifyitems(config, items):
    """Mark test items so the right fixture is requested automatically."""
    for item in items:
        cls = getattr(item, "cls", None)
        if cls is None:
            continue
        layer = getattr(cls, "layer", None)
        if layer is None:
            continue
        # Map layer classes to the fixture name that should be active.
        if layer is SMTPLayer:
            item.fixturenames.append("smtp_layer")
        elif issubclass(layer, ConfigLayer):
            item.fixturenames.append("config_layer")

