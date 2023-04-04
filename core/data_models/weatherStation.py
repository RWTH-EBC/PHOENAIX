from core.data_models import Device
import time
import threading
import random


class WeatherStation(Device):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # setup entity type (fix the entity type)
        self.entity_type = "WeatherStation"

    def run(self):
        while True:
            time.sleep(2)
            self.read_attrs()
            self.forecast()
            self.write_attrs()

    def run_in_thread(self, *args):
        """Create a new client for the topic"""
        t = threading.Thread(target=self.run, daemon=True, args=args)
        t.start()

    def forecast(self):
        """
        This function represent the algorithm that should be done in each time step

        Args:

        Returns:
            None
        """
        # get the input from platform
        temperature = self.attrs_read["temperature"]
        solarDirectRadiation = self.attrs_read["solarDirectRadiation"]
        solarDiffuseRadiation = self.attrs_read["solarDiffuseRadiation"]
        cloudCover = self.attrs_read["cloudCover"]

        # lunch the algorithm
        temperature += random.uniform(-1, 1)
        solarDirectRadiation += random.uniform(-1, 1)
        solarDiffuseRadiation += random.uniform(-1, 1)
        cloudCover += random.uniform(-1, 1)

        # update the result to attr_write
        self.attrs_write["temperature"] = temperature
        self.attrs_write["solarDirectRadiation"] = solarDirectRadiation
        self.attrs_write["solarDiffuseRadiation"] = solarDiffuseRadiation
        self.attrs_write["cloudCover"] = cloudCover


if __name__ == '__main__':
    weather_station = WeatherStation(entity_id="WeatherStation:001")

