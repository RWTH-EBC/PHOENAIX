from pathlib import Path
import json
import copy
from core.forecasts.buildingEnergyForecast import BuildingEnergyForecast
from core.optimizer.mpc import MPC
from core.simulation.modelica import ModelicaAgent
from tqdm import tqdm
import pandas as pd
import copy

def main():
    schema_path = Path.cwd() / 'core' / 'data_models' /\
        'schema' / 'BuildingEnergyForecast.json'
    with open(schema_path) as f:
        data_model = json.load(f)

    building_forecasts = {}
    for building_ix in range(5):
        
        entity_id = f'BuildingEnergyForecast:DEQ:MVP:{"{:03}".format(building_ix)}'
        building_energy_forecast = BuildingEnergyForecast(
            entity_id=entity_id,
            entity_type="BuildingEnergyForecast",
            building_ix=building_ix,
            offline_modus=True,
            data_model=copy.deepcopy(data_model)  # necessary because id gets popped from data_model. TODO change that in json schema to fiware converter
        )
        building_forecasts[building_ix] = building_energy_forecast
        
    schema_path = Path.cwd() / 'core' / 'data_models' /\
        'schema' / 'MPC.json'
    with open(schema_path) as f:
        data_model = json.load(f)
    mpc = MPC(
        entity_id='MPC:DEQ:MVP:000',
        entity_type='MPC',
        data_model=data_model,
        offline_modus=True  
    )

    schema_path = Path.cwd() / 'core' / 'data_models' /\
        'schema' / 'ModelicaAgent.json'
    with open(schema_path) as f:
        data_model = json.load(f)
    modelica = ModelicaAgent(
        entity_id='ModelicaAgent:DEQ:MVP:000',
        entity_type='ModelicaAgent',
        data_model=data_model,
        offline_modus=True      
    )
    
    STEPS = 8200
    modelica_results = None
    soc_init = None
    n_inf = 0
    results = []
    #STEPS = 5
    for _ in tqdm(range(STEPS)):
        
        input_dict_mpc = {}
        building_pred = {}
        for ix, forecast in building_forecasts.items():
            if modelica_results is None:
                prev_input = None
            else:
                prev_input = {}
                thermal_name = f'thermalDemand{ix}_prev'
                prev_input[thermal_name] = modelica_results[thermal_name]
                prev_input['sinTime'] = modelica_results['sinTime']
            
            ff = forecast.predict(prev_input=prev_input)
            
            
        
            for attr, values in ff.items():
                translation = mpc.attr_translation[attr]
                if translation not in input_dict_mpc:
                    input_dict_mpc[translation] = {}
                
                input_dict_mpc[translation][ix] = values

        mpc_results = mpc.predict(input_dict=input_dict_mpc,
                                soc_init=soc_init)
        
        input_modelica_keys = ['relativePower1',
                        'relativePower2',
                        'relativePower3']
        
        if mpc_results is None:
            n_inf += 1
            input_modelica = {key: 0 for key in input_modelica_keys}
        else:
            input_modelica = {key: mpc_results[key] for key in input_modelica_keys}

        modelica_results = modelica.do_step(input_modelica)
        res = {**modelica_results, **input_modelica}
        results.append(copy.deepcopy(res))
        soc_init = {'soc': {
            0: {'tes': 0},
            1: {'tes': modelica_results['SOC1']},
            2: {'tes': modelica_results['SOC2']},
            3: {'tes': modelica_results['SOC3']},
            4: {'tes': 0},
        }}
        
    df = pd.DataFrame(results)
    
    df.to_csv('temp.csv')

if __name__ == '__main__':
    main()