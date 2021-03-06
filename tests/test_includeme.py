import unittest

import kinto.core
from pyramid.exceptions import ConfigurationError
from pyramid import testing

from kinto_facebook import includeme


class IncludeMeTest(unittest.TestCase):
    def test_include_fails_if_kinto_was_not_initialized(self):
        config = testing.setUp()
        with self.assertRaises(ConfigurationError):
            config.include(includeme)

    def test_settings_are_filled_with_defaults(self):
        config = testing.setUp()
        kinto.core.initialize(config, '1.0.0')
        config.include(includeme)
        settings = config.get_settings()
        self.assertIsNotNone(settings.get('facebook.relier.enabled'))

    def test_a_heartbeat_is_registered_at_oauth(self):
        config = testing.setUp()
        kinto.core.initialize(config, '1.0.0')
        config.registry.heartbeats = {}
        config.include(includeme)
        self.assertIsNotNone(config.registry.heartbeats.get('facebook'))
