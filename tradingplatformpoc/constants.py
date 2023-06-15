from pkg_resources import resource_filename


DEFAULT_AGENTS_FILENAME = resource_filename("tradingplatformpoc.config", "default_agents.json")
AGENT_SPECS_FILENAME = resource_filename("tradingplatformpoc.config", "agents_specs.json")
AREA_INFO_SPECS = resource_filename("tradingplatformpoc.config", "area_info_specs.json")
MOCK_DATA_CONSTANTS_SPECS = resource_filename("tradingplatformpoc.config", "mock_data_constants_specs.json")
MOCK_DATA_PATH = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")
