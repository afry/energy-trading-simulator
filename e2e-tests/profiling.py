import cProfile
import json
import pstats
import io

from pkg_resources import resource_filename

from tradingplatformpoc.simulation_runner import run_trading_simulations

mock_datas_path = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")
results_path = "../results/"
config_filename = resource_filename("tradingplatformpoc.data", "default_config.json")
with open(config_filename, "r") as jsonfile:
    config_data = json.load(jsonfile)

pr = cProfile.Profile()
pr.enable()

clearing_prices_dict, all_trades_dict, all_extra_costs = run_trading_simulations(config_data,
                                                                                 mock_datas_path,
                                                                                 results_path)

pr.disable()
s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats('tottime')
ps.print_stats()

with open('readable_profiler_output.txt', 'w+') as f:
    f.write(s.getvalue())
