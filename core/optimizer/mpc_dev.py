from pathlib import Path
import sys
p = str(Path(__file__).parents[2])
if p not in sys.path:
    sys.path.insert(0, p)
import os
import gurobipy as gp
from pprint import pprint
import pandas as pd
#from config.definitions import ROOT_DIR
from config.definitions import ROOT_DIR
from core.utils.create_rh_params import create_rh_params
from core.utils.load_demands import load_demands_and_pv
from core.simulation.fmu_handler import FMUHandler
from tqdm import tqdm
import matplotlib.pyplot as plt
from mpc import MPC




def main():
    demands_and_pv = load_demands_and_pv()
    demands_and_pv = demands_and_pv[::4].copy()  # To make 15m interval hourly
    N_HORIZON = 10
    
    
    soc_init = None
        
    param_mpc = {}
    param_mpc["eco"] = {}
    param_mpc["gp"] = {}

    # Always EUR per kWh (meter per anno)
    # €/kWh valid for pv systems with < 10 kWp
    param_mpc["eco"]["sell_pv"] = 0.082
    param_mpc["eco"]["el_grid"] = 0.42
    # Durchschnitt Januar 2023, Quelle Handelsblatt
    param_mpc["eco"]["gas"] = 0.134

    # https://www.gurobi.com/documentation/9.1/refman/mipgap2.html
    param_mpc["gp"]["mip_gap"] = 0.01
    # [s]  https://www.gurobi.com/documentation/9.1/refman/timelimit.html
    param_mpc["gp"]["time_limit"] = 100
    # https://www.gurobi.com/documentation/9.1/refman/numericfocus.html
    param_mpc["gp"]["numeric_focus"] = 3
    
    buildings = MPC.load_buildings()
    
    
    for n in tqdm(range(8000)):
        # For Loop test

        input_dict = {}
        use_dem = demands_and_pv.iloc[n: n+N_HORIZON]
        for col1, col2 in use_dem.columns:
            if col1 not in input_dict:
                input_dict[col1] = {}

            input_dict[col1][col2] = use_dem[(col1, col2)].to_numpy()



        original_stdout = sys.stdout
        try:
            sys.stdout = open(os.devnull, 'w')
            res = MPC._run_central_optimization(demands_and_pv=input_dict,
                                                buildings=buildings,
                                                n_horizon=N_HORIZON,
                                                param_mpc=param_mpc,
                                                init_val=soc_init)
        except AttributeError:
            sys.stdout.close()
            sys.stdout = original_stdout
            res = MPC._run_central_optimization(demands_and_pv=input_dict,
                                                buildings=buildings,
                                                n_horizon=N_HORIZON,
                                                param_mpc=param_mpc,
                                                init_val=soc_init)
        finally:
            sys.stdout.close()
            sys.stdout = original_stdout
            
        res_soc = res[3]
        soc_init = {'soc': {
                0: {'tes': 0},
                1: {'tes': res_soc[1]['tes'][0]},
                2: {'tes': res_soc[2]['tes'][0]},
                3: {'tes': res_soc[3]['tes'][0]},
                4: {'tes': 0},
            }}
        
        #pprint(soc_init)
    

if __name__ == '__main__':
    main()
