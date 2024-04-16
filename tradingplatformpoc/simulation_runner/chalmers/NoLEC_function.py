import pandas as pd
import pyomo.environ as pyo
from AgentEMS import solve_model

# from solver import get_solver

start_time = "2019-07-01 00:00:00+00:00"
end_time = "2019-07-01 23:00:00+00:00"

price_data = pd.read_csv(r'C:\Users\mazadi\PycharmProjects\Jonstakaproject_version1\JonstakaProject\CEMS\Agent-data '
                         r'for default setup/electricity_pricing_nordpool_data.csv')
selected_data = price_data[(price_data['period'] >= start_time) & (price_data['period'] <= end_time)]
price_buy = selected_data['electricity_price'].reset_index(drop=True)
price_sell = 0.9 * selected_data['electricity_price'].reset_index(drop=True)

# demand and production
agent_data_dir = r'C:\Users\mazadi\PycharmProjects\Jonstakaproject_version1\JonstakaProject\CEMS' \
                 r'\agents_data_with_cooling'
ResidentialBuildingAgentB2 = pd.read_csv(r'%s\ResidentialBuildingAgentB2.csv' % agent_data_dir)
ResidentialBuildingAgentB2 = ResidentialBuildingAgentB2[(ResidentialBuildingAgentB2['period'] >= start_time) &
                                                        (ResidentialBuildingAgentB2['period'] <= end_time)]
ResidentialBuildingAgentBC1 = pd.read_csv(r'%s\ResidentialBuildingAgentBC1.csv' % agent_data_dir)
ResidentialBuildingAgentBC1 = ResidentialBuildingAgentBC1[(ResidentialBuildingAgentBC1['period'] >= start_time) &
                                                          (ResidentialBuildingAgentBC1['period'] <= end_time)]
ResidentialBuildingAgentB4 = pd.read_csv(r'%s\ResidentialBuildingAgentB4.csv' % agent_data_dir)
ResidentialBuildingAgentB4 = ResidentialBuildingAgentB4[(ResidentialBuildingAgentB4['period'] >= start_time) &
                                                        (ResidentialBuildingAgentB4['period'] <= end_time)]
ResidentialBuildingAgentBC6 = pd.read_csv(r'%s\ResidentialBuildingAgentBC6.csv' % agent_data_dir)
ResidentialBuildingAgentBC6 = ResidentialBuildingAgentBC6[(ResidentialBuildingAgentBC6['period'] >= start_time) &
                                                          (ResidentialBuildingAgentBC6['period'] <= end_time)]
Pdem = pd.DataFrame([ResidentialBuildingAgentB2['electricity_usage'],
                     ResidentialBuildingAgentBC1['electricity_usage'],
                     ResidentialBuildingAgentB4['electricity_usage'],
                     ResidentialBuildingAgentBC6['electricity_usage']])
Ppv = pd.DataFrame([ResidentialBuildingAgentB2['electricity_production'],
                    ResidentialBuildingAgentBC1['electricity_production'],
                    ResidentialBuildingAgentB4['electricity_production'],
                    ResidentialBuildingAgentBC6['electricity_production']])
Hhw = pd.DataFrame([ResidentialBuildingAgentB2['hot_water_usage'],
                    ResidentialBuildingAgentBC1['hot_water_usage'],
                    ResidentialBuildingAgentB4['hot_water_usage'],
                    ResidentialBuildingAgentBC6['hot_water_usage']])
Hsh = pd.DataFrame([ResidentialBuildingAgentB2['space_heating_usage'],
                    ResidentialBuildingAgentBC1['space_heating_usage'],
                    ResidentialBuildingAgentB4['space_heating_usage'],
                    ResidentialBuildingAgentBC6['space_heating_usage']])
Cld = pd.DataFrame([ResidentialBuildingAgentB2['cooling_usage'],
                    ResidentialBuildingAgentBC1['cooling_usage'],
                    ResidentialBuildingAgentB4['cooling_usage'],
                    ResidentialBuildingAgentBC6['cooling_usage']])
# Construct some mock data for excess low-tempered heat
hsh_excess_df = Hsh.copy()
hsh_excess_df.loc[:, :] = 0
hsh_excess_df.iloc[0, :] = 10.0

# Heat price
Hprice_energy = 0.521  # SEK/kWh
# HPrice_effect = {'f':{9510, 14560, 27863}, 'v':{911, 861, 808}} #f: SEK/year, v: #SEK/kWh year, 0-100, 101-250,
# 251-500
Hprice_peak = {'f': [9510], 'v': [911]}  # f: SEK/year, v: #SEK/kWh year for 0-100 kWh thermal

# BES data
eff = 0.95
SOCBES0 = [0.4, 0.4, 0.4, 0.4]
Emax_BES = [20, 10, 20, 0]
Pmax_BES_Cha = [10, 5, 5, 10]
Pmax_BES_Dis = [10, 5, 5, 10]

# Parameters of heat pump and booster heat pump
Phpmax = [60, 60, 60, 60]  # HP's maximum electricity limit
Hhpmax = [280, 280, 280, 280]  # HP's maximum heat limit
Chpmax = [280, 280, 280, 280]  # HP's maximum cool limit
COPhp = [4.6, 4.6, 4.6, 4.6]  # HP's coefficient of performance
PhpBmax = [60, 60, 60, 60]  # Booster HP's maximum electricity limit
HhpBmax = [280, 280, 280, 280]  # Booster HP's maximum heat limit
COPhpB = [4, 4, 4, 4]  # Booster HP's coefficient of performance
HP_Cproduct_active = [False, False, False, False]
# #####################Area of buildings that should be heated#############################
build_area = [1000, 1000, 1000, 1000]  # m2

# #####################Thermal energy storage#############################
SOCTES0 = [1, 1, 1, 1]
thermalstorage_max_temp = [65, 65, 65, 65]  # deg. C
thermalstorage_volume = [2, 2, 2, 2]  # m3
BITES_Eshallow0 = [0, 0, 0, 0]
BITES_Edeep0 = [0, 0, 0, 0]

# #####################Borehole#############################
borehole = [True, False, True, False]
# replace get_solver() with
# to solve the model.
# pyo.SolverFactory('gurobi', solver_io="python", executable=r"C:\gurobi1003\win64")
# get_solver()

n_agents = 4
mod = {}
res = {}
for j in range(n_agents):
    mod[j], res[j] = solve_model(pyo.SolverFactory('gurobi', solver_io="python", executable=r"C:\gurobi1003\win64"),
                                 summer_mode=True, month=7, agent=j, external_elec_buy_price=price_buy,
                                 external_elec_sell_price=price_sell, external_heat_buy_price=Hprice_energy,
                                 battery_capacity=Emax_BES[j], battery_charge_rate=Pmax_BES_Cha[j],
                                 battery_discharge_rate=Pmax_BES_Dis[j], SOCBES0=SOCBES0[j],
                                 HP_Cproduct_active=HP_Cproduct_active[j], heatpump_COP=COPhp[j],
                                 heatpump_max_power=Phpmax[j], heatpump_max_heat=Hhpmax[j],
                                 booster_heatpump_COP=COPhpB[j], booster_heatpump_max_power=PhpBmax[j],
                                 booster_heatpump_max_heat=HhpBmax[j], build_area=build_area[j], SOCTES0=SOCTES0[j],
                                 thermalstorage_max_temp=thermalstorage_max_temp[j],
                                 thermalstorage_volume=thermalstorage_volume[j], BITES_Eshallow0=BITES_Eshallow0[j],
                                 BITES_Edeep0=BITES_Edeep0[j], borehole=borehole[j], elec_consumption=Pdem.iloc[j, :],
                                 hot_water_heatdem=Hhw.iloc[j, :], space_heating_heatdem=Hsh.iloc[j, :],
                                 cold_consumption=Cld.iloc[j, :], pv_production=Ppv.iloc[j, :],
                                 excess_heat=hsh_excess_df.iloc[j, :], battery_efficiency=eff,
                                 max_elec_transfer_between_agents=500, max_elec_transfer_to_external=1000,
                                 max_heat_transfer_between_agents=500, max_heat_transfer_to_external=1000,
                                 chiller_COP=1.5, thermalstorage_efficiency=0.98, heat_trans_loss=0.05,
                                 cold_trans_loss=0.05, trading_horizon=24)

print(res[0].Problem._list)
