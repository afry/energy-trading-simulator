import json
from typing import Any, Dict

from tradingplatformpoc.constants import AGENT_SPECS_FILENAME, AREA_INFO_SPECS, \
    DEFAULT_AGENTS_FILENAME, MOCK_DATA_CONSTANTS_SPECS


def read_agent_specs() -> Dict[str, Dict[str, Dict[str, Any]]]:
    with open(AGENT_SPECS_FILENAME, "r") as jsonfile:
        return json.load(jsonfile)


def read_agent_defaults(agent_type, agent_specs) -> dict:
    return dict((param, val["default_value"]) for param, val in agent_specs[agent_type].items())


def read_param_specs(names) -> dict:
    """Reads and returns specified params specification from file."""
    file_dict = {'AreaInfo': AREA_INFO_SPECS,
                 'MockDataConstants': MOCK_DATA_CONSTANTS_SPECS}
    param_specs = {}
    for name in names:
        with open(file_dict[name], "r") as jsonfile:
            param_specs[name] = json.load(jsonfile)
    return param_specs


def read_default_params(names) -> dict:
    """Returns default values of params."""
    param_specs = read_param_specs(names)
    return dict((param_type, dict((param, values['default']) for param, values in param_dict.items()))
                for param_type, param_dict in param_specs.items())


def read_config() -> dict:
    """Reads and returns default config from file."""
    with open(DEFAULT_AGENTS_FILENAME, "r") as jsonfile:
        config = json.load(jsonfile)
        default_params = read_default_params(names=['AreaInfo', 'MockDataConstants'])
    return {'Agents': config, **default_params}


def fill_with_default_params(new_config: dict) -> dict:
    """If not all parameters are specified in uploaded config, use default for the unspecified ones."""
    param_specs = read_param_specs(['AreaInfo', 'MockDataConstants'])
    for param_type in ['AreaInfo', 'MockDataConstants']:
        params_only_in_default = dict((k, v) for k, v in param_specs[param_type].items()
                                      if k not in set(new_config[param_type].keys()))
        for k, v in params_only_in_default.items():
            new_config[param_type][k] = v
    return new_config


def fill_agent_with_defaults(agent: dict, agent_specs: dict) -> dict:
    """Fill agent with default values based on type if value is not specified."""
    default_values = read_agent_defaults(agent['Type'], agent_specs)
    to_add = dict((key, val) for key, val in default_values.items() if key not in agent.keys())
    agent.update(to_add)
    return agent


def fill_agents_with_defaults(new_config: dict) -> dict:
    """Read specification and fill agents with default values if value is not specified."""
    agent_specs = read_agent_specs()
    new_config['Agents'] = [fill_agent_with_defaults(agent, agent_specs) for agent in new_config['Agents']]
    return new_config
