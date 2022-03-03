from tradingplatformpoc import trading_platform_utils

WHOLESALE_PRICE_STR = 'External wholesale price'
RETAIL_PRICE_STR = 'External retail price'
LOCAL_PRICE_STR = 'Local price'
DATA_PATH = "tradingplatformpoc.data"

START_PAGE = "Start page"
SETUP_PAGE = "Set up experiment"
LOAD_PAGE = "Load results"
BIDS_PAGE = "Bids/trades"

SELECT_PAGE_RADIO_LABEL = "Select page"
ALL_PAGES = (START_PAGE, SETUP_PAGE, LOAD_PAGE, BIDS_PAGE)

# Long texts
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
    "   -   'AreaInfo'\n" \
    "       -   Requires the following properties:\n" \
    "           -   'DefaultPVEfficiency': A number specifying the efficiency of solar panels in the microgrid. Can " \
    "be overridden by individual agents. Number should be between 0 and 1, and is typically in the 0.15-0.25 range\n" \
    "           -   'ExternalHeatingWholesalePriceFraction': TODO\n" \
    "           -   'ExternalElectricityWholesalePriceOffset': TODO\n" \
    "           -   'ExternalElectricityRetailPriceOffset': TODO"
BUILDING_AGENT_SPEC_MARKDOWN = "-  Required properties, in addition to 'Type' and 'Name':\n" \
    "   -   'RandomSeed': An integer, used for simulating data. The value in itself does not really" \
    "matter, but it shouldn't be identical to the RandomSeed of any other BuildingAgent\n" \
    "   -   'GrossFloorArea': Specified in square meters, used for calculating the energy demand\n" \
    "-  Optional properties:\n" \
    "   -   'PVArea': Specified in square meters, used for calculating the energy produced " \
    "by rooftop solar panels. Default 0\n" \
    "   -   'FractionCommercial': A number from 0 to 1, specifying how large a " \
    "share of the area which should be treated as commercial buildings, as opposed to residential. " \
    "Used for calculating the pattern and quantity of energy demand\n" \
    "   -   'FractionSchool': A number from 0 to 1, specifying how large a " \
    "share of the area which should be treated as school buildings, as opposed to residential. " \
    "Used for calculating the pattern and quantity of energy demand\n" \
    "   -   'PVEfficiency': A number from 0 to 1, specifying the efficiency of solar panels that the agent may have" \
    "at its disposal. If missing, will default to the DefaultPVEfficiency specified in AreaInfo\n" \
    "-  BuildingAgent example:"
BUILDING_AGENT_EXAMPLE = """
{
    "Type": "BuildingAgent",
    "Name": "ResidentialBuildingAgentBC1",
    "RandomSeed": 1,
    "GrossFloorArea": 11305.3333333333,
    "PVArea": 1748.6666666667,
    "FractionCommercial": 0.2,
    "FractionSchool": 0.0,
    "PVEfficiency": 0.18
}
"""
STORAGE_AGENT_SPEC_MARKDOWN = "-  Required properties, in addition to 'Type' and 'Name':\n" \
    "   -   'Resource': A string specifying which resource the agent stores. Allowed values: " + \
                              str([res.name for res in trading_platform_utils.ALL_IMPLEMENTED_RESOURCES]) + "\n" \
    "   -   'Capacity': A number specifying the storage capacity, in kWh\n" \
    "   -   'ChargeRate': A number specifying how much of the maximum capacity can be charged in an hour. This value " \
    "being equal to 1 would mean that the storage entity can go from completely empty, to completely full, in one " \
    "hour. Must be a positive number\n" \
    "   -   'RoundTripEfficiency': A number specifying the round-trip efficiency. This value being equal to 1 would " \
    "mean that there are no losses for the storage entity; if one charges it with X kWh, one can later discharge " \
    "exactly the same amount. Must be a positive number, no larger than 1\n" \
    "   -   'NHoursBack': Used in the current StorageAgent strategy: The agent will use the prices from NHoursBack " \
    " to form an opinion on what its asking prices should be for upcoming periods\n" \
    "   -   'BuyPricePercentile': Used in the current StorageAgent strategy: The agent will look at historical " \
    "prices, as specified above, and set its buy-bid asking price to be this percentile of those historical prices\n" \
    "   -   'SellPricePercentile': Used in the current StorageAgent strategy: The agent will look at historical " \
    "prices, as specified above, and set its sell-bid asking price to be this percentile of those historical prices." \
    "SellPricePercentile must be bigger than BuyPricePercentile\n" \
    "-  Optional properties:\n" \
    "   -   'DischargeRate': A number specifying how much of the maximum capacity can be discharged in an hour. This " \
    "value being equal to 1 would mean that the storage entity can go from completely full, to completely empty, in " \
    "one hour. Must be a positive number. If not specified, will default to ChargeRate" \
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
    "   -   'Resource': A string specifying which resource the agent trades. Allowed values: " + \
                           str([res.name for res in trading_platform_utils.ALL_IMPLEMENTED_RESOURCES]) + "\n" \
    "   -   'TransferRate': A number specifying (in kWh) the maximum amount of energy the agent can transfer into, " \
    "or out from, the microgrid in an hour\n" + \
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
    "   -   'PVArea': Specified in square meters, indicating the total areal of solar panels that this agent " \
    "has at its disposal\n" \
    "-  Optional properties:\n" \
    "   -   'PVEfficiency': A number from 0 to 1, specifying the efficiency of the solar panels. If missing, will " \
    "default to the DefaultPVEfficiency specified in AreaInfo\n" \
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
    "   -   'PVArea': Specified in square meters, used for calculating the energy produced " \
    "by rooftop solar panels. In 2021, this Coop store had 320 sqm panels on its roof, but it can be modified here. " \
    "If not specified, will default to 0\n" \
    "   -   'PVEfficiency': A number from 0 to 1, specifying the efficiency of the solar panels. If missing, will " \
    "default to the DefaultPVEfficiency specified in AreaInfo\n" \
    "-  CommercialBuildingAgent example:"
GROCERY_STORE_AGENT_EXAMPLE = """
{
    "Type": "CommercialBuildingAgent",
    "Name": "GroceryStoreAgent",
    "PVArea": 320,
    "PVEfficiency": 0.18
}
"""
