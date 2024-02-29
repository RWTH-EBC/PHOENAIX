from pathlib import Path
import sys
p = str(Path(__file__).parents[2])
if p not in sys.path:
    sys.path.insert(0, p)
import gurobipy as gp
import os
import json
from pprint import pprint
import numpy as np
import numpy as np
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
import paho.mqtt.client as mqtt
from core.utils.load_demands import load_demands_and_pv


class ModelicaAgent(Device):
    def __init__(self, 
                 offline_modus: bool = False,
                 *args, 
                 **kwargs):
        super().__init__(*args, **kwargs)

        fmu_path = Path(__file__).parents[2] / 'data' / '01_input' / '05_fmu' / 'DEQ_MVP_FMU.fmu'
        self.offline_modus = offline_modus
        self.fmu = FMUHandler(fmu_path=fmu_path,
                         step_size=settings.TIMESTEP)
        self.fmu.initialize()
        
        if not self.offline_modus: 
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_message = self.on_message
            self.mqtt_client.connect(host=settings.MQTT_HOST,
                                    port=settings.MQTT_PORT)
        self.topic = '/fmu'
        
        self.actual_data = load_demands_and_pv().iloc[::4].copy()
        self.max_n = self.actual_data.shape[0]
        self.n = 0

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
            
            self.attributes[f'{name}_prev'] = Attribute(
                device=self,
                name=f'{name}_prev',
                initial_value=[None, None, None],
                is_array=True
            )
            
        self.attributes['sinTime'] = Attribute(
            device=self,
            name='sinTime',
            initial_value=[None, None, None],
            is_array=True
        )

    
            
        self.attributes[f'{name}_prev'] = Attribute(
                device=self,
                name=f'{name}_prev',
                initial_value=[None, None, None],
                is_array=True
            )
            
        self.attributes['sinTime'] = Attribute(
            device=self,
            name='sinTime',
            initial_value=[None, None, None],
            is_array=True
        )

        self.current_time = time.perf_counter()
            
    def get_input_dict_from_fiware(self):
        input_dict = {}
        
        mpc_id = 'MPC:DEQ:MVP:000'
        for name in ['relativePower1',
                     'relativePower2',
                     'relativePower3']:
            attr_value = self.cb_client.get_attribute_value(entity_id=mpc_id,
                                                       attr_name=name)
            
            input_dict[name] = attr_value
        return input_dict
    
    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected {self.__class__.__name__} with result code "+str(rc))
        # Subscribe to the /predict topic
        client.subscribe(self.topic)
        
    def on_message(self, client, userdata, msg):
        if msg.topic != self.topic:
            return
        self.do_step()
        
    def run(self):
        self.mqtt_client.loop_forever()
        
    def _shift_values(self, values, value):
        values[:-1] = values[1:]
        values[-1] = value
        
        return values
    
    def _online_pre_do_step(self):
        try:
            input_dict = self.get_input_dict_from_fiware()
            self.logger.info('Got input successfully')
        except HTTPError as e:
            error_message = str(e)
            stack_trace = traceback.format_exc()
            self.logger.error(f"OperationalError occurred: {error_message}\nStack Trace:\n{stack_trace}")
            time.sleep(settings.CYCLE_TIME - (time.perf_counter() - self.current_time))
            self.current_time = time.perf_counter()
            self.mqtt_client.publish('/mpc')
            return
        
        return input_dict

        

            
    def do_step(self,
                input_dict: dict = None):
        if not self.offline_modus:
            input_dict = self._online_pre_do_step()
        
        for building_ix in range(5):
            heat_demand = self.actual_data.iloc[self.n][('heating', building_ix)]
            input_dict[f'thermalDemand{building_ix}'] = heat_demand
            
        self.fmu.do_step(input_dict)
        
        offline_dict = {}
        for modelica_variable in self.attr_translation:
        
            soc = self.fmu.get_value(modelica_variable) / 3600
            attr = self.attributes[self.attr_translation[modelica_variable]]
            
            offline_dict[self.attr_translation[modelica_variable]] = soc
            attr.value = soc
            if not self.offline_modus:
                attr.push()
        
        for name in ['thermalDemand0',
                    'thermalDemand1',
                    'thermalDemand2',
                    'thermalDemand3',
                    'thermalDemand4']:
            attr = self.attributes[name]
            attr.value = input_dict[name]
            offline_dict[name] = input_dict[name]
            if not self.offline_modus:
                attr.push()
            
            prev_name = f'{name}_prev'
            attr_prev = self.attributes[prev_name]
            values = self._shift_values(attr_prev.value, attr.value)
            offline_dict[prev_name] = values
            attr_prev.value = values        
            if not self.offline_modus:    
                attr_prev.push()
            
        attr = self.attributes['sinTime']

        values = self._shift_values(attr.value, self.n % 24)
        
        attr.value = values
        offline_dict['sinTime'] = values
        
        if not self.offline_modus:
            attr.push()
            self.logger.info('Push of attributes succesful')
            
        self.fmu.current_time += settings.TIMESTEP
        self.n += 1
        if self.offline_modus:
            return offline_dict
        
        ct = time.perf_counter() 
        sleep_time = (settings.CYCLE_TIME - (ct - self.current_time))
        
        if sleep_time < 0:
            self.logger.warning(f'Negative sleep time {sleep_time} --> adjust cycle time')
        else:
            time.sleep(sleep_time)
        self.current_time = ct
        self.n += 1
        self.mqtt_client.publish('/mpc')
            

if __name__ == '__main__':
    clean_up()
    clean_up()
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
