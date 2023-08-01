import pandas as pd


class PhotoVoltaics:
    """
    TODO
    """

    electricity_production: pd.Series

    def __init__(self, electricity_production: pd.Series):
        self.electricity_production = electricity_production

    def get_production(self, period) -> float:
        return self.electricity_production.loc[period]
