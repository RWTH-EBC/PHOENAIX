import json
from deq_demonstrator.forecasts.buildingEnergyForecast import BuildingEnergyForecast
from deq_demonstrator.optimizer.mpc import MPC
from deq_demonstrator.simulation.modelica import ModelicaAgent
from pathlib import Path
from deq_demonstrator.utils.fiware_utils import clean_up
from deq_demonstrator.config import ROOT_DIR
import copy
import logging
import threading
import time

def run_forecasts(building_ix, stop_event):
    schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' /\
        'schema' / 'BuildingEnergyForecast.json'
    with open(schema_path) as f:
        data_model = json.load(f)

    entity_id = f'BuildingEnergyForecast:DEQ:MVP:{"{:03}".format(building_ix)}'
    building_energy_forecast = BuildingEnergyForecast(
        entity_id=entity_id,
        entity_type="BuildingEnergyForecast",
        building_ix=building_ix,
        data_model=copy.deepcopy(data_model),# necessary because id gets popped from data_model. TODO change that in json schema to fiware converter,
        stop_event=stop_event
    )
    building_energy_forecast.logger.setLevel(logging.INFO)
    building_energy_forecast.run()
                
def run_mpc(stop_event):
    schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' /\
        'schema' / 'MPC.json'
    with open(schema_path) as f:
        data_model = json.load(f)
    mpc = MPC(
        entity_id='MPC:DEQ:MVP:000',
        entity_type='MPC',
        data_model=data_model,
        save_history=True,
        stop_event=stop_event
    )
    mpc.run()
    

def run_modelica(stop_event):
    schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' /\
        'schema' / 'ModelicaAgent.json'
    with open(schema_path) as f:
        data_model = json.load(f)
    modelica = ModelicaAgent(
        entity_id='ModelicaAgent:DEQ:MVP:000',
        entity_type='ModelicaAgent',
        data_model=data_model,
        save_history=True ,
        stop_event=stop_event       
    )
    modelica.run()

def main():
    clean_up()
    print("Cleaned up")
    stop_event = threading.Event()
    
    threads = []
    for building_ix in range(5):
        t = threading.Thread(target=run_forecasts, args=[building_ix, stop_event])
        threads.append(t)
        t.start()
        
    print("Started building forecasts")

    t = threading.Thread(target=run_mpc, args=[stop_event])
    threads.append(t)
    t.start()
    
    print("Started MPC")
    
    t = threading.Thread(target=run_modelica, args=[stop_event])
    threads.append(t)
    t.start()
    
    print("Started Modelica")
    
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print("KeyboadInterrupt received, stopping threads...")
            stop_event.set()
            break
    
    for t in threads:
        t.join()
        
    print("All threads stopped")
        
        
    
if __name__ == '__main__':
    main()