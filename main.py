import argparse
import os
from logging.handlers import TimedRotatingFileHandler

from pkg_resources import resource_filename
import logging
import sys
from tradingplatformpoc.app.app_constants import DEFAULT_CONFIG_NAME
from tradingplatformpoc.connection import SessionMaker
from tradingplatformpoc.database import create_db_and_tables, insert_default_config_into_db

from tradingplatformpoc.simulation_runner.trading_simulator import TradingSimulator
from tradingplatformpoc.sql.job.crud import delete_job, get_job_id_for_config

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
parser = argparse.ArgumentParser()
parser.add_argument("--config_id", dest="config_id", default=DEFAULT_CONFIG_NAME,
                    help="Config ID", type=str)
args = parser.parse_args()

# config_data = read_config(name=args.config_name)

if __name__ == '__main__':
    logger.info("Running main with config {}.".format(args.config_id))
    create_db_and_tables()
    insert_default_config_into_db()
    with SessionMaker() as sess:
        job_id = get_job_id_for_config(args.config_id, sess)
    delete_job(job_id)
    simulator = TradingSimulator(args.config_id)
    simulation_results = simulator()
    if simulation_results is not None:
        logger.info("Finished running simulations. Will save simulations results as a pickle file.")
        with open(results_path + 'simulation_results.pickle', 'wb') as destination:
            pickle.dump(simulation_results, destination)
    else:
        logger.info("Could not finish simulation.")
