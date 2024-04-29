from typing import Any, Dict

import streamlit as st
from streamlit.elements.lib.column_types import ColumnConfig

BOOL_OPTIONS = [True, False]


def add_params_to_form(form, param_spec_dict: dict, info_type: str, exclude_keys: list):
    """
    Populate parameter forms. Will use radio buttons for booleans, select-boxes if "options" is specified, and
    number inputs for all others.
    "disabled_cond" are used to disable (and in some cases, set values of) fields based on values of other fields.
    """
    current_config = st.session_state.config_data
    for key, val in param_spec_dict.items():
        if key not in exclude_keys:
            kwargs = {k: v for k, v in val.items() if k not in ['display', 'default', 'disabled_cond']}

            if 'disabled_cond' in val.keys():
                for k, v in val['disabled_cond']['disabled_when'].items():
                    condition_filled = current_config[info_type][k] == v
                    kwargs['disabled'] = condition_filled
                    if condition_filled and 'set_value' in val['disabled_cond'].keys():
                        current_config[info_type][key] = val['disabled_cond']['set_value']

            if isinstance(val['default'], bool):
                st.session_state.config_data[info_type][key] = form.radio(
                    label=val['display'], options=BOOL_OPTIONS,
                    index=BOOL_OPTIONS.index(current_config[info_type][key]),
                    **kwargs)
            elif 'options' in val.keys():
                st.session_state.config_data[info_type][key] = form.selectbox(
                    label=val['display'],
                    index=val['options'].index(current_config[info_type][key]),
                    **kwargs)
            else:
                st.session_state.config_data[info_type][key] = form.number_input(
                    val['display'], value=current_config[info_type][key], **kwargs)


def column_config_for_agent_type(agent_specs: Dict[str, Dict[str, Any]]) -> Dict[str, ColumnConfig]:
    config_dict: Dict[str, ColumnConfig] = {
        "Name": st.column_config.TextColumn(required=True, max_chars=100, default="NewAgent")
    }
    for col_name, params in agent_specs.items():
        this_col_config = {k: v for k, v in params.items() if k not in
                           ['display', 'default_value', 'type']}
        this_col_config['default'] = params['default_value']

        if ("type", "float") in params.items():
            config_dict[col_name] = st.column_config.NumberColumn(**this_col_config)
        if ("type", "bool") in params.items():
            config_dict[col_name] = st.column_config.CheckboxColumn(**this_col_config)

    return config_dict
