import pandas as pd
from config.definitions import ROOT_DIR
from pathlib import Path

DEMANDS_PATH = Path(ROOT_DIR) / 'data' / '01_input' / '01_demands'

def load_demands(year=2018):
    building_id_map = {
        0: 'SFH_1_0',
        1: 'SFH_1_1',
        2: 'SFH_1_2',
        3: 'SFH_1_3',
        4: 'MFH_5_0'}

    start_date = f'{year}-01-01 00:00:00'
    end_date = f'{year}-12-31 23:59:59'

    # Create the time index with 15-minute intervals
    time_index = pd.date_range(start=start_date, end=end_date, freq='15T')
    demands = {}
    for demand in ['cooling', 'dhw', 'elec', 'heating']:
        dfs = []
        for id, name in building_id_map.items():
            file_name = f'{demand}_{name}.csv'
            _df = pd.read_csv(DEMANDS_PATH / file_name, header=None)
            _df.index = time_index
            _df.columns = [id]
            dfs.append(_df)

        df = pd.concat(dfs, axis=1)
        demands[demand] = df

    return demands