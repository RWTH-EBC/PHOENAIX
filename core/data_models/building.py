import json
import time
from pathlib import Path

import pandas as pd

from config.definitions import ROOT_DIR
from core.data_models import Attribute
from core.data_models import Device
import threading


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

        self.electricityConsumption_data = list(
            electricity_consumption_data[str(building_number)].values)

    def run(self):
        while True:
            time.sleep(2)
            print("read from cloud")
            # ONLY FOR DEMONSTRATION
            # here it does not need to read the latest temperature from FIWARE
            self.electricityConsumption.pull()
            print(f"Get last value of electricity_consumption: "
                  f"{self.electricityConsumption.value}")

            # do your calculation/analysis/etc.
            self.forecast()

            self.electricityConsumption.push()
            print(f"Write next value of temperature: "
                  f"{self.electricityConsumption.value}")

    def forecast(self):
        """
        This function represent the algorithm that should be done in each time step

        Args:

        Returns:
            None
        """
        # ONLY FOR DEMONSTRATION:
        # how to access the current attribute value if you need any inputs
        electricity_consumption = self.electricityConsumption.value

        # lunch the algorithm
        # assume that here you calculate
        self.electricityConsumption.value = self.electricityConsumption_data.pop()


if __name__ == '__main__':
    with open("./schema/Building.json") as f:
        data_model = json.load(f)

    load_data_path = Path(ROOT_DIR) / 'data' / \
                     '01_input' / '02_electric_loadprofiles_HTW' / \
                     'el_loadprofiles_HTW_processed.csv'
    building_number = 0
    building = Building(
        entity_id="Building:DEQ:MVP:000",
        entity_type="Building",
        building_number=building_number,
        data_model=data_model,
        # TODO change it if not work
        load_path=load_data_path
    )
    building.run_in_thread()
