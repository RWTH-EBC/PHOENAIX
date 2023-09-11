import json
import time
from pathlib import Path

import pandas as pd
from core.utils.fiware_utils import clean_up
from config.definitions import ROOT_DIR
from core.data_models import Attribute
from core.data_models import Device
from core.machine_learning.autogluon import AutoGluonForecaster
import threading
from config.logger import setup_logger



class Building(Device):
    def __init__(self, load_path, building_number, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # initialize interactive attributes
        self.electricityConsumption = Attribute(
            device=self,
            name="electricityConsumption",
            initial_value=None
        )

        electricity_consumption_data = pd.read_csv(load_path, index_col=0, parse_dates=True)

        _timestamp_vals_tuples = list(electricity_consumption_data[str(building_number)].items())
        self.electricityConsumption_data = [(i.strftime('%Y-%m-%dT%H:%M:%S'), j) for i, j in _timestamp_vals_tuples]
        self.timeStamp = None
        self.timesteps_month = 24 * 4 * 30
        #self.timesteps_month = 100
        self.current_timestep = 0
        self.ml_model = AutoGluonForecaster()
        self.logger = setup_logger()
        self.successful_training = False

    def run(self):
        while True:
            self.forecast()
            self.electricityConsumption.push(timestamp=self.timeStamp)
            self.current_timestep += 1

            # To speed up process until necessary training data is in crate DB
            if self.current_timestep < self.timesteps_month - 10:
                continue

            if not self.successful_training:
                self.logger.debug('Trying to train ml model')
                self._try_training_ml_model()

            if not self.ml_model.trained:
                time.sleep(2)
                continue

            self.do_mpc_step()
            self.logger.debug('MODEL IS TRAINED')
            time.sleep(2)

    def transform_ql_dataframe(self,
                               df: pd.DataFrame):
        df_use = df.copy()
        df_use.columns = df_use.columns.droplevel([0, 1])
        df_use = df_use.reset_index()
        df_use = df_use.rename({'datetime': 'timestamp'}, axis=1)
        df_use['timestamp'] = pd.to_datetime(df_use['timestamp'])
        df_use['timestamp'] = df_use['timestamp'].dt.tz_localize(None)
        df_use = df_use[['timestamp', 'electricityConsumption']]
        df_use = df_use.dropna()
        return df_use

    def do_mpc_step(self):
        # Here the mpc step will be done, for now only the prediction of the model will be done
        # TODO: more intelligent error handling, because quantum leap seems to give errors often
        try:
            current_past_data = self.electricityConsumption.pull_history(last_n=10).to_pandas()
        except:
            self.logger.debug('Error when retrieving data')
            return

        df_use = self.transform_ql_dataframe(current_past_data)
        prediction = self.ml_model.predict_model(df_use)
        print(prediction['mean'].to_numpy())


    def _try_training_ml_model(self):
        # TODO: more intelligent error handling, because quantum leap seems to give errors often
        try:
            current_past_data = self.electricityConsumption.pull_history(last_n=self.timesteps_month).to_pandas()
        except:
            self.logger.debug('Error when retrieving data')

            current_past_data = pd.DataFrame()

        if current_past_data.shape[0] < self.timesteps_month:
            self.logger.debug(f'Current datapoints: {current_past_data.shape[0]} --> Too few to train')
            return

        self.logger.debug(f'Current datapoints: {current_past_data.shape[0]} --> Starting training')
        self.logger.debug('Training model')

        df_use = self.transform_ql_dataframe(current_past_data)
        self.successful_training = True
        self.ml_model.train_on_thread(training_data=df_use,
                                      target_variable='electricityConsumption',
                                      prediction_horizon=48)

    def forecast(self):
        """
        This function represent the algorithm that should be done in each time step

        Args:

        Returns:
            None
        """
        _time_stamp, value = self.electricityConsumption_data.pop()
        self.electricityConsumption.value = value
        self.timeStamp = _time_stamp


if __name__ == '__main__':
    with open("./schema/Building.json") as f:
        data_model = json.load(f)

    clean_up()
    load_data_path = Path(ROOT_DIR) / 'data' / \
                     '01_input' / '02_electric_loadprofiles_HTW' / \
                     'el_loadprofiles_HTW_processed.csv'
    building_number = 0
    building = Building(
        entity_id="Building:DEQ:MVP:000",
        entity_type="Building",
        building_number=building_number,
        data_model=data_model,
        save_history=True,
        load_path=load_data_path
    )
    building.run_in_thread()
