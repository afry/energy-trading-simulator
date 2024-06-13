import copy
from unittest import TestCase

from tradingplatformpoc.app.app_functions import config_naming_is_valid, has_control_characters
from tradingplatformpoc.config.screen_config import config_data_agent_screening, config_data_feasibility_screening, \
    config_data_keys_screening, config_data_param_screening


class TestAppFunctions(TestCase):
    mock_grid_el = {"Type": "GridAgent", "Name": "ElectricityGridAgent",
                    "Resource": "ELECTRICITY", "TransferRate": 5.0}
    mock_grid_he = {"Type": "GridAgent", "Name": "HeatingGridAgent",
                    "Resource": "HIGH_TEMP_HEAT", "TransferRate": 5.0}
    mock_bakery = {"Type": "HeatProducerAgent", "Name": "HPA", "Profile": "Bakery"}
    mock_pv = {"Type": "BlockAgent",
               "Name": "PVParkAgent",
               "Atemp": 0.0,
               "FractionCommercial": 0.0,
               "FractionSchool": 0.0,
               "FractionOffice": 0.0,
               "HeatPumpMaxInput": 0.0,
               "HeatPumpMaxOutput": 0.0,
               "BoosterPumpMaxInput": 0.0,
               "BoosterPumpMaxOutput": 0.0,
               "BatteryCapacity": 0.0,
               "AccumulatorTankCapacity": 0.0,
               "FractionUsedForBITES": 0.0,
               "HeatPumpForCooling": False,
               "PVArea": 20.0}

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
        # PVEfficiency, min value: 0.01, max value: 0.99
        self.assertIsNotNone(config_data_param_screening({'AreaInfo': {'PVEfficiency': -0.1}}))
        self.assertIsNotNone(config_data_param_screening({'AreaInfo': {'PVEfficiency': 2.0}}))
        self.assertIsNone(config_data_param_screening({'AreaInfo': {'PVEfficiency': 0.165}}))

    def test_config_data_agent_screening(self):
        """Test of agent input check."""

        self.assertIsNone(config_data_agent_screening({'Agents': [self.mock_grid_el, self.mock_grid_he, self.mock_pv]}))

        # No Type
        self.assertEqual('Agent ElectricityGridAgent provided without \'Type\'.',
                         config_data_agent_screening({'Agents': [{"Name": "ElectricityGridAgent",
                                                                  "Resource": "ELECTRICITY",
                                                                  "TransferRate": 5.0},
                                                                 self.mock_grid_he,
                                                                 self.mock_pv]}))
        # No Name
        self.assertEqual('Agent of type GridAgent provided without \'Name\'.',
                         config_data_agent_screening({'Agents': [{"Type": "GridAgent",
                                                                  "Resource": "ELECTRICITY",
                                                                  "TransferRate": 5.0},
                                                                 self.mock_grid_he,
                                                                 self.mock_pv]}))
        
        # Missing resource for GridAgent
        self.assertEqual("No specified resource for agent ElectricityGridAgent.",
                         config_data_agent_screening({'Agents': [{"Type": "GridAgent",
                                                                  "Name": "ElectricityGridAgent",
                                                                  "TransferRate": 5.0},
                                                                 self.mock_grid_he,
                                                                 self.mock_pv]}))
        
        # Too many GridAgents
        self.assertEqual('Too many GridAgents provided, should be one for each resource!',
                         config_data_agent_screening({'Agents': [{"Type": "GridAgent",
                                                                  "Name": "ElectricityGridAgent",
                                                                  'Resource': "ELECTRICITY",
                                                                  "TransferRate": 5.0},
                                                                 self.mock_grid_el,
                                                                 self.mock_grid_he,
                                                                 self.mock_pv]}))
        
        # Invalid resource
        self.assertEqual("Resource ThisIsNotAValidResource is not in available for agent ElectricityGridAgent.",
                         config_data_agent_screening({'Agents': [{"Type": "GridAgent",
                                                                  "Name": "ElectricityGridAgent",
                                                                  "Resource": "ThisIsNotAValidResource",
                                                                  "TransferRate": 5.0},
                                                                 self.mock_grid_he,
                                                                 self.mock_pv]}))

        # Missing GridAgents
        self.assertEqual('No GridAgent provided!',
                         config_data_agent_screening({'Agents': [self.mock_pv]}))

        # Missing GridAgent HIGH_TEMP_HEAT
        self.assertEqual('No GridAgent with resource: HIGH_TEMP_HEAT provided!',
                         config_data_agent_screening({'Agents': [self.mock_pv, self.mock_grid_el]}))

        # Missing GridAgent ELECTRICITY
        self.assertEqual('No GridAgent with resource: ELECTRICITY provided!',
                         config_data_agent_screening({'Agents': [self.mock_pv, self.mock_grid_he]}))

        # Missing one agent that is not a GridAgent
        self.assertEqual('No non-GridAgents provided, needs at least one other agent!',
                         config_data_agent_screening({'Agents': [self.mock_grid_el, self.mock_grid_he]}))
        
        # Too many GridAgents
        self.assertEqual('Too many GridAgents provided, should be one for each resource!',
                         config_data_agent_screening(
                             {'Agents': [self.mock_grid_el, self.mock_grid_he, self.mock_grid_he]}))
                             
        # Invalid agent Type
        self.assertEqual('Agent ThisIsNotAValidAgent provided with unrecognized \'Type\' ThisIsNotAValidAgentType.',
                         config_data_agent_screening({'Agents': [{"Type": "ThisIsNotAValidAgentType",
                                                                  "Name": "ThisIsNotAValidAgent",
                                                                  "Resource": "ELECTRICITY",
                                                                  "TransferRate": 5.0},
                                                                 self.mock_grid_he,
                                                                 self.mock_grid_el]}))
        
        # Missing required parameter
        self.assertEqual("Missing parameter TransferRate for agent ElectricityGridAgent.",
                         config_data_agent_screening({'Agents': [{"Type": "GridAgent",
                                                                  "Name": "ElectricityGridAgent",
                                                                  "Resource": "ELECTRICITY"},
                                                                 self.mock_grid_he,
                                                                 self.mock_pv]}))
        
        # Unknown parameter
        self.assertEqual("Specified ThisIsNotAValidAgentParameter not in available "
                         "input params for agent HeatingGridAgent of type GridAgent.",
                         config_data_agent_screening({'Agents': [{**self.mock_grid_he,
                                                                  **{'ThisIsNotAValidAgentParameter': 0.0}},
                                                                 self.mock_grid_el, self.mock_pv]}))

        # TransferRate of Storage Agent min value: 0.0
        faulty_grid_he = copy.copy(self.mock_grid_he)
        faulty_grid_he['TransferRate'] = -0.1
        self.assertEqual("Specified TransferRate: -0.1 < 0.0.",
                         config_data_agent_screening({'Agents': [faulty_grid_he, self.mock_grid_el, self.mock_pv]}))

    def test_heat_producer_agent_screening(self):
        """Test that we catch when an un-supported profile is specified for a HeatProducerAgent"""
        agents = [self.mock_grid_el, self.mock_grid_he, self.mock_pv, self.mock_bakery]
        self.assertEqual("Unrecognized Profile: Bakery, needs to be one of ['Grocery store']",
                         config_data_agent_screening({'Agents': agents}))

    def test_config_naming_is_valid(self):
        """Test that we allow/disallow config names appropriately"""
        self.assertTrue(config_naming_is_valid('2 block agents'))
        self.assertFalse(config_naming_is_valid(' '))
        self.assertFalse(config_naming_is_valid('abc\x0123'))

    def test_has_control_characters(self):
        self.assertTrue(has_control_characters('abc\x0123'))
        self.assertFalse(has_control_characters('Just a normal string'))

    def test_screen_feasibility(self):
        config_data = {'Agents': [self.mock_grid_el, self.mock_grid_he, self.mock_pv],
                       'AreaInfo': {'CompChillerMaxInput': 0.0,
                                    'CompChillerCOP': 0.0,
                                    'COPHeatPumpsHighTemp': 3.0,
                                    'COPHeatPumpsLowTemp': 2.0,
                                    'LocalMarketEnabled': True}}
        self.assertIsNone(config_data_feasibility_screening(config_data))

        config_data = {'Agents': [self.mock_grid_el, self.mock_grid_he, self.mock_pv,
                                  {"Type": "BlockAgent",
                                   "Name": "AgentWithoutBoosterHP",
                                   "Atemp": 1000.0,
                                   "FractionCommercial": 0.0,
                                   "FractionSchool": 0.0,
                                   "FractionOffice": 0.0,
                                   "HeatPumpMaxInput": 0.0,
                                   "HeatPumpMaxOutput": 0.0,
                                   "BoosterPumpMaxInput": 0.0,
                                   "BoosterPumpMaxOutput": 0.0,
                                   "BatteryCapacity": 0.0,
                                   "AccumulatorTankCapacity": 0.0,
                                   "FractionUsedForBITES": 0.0,
                                   "HeatPumpForCooling": False,
                                   "PVArea": 0.0}],
                       'AreaInfo': {'CompChillerMaxInput': 0.0,
                                    'CompChillerCOP': 0.0,
                                    'COPHeatPumpsHighTemp': 3.0,
                                    'COPHeatPumpsLowTemp': 2.0,
                                    'LocalMarketEnabled': True}}
        self.assertIsNotNone(config_data_feasibility_screening(config_data))
