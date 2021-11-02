import pandas as pd


class DataStore:
    nordpool_data: pd.DataFrame

    def __init__(self, external_price_csv='data/nordpool_area_grid_el_price.csv'):
        self.nordpool_data = pd.read_csv(external_price_csv, index_col=0)
        if self.nordpool_data.mean()[0] > 100:
            # convert price from SEK per MWh to SEK per kWh
            self.nordpool_data = self.nordpool_data / 1000
        self.nordpool_data.columns = ['price_sek_kwh']

        # Read more data here

    def get_nordpool_price_for_period(self, period):
        return self.nordpool_data.loc[period].iloc[0]
