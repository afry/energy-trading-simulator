
# External grid buys heat at 50% of the price they buy for - arbitrary
DEFAULT_HEATING_WHOLESALE_PRICE_FRACTION = 0.5
# Variable consumption fee + effektavgift/(hours in a year) = 0.0588+620/8768 = 0.13
DEFAULT_ELECTRICITY_WHOLESALE_PRICE_OFFSET = 0.05


param_spec_dict = {
    "AreaInfo": {
        "DefaultPVEfficiency": {
            "display": "Default PV efficiency:",
            "min_value": 0.01,
            "max_value": 0.99,
            "format": "%.3f",
            "help": "A number specifying the efficiency of solar panels in "
                    "the microgrid. Can be overridden by individual agents. "
                    "Number must be between 0 and 1, and is typically in the 0.15-0.25 "
                    "range",
            "required": True
        },
        "HeatTransferLoss": {
            "display": "Heat transfer loss:",
            "min_value": 0.0,
            "max_value": 0.99,
            "format": "%.3f",
            "help": "A number specifying the loss of heat in every transfer. Must be between 0 and "
                    "0.99, where 0 would mean no losses at all, and 0.99 would mean that almost all energy "
                    "is lost when trying to transfer heat from one agent to another. A reasonable number "
                    "would be in the 0-0.10 range.",
            "required": True
        },
        "ExternalElectricityWholesalePriceOffset": {
            "display": "External electricity wholesale price offset:",
            "min_value": -1.0,
            "max_value": 1.0,
            "default": DEFAULT_ELECTRICITY_WHOLESALE_PRICE_OFFSET,
            "help": "The price at which the microgrid can export electricity to the external grid, "
                    "will be set to the Nordpool spot price, plus this offset. The unit is SEK/kWh. "
                    "For Varberg Energi, indications are that this will be in the 0-0.15 range. "
                    "If not specified, will default to " + str(DEFAULT_ELECTRICITY_WHOLESALE_PRICE_OFFSET),
            "required": False
        },
        "ElectricityTax": {
            "display": "Electricity tax:",
            "min_value": 0.0,
            "format": "%.3f",
            "help": "The electricity tax in SEK/kWh, for trades not inside the local market. For 2022, this "
                    "is 0.392, but here it can be set to any (non-negative) number",
            "required": True
        },
        "ElectricityGridFee": {
            "display": "Electricity grid fee:",
            "min_value": 0.0,
            "format": "%.3f",
            "help": "The electricity grid fee in SEK/kWh, for trades not inside the local market. The "
                    "price at which electricity can be "
                    "imported into the microgrid will be set to the Nordpool spot price, plus the "
                    "electricity tax, plus this number. In reality it is quite complicated to calculate,"
                    " since it depends on the average effect used for the three months with highest "
                    "consumption over the year, but here we approximate it with a flat SEK/kWh rate. "
                    "For Varberg Energi in 2023 this approximation is roughly equal "
                    "to 0.148, but here it can be set to any (non-negative) number",
            "required": True
        },
        "ElectricityTaxInternal": {
            "display": "Electricity tax (internal):",
            "min_value": 0.0,
            "format": "%.3f",
            "help": "The electricity tax in SEK/kWh, paid on internal trades in the local market. "
                    "Should be between 0 and the 'external'/'normal' tax",
            "required": True
        },
        "ElectricityGridFeeInternal": {
            "display": "Electricity grid fee (internal):",
            "min_value": 0.0,
            "format": "%.3f",
            "help": "The grid fee, in SEK/kWh, paid on internal trades in the local market. "
                    "Should be between 0 and the 'external'/'normal' grid fee",
            "required": True
        },
        "ExternalHeatingWholesalePriceFraction": {
            "display": "External heating wholesale price fraction:",
            "min_value": 0.0,
            "max_value": 1.0,
            "default": DEFAULT_HEATING_WHOLESALE_PRICE_FRACTION,
            "help": "The price at which the microgrid can export heat to the "
                    "external grid, will be set to the import (retail) price, multiplied by this factor. "
                    "Should be less than 1. In reality, the external grid may not want to buy any heat from "
                    "the microgrid at all - this can be achieved by setting this number to 0. "
                    "If not specified, will default to " + str(DEFAULT_HEATING_WHOLESALE_PRICE_FRACTION),
            "required": False
        }
    },
    "MockDataConstants": {
        "ResidentialElecKwhPerYearM2Atemp": {
            "display": "Residential electricity kWh/year/m2:",
            "min_value": 1,
            "max_value": 100,
            "help": "Number indicating the electricity consumption of residential areas, in kWh per "
                    "year and square meter. The default of 20 kWh/year/m2 'atemp' comes from a "
                    "2017-2018 metering study made by Skanska, 'Hushållsel i nybyggda flerbostadshus'. "
                    "'Atemp' refers to a specific surface area measurement from which energy-related "
                    "metrics are calculated. Essentially, it's the surface area which experiences a "
                    "temperature modulation by an energy source.",
            "required": False
        },
        "ResidentialSpaceHeatKwhPerYearM2": {
            "display": "Residential space heat kWh/year/m2:",
            "min_value": 1,
            "max_value": 100,
            "help": "Number indicating the space heating consumption of residential "
                    "areas, in kWh per year and square meter. The default of 25 "
                    "kWh/year/m2 has been provided by BDAB.",
            "required": False
        },
        "ResidentialHotTapWaterKwhPerYearM2": {
            "display": "Residential hot tap water kWh/year/m2:",
            "min_value": 1,
            "max_value": 100,
            "help": "Number indicating the hot tap water consumption of residential "
                    "areas, in kWh per year and square meter. The default of 25 "
                    "kWh/year/m2 has been provided by BDAB.",
            "required": False
        },
        "ResidentialHeatingRelativeErrorStdDev": {
            "display": "Residential hot tap water relative standard deviation:",
            "min_value": 0.0,
            "max_value": 1.0,
            "help": "The standard deviation of simulated heating consumption of "
                    "residential areas, in relative terms. For a given hour, an expected "
                    "value will be calculated, and the simulated value will then be this "
                    "expected value, multiplied with a factor normally distributed with a "
                    "mean of 1 and a standard deviation of this value. Basically, the "
                    "higher this value is, the more residential heating consumption will "
                    "vary, hour-to-hour.",
            "required": False
        },
        "CommercialElecKwhPerYearM2": {
            "display": "Commercial electricity kWh/year/m2:",
            "min_value": 1,
            "max_value": 200,
            "help": "Number indicating the electricity consumption of commercial areas, in kWh per "
                    "year and square meter. The default of 118 kWh/year/m2 comes from "
                    "Energimyndigheten's 2009 report 'Energianvändning i handelslokaler'. This "
                    "number is given for 'non-grocery-related' trades premises.",
            "required": False
        },
        "CommercialElecRelativeErrorStdDev": {
            "display": "Commercial electricity relative standard deviation:",
            "min_value": 0.0,
            "max_value": 1.0,
            "help": "The standard deviation of simulated electricity consumption of commercial "
                    "areas, in relative terms. For a given hour, an expected value will be "
                    "calculated, and the simulated value will then be this expected value, "
                    "multiplied with a factor normally distributed with a mean of 1 and a "
                    "standard deviation of this value. Basically, the higher this value is, the "
                    "more commercial electricity consumption will vary, hour-to-hour.",
            "required": False
        },
        "CommercialSpaceHeatKwhPerYearM2": {
            "display": "Commercial space heat kWh/year/m2:",
            "min_value": 1,
            "max_value": 100,
            "help": "Number indicating the space heating consumption of commercial areas, "
                    "in kWh per year and square meter. The default of 32 kWh/year/m2 has "
                    "been derived from a combination of numbers provided by BDAB: For "
                    "commercial office buildings, they quote 20 kWh/year/m2, and for "
                    "'köpcentrum' 44 kWh/year/m2. Since these commercial areas will "
                    "likely be of mixed character, we split these numbers down the middle.",
            "required": False
        },
        "CommercialHotTapWaterKwhPerYearM2": {
            "display": "Commercial hot tap water kWh/year/m2:",
            "min_value": 1.0,
            "max_value": 10.0,
            "step": 0.5,
            "help": "Number indicating the hot tap water consumption of commercial areas, "
                    "in kWh per year and square meter. The default of 3.5 kWh/year/m2 has "
                    "been derived from a combination of numbers provided by BDAB: For "
                    "commercial office buildings, they quote 2 kWh/year/m2, and for "
                    "'köpcentrum' 5 kWh/year/m2. Since these commercial areas will "
                    "likely be of mixed character, we split these numbers down the middle.",
            "required": False
        },
        "CommercialHotTapWaterRelativeErrorStdDev": {
            "display": "Commercial hot tap water relative standard deviation:",
            "min_value": 0.0,
            "max_value": 1.0,
            "help": "The standard deviation of simulated hot tap water consumption of "
                    "commercial areas, in relative terms. For a given hour, an expected "
                    "value will be calculated, and the simulated value will then be "
                    "this expected value, multiplied with a factor normally distributed "
                    "with a mean of 1 and a standard deviation of this value. "
                    "Basically, the higher this value is, the more commercial hot tap "
                    "water consumption will vary, hour-to-hour.",
            "required": False
        },
        "SchoolElecKwhPerYearM2": {
            "display": "School electricity kWh/year/m2:",
            "min_value": 1,
            "max_value": 200,
            "help": "Number indicating the electricity consumption of school buildings, "
                    "in kWh per year and square meter. The default of 60 kWh/year/m2 "
                    "comes from Energimyndigheten's 2009 report 'Energin i skolan'.",
            "required": False
        },
        "SchoolElecRelativeErrorStdDev": {
            "display": "School electricity relative standard deviation:",
            "min_value": 0.0,
            "max_value": 1.0,
            "help": "The standard deviation of simulated electricity consumption of school "
                    "areas, in relative terms. For a given hour, an expected value will be "
                    "calculated, and the simulated value will then be this expected value, "
                    "multiplied with a factor normally distributed with a mean of 1 and a "
                    "standard deviation of this value. Basically, the higher this value is, "
                    "the more school electricity consumption will vary, hour-to-hour.",
            "required": False
        },
        "SchoolSpaceHeatKwhPerYearM2": {
            "display": "School space heat kWh/year/m2:",
            "min_value": 1,
            "max_value": 100,
            "help": "Number indicating the space heating consumption of school "
                    "buildings, in kWh per year and square meter. The default of 25 "
                    "kWh/year/m2 has been provided by BDAB.",
            "required": False
        },
        "SchoolHotTapWaterKwhPerYearM2": {
            "display": "School hot tap water kWh/year/m2:",
            "min_value": 1,
            "max_value": 100,
            "help": "Number indicating the hot tap water consumption of school "
                    "buildings, in kWh per year and square meter. The default of 7 "
                    "kWh/year/m2 has been provided by BDAB.",
            "required": False
        },
        "SchoolHotTapWaterRelativeErrorStdDev": {
            "display": "School hot tap water relative standard deviation:",
            "min_value": 0.0,
            "max_value": 1.0,
            "help": "The standard deviation of simulated hot tap water consumption of "
                    "school buildings, in relative terms. For a given hour, an "
                    "expected value will be calculated, and the simulated value "
                    "will then be this expected value, multiplied with a factor "
                    "normally distributed with a mean of 1 and a standard deviation "
                    "of this value. Basically, the higher this value is, the more "
                    "school hot tap water consumption will vary, hour-to-hour.",
            "required": False
        }
    
    }
}
