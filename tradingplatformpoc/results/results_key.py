from enum import Enum


class ResultsKey(Enum):
    SAVING_ABS_GROSS = "Saving by using local market, before taking penalties into account [SEK]"
    SAVING_REL_GROSS = "Saving by using local market, before taking penalties into account [%]"
    SAVING_ABS_NET = "Saving by using local market, before taking penalties into account [SEK]"
    SAVING_REL_NET = "Saving by using local market, before taking penalties into account [%]"
    PENALTIES_BID_INACCURACY = "Total penalties accrued for bid inaccuracies [SEK]"
    ELEC_BOUGHT = "Electricity bought [kWh]"
    HEAT_BOUGHT = "Heating bought [kWh]"
    ELEC_SOLD = "Electricity sold [kWh]"
    HEAT_SOLD = "Heating sold [kWh]"
    PROFIT_GROSS = "Profit before taxes and grid fees [SEK]"
    PROFIT_NET = "Profit after taxes and grid fees [SEK]"
    TAX_PAID = "Taxes paid [SEK]"
    GRID_FEES_PAID = "Grid fees paid [SEK]"
    AVG_BUY_PRICE_ELEC = "Average buy price of electricity [SEK/kWh]"
    AVG_SELL_PRICE_ELEC = "Average sell price of electricity [SEK/kWh]"
    AVG_BUY_PRICE_HEAT = "Average buy price of heating [SEK/kWh]"
    AVG_SELL_PRICE_HEAT = "Average sell price of heating [SEK/kWh]"
