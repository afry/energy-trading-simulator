from contextlib import _GeneratorContextManager
from typing import Callable, List, Tuple

import pandas as pd

from sqlalchemy import func, select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.database import bulk_insert
from tradingplatformpoc.market.extra_cost import ExtraCost, ExtraCostType
from tradingplatformpoc.sql.extra_cost.models import ExtraCost as TableExtraCost


def extra_costs_to_db(all_extra_costs_list: List[ExtraCost], job_id: str):
    objects = [TableExtraCost(job_id=job_id,
                              period=x.period,
                              agent=x.agent,
                              cost_type=x.cost_type.name,
                              cost=x.cost)
               for x in all_extra_costs_list]
    bulk_insert(objects)


def db_to_extra_cost_df(job_id: str,
                        session_generator: Callable[[], _GeneratorContextManager[Session]]
                        = session_scope) -> pd.DataFrame:
    with session_generator() as db:
        extra_costs = db.execute(select(TableExtraCost).where(TableExtraCost.job_id == job_id)).all()
        return pd.DataFrame.from_records([{'period': extra_cost.period,
                                           'agent': extra_cost.agent,
                                           'cost_type': extra_cost.cost_type,
                                           'cost': extra_cost.cost
                                           } for (extra_cost, ) in extra_costs])


def db_to_aggregated_extra_costs_by_agent(agent_guid: str, job_id: str,
                                          session_generator: Callable[[], _GeneratorContextManager[Session]]
                                          = session_scope) -> Tuple[float, float]:

    with session_generator() as db:
        res = db.query(
            TableExtraCost.cost_type,
            func.sum(TableExtraCost.cost).label('sum_cost'),
        ).filter(TableExtraCost.agent == agent_guid, TableExtraCost.job_id == job_id)\
         .group_by(TableExtraCost.cost_type).all()

        extra_costs_for_bad_bids = sum([elem.sum_cost for elem in res if elem.cost_type
                                        in [ExtraCostType.ELEC_BID_INACCURACY, ExtraCostType.HEAT_BID_INACCURACY]])
        extra_costs_for_heat_cost_discr = sum([elem.sum_cost for elem in res if elem.cost_type
                                               in [ExtraCostType.HEAT_EXT_COST_CORR]])
        return extra_costs_for_bad_bids, extra_costs_for_heat_cost_discr
