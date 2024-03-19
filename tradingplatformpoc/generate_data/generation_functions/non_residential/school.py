import datetime


def get_monday_of_week(year: int, week_number: int) -> datetime.datetime:
    return datetime.datetime.strptime(str(year) + '-W' + str(week_number) + '-1', "%Y-W%W-%w")


# Constants used in the 'is_break' method. Better to instantiate these here, since is_break is called many times, and
# instantiating these over and over again is really unnecessary.
# Year doesn't really matter, we'll only use the day-of-year
JUST_SOME_NONE_LEAP_YEAR = 2019
# Summer break 15/6 - 15/8
SUMMER_START = datetime.datetime(JUST_SOME_NONE_LEAP_YEAR, 6, 15).timetuple().tm_yday
SUMMER_END = SUMMER_START + 60
# Fall break week 44
FALL_START = get_monday_of_week(JUST_SOME_NONE_LEAP_YEAR, 44).timetuple().tm_yday
FALL_END = FALL_START + 7
# Christmas break 22/12 - 2/1
CHRISTMAS_START = datetime.datetime(JUST_SOME_NONE_LEAP_YEAR, 12, 22).timetuple().tm_yday
CHRISTMAS_END = CHRISTMAS_START + 14
# Sportlov week 8
SPRING_START = get_monday_of_week(JUST_SOME_NONE_LEAP_YEAR, 8).timetuple().tm_yday
SPRING_END = SPRING_START + 7
# Easter week 15
# Easter moves yearly, but since we are only interested in capturing the feature
# of a week off school sometime in mid-spring, we simply chose an average date (early-mid April)
EASTER_START = get_monday_of_week(JUST_SOME_NONE_LEAP_YEAR, 15).timetuple().tm_yday
EASTER_END = EASTER_START + 8


def is_break(timestamp: datetime.datetime):
    # We compare the day-of-year to some pre-defined starts and ends of break periods
    day_of_year = timestamp.timetuple().tm_yday

    # Return true if timestamp falls on break, false if not
    if SUMMER_START <= day_of_year <= SUMMER_END:
        return True

    if FALL_START <= day_of_year <= FALL_END:
        return True

    if CHRISTMAS_START <= day_of_year <= CHRISTMAS_END:
        return True

    if SPRING_START <= day_of_year <= SPRING_END:
        return True

    if EASTER_START <= day_of_year <= EASTER_END:
        return True


def get_school_heating_consumption_hourly_factor(timestamp: datetime.datetime) -> float:
    """Assuming opening hours 8-17:00 except for weekends and breaks"""
    if timestamp.weekday() == 5 or timestamp.weekday() == 6:  # Saturday or sunday
        return 0.5
    if is_break(timestamp):
        return 0.5
    if not (8 <= timestamp.hour < 17):
        return 0.5
    return 1
