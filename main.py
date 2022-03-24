from pkg_resources import resource_filename
from tradingplatformpoc.simulation_runner import run_trading_simulations
import json
import logging
import sys

# --- Read sys.argv to get logging level, if it is specified ---
string_to_log_later = None
if len(sys.argv) > 1 and type(sys.argv[1]) == str:
    arg_to_upper = str.upper(sys.argv[1])
    try:
        console_log_level = getattr(logging, arg_to_upper)
    except AttributeError:
        # Since we haven't set up the logger yet, will store this message and log it a little bit further down.
        string_to_log_later = "No logging level found with name '{}', console logging level will default to INFO.".\
            format(arg_to_upper)
        console_log_level = logging.INFO
else:
    console_log_level = logging.INFO

# --- Format logger for print statements
FORMAT = "%(asctime)-15s | %(levelname)-7s | %(name)-35.35s | %(message)s"

file_handler = logging.FileHandler("trading-platform-poc.log")
file_handler.setLevel(logging.DEBUG)  # File logging always DEBUG
stream_handler = logging.StreamHandler()
stream_handler.setLevel(console_log_level)

logging.basicConfig(
    level=logging.DEBUG, format=FORMAT, datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[file_handler, stream_handler], force=True  # Note that we remove all previously existing handlers here
)

logger = logging.getLogger(__name__)

if string_to_log_later is not None:
    logger.info(string_to_log_later)

# --- Define path to mock data
mock_datas_path = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")
results_path = "./results/"
config_filename = resource_filename("tradingplatformpoc.data", "default_config.json")
with open(config_filename, "r") as jsonfile:
    config_data = json.load(jsonfile)

if __name__ == '__main__':
    logger.info("Running main")
    simulation_results = run_trading_simulations(config_data, mock_datas_path, results_path)
