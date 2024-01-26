import pandas as pd

PERCENT_OF_BYA_TO_COVER_WITH_PV_PANELS = 0.5

# It is estimated that 50% of BYA can be covered by rooftop PV panels
# (see https://doc.afdrift.se/display/RPJ/BDAB+data)
DEFAULT_SHARE_COMMERCIAL_IN_BC_AREAS = 0.2

FILE_NAME = 'Jonstaka_ytberakning_overslag_210512_White.xlsx'

"""
This script takes in an Excel file, of the same format that we got from White, via BDAB, during fall 2021,
which details the planned sub-areas in Jonstaka. It translates these into our preferred JSON config format."""

if __name__ == '__main__':
    areas = pd.read_excel('./tradingplatformpoc/data/{}'.format(FILE_NAME),
                          names=['Name', 'BYA', 'GrossFloorArea'],
                          usecols='A,C,D',
                          skiprows=10, nrows=20)
    should_include_commercial = areas['Name'].str[:2] == 'BC'
    # The area should include commercial elements
    areas['FractionCommercial'] = should_include_commercial * DEFAULT_SHARE_COMMERCIAL_IN_BC_AREAS
    areas['Type'] = 'ResidentialBlockAgent'
    areas['Name'] = 'ResidentialBlockAgent' + areas['Name']
    areas['PVArea'] = areas['BYA'] * PERCENT_OF_BYA_TO_COVER_WITH_PV_PANELS
    areas = areas[['Type', 'Name', 'GrossFloorArea', 'PVArea', 'FractionCommercial']]
    print(areas.to_json(orient='records'))
