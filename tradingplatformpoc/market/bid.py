from enum import Enum


class Action(Enum):
    BUY = 0
    SELL = 1


class Resource(Enum):
    ELECTRICITY = 0
    HEATING = 1  # TODO: remove
    COOLING = 2
    LOW_TEMP_HEAT = 3  # ~40 degrees Celsius - can cover space heating demand
    HIGH_TEMP_HEAT = 4  # ~65 degrees Celsius - needed for hot water, but can also cover space heating

    def get_display_name(self, capitalized: bool = False) -> str:
        un_capitalized: str
        if self.name == 'LOW_TEMP_HEAT':
            un_capitalized = 'low-temp heat'
        elif self.name == 'HIGH_TEMP_HEAT':
            un_capitalized = 'high-temp heat'
        else:
            un_capitalized = self.name.lower()
        return un_capitalized.capitalize() if capitalized else un_capitalized

    @staticmethod
    def is_resource_name(a_string: str, case_sensitive: bool = True) -> bool:
        for res in Resource:
            if (a_string == res.name) or (not case_sensitive and (a_string.lower() == res.name.lower())):
                return True
        return False

    @staticmethod
    def from_string(a_string: str):
        for res in Resource:
            if a_string.lower() == res.name.lower():
                return res
        raise RuntimeError('No resource with name ' + a_string)
