import unittest
from unittest.mock import patch

import main
from config.settings import Settings


class AutoSeedSettingsTests(unittest.TestCase):
    def test_auto_seed_defaults_to_true_in_development(self):
        settings = Settings(ENVIRONMENT="development", AUTO_SEED_MOCK_DATA=None)

        self.assertTrue(settings.auto_seed_mock_data)

    def test_auto_seed_defaults_to_false_outside_development(self):
        settings = Settings(ENVIRONMENT="production", AUTO_SEED_MOCK_DATA=None)

        self.assertFalse(settings.auto_seed_mock_data)

    def test_auto_seed_can_be_explicitly_enabled(self):
        settings = Settings(ENVIRONMENT="production", AUTO_SEED_MOCK_DATA=True)

        self.assertTrue(settings.auto_seed_mock_data)


class StartupSeedTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifespan_skips_seed_store_when_auto_seed_is_disabled(self):
        with (
            patch.object(main.settings, "AUTO_SEED_MOCK_DATA", False),
            patch.object(main, "ensure_directories"),
            patch.object(main, "get_recommendation_store") as get_store,
        ):
            async with main.lifespan(main.app):
                pass

        get_store.assert_not_called()
