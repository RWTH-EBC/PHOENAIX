import pandas as pd
from datetime import timedelta

from config.definitions import ROOT_DIR

"""
Calculate the electrical demand from the HTW files, which give different phases and reactive power.
The processed data set is converted to UTC.
"""


# specifying input pathes, like downloaded from
# https://solar.htw-berlin.de/elektrische-lastprofile-fuer-wohngebaeude/
input_path = "D:\\00_Temp\CSV_74_Loadprofiles_1min_W_var_2"
data_files_P = ["PL1.csv", "PL2.csv", "PL3.csv"]
data_files_Q = ["QL1.csv", "QL2.csv", "QL3.csv"]
time_file = "time_datevec_MEZ.csv"

# create index
df_index = pd.read_csv(f"{input_path}\\{time_file}", header=None)
df_index.columns = ["year", "month", "day", "hour", "minute", "second"]
# convert from year 2010 to year 2018
df_index["year"] = df_index["year"] + 8
# convert from MEZ winter to UTC
datetime_col = pd.to_datetime(df_index, utc=True)
datetime_col = datetime_col - timedelta(hours=1)

df = pd.DataFrame(index=datetime_col, columns=range(0, 74, 1), data=0)

for p_file, q_file in zip(data_files_P, data_files_Q):
    # load csv file into a pandas dataframe
    df_data_p = pd.read_csv(f"{input_path}\\{p_file}", header=None)
    df_data_q = pd.read_csv(f"{input_path}\\{q_file}", header=None)

    # calculate true power S = sqrt(P^2 + Q^2)
    df_data = (df_data_p**2 + df_data_q**2) ** (1 / 2)
    df_data = df_data.set_index(datetime_col)

    # sum up over all phases
    df = df.add(df_data)

# resample from 1min to lower time resolution 15min
# time stamp contains mean of following 15 minutes
df = df.resample("15min").mean()

# save as csv
path_result_file = "data\\01_input\\02_electric_loadprofiles_HTW"
name_result_file = "el_loadprofiles_HTW_processed"
df.to_csv(f"{ROOT_DIR}\\{path_result_file}\\{name_result_file}.csv")

print(f"File saved to {ROOT_DIR}\\{path_result_file}\\{name_result_file}.csv")
