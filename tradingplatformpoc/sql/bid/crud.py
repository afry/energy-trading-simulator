from contextlib import _GeneratorContextManager
from typing import Any, Callable, Dict, List

import pandas as pd

from sqlalchemy import select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.market.bid import NetBidWithAcceptanceStatus
from tradingplatformpoc.sql.bid.models import Bid as TableBid


def bids_to_db_dict(trades_list: List[NetBidWithAcceptanceStatus],
                    job_id: str) -> List[Dict[str, Any]]:
    dict = [{'job_id': job_id,
             'period': x.period,
             'source': x.source,
             'by_external': x.by_external,
             'action': x.action,
             'resource': x.resource,
             'quantity': x.quantity,
             'price': x.price,
             'accepted_quantity': x.accepted_quantity}
            for some_collection in trades_list for x in some_collection]
    return dict


def db_to_bid_df(job_id: str,
                 session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope) -> pd.DataFrame:
    with session_generator() as db:
        bids = db.execute(select(TableBid).where(TableBid.job_id == job_id)).all()
        return pd.DataFrame.from_records([{'period': bid.period,
                                           'action': bid.action,
                                           'resource': bid.resource,
                                           'quantity': bid.quantity,
                                           'price': bid.price,
                                           'source': bid.source,
                                           'by_external': bid.by_external,
                                           } for (bid, ) in bids])


def db_to_viewable_bid_df_for_agent(job_id: str, agent_guid: str,
                                    session_generator: Callable[[], _GeneratorContextManager[Session]]
                                    = session_scope) -> pd.DataFrame:
    """
    Fetches bids data from database for specified agent (agent_guid) and changes to a df.
    """
    with session_generator() as db:
        bids = db.query(TableBid).filter(TableBid.source == agent_guid, TableBid.job_id == job_id).all()

        if len(bids) > 0:
            return pd.DataFrame.from_records([{'period': bid.period,
                                               'action': bid.action.name,
                                               'resource': bid.resource.name,
                                               'quantity': bid.quantity,
                                               'price': bid.price,
                                               } for bid in bids], index='period')
        else:
            return pd.DataFrame(columns=['period', 'action', 'resource', 'quantity', 'price'])
