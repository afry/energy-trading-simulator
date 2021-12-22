import pandas as pd


def calculate_solar_prod(irradiation_data, pv_sqm, pv_efficiency):
    """
    Calculates the solar energy production from some solar panels, given irradiation, total size of solar panels, and
    their efficiency.

    Parameters
    ----------
    irradiation_data : pd.Series
        Irradiation data per datetime, in W/m2
    pv_sqm : float
        Total square meterage of solar panels
    pv_efficiency : float
        Efficiency of solar panels

    Returns
    -------
    pd.Series
        The solar energy production in kWh
    """
    return irradiation_data * pv_sqm * pv_efficiency / 1000


class DataStore:
    nordpool_data: pd.Series
    tornet_household_elec_cons: pd.Series
    coop_elec_cons: pd.Series  # Electricity used for cooling included
    tornet_heat_cons: pd.Series
    coop_heat_cons: pd.Series
    tornet_pv_prod: pd.Series
    coop_pv_prod: pd.Series  # Rooftop PV production

    def __init__(self, config_data, external_price_csv_path='../data/nordpool_area_grid_el_price.csv',
                 energy_data_csv_path='../data/full_mock_energy_data.csv',
                 irradiation_csv_path='../data/varberg_irradiation_W_m2_h.csv', ):
        self.pv_efficiency = config_data["PVEfficiency"]
        self.store_pv_area = config_data["StorePVArea"]
        self.park_pv_area = config_data["ParkPVArea"]
        self.rooftop_pv_area = config_data["RooftopPVArea"]
        self.total_tornet_pv_area = self.park_pv_area + self.rooftop_pv_area

        self.nordpool_data = self.__read_nordpool_data(external_price_csv_path)
        self.tornet_household_elec_cons, self.coop_elec_cons, \
            self.tornet_heat_cons, self.coop_heat_cons = self.__read_energy_data(energy_data_csv_path)
        irradiation_data = self.__read_solar_irradiation(irradiation_csv_path)
        self.coop_pv_prod = calculate_solar_prod(irradiation_data, self.store_pv_area, self.pv_efficiency)
        self.tornet_pv_prod = calculate_solar_prod(irradiation_data, self.total_tornet_pv_area, self.pv_efficiency)

    @staticmethod
    def __read_nordpool_data(external_price_csv):
        price_data = pd.read_csv(external_price_csv, index_col=0)
        price_data = price_data.squeeze()
        if price_data.mean() > 100:
            # convert price from SEK per MWh to SEK per kWh
            price_data = price_data / 1000
        price_data.index = pd.to_datetime(price_data.index)
        return price_data

    @staticmethod
    def __read_energy_data(energy_csv_path):
        energy_data = pd.read_csv(energy_csv_path, index_col=0)
        energy_data.index = pd.to_datetime(energy_data.index)
        return energy_data['tornet_electricity_consumed_household_kwh'], \
               energy_data['coop_electricity_consumed_cooling_kwh'] + \
               energy_data['coop_electricity_consumed_other_kwh'], \
               energy_data['tornet_energy_consumed_heat_kwh'], \
               energy_data['coop_net_heat_consumed']

    @staticmethod
    def __read_solar_irradiation(irradiation_csv_path):
        """Return solar irradiation, according to SMHI, in Watt per square meter"""
        irradiation_data = pd.read_csv(irradiation_csv_path, index_col=0)
        irradiation_series = irradiation_data['irradiation']
        irradiation_series.index = pd.to_datetime(irradiation_series.index)
        return irradiation_series

    def get_nordpool_price_for_period(self, period):
        return self.nordpool_data.loc[period]

    def get_retail_price(self, period):
        """Returns the price at which the external grid operator is willing to sell electricity, in SEK/kWh"""
        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        return self.get_nordpool_price_for_period(period) + 0.48

    def get_wholesale_price(self, period):
        """Returns the price at which the external grid operator is willing to buy electricity, in SEK/kWh"""
        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        return self.get_nordpool_price_for_period(period) + 0.05

    def get_tornet_household_electricity_consumed(self, period):
        return self.tornet_household_elec_cons.loc[period]

    def get_tornet_pv_produced(self, period):
        return self.tornet_pv_prod.loc[period]

    def get_coop_pv_produced(self, period):
        return self.coop_pv_prod.loc[period]

    def get_coop_electricity_consumed(self, period):
        return self.coop_elec_cons.loc[period]

    def get_trading_periods(self):
        tornet_household_times = self.tornet_household_elec_cons.index.tolist()
        nordpool_times = self.nordpool_data.index.tolist()
        timestamps = [time for time in tornet_household_times if time in nordpool_times]

        return timestamps
