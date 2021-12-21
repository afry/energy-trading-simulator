from tradingplatformpoc.simulation_runner import run_trading_simulations
import logging

# --- Format logger for print statements
FORMAT = "%(asctime)-15s | %(levelname)-7s | %(name)-35.35s | %(message)s"

file_handler = logging.FileHandler("../trading-platform-poc.log")
file_handler.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)

logging.basicConfig(
    level=logging.DEBUG, format=FORMAT, datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[file_handler, stream_handler]
)

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info("Running main")
    clearing_prices_dict, all_trades_list, all_extra_costs_dict = run_trading_simulations()
