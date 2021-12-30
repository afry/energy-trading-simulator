import pandas as pd

FILE_NAME = 'Jonstaka_ytberakning_overslag_210512_White.xlsx'

if __name__ == '__main__':
    areas = pd.read_excel('./tradingplatformpoc/data/{}'.format(FILE_NAME),
                          names=['Name', 'BYA', 'GrossFloorArea'],
                          usecols='A,C,D',
                          skiprows=10, nrows=20)
    areas['Type'] = 'BuildingAgent'
    areas['Name'] = 'BuildingAgent' + areas['Name']
    areas['RooftopPVArea'] = areas['BYA'] / 2.0
    areas['RandomSeed'] = range(1, len(areas)+1)
    areas = areas[["Type", "Name", "RandomSeed", "GrossFloorArea", "RooftopPVArea"]]
    print(areas.to_json(orient='records'))
