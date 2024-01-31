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
from core.optimizer.mpc import MPC

def main():
    demands_and_pv = load_demands_and_pv()
    demands_and_pv = demands_and_pv[::4].copy()  # To make 15m interval hourly
    N_HORIZON = 10
    STEPSIZE = 3600
    
    soc_init = None
    
    results = []
    n_inf = 0
    
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
    
    fmu_path = Path(__file__).parents[2] / 'data' / '01_input' / '05_fmu' / 'DEQ_MVP_FMU.fmu'

    fmu = FMUHandler(fmu_path=fmu_path,
                         step_size=STEPSIZE)
    fmu.initialize()
    
    
    add_ix = 0
    n_inf = 0
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
            with open(os.devnull, 'w') as f:
                sys.stdout = f
                res = MPC._run_central_optimization(demands_and_pv=input_dict,
                                                    buildings=buildings,
                                                    n_horizon=N_HORIZON,
                                                    param_mpc=param_mpc,
                                                    init_val=soc_init)
        except:
            res = None
            n_inf += 1
            
        finally:
            sys.stdout.close()
            sys.stdout = original_stdout
                    
        modelica_input_dict = {
            'thermalDemand0': input_dict['heating'][0][0],
            'thermalDemand1': input_dict['heating'][1][0],
            'thermalDemand2': input_dict['heating'][2][0],
            'thermalDemand3': input_dict['heating'][3][0],
            'thermalDemand4': input_dict['heating'][4][0],
        }

        for key, name in [(1, 'relativePower1'),
                        (2, 'relativePower2'),
                        (3, 'relativePower3')]:
            

            if res is None:
                _rel_hp = results[-1][name]
            else:
                _rel_hp = res[1][key]['hp'][0+add_ix] / 5000
            modelica_input_dict[name] = _rel_hp
        
        fmu.do_step(modelica_input_dict)
        
        soc_dict = {}
        for name in ['haus_1.SOC',
                    'haus_2.SOC',
                    'haus_3.SOC']:
            
            soc = fmu.get_value(name) / 3600
            soc_dict[name] = soc

        
        soc_init = {'soc': {
            0: {'tes': 0},
            1: {'tes': soc_dict['haus_1.SOC']},
            2: {'tes': soc_dict['haus_2.SOC']},
            3: {'tes': soc_dict['haus_3.SOC']},
            4: {'tes': 0},
        }}
        
        fmu.current_time += STEPSIZE
        
        total_dict = {**modelica_input_dict, **soc_dict}
        results.append(total_dict)
    
    print(f'n_inf: {n_inf}')
    df = pd.DataFrame(data=results)
    
    return df
        

if __name__ == '__main__':
    main()
