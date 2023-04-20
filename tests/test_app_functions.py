from unittest import TestCase

from tradingplatformpoc.app.app_functions import config_data_keys_screening


class TestAppFunctions(TestCase):

    def test_config_data_json_screening(self):
        """Check that no unknown keys can be passed"""
        mock_json = {'Unknown': {}}
        self.assertIsNotNone(config_data_keys_screening(mock_json))

    def config_data_keys_screening(self):
        """Check that data is organized as expected"""
        mock_json = {'AreaInfo': [], 'Agents': [{}]}
        self.assertIsNotNone(config_data_keys_screening(mock_json))
        mock_json = {'MockDataConstants': [], 'Agents': [{}]}
        self.assertIsNotNone(config_data_keys_screening(mock_json))
        mock_json = {'AreaInfo': {}, 'Agents': [{}]}
        self.assertIsNone(config_data_keys_screening(mock_json))
        mock_json = {'MockDataConstants': {}, 'Agents': [{}]}
        self.assertIsNone(config_data_keys_screening(mock_json))
        mock_json = {'Agents': {}}
        self.assertIsNotNone(config_data_keys_screening(mock_json))
        mock_json = {'Agents': [{}]}
        self.assertIsNone(config_data_keys_screening(mock_json))

    # TODO: Add more tests for json screening
