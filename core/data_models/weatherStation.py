import json
from core.utils.fiware_utils import clean_up
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
        weather_data = pd.read_csv(weather_data_path, index_col=0)
        self.timeStamp_data = list(weather_data.index)
        self.timeStamp = self.timeStamp_data[0]
        self.solarDirectRadiation_data = list(weather_data["DirNormRad"].values)
        self.solarDiffuseRadiation_data = list(weather_data["DiffHorRad"].values)
        self.cloudCover_data = list(weather_data["TotalSkyCover"].values)
        self.temperature_data = list(weather_data["DryBulbTemp"].values)

    def run(self):
        while True:
            time.sleep(2)
            print("read from cloud")
            # ONLY FOR DEMONSTRATION
            # here it does not need to read the latest temperature from FIWARE
            self.temperature.pull()
            print(f"Get last value of temperature: {self.temperature.value}")

            # do your calculation/analysis/etc.
            self.forecast()

            # send output data to FIWARE
            # self.write_attrs()
            print("write to cloud")
            self.solarDirectRadiation.push(timestamp=self.timeStamp)
            self.solarDiffuseRadiation.push(timestamp=self.timeStamp)
            self.cloudCover.push(timestamp=self.timeStamp)
            self.temperature.push(timestamp=self.timeStamp)
            print(f"Write next value of temperature: {self.temperature.value}")

    def forecast(self):
        """
        This function represent the algorithm that should be done in each time step

        Args:

        Returns:
            None
        """
        # ONLY FOR DEMONSTRATION:
        # how to access the current attribute value if you need any inputs
        temperature = self.temperature.value

        # lunch the algorithm
        # assume that here you calculate
        self.temperature.value = self.temperature_data.pop()
        self.solarDirectRadiation.value = self.solarDirectRadiation_data.pop()
        self.solarDiffuseRadiation.value = self.solarDiffuseRadiation_data.pop()
        self.cloudCover.value = self.cloudCover_data.pop()
        self.timeStamp = self.timeStamp_data.pop().replace(" ", "T")
        print("timestamp: " + self.timeStamp)


if __name__ == '__main__':
    with open("./schema/WeatherStation.json") as f:
        data_model = json.load(f)
    # clean up context broker and time-series
    # database before simulation
    clean_up()
    weather_station = WeatherStation(
        entity_id="WeatherStation:DEQ:MVP:001",
        entity_type="WeatherStation",
        data_model=data_model,
        save_history=True,
        # TODO change it if not work
        weather_data_path="../../data/01_input/01_weather/DWD_Wetterdaten_Aachen_2018-2020.csv"
    )
    weather_station.run_in_thread(daemon=True)
    time.sleep(10)
    temperature_history = weather_station.temperature.pull_history(last_n=100)
