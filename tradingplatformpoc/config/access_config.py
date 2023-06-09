import json
import os
from typing import Tuple

from tradingplatformpoc.app import app_constants


def read_agent_specs():
    with open(app_constants.AGENT_SPECS_FILENAME, "r") as jsonfile:
        return json.load(jsonfile)


def read_agent_defaults(agent_type, agent_specs):
    return dict((param, val["default_value"]) for param, val in agent_specs[agent_type].items())


def read_param_specs(names):
    """Reads and returns specified params specification from file."""
    file_dict = {'AreaInfo': app_constants.AREA_INFO_SPECS,
                 'MockDataConstants': app_constants.MOCK_DATA_CONSTANTS_SPECS}
    param_specs = {}
    for name in names:
        with open(file_dict[name], "r") as jsonfile:
            param_specs[name] = json.load(jsonfile)
    return param_specs


def read_default_params(names):
    """Returns default values of params."""
    param_specs = read_param_specs(names)
    return dict((param_type, dict((param, values['default']) for param, values in param_dict.items()))
                for param_type, param_dict in param_specs.items())


def set_config(config: dict):
    """Writes config to current configuration file."""
    with open(app_constants.CURRENT_CONFIG_FILENAME, 'w') as f:
        json.dump(config, f)


def read_config(name: str = 'current') -> dict:
    """Reads and returns specified config from file."""
    file_dict = {'current': app_constants.CURRENT_CONFIG_FILENAME,
                 'default': app_constants.DEFAULT_AGENTS_FILENAME}

    with open(file_dict[name], "r") as jsonfile:
        config = json.load(jsonfile)
    if name == 'default':
        default_params = read_default_params(names=['AreaInfo', 'MockDataConstants'])
        config = {'Agents': config, **default_params}
    return config


def reset_config():
    """Reads default configuration from file and writes to current configuration file."""
    config = read_config(name='default')
    set_config(config)


def get_config(reset: bool) -> Tuple[dict, str]:
    """
    If no current config file exists or the reset button is clicked, reset.
    Return current config.
    """
    if not os.path.exists(app_constants.CURRENT_CONFIG_FILENAME):
        reset_config()
        message = "**Current configuration: :blue[DEFAULT]**"
    elif reset:
        reset = False
        reset_config()
        message = "**Current configuration: :blue[DEFAULT]**"
    else:
        message = "**Current configuration: :blue[LAST SAVED]**"
    config = read_config()
    return config, message


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
