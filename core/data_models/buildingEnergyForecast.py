import json
import time
from pathlib import Path

import pandas as pd

from config.definitions import ROOT_DIR
from core.data_models import Attribute
from core.data_models import Device


class DummyModel:
    def __init__(self):
        pass

    def forecast(self,
                 input_df):

        output_df = input_df.iloc[-10:].copy()
        output_df += 100
        return output_df

%##
class BuildingEnergyForecast(Device):
    def __init__(self, building_id, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.building_id = building_id
        self.ml_model = DummyModel()

        # initialize interactive attributes
        self.electricityDemand = Attribute(
            device=self,
            name="electricityDemand",
            initial_value=None
        )

    def run(self):
        while True:
            time.sleep(2)
            print("read from cloud")
            # ONLY FOR DEMONSTRATION
            # here it does not need to read the latest temperature from FIWARE
            self.electricityDemand.pull()
            print(f"Get last value of electricity_consumption: "
                  f"{self.electricityDemand.value}")

            # do your calculation/analysis/etc.
            self.forecast()
            self.electricityDemand.push()

    def _create_dummy_df(self,
                         value):
        data = [value] * 168
        df = pd.DataFrame(data, columns=["0"])
        return df

    def get_current_building_data(self):
        previous_electricity_demand = self.cb_client.get_attribute_value(
            entity_id=self.building_id,
            entity_type='Building',
            attr_name='electricityConsumption'
        )

        df = self._create_dummy_df(previous_electricity_demand)
        return df

    def forecast(self):
        """
        This function represent the algorithm that should be done in each time step

        Args:

        Returns:
            None
        """

        input_df = self.get_current_building_data()

        output_df = self.ml_model.forecast(input_df)
        forecast_values = output_df.to_numpy().flatten()
        self.electricityDemand.value = list(forecast_values)

if __name__ == '__main__':
    with open("./schema/BuildingEnergyForecast.json") as f:
        data_model = json.load(f)

    building_energy_forecast = BuildingEnergyForecast(
        entity_id="BuildingEnergyForecast:DEQ:MVP:000",
        entity_type="BuildingEnergyForecast",
        building_id="Building:DEQ:MVP:000",
        data_model=data_model,
    )
    building_energy_forecast.run()
