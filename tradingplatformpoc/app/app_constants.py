from tradingplatformpoc import data_store, trading_platform_utils

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

DEFAULT_PV_EFFICIENCY_HELP_TEXT = "A number specifying the efficiency of solar panels in the microgrid. Can " \
    "be overridden by individual agents. Number must be between 0 and 1, and is typically in the 0.15-0.25 range"
HEAT_TRANSFER_LOSS_HELP_TEXT = "A number specifying the loss of heat in every transfer. Must be between 0 and " \
    "0.99, where 0 would mean no losses at all, and 0.99 would mean that almost all energy " \
    "is lost when trying to transfer heat from one agent to another. A reasonable number would be in the 0-0.10 range."
ELECTRICITY_WHOLESALE_PRICE_OFFSET_HELP_TEXT = "The price at which the microgrid can export " \
    "electricity to the external grid, will be set to the Nordpool spot price, plus this offset. The unit is SEK/kWh." \
    " For Varberg Energi, indications are that this will be in the 0-0.15 range. If not specified, will default " \
    "to " + str(data_store.DEFAULT_ELECTRICITY_WHOLESALE_PRICE_OFFSET)
ELECTRICITY_TAX_HELP_TEXT = "The electricity tax in SEK/kWh, for trades not inside the local market. For 2022, this " \
                            "is 0.392, but here it can be set to any (non-negative) number"
ELECTRICITY_GRID_FEE_HELP_TEXT = "The electricity grid fee in SEK/kWh, for trades not inside the local market. The " \
                                 "price at which electricity can be " \
                                 "imported into the microgrid will be set to the Nordpool spot price, plus the " \
                                 "electricity tax, plus this number. In reality it is quite complicated to calculate," \
                                 " since it depends on the average effect used for the three months with highest " \
                                 "consumption over the year, but here we approximate it with a flat SEK/kWh rate. " \
                                 "For Varberg Energi in 2023 this approximation is roughly equal " \
                                 "to 0.148, but here it can be set to any (non-negative) number"
ELECTRICITY_TAX_INTERNAL_HELP_TEXT = "The electricity tax in SEK/kWh, paid on internal trades in the local market. " \
                                     "Should be between 0 and the 'external'/'normal' tax"
ELECTRICITY_GRID_FEE_INTERNAL_HELP_TEXT = "The grid fee, in SEK/kWh, paid on internal trades in the local market. " \
                                          "Should be between 0 and the 'external'/'normal' grid fee"
HEATING_WHOLESALE_PRICE_FRACTION_HELP_TEXT = "The price at which the microgrid can export heat to the " \
    "external grid, will be set to the import (retail) price, multiplied by this factor. Should be less than 1. " \
    "In reality, the external grid may not want to buy any heat from the microgrid at all - this can be achieved by " \
    "setting this number to 0. If not specified, will default to " + \
    str(data_store.DEFAULT_HEATING_WHOLESALE_PRICE_FRACTION)
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
KWH_PER_YEAR_M2_ATEMP_HELP_TEXT = "Number indicating the electricity consumption of residential areas, in kWh per " \
                                  "year and square meter. The default of 20 kWh/year/m2 'atemp' comes from a " \
                                  "2017-2018 metering study made by Skanska, 'Hushållsel i nybyggda flerbostadshus'. " \
                                  "'Atemp' refers to a specific surface area measurement from which energy-related " \
                                  "metrics are calculated. Essentially, it's the surface area which experiences a " \
                                  "temperature modulation by an energy source."
KWH_PER_YEAR_M2_RES_SPACE_HEATING_HELP_TEXT = "Number indicating the space heating consumption of residential " \
                                              "areas, in kWh per year and square meter. The default of 25 " \
                                              "kWh/year/m2 has been provided by BDAB."
KWH_PER_YEAR_M2_RES_HOT_TAP_WATER_HELP_TEXT = "Number indicating the hot tap water consumption of residential " \
                                              "areas, in kWh per year and square meter. The default of 25 " \
                                              "kWh/year/m2 has been provided by BDAB."
RES_HEATING_REL_ERROR_STD_DEV_HELP_TEXT = "The standard deviation of simulated heating consumption of " \
                                          "residential areas, in relative terms. For a given hour, an expected " \
                                          "value will be calculated, and the simulated value will then be this " \
                                          "expected value, multiplied with a factor normally distributed with a " \
                                          "mean of 1 and a standard deviation of this value. Basically, the " \
                                          "higher this value is, the more residential heating consumption will " \
                                          "vary, hour-to-hour."
COMM_ELEC_KWH_PER_YEAR_M2_HELP_TEXT = "Number indicating the electricity consumption of commercial areas, in kWh per " \
                                      "year and square meter. The default of 118 kWh/year/m2 comes from " \
                                      "Energimyndigheten's 2009 report 'Energianvändning i handelslokaler'. This " \
                                      "number is given for 'non-grocery-related' trades premises."
COMM_ELEC_REL_ERROR_STD_DEV_HELP_TEXT = "The standard deviation of simulated electricity consumption of commercial " \
                                        "areas, in relative terms. For a given hour, an expected value will be " \
                                        "calculated, and the simulated value will then be this expected value, " \
                                        "multiplied with a factor normally distributed with a mean of 1 and a " \
                                        "standard deviation of this value. Basically, the higher this value is, the " \
                                        "more commercial electricity consumption will vary, hour-to-hour."
KWH_SPACE_HEATING_PER_YEAR_M2_COMM_HELP_TEXT = "Number indicating the space heating consumption of commercial areas, " \
                                               "in kWh per year and square meter. The default of 32 kWh/year/m2 has " \
                                               "been derived from a combination of numbers provided by BDAB: For " \
                                               "commercial office buildings, they quote 20 kWh/year/m2, and for " \
                                               "'köpcentrum' 44 kWh/year/m2. Since these commercial areas will " \
                                               "likely be of mixed character, we split these numbers down the middle."
KWH_HOT_TAP_WATER_PER_YEAR_M2_COMM_HELP_TEXT = "Number indicating the hot tap water consumption of commercial areas, " \
                                               "in kWh per year and square meter. The default of 3.5 kWh/year/m2 has " \
                                               "been derived from a combination of numbers provided by BDAB: For " \
                                               "commercial office buildings, they quote 2 kWh/year/m2, and for " \
                                               "'köpcentrum' 5 kWh/year/m2. Since these commercial areas will " \
                                               "likely be of mixed character, we split these numbers down the middle."
COMM_HOT_TAP_WATER_REL_ERROR_STD_DEV_HELP_TEXT = "The standard deviation of simulated hot tap water consumption of " \
                                                 "commercial areas, in relative terms. For a given hour, an expected " \
                                                 "value will be calculated, and the simulated value will then be " \
                                                 "this expected value, multiplied with a factor normally distributed " \
                                                 "with a mean of 1 and a standard deviation of this value. " \
                                                 "Basically, the higher this value is, the more commercial hot tap " \
                                                 "water consumption will vary, hour-to-hour."
KWH_ELECTRICITY_PER_YEAR_M2_SCHOOL_HELP_TEXT = "Number indicating the electricity consumption of school buildings, " \
                                               "in kWh per year and square meter. The default of 60 kWh/year/m2 " \
                                               "comes from Energimyndigheten's 2009 report 'Energin i skolan'."
SCHOOL_ELEC_REL_ERROR_STD_DEV_HELP_TEXT = "The standard deviation of simulated electricity consumption of school " \
                                          "areas, in relative terms. For a given hour, an expected value will be " \
                                          "calculated, and the simulated value will then be this expected value, " \
                                          "multiplied with a factor normally distributed with a mean of 1 and a " \
                                          "standard deviation of this value. Basically, the higher this value is, " \
                                          "the more school electricity consumption will vary, hour-to-hour."
KWH_SPACE_HEATING_PER_YEAR_M2_SCHOOL_HELP_TEXT = "Number indicating the space heating consumption of school " \
                                                 "buildings, in kWh per year and square meter. The default of 25 " \
                                                 "kWh/year/m2 has been provided by BDAB."
KWH_HOT_TAP_WATER_PER_YEAR_M2_SCHOOL_HELP_TEXT = "Number indicating the hot tap water consumption of school " \
                                                 "buildings, in kWh per year and square meter. The default of 7 " \
                                                 "kWh/year/m2 has been provided by BDAB."
SCHOOL_HOT_TAP_WATER_REL_ERROR_STD_DEV_HELP_TEXT = "The standard deviation of simulated hot tap water consumption of " \
                                                   "school buildings, in relative terms. For a given hour, an " \
                                                   "expected value will be calculated, and the simulated value " \
                                                   "will then be this expected value, multiplied with a factor " \
                                                   "normally distributed with a mean of 1 and a standard deviation " \
                                                   "of this value. Basically, the higher this value is, the more " \
                                                   "school hot tap water consumption will vary, hour-to-hour."
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
    "   -   'AreaInfo'\n" \
    "       -   Requires the following properties:\n" \
    "           -   'DefaultPVEfficiency': " + DEFAULT_PV_EFFICIENCY_HELP_TEXT + "\n" \
    "           -   'HeatTransferLoss': " + HEAT_TRANSFER_LOSS_HELP_TEXT + "\n" \
    "           -   'ElectricityTax': " + ELECTRICITY_TAX_HELP_TEXT + "\n" \
    "           -   'ElectricityGridFee': " + ELECTRICITY_GRID_FEE_HELP_TEXT + "\n" \
    "           -   'ElectricityTaxInternal': " + ELECTRICITY_TAX_INTERNAL_HELP_TEXT + "\n" \
    "           -   'ElectricityGridFeeInternal': " + ELECTRICITY_GRID_FEE_INTERNAL_HELP_TEXT + "\n" \
    "       -   Optional properties:\n" \
    "           -   'ExternalElectricityWholesalePriceOffset': " + ELECTRICITY_WHOLESALE_PRICE_OFFSET_HELP_TEXT + "\n" \
    "           -   'ExternalHeatingWholesalePriceFraction': " + HEATING_WHOLESALE_PRICE_FRACTION_HELP_TEXT + "\n" \
    "       -  AreaInfo example:"
AREA_INFO_EXAMPLE = """
{
    "DefaultPVEfficiency": 0.165,
    "HeatTransferLoss": 0.05,
    "ElectricityTax": 0.392,
    "ElectricityGridFee": 0.13,
    "ElectricityTaxInternal": 0.2,
    "ElectricityGridFeeInternal": 0.065,
    "ExternalHeatingWholesalePriceFraction": 0.5,
    "ExternalElectricityWholesalePriceOffset": 0.05
}
"""
MOCK_DATA_CONSTANTS_MARKDOWN = "" \
    "   -   'MockDataConstants'\n" \
    "       -   Optional properties:\n" \
    "           -   'ResidentialElecKwhPerYearM2Atemp': " + KWH_PER_YEAR_M2_ATEMP_HELP_TEXT + "\n" \
    "           -   'ResidentialSpaceHeatKwhPerYearM2': " + KWH_PER_YEAR_M2_RES_SPACE_HEATING_HELP_TEXT + "\n" \
    "           -   'ResidentialHotTapWaterKwhPerYearM2': " + KWH_PER_YEAR_M2_RES_HOT_TAP_WATER_HELP_TEXT + "\n" \
    "           -   'ResidentialHeatingRelativeErrorStdDev': " + RES_HEATING_REL_ERROR_STD_DEV_HELP_TEXT + "\n" \
    "           -   'CommercialElecKwhPerYearM2': " + COMM_ELEC_KWH_PER_YEAR_M2_HELP_TEXT + "\n" \
    "           -   'CommercialElecRelativeErrorStdDev': " + COMM_ELEC_REL_ERROR_STD_DEV_HELP_TEXT + "\n" \
    "           -   'CommercialSpaceHeatKwhPerYearM2': " + KWH_SPACE_HEATING_PER_YEAR_M2_COMM_HELP_TEXT + "\n" \
    "           -   'CommercialHotTapWaterKwhPerYearM2': " + KWH_HOT_TAP_WATER_PER_YEAR_M2_COMM_HELP_TEXT + "\n" \
    "           -   'CommercialHotTapWaterRelativeErrorStdDev': " + COMM_HOT_TAP_WATER_REL_ERROR_STD_DEV_HELP_TEXT + \
                               "\n" \
    "           -   'SchoolElecKwhPerYearM2': " + KWH_ELECTRICITY_PER_YEAR_M2_SCHOOL_HELP_TEXT + "\n" \
    "           -   'SchoolElecRelativeErrorStdDev': " + SCHOOL_ELEC_REL_ERROR_STD_DEV_HELP_TEXT + "\n" \
    "           -   'SchoolSpaceHeatKwhPerYearM2': " + KWH_SPACE_HEATING_PER_YEAR_M2_SCHOOL_HELP_TEXT + "\n" \
    "           -   'SchoolHotTapWaterKwhPerYearM2': " + KWH_HOT_TAP_WATER_PER_YEAR_M2_SCHOOL_HELP_TEXT + "\n" \
    "           -   'SchoolHotTapWaterRelativeErrorStdDev': " + SCHOOL_HOT_TAP_WATER_REL_ERROR_STD_DEV_HELP_TEXT + \
                               "\n" \
    "       -  MockDataConstants example:"
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
