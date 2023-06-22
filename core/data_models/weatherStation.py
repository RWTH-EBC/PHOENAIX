import json

from core.data_models import Device
import pandas as pd
import time
from core.data_models import Attribute


class WeatherStation(Device):
    def __init__(self, weather_data_path, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # initialize interactive attributes
        self.temperature = Attribute(
            device=self,
            name="temperature",
            initial_value=None
        )
        self.cloudCover = Attribute(
            device=self,
            name="cloudCover",
            initial_value=None
        )
        self.solarDirectRadiation = Attribute(
            device=self,
            name="solarDirectRadiation",
            initial_value=None
        )
        self.solarDiffuseRadiation = Attribute(
            device=self,
            name="solarDiffuseRadiation",
            initial_value=None
        )

        # load weather data
        weather_data = pd.read_csv(weather_data_path)
        self.solarDirectRadiation_data = list(weather_data["DirNormRad"].values)
        self.solarDiffuseRadiation_data = list(weather_data["DiffHorRad"].values)
        self.cloudCover_data = list(weather_data["TotalSkyCover"].values)
        self.temperature_data = list(weather_data["DryBulbTemp"].values)

    def run(self):
        while True:
            time.sleep(2)
            print("read from cloud:")
            # ONLY FOR DEMONSTRATION
            # here it does not need to read the latest temperature from FIWARE
            self.temperature.pull()

            # do your calculation/analysis/etc.
            self.forecast()

            # send output data to FIWARE
            # self.write_attrs()
            print("write to cloud:")
            self.solarDirectRadiation.push()
            self.solarDiffuseRadiation.push()
            self.cloudCover.push()
            self.temperature.push()

    def forecast(self):
        """
        This function represent the algorithm that should be done in each time step

        Args:

        Returns:
            None
        """
        # ONLY FOR DEMONSTRATION:
            # how to access the current attribute value
        temperature = self.temperature.value

        # lunch the algorithm
        # assume that here you calculate
        self.temperature.value = self.temperature_data.pop()
        self.solarDirectRadiation.value = self.solarDirectRadiation_data.pop()
        self.solarDiffuseRadiation.value = self.solarDiffuseRadiation_data.pop()
        self.cloudCover.value = self.cloudCover_data.pop()


if __name__ == '__main__':
    with open("./schema/WeatherStation.json") as f:
        data_model = json.load(f)
    weather_station = WeatherStation(
        entity_id="WeatherStation:DEQ:MVP:001",
        entity_type="WeatherStation",
        data_model=data_model,
        weather_data_path="D:\Git\deq_demonstrator\\data\\01_input\\01_weather\\DWD_Wetterdaten_Aachen_2018-2020.csv"
    )
    weather_station.run()
