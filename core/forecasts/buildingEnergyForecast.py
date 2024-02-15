from pathlib import Path
import sys
p = str(Path(__file__).parents[2])
if p not in sys.path:
    sys.path.insert(0, p)

import paho.mqtt.client as mqtt
import time
import json
import pandas as pd
from core.utils.fiware_utils import clean_up
from config.definitions import ROOT_DIR
from core.data_models import Attribute
from core.data_models import Device
from core.utils.load_demands import load_demands_and_pv
from core.settings import settings
from core.utils.setup_logger import setup_logger
from requests.exceptions import HTTPError



class BuildingEnergyForecast(Device):
    def __init__(self,
                 building_ix,
                 *args,
                 **kwargs):
        super().__init__(*args, **kwargs)
        
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)
        
        
        self.n_horizon = settings.N_HORIZON
        self.timestep = settings.TIMESTEP
        
        self.building_ix = building_ix
        self.topic = f"/predict{self.building_ix}"

        self.attribute_df_dict = {
            'electricityDemand': ('elec', building_ix),
            'heatingDemand': ('heating', building_ix),
            'coolingDemand': ('cooling', building_ix),
            'dhwDemand': ('dhw', building_ix),
            'pvPower': ('pv_power', building_ix)
        }
        
        self.logger = setup_logger(name=kwargs['entity_id'])
        
        self.ix = 0
                

        # TODO 3600 is at the moment hardcoded as .iloc[::4]
        important_columns = list(self.attribute_df_dict.values())
        self.load_demands_and_pv = load_demands_and_pv()[
            important_columns].iloc[::4].copy()
        
        self.max_n = self.load_demands_and_pv.shape[0]

        # initialize interactive attributes
        self.electricityDemand = Attribute(
            device=self,
            name="electricityDemand",
            initial_value=None
        )
        
        self.heatingDemand = Attribute(
            device=self,
            name="heatingDemand",
            initial_value=None
        )
        
        self.coolingDemand = Attribute(
            device=self,
            name="coolingDemand",
            initial_value=None
        )
        
        self.dhwDemand = Attribute(
            device=self,
            name="dhwDemand",
            initial_value=None
        )
        
        self.pvPower = Attribute(
            device=self,
            name="pvPower",
            initial_value=None
        )
        
        self.attribute_name_dict = {
            'electricityDemand': self.electricityDemand,
            'heatingDemand': self.heatingDemand,
            'coolingDemand': self.coolingDemand,
            'dhwDemand': self.dhwDemand,
            'pvPower': self.pvPower
        }

        assert self.attribute_df_dict.keys() == self.attribute_name_dict.keys()
        
    
    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        # Subscribe to the /predict topic
        client.subscribe(self.topic)
        
    def on_message(self, client, userdata, msg):
        if msg.topic != self.topic:
            return
        
        self.predict()
            
        
    def predict(self):
        data_this_step = self.load_demands_and_pv.iloc[self.ix: self.ix+self.n_horizon]
        
        for attr_name, column in self.attribute_df_dict.items():
            attr_values = data_this_step[column].to_list()
            attr = self.attribute_name_dict[attr_name]
            attr.value = attr_values
            attr.push()

        self.logger.info('Push successfull')
        self.ix += 1
        if self.ix > self.max_n:
            self.ix = 0

    def run(self):
        self.mqtt_client.loop_forever()
        
        
if __name__ == '__main__':
    #clean_up()
    schema_path = Path(__file__).parents[1] / 'data_models' /\
        'schema' / 'BuildingEnergyForecast.json'
    with open(schema_path) as f:
        data_model = json.load(f)

    building_energy_forecast = BuildingEnergyForecast(
        entity_id="BuildingEnergyForecast:DEQ:MVP:000",
        entity_type="BuildingEnergyForecast",
        building_ix=0,
        data_model=data_model,
    )
    
    building_energy_forecast.run_in_thread()
