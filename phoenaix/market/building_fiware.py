import paho.mqtt.client as mqtt
import time
from datetime import datetime
from local_energy_market.classes import Building, ResultHandler
from phoenaix.market.market_agent_fiware import MarketAgentFiware
from phoenaix.data_models import Device
from phoenaix.settings import settings
from phoenaix.utils.setup_logger import setup_logger


class BuildingFiware(Building, Device):
    """
    Building class that implements the Building class from the local_energy_market package.
    """
    def __init__(self, building_id: int, nodes: dict, *args, **kwargs):
        self.stop_event = kwargs.get("stop_event", None)

        self.logger = setup_logger(name=f"BuildingFiware {building_id}", cd=None, level="DEBUG")

        # create the result handler to store the result locally
        result_handler = ResultHandler(file_name=f"{datetime.now().strftime('%m-%d_%H-%M-%S')}_building_{building_id}")
        # initialize the building from the local_energy_market package
        Building.__init__(self, building_id=building_id, nodes=nodes, result_handler=result_handler,
                          start_opti_step=2160)  # TODO: use the start_opti_step from the settings
        # initialize the device
        Device.__init__(self, *args, **kwargs)

        # create the market agent for the building
        self.market_agent = MarketAgentFiware(agent_id=building_id, building=self, result_handler=result_handler,
                                              *args, **kwargs)

        # TODO: use the device class for the clients
        self.mqtt_client = mqtt.Client()
        self.topic = f"/building/#"
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)

    def on_connect(self, client, userdata, flags, rc) -> None:
        self.logger.info(f"Connected with result code {rc}")
        client.subscribe(self.topic)
        self.logger.info(f"Subscribed to topic {self.topic}")

    def on_message(self, client, userdata, message) -> None:
        match message.topic:
            case "/building/calculate_forecast":
                self.logger.debug(f"Building {self.building_id}: Received message to calculate forecast")
                self.calculate_forecast()
                self.logger.debug(f"Building {self.building_id}: Forecast calculated")
                client.publish(topic="/notification/forecast", payload=f"{self.building_id}")
            case "/building/optimize":
                self.logger.debug(f"Building {self.building_id}: Received message to optimize")
                self.run_optimization()
                self.trigger_bid_creation()
                self.logger.debug(f"Building {self.building_id}: Optimization done and bid created.")
                client.publish(topic="/notification/optimize", payload=f"{self.building_id}")
            case "/building/prepare":
                self.logger.debug(f"Building {self.building_id}: Received message to prepare")
                self.update_and_prepare_for_next_opti_step()
                self.logger.debug(f"Building {self.building_id}: Building prepared")
                client.publish(topic="/notification/prepared", payload=f"{self.building_id}")
            case _:
                self.logger.warning(f"Building {self.building_id}: Received message on unknown topic {message.topic}")

    def run(self):
        """
        Run the MQTT client of the building and the market agent.
        """
        # TODO: maybe use threads?
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
