from unittest import TestCase

from tradingplatformpoc.app.app_functions import config_data_agent_screening, config_data_keys_screening, \
    config_data_param_screening


class TestAppFunctions(TestCase):

    def test_config_data_json_screening(self):
        """Test of check for unknown keys."""
        self.assertIsNotNone(config_data_keys_screening({'Unknown': {}}))

    def test_config_data_keys_screening(self):
        """Test of check that data is organized as expected."""
        self.assertIsNotNone(config_data_keys_screening({'AreaInfo': [], 'Agents': [{}]}))
        self.assertIsNotNone(config_data_keys_screening({'MockDataConstants': [], 'Agents': [{}]}))
        self.assertIsNone(config_data_keys_screening({'AreaInfo': {}, 'Agents': [{}]}))
        self.assertIsNone(config_data_keys_screening({'MockDataConstants': {}, 'Agents': [{}]}))
        self.assertIsNotNone(config_data_keys_screening({'Agents': {}}))
        self.assertIsNone(config_data_keys_screening({'Agents': [{}]}))

    def test_config_data_param_screening(self):
        """Test of parameter check."""
        self.assertIsNotNone(config_data_param_screening({'AreaInfo': {'ThisIsNotAValidParam': 1.0}}))
        # DefaultPVEfficiency, min value: 0.01, max value: 0.99
        self.assertIsNotNone(config_data_param_screening({'AreaInfo': {'DefaultPVEfficiency': -0.1}}))
        self.assertIsNotNone(config_data_param_screening({'AreaInfo': {'DefaultPVEfficiency': 2.0}}))
        self.assertIsNone(config_data_param_screening({'AreaInfo': {'DefaultPVEfficiency': 0.165}}))

    def test_config_data_agent_screening(self):
        " Test of agent input check."
        mock_agent = {"Type": "GridAgent", "Name": "ElectricityGridAgent",
                      "Resource": "ELECTRICITY", "TransferRate": 5.0}

        self.assertIsNone(config_data_agent_screening({'Agents': [mock_agent]}))

        # No Type
        self.assertIsNotNone(config_data_agent_screening({'Agents': [{"Name": "ElectricityGridAgent",
                                                                      "Resource": "ELECTRICITY",
                                                                      "TransferRate": 5.0}]}))
        # No Name
        self.assertIsNotNone(config_data_agent_screening({'Agents': [{"Type": "GridAgent",
                                                                      "Resource": "ELECTRICITY",
                                                                      "TransferRate": 5.0}]}))
        # Missing GridAgent
        self.assertIsNotNone(config_data_agent_screening({'Agents': [{"Type": "PVAgent",
                                                                      "Name": "PVAgent1",
                                                                      "PVArea": 20.0}]}))
        # Invalid agent Type
        self.assertIsNotNone(config_data_agent_screening({'Agents': [{"Type": "ThisIsNotAValidAgentType",
                                                                      "Name": "ThisIsNotAValidAgent",
                                                                      "Resource": "ELECTRICITY",
                                                                      "TransferRate": 5.0},
                                                                     {"Type": "GridAgent",
                                                                      "Name": "ElectricityGridAgent",
                                                                      "Resource": "ELECTRICITY",
                                                                      "TransferRate": 5.0}]}))
        
        # Missing resource for GridAgent
        self.assertIsNotNone(config_data_agent_screening({'Agents': [{"Type": "GridAgent",
                                                                      "Name": "ElectricityGridAgent",
                                                                      "TransferRate": 5.0}]}))
        # Missing required parameter
        self.assertIsNotNone(config_data_agent_screening({'Agents': [{"Type": "GridAgent",
                                                                      "Name": "ElectricityGridAgent",
                                                                      "Resource": "ELECTRICITY"}]}))
        # Invalid resouce
        self.assertIsNotNone(config_data_agent_screening({'Agents': [{"Type": "GridAgent",
                                                                      "Name": "ElectricityGridAgent",
                                                                      "Resource": "ThisIsNotAValidResource",
                                                                      "TransferRate": 5.0}]}))
        # Unknown parameter
        self.assertIsNotNone(config_data_agent_screening({'Agents': [{**mock_agent,
                                                                      **{'ThisIsNotAValidAgentParameter': 0.0}}]}))
        # TransferRate of Storage Agent min value: 0.0
        mock_agent['TransferRate'] = -0.1
        self.assertIsNotNone(config_data_agent_screening({'Agents': [mock_agent]}))
