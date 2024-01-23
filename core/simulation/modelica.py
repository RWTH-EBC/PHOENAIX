from pathlib import Path
import sys
p = str(Path(__file__).parents[2])
if p not in sys.path:
    sys.path.insert(0, p)
import gurobipy as gp
import os
import json
from pprint import pprint
import pandas as pd
from config.definitions import ROOT_DIR
from core.settings import settings
from core.data_models import Device, Attribute
from core.utils.setup_logger import setup_logger
from core.utils.fiware_utils import clean_up
from requests.exceptions import HTTPError
import traceback
import time
from .fmu_handler import FMUHandler


class ModelicaAgent(Device):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        fmu_path = Path(__file__).parents[2] / 'data' / '01_input' / '05_fmu' / 'DEQ_MVP_FMU.fmu'

        self.fmu = FMUHandler(fmu_path=fmu_path,
                         step_size=settings.TIMESTEP)
        self.fmu.initialize()

        self.attr_translation = {
            'haus_1.SOC': 'SOC1',
            'haus_2.SOC': 'SOC2',
            'haus_3.SOC': 'SOC3'
        }
        
        self.logger = setup_logger(name=kwargs['entity_id'])
        
        self.attributes = {}
        for name in ['thermalDemand0',
                     'thermalDemand1',
                     'thermalDemand2',
                     'thermalDemand3',
                     'thermalDemand4',
                     'SOC1',
                     'SOC2',
                     'SOC3']:
            self.attributes[name] = Attribute(
                device=self,
                name=name,
                initial_value=None
            )
            
    def get_input_dict_from_fiware(self):
        input_dict = {}
        for building_ix in range(5):
            entity_id = f'BuildingEnergyForecast:DEQ:MVP:{"{:03}".format(building_ix)}'
            attrs = self.cb_client.get_entity_attributes(entity_id=entity_id,
                                                         response_format='keyValues')

            input_dict[f'thermalDemand{building_ix}'] = attrs['heatingDemand'][0]
        
        mpc_id = 'MPC:DEQ:MVP:000'
        for name in ['relativePower1',
                     'relativePower2',
                     'relativePower3']:
            attr_value = self.cb_client.get_attribute_value(entity_id=mpc_id,
                                                       attr_name=name)
            
            input_dict[name] = attr_value

        return input_dict


        try:
            raise HTTPError
            self.logger.info('Got SOC init from fiware')
        except HTTPError:
            self.logger.warning('Couldnt get SOC_init, using default')
            return None
            
    def run(self):
        while True:
            _start = time.perf_counter()
            try:
                input_dict = self.get_input_dict_from_fiware()
                self.logger.info('Got input successfully')
            except HTTPError as e:
                error_message = str(e)
                stack_trace = traceback.format_exc()
                self.logger.error(f"OperationalError occurred: {error_message}\nStack Trace:\n{stack_trace}")
                time.sleep(2 - (time.perf_counter() - _start))
                continue
            
            self.fmu.do_step(input_dict)
            
            for modelica_variable in self.attr_translation:
            
                soc = self.fmu.get_value(modelica_variable) / 3600
                attr = self.attributes[self.attr_translation[modelica_variable]]
                attr.value = soc
                attr.push()
                
            for name in ['thermalDemand0',
                     'thermalDemand1',
                     'thermalDemand2',
                     'thermalDemand3',
                     'thermalDemand4']:
                attr = self.attributes[name]
                attr.value = input_dict[name]
                attr.push()
                
            self.logger.info('Push of attributes succesful')
            self.fmu.current_time += settings.TIMESTEP
            
            _time = time.perf_counter() - _start
            time.sleep(2-_time)
            

if __name__ == '__main__':
    #clean_up()
    schema_path = Path(__file__).parents[1] / 'data_models' /\
        'schema' / 'ModelicaAgent.json'
    with open(schema_path) as f:
        data_model = json.load(f)
    mpc = ModelicaAgent(
        entity_id='ModelicaAgent:DEQ:MVP:000',
        entity_type='ModelicaAgent',
        data_model=data_model,
        save_history=True        
    )
    mpc.run()
