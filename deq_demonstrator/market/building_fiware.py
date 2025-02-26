from typing_extensions import override
import paho.mqtt.client as mqtt
import time
from datetime import datetime

from local_energy_market.classes import Building, ResultHandler
from deq_demonstrator.market.market_agent_fiware import MarketAgentFiware
from deq_demonstrator.data_models import Device
from deq_demonstrator.settings import settings

class BuildingFiware(Building, Device):
    def __init__(self, building_id: int, nodes: dict, *args, **kwargs):
        result_handler = ResultHandler(file_name=f"{datetime.now().strftime('%m-%d_%H-%M-%S')}_building_{building_id}")
        Building.__init__(self, building_id=building_id, nodes=nodes, result_handler=result_handler)
        Device.__init__(self,*args, **kwargs)

        self.market_agent = MarketAgentFiware(agent_id=building_id, building=self, result_handler=result_handler, *args, **kwargs)

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)
        self.topic = f"/building/#"
        self.stop_event = kwargs.get("stop_event", None)


    #@override
    #def calculate_forecast(self) -> None:
    #    forecast_entities = self.cb_client.get_entity_list(type_pattern="BuildingEnergyForecast")
    #    pass

    def on_connect(self, client, userdata, flags, rc) -> None:
        print(f"Connected with result code {rc}")
        client.subscribe(self.topic)
        print(f"Subscribed to topic {self.topic}")

    def on_message(self, client, userdata, message) -> None:
        if message.topic == "/building/calculate_forecast":
            print(f"Building {self.building_id}: Received message to calculate forecast")
            self.calculate_forecast()
            print(f"Building {self.building_id}: Forecast calculated")
            client.publish(topic="/notification/forecast", payload=f"{self.building_id}")
        elif message.topic == "/building/optimize":
            print(f"Building {self.building_id}: Received message to optimize")
            self.run_optimization()
            print(f"Building {self.building_id}: Optimization done")
            client.publish(topic="/notification/optimize", payload=f"{self.building_id}")
        elif message.topic == "/building/prepare":
            print(f"Building {self.building_id}: Received message to prepare")
            self.update_and_prepare_for_next_opti_step()
            print(f"Building {self.building_id}: Building prepared")
            client.publish(topic="/notification/prepared", payload=f"{self.building_id}")


    def run(self):
        self.mqtt_client.loop_start()
        self.market_agent.mqtt_client.loop_start()

        while not self.stop_event.is_set():
            time.sleep(1)
        self.mqtt_client.loop_stop()
        self.market_agent.mqtt_client.loop_stop()

        if self.stop_event is not None:
            self.mqtt_client.loop_start()
            self.market_agent.mqtt_client.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client.loop_stop()
            self.market_agent.mqtt_client.loop_stop()

        else:
            self.mqtt_client.loop_forever()
            self.market_agent.mqtt_client.loop_forever()