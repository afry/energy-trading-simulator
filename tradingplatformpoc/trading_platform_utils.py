from datetime import datetime, timedelta


def minus_n_hours(t1: datetime, n_hours: int):
    new_time = t1 - timedelta(hours=n_hours)
    return new_time
