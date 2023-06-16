import os
import pickle
from logging.handlers import TimedRotatingFileHandler

from pkg_resources import resource_filename
from tradingplatformpoc.app.app_inputs import read_config
import logging
import sys
from tradingplatformpoc.constants import MOCK_DATA_PATH
from tradingplatformpoc.database import create_db_and_tables

from tradingplatformpoc.simulation_runner.trading_simulator import TradingSimulator

# --- Read sys.argv to get logging level, if it is specified ---
string_to_log_later = None
if len(sys.argv) > 1 and type(sys.argv[1]) == str:
    arg_to_upper = str.upper(sys.argv[1])
    try:
        log_level = getattr(logging, arg_to_upper)
    except AttributeError:
        # Since we haven't set up the logger yet, will store this message and log it a little bit further down.
        string_to_log_later = "No logging level found with name '{}', console logging level will default to INFO.".\
            format(arg_to_upper)
        log_level = logging.INFO
else:
    log_level = logging.INFO

# --- Format logger for print statements
FORMAT = "%(asctime)-15s | %(levelname)-7s | %(name)-35.35s | %(message)s"

if not os.path.exists("logfiles"):
    os.makedirs("logfiles")
file_handler = TimedRotatingFileHandler("logfiles/trading-platform-poc.log", when="midnight", interval=1)
file_handler.suffix = "%Y-%m-%d"
file_handler.setLevel(log_level)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(log_level)

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
config_data = read_config(name='default')

if __name__ == '__main__':
    logger.info("Running main")
    create_db_and_tables()
    simulator = TradingSimulator('main_job_id', read_config(), MOCK_DATA_PATH)
    simulation_results = simulator.run()
    logger.info("Finished running simulations. Will save simulations results as a pickle file.")
    with open(results_path + 'simulation_results.pickle', 'wb') as destination:
        pickle.dump(simulation_results, destination)
