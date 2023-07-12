
import datetime
from typing import Dict, List

from tradingplatformpoc.market.bid import Resource
from tradingplatformpoc.sql.clearing_price.models import ClearingPrice as TableClearingPrice


def clearing_prices_to_db_objects(clearing_prices_dict:
                                  Dict[datetime.datetime, Dict[Resource, float]], job_id: str
                                  ) -> List[TableClearingPrice]:
    objects = [TableClearingPrice(period=period,
                                  job_id=job_id,
                                  resource=resource,
                                  price=price)
               for period, some_dict in clearing_prices_dict.items()
               for resource, price in some_dict.items()]
    return objects
