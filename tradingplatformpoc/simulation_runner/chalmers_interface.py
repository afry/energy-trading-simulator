import datetime
import logging
from typing import Any, Dict, List

import numpy as np

import pyomo.environ as pyo

from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.market.trade import Market, Trade
from tradingplatformpoc.trading_platform_utils import add_to_nested_dict

logger = logging.getLogger(__name__)


def get_power_transfers(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime) -> List[Trade]:
    # For example: Pbuy_market is how much the LEC bought from the external grid operator
    return get_transfers(optimized_model, start_datetime,
                         sold_to_external_name='Psell_market', bought_from_external_name='Pbuy_market',
                         sold_internal_name='Psell_grid', bought_internal_name='Pbuy_grid')


def get_transfers(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                  sold_to_external_name: str, bought_from_external_name: str,
                  sold_internal_name: str, bought_internal_name: str) -> List[Trade]:
    """
    We probably want methods like this, to translate the optimized pyo.ConcreteModel to our domain.
    """
    transfers = []
    for hour in optimized_model.time:
        # TODO: grid_agent_guid
        trade = construct_external_trade(bought_from_external_name, hour, optimized_model, sold_to_external_name,
                                         start_datetime, 'ExternalGridAgent', Resource.ELECTRICITY)
        transfers.append(trade)
        for i_agent in optimized_model.agent:
            t = construct_agent_trade(bought_internal_name, sold_internal_name, hour, i_agent, optimized_model,
                                      start_datetime, Resource.ELECTRICITY)
            transfers.append(t)
    return transfers


def construct_agent_trade(bought_internal_name: str, sold_internal_name: str, hour: int, i_agent: int,
                          optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime, resource: Resource) \
        -> Trade:
    quantity = pyo.value(getattr(optimized_model, bought_internal_name)[i_agent, hour]
                         - getattr(optimized_model, sold_internal_name)[i_agent, hour])
    agent_name = agent_guid_from_index(optimized_model, i_agent)
    return Trade(period=start_datetime + datetime.timedelta(hours=hour),
                 action=Action.BUY if quantity > 0 else Action.SELL, resource=resource,
                 quantity=abs(quantity), price=np.nan, source=agent_name, by_external=False, market=Market.LOCAL)


def construct_external_trade(bought_from_external_name: str, hour: int, optimized_model: pyo.ConcreteModel,
                             sold_to_external_name: str, start_datetime: datetime.datetime, grid_agent_guid: str,
                             resource: Resource) -> Trade:
    external_quantity = pyo.value(getattr(optimized_model, sold_to_external_name)[hour]
                                  - getattr(optimized_model, bought_from_external_name)[hour])
    return Trade(period=start_datetime + datetime.timedelta(hours=hour),
                 action=Action.BUY if external_quantity > 0 else Action.SELL, resource=resource,
                 quantity=abs(external_quantity), price=np.nan, source=grid_agent_guid, by_external=True,
                 market=Market.LOCAL)


def agent_guid_from_index(optimized_model: pyo.ConcreteModel, i_agent: int) -> str:
    # TODO: Translate index to agent GUID in some way.
    #  Perhaps use names from the input data frames on the model object, or pass it separately, into an intermediate
    #  method, which lives between trading_simulator and the Chalmers code, and then use here
    return str(i_agent)


def add_value_per_agent_to_dict(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                                dict_to_add_to: Dict[str, Dict[datetime.datetime, Any]],
                                variable_name: str):
    """
    Example variable names: Hhp for heat pump production, SOCBES for state of charge of battery storage
    """
    for hour in optimized_model.time:
        for i_agent in optimized_model.agent:
            quantity = pyo.value(getattr(optimized_model, variable_name)[i_agent, hour])
            period = start_datetime + datetime.timedelta(hours=hour)
            add_to_nested_dict(dict_to_add_to, agent_guid_from_index(optimized_model, i_agent), period, quantity)
