import datetime
from typing import Dict

from tradingplatformpoc.sql.level.models import Level


def levels_to_db_objects(levels_dict: Dict[str, Dict[datetime.datetime, float]],
                         level_type: str, job_id: str):
    objects = [Level(period=period,
                     job_id=job_id,
                     agent=agent,
                     type=level_type,
                     level=level)
               for agent, some_dict in levels_dict.items() for period, level in some_dict.items()]
    return objects
