import pandas as pd
import pickle

def read(file):
    data            =pd.read_pickle(file)
    meta            = pd.DataFrame(data.iloc[-1]).transpose().dropna(axis=1, how="all")
    weatherdata     = data.drop([0], axis=0).dropna(axis=1, how="all")

    return weatherdata, meta

def store(data,filename):
    data.to_csv(filename)

if __name__ == "__main__" :
    weatherdata, meta = read(file="DWD_Wetterdaten_Station_15000_2018-2020.pkl")
    store(data=weatherdata,filename="DWD_Wetterdaten_Aachen_2018-2020.csv")