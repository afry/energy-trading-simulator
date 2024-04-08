import pandas as pd

PERCENT_OF_BYA_TO_COVER_WITH_PV_PANELS = 0.25
# White estimated that 50% of BYA can be covered by rooftop PV panels
# (see https://doc.afdrift.se/display/RPJ/BDAB+data)
# But for our base case, we'll go with a more modest number, 20%
DEFAULT_SHARE_COMMERCIAL_IN_BC_AREAS = 0.2

BTA_TO_ATEMP = 0.9
# Atemp = 0.9 * BTA, according to https://www.sveby.org/wp-content/uploads/2012/01/brukarindata_bostader.pdf

"""
This script takes in an Excel file, of the same format that we got from White, via BDAB, during fall 2021,
which details the planned sub-areas in Jonstaka. It translates these into our preferred JSON config format."""

if __name__ == '__main__':
    areas = pd.read_excel('../tradingplatformpoc/data/Jonstaka_ytberakning_overslag_210512_White.xlsx',
                          names=['Name', 'BYA', 'GrossFloorArea'],
                          usecols='A,C,D',
                          skiprows=10, nrows=20)
    should_include_commercial = areas['Name'].str[:2] == 'BC'
    # The area should include commercial elements
    areas['FractionCommercial'] = should_include_commercial * DEFAULT_SHARE_COMMERCIAL_IN_BC_AREAS
    areas['Type'] = 'BlockAgent'
    areas['Name'] = 'ResidentialBlockAgent' + areas['Name']
    # "Atemp" is the space meant to be kept heated. Scaling factors are given for this measure, so we need to convert
    # our "GrossFloorArea"/"BTA"
    areas['Atemp'] = areas['GrossFloorArea'] * BTA_TO_ATEMP
    areas['PVArea'] = areas['BYA'] * PERCENT_OF_BYA_TO_COVER_WITH_PV_PANELS
    areas = areas[['Type', 'Name', 'Atemp', 'PVArea', 'FractionCommercial']]
    areas['FractionSchool'] = 0.0
    areas['FractionOffice'] = 0.0
    # BC areas need a heat pump to be able to produce cooling
    areas['HeatPumpMaxInput'] = [45.0 if should_include_commercial.values[i] or i >= 14 else 0.0 for i in range(20)]
    areas['HeatPumpMaxOutput'] = [145.0 if should_include_commercial.values[i] or i >= 14 else 0.0 for i in range(20)]
    areas['BoosterPumpMaxInput'] = 25.0
    areas['BoosterPumpMaxOutput'] = 100.0
    areas['HeatPumpForCooling'] = should_include_commercial.values
    areas['BatteryCapacity'] = 100.0
    areas['AccumulatorTankCapacity'] = 300.0
    areas['FractionUsedForBITES'] = 0.0
    print(areas.to_json(orient='records'))
