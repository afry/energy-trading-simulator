import json

from tradingplatformpoc.app import app_constants
from tradingplatformpoc.data.config import params_specs


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
        default_params = {param_type: {param: values['default'] for param, values in param_dict.items()}
                          for param_type, param_dict in params_specs.param_spec_dict.items()}
        config = {'Agents': config, **default_params}
    return config


def reset_config():
    """Reads default configuration from file and writes to current configuration file."""
    config = read_config(name='default')
    set_config(config)


def fill_with_default_params(new_config: dict) -> dict:
    """If not all parameters are specified in uploaded config, use default for the unspecified ones."""
    for param_type in ['AreaInfo', 'MockDataConstants']:
        params_only_in_default = dict((k, v) for k, v in params_specs.param_spec_dict[param_type].items()
                                      if k not in set(new_config[param_type].keys()))
        for k, v in params_only_in_default.items():
            new_config[param_type][k] = v
    return new_config
