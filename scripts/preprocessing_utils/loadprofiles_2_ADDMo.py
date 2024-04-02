import pandas as pd
import numpy as np
import math

from config.definitions import ROOT_DIR


# load loadprofiles csv
path_result_file = "data\\01_input\\02_electric_loadprofiles_HTW"
name_result_file = "el_loadprofiles_HTW_processed"
df = pd.read_csv(f"{ROOT_DIR}\\{path_result_file}\\{name_result_file}.csv", index_col=0)

# choose one loadprofile for faster processing
loadprofile_nr = 0
df = df.iloc[:, [loadprofile_nr]]

# convert to ADDMo format and save as excel
df = df.add_suffix(" [W]")
df.index = pd.to_datetime(df.index)
df.index = df.index.tz_localize(None)

# add sinoidal time features to df
df["daytime_sin []"] = df.index.hour * 60 + df.index.minute
df["daytime_sin []"] = np.cos(2 * math.pi * df["daytime_sin []"] / df["daytime_sin []"].max())
df["weektime_sin []"] = df.index.weekday * 24 * 60 + df.index.hour * 60 + df.index.minute
df["weektime_sin []"] = np.cos(2 * math.pi * df["weektime_sin []"] / df["weektime_sin []"].max())

df.to_excel(f"{ROOT_DIR}\\{path_result_file}\\{name_result_file}_{loadprofile_nr}.xlsx", index=True)

print(f"File saved to {ROOT_DIR}\\{path_result_file}\\{name_result_file}_{loadprofile_nr}.xlsx")