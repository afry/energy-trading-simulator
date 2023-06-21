import datetime
from contextlib import _GeneratorContextManager
from typing import Callable, Collection, Dict

import pandas as pd

from sqlalchemy import select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.database import bulk_insert
from tradingplatformpoc.market.bid import NetBidWithAcceptanceStatus
from tradingplatformpoc.sql.bid.models import Bid as TableBid


def bids_to_db(trades_dict: Dict[datetime.datetime, Collection[NetBidWithAcceptanceStatus]], job_id: str):
    objects = [TableBid(period=period,
                        job_id=job_id,
                        source=x.source,
                        by_external=x.by_external,
                        action=x.action.name,
                        resource=x.resource.name,
                        quantity=x.quantity,
                        price=x.price,
                        accepted_quantity=x.accepted_quantity)
               for period, some_collection in trades_dict.items() for x in some_collection]
    bulk_insert(objects)


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
                                           'accepted_quantity': bid.quantity
                                           } for (bid, ) in bids])
