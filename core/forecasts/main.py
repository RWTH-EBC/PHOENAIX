import json
from buildingEnergyForecast import BuildingEnergyForecast
from pathlib import Path
from core.utils.fiware_utils import clean_up
import copy
import logging

#logging.basicConfig(level=logging.WARNING)

def main():
    clean_up()
    schema_path = Path(__file__).parents[1] / 'data_models' /\
        'schema' / 'BuildingEnergyForecast.json'
    with open(schema_path) as f:
        data_model = json.load(f)
        
    for building_ix in range(5):
        entity_id = f'BuildingEnergyForecast:DEQ:MVP:{"{:03}".format(building_ix)}'
        building_energy_forecast = BuildingEnergyForecast(
            entity_id=entity_id,
            entity_type="BuildingEnergyForecast",
            building_ix=building_ix,
            data_model=copy.deepcopy(data_model)  # necessary because id gets popped from data_model. TODO change that in json schema to fiware converter
        )
        building_energy_forecast.logger.setLevel(logging.WARNING)
        building_energy_forecast.run_in_thread()
    
if __name__ == '__main__':
    main()
    