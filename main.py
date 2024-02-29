import json
from core.forecasts.buildingEnergyForecast import BuildingEnergyForecast
from core.optimizer.mpc import MPC
from core.simulation.modelica import ModelicaAgent
from pathlib import Path
from core.utils.fiware_utils import clean_up
import copy
import logging
import threading
import threading

#logging.basicConfig(level=logging.WARNING)

def run_forecasts(building_ix):
def run_forecasts(building_ix):
    schema_path = Path(__file__).parents[0] / 'core' / 'data_models' /\
        'schema' / 'BuildingEnergyForecast.json'
    with open(schema_path) as f:
        data_model = json.load(f)

    entity_id = f'BuildingEnergyForecast:DEQ:MVP:{"{:03}".format(building_ix)}'
    building_energy_forecast = BuildingEnergyForecast(
        entity_id=entity_id,
        entity_type="BuildingEnergyForecast",
        building_ix=building_ix,
        data_model=copy.deepcopy(data_model)  # necessary because id gets popped from data_model. TODO change that in json schema to fiware converter
    )
    building_energy_forecast.logger.setLevel(logging.INFO)
    building_energy_forecast.run()
        
def run_mpc():

    entity_id = f'BuildingEnergyForecast:DEQ:MVP:{"{:03}".format(building_ix)}'
    building_energy_forecast = BuildingEnergyForecast(
        entity_id=entity_id,
        entity_type="BuildingEnergyForecast",
        building_ix=building_ix,
        data_model=copy.deepcopy(data_model)  # necessary because id gets popped from data_model. TODO change that in json schema to fiware converter
    )
    building_energy_forecast.logger.setLevel(logging.INFO)
    building_energy_forecast.run()
        
def run_mpc():
    schema_path = Path(__file__).parents[0] / 'core' / 'data_models' /\
        'schema' / 'MPC.json'
    with open(schema_path) as f:
        data_model = json.load(f)
    mpc = MPC(
        entity_id='MPC:DEQ:MVP:000',
        entity_type='MPC',
        data_model=data_model,
        save_history=True        
    )
    mpc.run()
    mpc.run()
    

def run_modelica():

def run_modelica():
    schema_path = Path(__file__).parents[0] / 'core' / 'data_models' /\
        'schema' / 'ModelicaAgent.json'
    with open(schema_path) as f:
        data_model = json.load(f)
    modelica = ModelicaAgent(
        entity_id='ModelicaAgent:DEQ:MVP:000',
        entity_type='ModelicaAgent',
        data_model=data_model,
        save_history=True        
    )
    modelica.run()

def main():
    clean_up()
    
    for building_ix in range(5):
        threading.Thread(target=run_forecasts, args=[building_ix]).start()
        

    threading.Thread(target=run_mpc).start()
    threading.Thread(target=run_modelica).start()
    
    
if __name__ == '__main__':
    main()