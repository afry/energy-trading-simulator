import pandas as pd


class DataStore:
    nordpool_data: pd.Series
    tornet_household_elec_cons: pd.Series
    coop_elec_cons: pd.Series  # Electricity used for cooling included
    tornet_pv_prod: pd.Series
    coop_pv_prod: pd.Series  # Rooftop PV production

    def __init__(self, external_price_csv_path='data/nordpool_area_grid_el_price.csv',
                 energy_data_csv_path='data/full_mock_energy_data.csv'):
        self.nordpool_data = self.__read_nordpool_data(external_price_csv_path)
        self.tornet_household_elec_cons, self.coop_elec_cons, self.tornet_pv_prod, self.coop_pv_prod = \
            self.__read_energy_data(energy_data_csv_path)
        # Read more data here

    @staticmethod
    def __read_nordpool_data(external_price_csv):
        price_data = pd.read_csv(external_price_csv, index_col=0)
        price_data = price_data.squeeze()
        if price_data.mean() > 100:
            # convert price from SEK per MWh to SEK per kWh
            price_data = price_data / 1000
        return price_data

    @staticmethod
    def __read_energy_data(energy_csv_path):
        energy_data = pd.read_csv(energy_csv_path, index_col=0)
        return energy_data['tornet_electricity_consumed_household_kwh'], \
               energy_data['coop_electricity_consumed_cooling_kwh'] + energy_data[
                   'coop_electricity_consumed_other_kwh'], \
               energy_data['tornet_electricity_produced_PV_kwh'], \
               energy_data['coop_electricity_produced_rooftop_PV_kwh']

    def get_nordpool_price_for_period(self, period):
        return self.nordpool_data.loc[period]

    def get_tornet_household_electricity_consumed(self, period):
        return self.tornet_household_elec_cons.loc[period]

    def get_tornet_pv_produced(self, period):
        return self.tornet_pv_prod.loc[period]

    def get_coop_pv_produced(self, period):
        return self.coop_pv_prod.loc[period]

    def get_coop_electricity_consumed(self, period):
        return self.coop_elec_cons.loc[period]
    
    def get_energy_mock_timestamps(self):
        return self.tornet_household_elec_cons.index.tolist()
