import pandas as pd
from datetime import datetime, timezone, timedelta
import math

'''
Calculate the electrical demand from the HTW files, which give different phases and reactive power.
The processed data set is converted to UTC.
'''


# specifying input pathes
input_path = "D:\\00_Temp\CSV_74_Loadprofiles_1min_W_var_2"
data_files_P = ["PL1.csv", "PL2.csv", "PL3.csv"]
data_files_Q = ["QL1.csv", "QL2.csv", "QL3.csv"]
time_file = "time_datevec_MEZ.csv"

# create index
df_index = pd.read_csv(f"{input_path}\\{time_file}", header=None)
df_index.columns = ['year', 'month', 'day', 'hour', 'minute', 'second']
# convert from year 2010 to year 2018
df_index['year'] = df_index['year'] + 8
# convert from MEZ winter to UTC
datetime_col = pd.to_datetime(df_index, utc=True)
datetime_col = datetime_col - timedelta(hours=1)

df = pd.DataFrame(index=datetime_col, columns=range(0,74,1), data=0)

for p_file, q_file in zip(data_files_P, data_files_Q):
    # load csv file into a pandas dataframe
    df_data_p = pd.read_csv(f"{input_path}\\{p_file}", header=None)
    df_data_q = pd.read_csv(f"{input_path}\\{q_file}", header=None)

    # calculate true power S = sqrt(P^2 + Q^2)
    df_data = (df_data_p**2 + df_data_q**2)**(1/2)
    df_data = df_data.set_index(datetime_col)

    # add the values of the dataframes (power of phases and blind power phases)
    df = df.add(df_data)


df.to_csv("D:\\00_Temp\CSV_74_Loadprofiles_1min_W_var_2\el_load_processed.csv")

# Import review
processed = pd.read_csv("D:\\00_Temp\CSV_74_Loadprofiles_1min_W_var_2\el_load_processed.csv",index_col=0)

print("finish")