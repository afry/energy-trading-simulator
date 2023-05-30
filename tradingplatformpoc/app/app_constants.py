from pkg_resources import resource_filename

from tradingplatformpoc import heat_pump, trading_platform_utils

WHOLESALE_PRICE_STR = 'Wholesale price'
RETAIL_PRICE_STR = 'Retail price'
LOCAL_PRICE_STR = 'Local price'
DATA_PATH = "tradingplatformpoc.data"

ELEC_CONS = "Electricity consumption"
ELEC_PROD = "Electricity production"
HEAT_CONS = "Heat consumption"
HEAT_PROD = "Heat production"

ALTAIR_BASE_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
                      "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

HEAT_PUMP_CHART_COLOR = 'gray'

START_PAGE = "Start page"
SETUP_PAGE = "Set up experiment"
LOAD_PAGE = "Load results"
BIDS_PAGE = "Results per agent"

SELECT_PAGE_RADIO_LABEL = "Select page"
ALL_PAGES = (START_PAGE, SETUP_PAGE, LOAD_PAGE, BIDS_PAGE)

CO2_PEN_RATE_HELP_TEXT = "Not yet implemented!"
GROSS_FLOOR_AREA_HELP_TEXT = "Specified in square meters, used for calculating the energy demand"
FRACTION_COMMERCIAL_HELP_TEXT = "A number from 0 to 1, specifying how large a " \
    "share of the area which should be treated as commercial buildings, as opposed to residential. " \
    "Used for calculating the pattern and quantity of energy demand"
FRACTION_SCHOOL_HELP_TEXT = "A number from 0 to 1, specifying how large a " \
    "share of the area which should be treated as school buildings, as opposed to residential. " \
    "Used for calculating the pattern and quantity of energy demand"
PV_AREA_HELP_TEXT = "Specified in square meters, indicating the total areal of solar panels that this agent " \
    "has at its disposal"
PV_EFFICIENCY_HELP_TEXT = "A number from 0 to 1, specifying the efficiency of solar panels that the agent may have" \
    "at its disposal. If missing, will default to the default PV efficiency specified in 'AreaInfo'"
RESOURCE_HELP_TEXT = "A string specifying which resource the agent handles. Allowed values: " + \
                     str(trading_platform_utils.ALL_IMPLEMENTED_RESOURCES_STR)
CAPACITY_HELP_TEXT = "A number specifying the storage capacity, in kWh"
CHARGE_RATE_HELP_TEXT = "A number specifying how much of the maximum capacity can be charged in an hour. This value " \
    "being equal to 1 would mean that the storage entity can go from completely empty, to completely full, in one " \
    "hour. Must be a positive number"
ROUND_TRIP_EFFICIENCY_HELP_TEXT = "A number specifying the round-trip efficiency. This value being equal to 1 would " \
    "mean that there are no losses for the storage entity; if one charges it with X kWh, one can later discharge " \
    "exactly the same amount. Must be a positive number, no larger than 1"
N_HOURS_BACK_HELP_TEXT = "Used in the current StorageAgent strategy: The agent will use the prices from NHoursBack " \
    " to form an opinion on what its asking prices should be for upcoming periods"
BUY_PERC_HELP_TEXT = "Used in the current StorageAgent strategy: The agent will look at historical " \
    "prices, as specified above, and set its buy-bid asking price to be this percentile of those historical prices"
SELL_PERC_HELP_TEXT = "Used in the current StorageAgent strategy: The agent will look at historical " \
    "prices, as specified above, and set its sell-bid asking price to be this percentile of those historical prices." \
    "SellPricePercentile must be bigger than BuyPricePercentile"
DISCHARGE_RATE_HELP_TEXT = "A number specifying how much of the maximum capacity can be discharged in an hour. This " \
    "value being equal to 1 would mean that the storage entity can go from completely full, to completely empty, in " \
    "one hour. Must be a positive number. If not specified, will default to the charge rate"
TRANSFER_RATE_HELP_TEXT = "A number specifying (in kWh) the maximum amount of energy the agent can transfer into, " \
    "or out from, the microgrid in an hour"
HEAT_PUMPS_HELP_TEXT = "Heat pumps allow the building agent to convert electricity into heating. Currently, all heat " \
    "pumps are medium sized 'Thermia Mega 2020' pumps, with a maximum effect of 44 kW"
HEAT_PUMP_COP_HELP_TEXT = "With this parameter, one can modify the relative Coefficient of Performance of the " \
    "agent's heat pumps. The default is 4.6, which is the tabulated value for a medium sized 'Thermia Mega 2020' " \
    "running on 3600 RPM, with a forward temperature of 35 degrees and a brine fluid temperature of 0 degrees Celsius"

# Long texts
# CONFIG_GUIDELINES_MARKDOWN is kind of deprecated - now that we have input fields, descriptions on the JSON file is
# kind of redundant since no one will presumably be constructing it by hand anyway.
CONFIG_GUIDELINES_MARKDOWN = "-  The configuration file should be in JSON format\n" \
    "-  To construct your own configuration file, you could copy the file below and modify it with " \
    "an editor of your choice\n" \
    "-  Required properties:\n" \
    "   -   'Agents'\n" \
    "       -   Value here should be an array of the agents one wants to include\n" \
    "       -   All agents require the following properties:\n" \
    "           -   'Type'\n" \
    "           -   'Name'\n" \
    "       -   See below for more information on different agent types\n" \

AREA_INFO_EXAMPLE = """
{
    "DefaultPVEfficiency": 0.165,
    "HeatTransferLoss": 0.05,
    "ElectricityTax": 0.392,
    "ElectricityGridFee": 0.148,
    "ElectricityTaxInternal": 0.392,
    "ElectricityGridFeeInternal": 0.148,
    "ExternalHeatingWholesalePriceFraction": 0.5,
    "ExternalElectricityWholesalePriceOffset": 0.05
}
"""
MOCK_DATA_CONSTANTS_MARKDOWN = "" \
    "   -   'MockDataConstants'\n" \
    "       -   Requires the following properties:\n"
# + "\n".join([key + ': ' + value['help'] for key, value in
#              param_spec_dict['MockDataConstants'].items() if value['required']])
# + "       -   Optional properties:\n"
# + "\n".join([key + ': ' + value['help'] for key, value in
#              param_spec_dict['MockDataConstants'].items() if not value['required']])
# "       -  MockDataConstants example:"

MOCK_DATA_CONSTANTS_EXAMPLE = """
{
    "ResidentialElecKwhPerYearM2Atemp": 20,
    "ResidentialSpaceHeatKwhPerYearM2": 25,
    "ResidentialHotTapWaterKwhPerYearM2": 25,
    "ResidentialHeatingRelativeErrorStdDev": 0.2,
    "CommercialElecKwhPerYearM2": 118.0,
    "CommercialElecRelativeErrorStdDev": 0.2,
    "CommercialSpaceHeatKwhPerYearM2": 32,
    "CommercialHotTapWaterKwhPerYearM2": 3.5,
    "CommercialHotTapWaterRelativeErrorStdDev": 0.2,
    "SchoolElecKwhPerYearM2": 60,
    "SchoolElecRelativeErrorStdDev": 0.2,
    "SchoolSpaceHeatKwhPerYearM2": 25,
    "SchoolHotTapWaterKwhPerYearM2": 7,
    "SchoolHotTapWaterRelativeErrorStdDev": 0.2
}
"""
BUILDING_AGENT_SPEC_MARKDOWN = "-  Required properties, in addition to 'Type' and 'Name':\n" \
    "   -   'GrossFloorArea': " + GROSS_FLOOR_AREA_HELP_TEXT + "\n" \
    "-  Optional properties:\n" \
    "   -   'PVArea': " + PV_AREA_HELP_TEXT + ". Default 0\n" \
    "   -   'FractionCommercial': " + FRACTION_COMMERCIAL_HELP_TEXT + "\n" \
    "   -   'FractionSchool': " + FRACTION_SCHOOL_HELP_TEXT + "\n" \
    "   -   'PVEfficiency': " + PV_EFFICIENCY_HELP_TEXT + "\n" \
    "   -   'NumberHeatPumps': " + HEAT_PUMPS_HELP_TEXT + "\n" \
    "   -   'COP': " + HEAT_PUMP_COP_HELP_TEXT + "\n" \
    "-  BuildingAgent example:"
BUILDING_AGENT_EXAMPLE = """
{
    "Type": "BuildingAgent",
    "Name": "ResidentialBuildingAgentBC1",
    "GrossFloorArea": 11305.3333333333,
    "PVArea": 1748.6666666667,
    "FractionCommercial": 0.2,
    "FractionSchool": 0.0,
    "PVEfficiency": 0.18,
    "NumberHeatPumps": 2,
    "COP": 4.2
}
"""
STORAGE_AGENT_SPEC_MARKDOWN = "-  Required properties, in addition to 'Type' and 'Name':\n" \
    "   -   'Resource': " + RESOURCE_HELP_TEXT + "\n" \
    "   -   'Capacity': " + CAPACITY_HELP_TEXT + "\n" \
    "   -   'ChargeRate': " + CHARGE_RATE_HELP_TEXT + "\n" \
    "   -   'RoundTripEfficiency': " + ROUND_TRIP_EFFICIENCY_HELP_TEXT + "\n" \
    "   -   'NHoursBack': " + N_HOURS_BACK_HELP_TEXT + "\n" \
    "   -   'BuyPricePercentile': " + BUY_PERC_HELP_TEXT + "\n" \
    "   -   'SellPricePercentile': " + SELL_PERC_HELP_TEXT + "\n" \
    "-  Optional properties:\n" \
    "   -   'DischargeRate': " + DISCHARGE_RATE_HELP_TEXT + \
    "-  StorageAgent example:"
STORAGE_AGENT_EXAMPLE = """
{
    "Type": "StorageAgent",
    "Name": "BatteryStorageAgent1",
    "Resource": "ELECTRICITY",
    "Capacity": 1000,
    "ChargeRate": 0.4,
    "DischargeRate": 0.5,
    "RoundTripEfficiency": 0.93,
    "NHoursBack": 168,
    "BuyPricePercentile": 20,
    "SellPricePercentile": 80
}
"""
GRID_AGENT_SPEC_MARKDOWN = "-  Required properties, in addition to 'Type' and 'Name':\n" \
    "   -   'Resource': " + RESOURCE_HELP_TEXT + "\n" \
    "   -   'TransferRate': " + TRANSFER_RATE_HELP_TEXT + "\n" + \
    "-  GridAgent example:"
GRID_AGENT_EXAMPLE = """
{
    "Type": "GridAgent",
    "Name": "ElectricityGridAgent",
    "Resource": "ELECTRICITY",
    "TransferRate": 10000
}
"""
PV_AGENT_SPEC_MARKDOWN = "-  Required properties, in addition to 'Type' and 'Name':\n" \
    "   -   'PVArea': " + PV_AREA_HELP_TEXT + "\n" \
    "-  Optional properties:\n" \
    "   -   'PVEfficiency': " + PV_EFFICIENCY_HELP_TEXT + "\n" \
    "-  PVAgent example:"
PV_AGENT_EXAMPLE = """
{
    "Type": "PVAgent",
    "Name": "PVAgent1",
    "PVArea": 10000,
    "PVEfficiency": 0.18
}
"""
GROCERY_STORE_AGENT_SPEC_MARKDOWN = "-  A specific agent type, designed to mimic the Coop store which neighbours " \
    "the Jonstaka area. Energy consumption patterns are hard-coded and can not be modified\n" \
    "-  Has no required properties except 'Type' and 'Name'\n" \
    "-  Optional properties:\n" \
    "   -   'PVArea': " + PV_AREA_HELP_TEXT + ". In 2021, this Coop store had 320 sqm panels on its roof, but it can " \
    "be modified here. If not specified, will default to 0\n" \
    "   -   'PVEfficiency': " + PV_EFFICIENCY_HELP_TEXT + "\n" \
    "-  GroceryStoreAgent example:"
GROCERY_STORE_AGENT_EXAMPLE = """
{
    "Type": "GroceryStoreAgent",
    "Name": "GroceryStoreAgent",
    "PVArea": 320,
    "PVEfficiency": 0.18
}
"""

DEFAULT_AGENTS_FILENAME = resource_filename("tradingplatformpoc.data.config", "default_agents.json")
CURRENT_CONFIG_FILENAME = resource_filename("tradingplatformpoc.data.config", "current_config.json")
LAST_SIMULATION_RESULTS = resource_filename("tradingplatformpoc.data", "last_simulation_results.pickle")
MOCK_DATA_PATH = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")

agent_specs_dict = {
    "BuildingAgent": {
        "GrossFloorArea": {
            "display": "Gross floor area (sqm)",
            "min_value": 0.0,
            "step": 10.0,
            "help": GROSS_FLOOR_AREA_HELP_TEXT,
            "type": float,
            "required": True
        },
        "FractionCommercial": {
            "display": "Fraction commercial",
            "min_value": 0.0,
            "max_value": 1.0,
            "help": FRACTION_COMMERCIAL_HELP_TEXT,
            "default_value": 0.0,
            "type": float,
            "required": False
        },
        "FractionSchool": {
            "display": "Fraction school",
            "min_value": 0.0,
            "max_value": 1.0,
            "help": FRACTION_SCHOOL_HELP_TEXT,
            "default_value": 0.0,
            "type": float,
            "required": False
        },
        "PVArea": {
            "display": "PV area (sqm)",
            "min_value": 0.0,
            "step": 10.0,
            "format": '%.1f',
            "help": PV_AREA_HELP_TEXT,
            "default_value": 0.0,
            "type": float,
            "required": False
        },
        "PVEfficiency": {
            "display": "PV efficiency",
            "min_value": 0.01,
            "max_value": 0.99,
            "format": '%.1f',
            "help": PV_EFFICIENCY_HELP_TEXT,
            "type": float,
            "required": False
        },
        "NumberHeatPumps": {
            "display": "Heat pumps",
            "min_value": 0,
            "step": 1,
            "help": HEAT_PUMPS_HELP_TEXT,
            "default_value": 0,
            "type": int,
            "required": False
        },
        "COP": {
            "display": "COP",
            "min_value": 2.0,
            "step": 0.1,
            "help": HEAT_PUMP_COP_HELP_TEXT,
            "default_value": heat_pump.DEFAULT_COP,
            "type": float,
            "disabled_cond": {'NumberHeatPumps': 0},
            "required": False
        }
    },
    "StorageAgent": {
        "Capacity": {
            "display": "Capacity",
            "min_value": 0.0,
            "step": 1.0,
            "help": CAPACITY_HELP_TEXT,
            "type": float,
            "required": True
        },
        "ChargeRate": {
            "display": "Charge rate",
            "min_value": 0.01,
            "max_value": 10.0,
            "help": CHARGE_RATE_HELP_TEXT,
            "type": float,
            "required": True
        },
        "RoundTripEfficiency": {
            "display": "Round-trip efficiency",
            "min_value": 0.01,
            "max_value": 1.0,
            "help": ROUND_TRIP_EFFICIENCY_HELP_TEXT,
            "type": float,
            "required": True
        },
        "NHoursBack": {
            "display": "\'N hours back\'",
            "min_value": 1,
            "max_value": 8760,
            "help": N_HOURS_BACK_HELP_TEXT,
            "type": int,
            "required": True
        },
        "BuyPricePercentile": {
            "display": "\'Buy-price percentile\'",
            "min_value": 0.0,
            "max_value": 100.0,
            "step": 1.0,
            "help": BUY_PERC_HELP_TEXT,
            "type": float,
            "required": True
        },
        "SellPricePercentile": {
            "display": "\'Sell-price percentile\'",
            "min_value": 0.0,
            "max_value": 100.0,
            "step": 1.0,
            "help": SELL_PERC_HELP_TEXT,
            "type": float,
            "required": True
        },
        "DischargeRate": {
            "display": "Discharge rate",
            "min_value": 0.01,
            "max_value": 10.0,
            "help": DISCHARGE_RATE_HELP_TEXT,
            "type": float,
            "required": False
        }
    },
    "GridAgent": {
        "TransferRate": {
            "display": "Transfer rate",
            "min_value": 0.0,
            "step": 10.0,
            "help": TRANSFER_RATE_HELP_TEXT,
            "type": float,
            "required": True
        }
    },
    "PVAgent": {
        "PVArea": {
            "display": "PV area (sqm)",
            "min_value": 0.0,
            "step": 10.0,
            "format": '%.1f',
            "help": PV_AREA_HELP_TEXT,
            "default_value": 0.0,
            "type": float,
            "required": True
        },
        "PVEfficiency": {
            "display": "PV efficiency",
            "min_value": 0.01,
            "max_value": 0.99,
            "format": '%.1f',
            "help": PV_EFFICIENCY_HELP_TEXT,
            "type": float,
            "required": False
        }
    },
    "GroceryStoreAgent": {
        "PVArea": {
            "display": "PV area (sqm)",
            "min_value": 0.0,
            "step": 10.0,
            "format": '%.1f',
            "help": PV_AREA_HELP_TEXT,
            "default_value": 0.0,
            "type": float,
            "required": False
        },
        "PVEfficiency": {
            "display": "PV efficiency",
            "min_value": 0.01,
            "max_value": 0.99,
            "format": '%.1f',
            "help": PV_EFFICIENCY_HELP_TEXT,
            "type": float,
            "required": False
        }
    }
}
