import datetime
import logging
from typing import Any, Collection, Dict, List

from tradingplatformpoc.price.heating_price import HeatingPrice

logger = logging.getLogger(__name__)


def get_external_heating_prices(heat_pricing: HeatingPrice, job_id: str,
                                trading_periods: Collection[datetime.datetime]) -> List[Dict[str, Any]]:
    heating_price_by_ym_list: List[Dict[str, Any]] = []
    for (year, month) in set([(dt.year, dt.month) for dt in trading_periods]):
        first_day_of_month = datetime.datetime(year, month, 1)  # Which day it is doesn't matter
        heating_price_by_ym_list.append({
            'job_id': job_id,
            'year': year,
            'month': month,
            'exact_retail_price': heat_pricing.get_exact_retail_price(first_day_of_month, include_tax=True),
            'exact_wholesale_price': heat_pricing.get_exact_wholesale_price(first_day_of_month),
            'estimated_retail_price': heat_pricing.get_estimated_retail_price(first_day_of_month, include_tax=True),
            'estimated_wholesale_price': heat_pricing.get_estimated_wholesale_price(first_day_of_month)})
    return heating_price_by_ym_list
