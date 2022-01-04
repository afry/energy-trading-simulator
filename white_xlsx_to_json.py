import pandas as pd

FILE_NAME = 'Jonstaka_ytberakning_overslag_210512_White.xlsx'

"""
This script takes in an Excel file, of the same format that we got from White, via BDAB, during fall 2021,
which details the planned sub-areas in Jonstaka. It translates these into our preferred JSON config format."""

if __name__ == '__main__':
    areas = pd.read_excel('./tradingplatformpoc/data/{}'.format(FILE_NAME),
                          names=['Name', 'BYA', 'GrossFloorArea'],
                          usecols='A,C,D',
                          skiprows=10, nrows=20)
    areas['Type'] = 'BuildingAgent'
    areas['Name'] = 'BuildingAgent' + areas['Name']
    # It is estimated that 50% of BYA can be covered by rooftop PV panels
    # (see https://doc.afdrift.se/display/RPJ/BDAB+data)
    areas['RooftopPVArea'] = areas['BYA'] / 2.0
    areas['RandomSeed'] = range(1, len(areas)+1)
    areas = areas[["Type", "Name", "RandomSeed", "GrossFloorArea", "RooftopPVArea"]]
    print(areas.to_json(orient='records'))
