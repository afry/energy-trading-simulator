from pkg_resources import resource_filename

from tradingplatformpoc import trading_platform_utils

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

CO2_PEN_RATE_HELP_TEXT = "Not yet implemented!"
RESOURCE_HELP_TEXT = "A string specifying which resource the agent handles. Allowed values: " + \
                     str(trading_platform_utils.ALL_IMPLEMENTED_RESOURCES_STR)

CURRENT_CONFIG_FILENAME = resource_filename("tradingplatformpoc.config", "current_config.json")
LAST_SIMULATION_RESULTS = resource_filename("tradingplatformpoc.data", "last_simulation_results.pbz2")

DEFAULT_CONFIG_NAME = "default"

CONFIG_ID_MAX_LENGTH = 20
CONFIG_DESCRIPTION_MAX_LENGTH = 100
