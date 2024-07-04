from pathlib import Path
from deq_demonstrator.machine_learning.heat_demand_forecast import HeatingDemandLearner
import numpy as np
import paho.mqtt.client as mqtt
from deq_demonstrator.machine_learning.heat_demand_forecast import HeatingDemandLearner
import json
import pandas as pd
import time
from deq_demonstrator.utils.load_demands import load_demands_and_pv
from deq_demonstrator.settings import settings
from deq_demonstrator.utils.setup_logger import setup_logger
from deq_demonstrator.data_models import Attribute
from deq_demonstrator.data_models import Device
from deq_demonstrator.config import ROOT_DIR
from ebcpy import TimeSeriesData


class BuildingEnergyForecast(Device):
    def __init__(self,
                 building_ix: int,
                 offline_modus: bool = False,
                 *args,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.offline_modus = offline_modus

        if not self.offline_modus:
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
        self.predictor = HeatingDemandLearner(building_ix=self.building_ix)
        self.predictor.get_model(n_horizon=self.n_horizon)
        self.logger.info('Heat Predictor learned')

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
        
        self.stop_event = kwargs.get('stop_event', None)

        assert self.attribute_df_dict.keys() == self.attribute_name_dict.keys()

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        # Subscribe to the /predict topic
        client.subscribe(self.topic)
        print(f'Subscribed to topic {self.topic}')

    def on_message(self, client, userdata, msg):
        if msg.topic != self.topic:
            return
        self.predict()

    def predict(self,
                prev_input=None):
        if not self.offline_modus:

            prev = self.cb_client.get_entity_attributes(entity_id='ModelicaAgent:DEQ:MVP:000',
                                                        response_format='keyValues')

            prev_heating = prev[f'thermalDemand{self.building_ix}_prev']
            sin_time = prev['sinTime']
        else:
            if prev_input is None:
                prev_heating = None
                sin_time = None
            else:
                prev_heating = prev_input[f'thermalDemand{self.building_ix}_prev']
                sin_time = prev_input['sinTime']

        if any(i is None for i in [prev_heating, sin_time]):
            data = None
        else:
            prev_heating_rev = list(reversed(prev_heating))
            prev_sin_rev = list(reversed(sin_time))
            current_sin = [prev_sin_rev[0] + 1]
            data = prev_heating_rev + current_sin + prev_sin_rev
            data.append(1)

        columns1 = [f'heating_{self.building_ix}//{n+1}' for n in range(3)]
        columns2 = ['sin'] + [f'sin//{n+1}' for n in range(3)]
        columns = columns1 + columns2 + ['ones']

        if data is None:
            data = [np.nan] * len(columns)
        data = dict(zip(columns, data))

        df = pd.DataFrame([data])

        tsd = TimeSeriesData(df)
        tsd.fillna(value=np.nan, inplace=True)

        y_hat = self.predictor.predict_n_steps(input_tsd=tsd)

        if np.isnan(y_hat).any():
            self.logger.warning('NaNs in array. Filling with 0')
            y_hat = np.nan_to_num(y_hat)

        y_hat[y_hat < 0] = 0
        data_this_step = self.load_demands_and_pv.iloc[self.ix: self.ix+self.n_horizon]

        offline_dict = {}
        for attr_name, column in self.attribute_df_dict.items():
            if attr_name == 'heatingDemand':
                attr_values = list(y_hat.flatten())
            else:
                attr_values = data_this_step[column].to_list()

            offline_dict[attr_name] = attr_values

            attr = self.attribute_name_dict[attr_name]
            attr.value = attr_values
            if not self.offline_modus:
                attr.push()
        if not self.offline_modus:
            self.logger.info('Push successfull')

        payload = {'building_id': self.building_ix,
                   'current_ix': self.ix}
        self.mqtt_client.publish('/predicted',
                                 payload=json.dumps(payload))

        self.ix += 1
        if self.ix > self.max_n:
            self.ix = 0

        return offline_dict

    def run(self):
        if self.offline_modus:
            self.logger.error(
                'You cant run this, if it is set to be in offline modus!')
            return
        
        if self.stop_event is not None:
            self.mqtt_client.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client.loop_stop()

        else:
            self.mqtt_client.loop_forever()


if __name__ == '__main__':
    # clean_up()
    # clean_up()
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
