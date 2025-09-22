import paho.mqtt.client as mqtt
import time
from phoenaix.settings import settings
from phoenaix.utils.setup_logger import setup_logger
import threading
import pickle
from pathlib import Path


class MarketController:
    """
    Market controller class to handle and synchronize the market.
    """

    def __init__(self, building_ids: list[str], *args, **kwargs):

        # read the global stop event used to stop the market and the MQTT clients
        self.stop_event = kwargs.get("stop_event", None)

        # set up the logger
        self.logger = setup_logger(name="MarketController", cd=None, level="INFO")

        # create a MQTT client for the controller to receive the start and stop messages and to send trigger messages
        self.mqtt_client_controller = mqtt.Client()
        self.topic_controller = "/controller/#"
        self.mqtt_client_controller.on_connect = self.on_connect_controller
        self.mqtt_client_controller.on_message = self.on_message_controller
        self.mqtt_client_controller.connect(host=settings.MQTT_HOST,
                                            port=settings.MQTT_PORT)

        # create a second MQTT client to receive notifications
        self.topic_notification_handler = "/notification/#"
        self.mqtt_client_notification_handler = mqtt.Client()
        self.mqtt_client_notification_handler.on_connect = self.on_connect_notification_handler
        self.mqtt_client_notification_handler.on_message = self.on_message_notification_handler
        self.mqtt_client_notification_handler.connect(host=settings.MQTT_HOST,
                                                      port=settings.MQTT_PORT)

        # create events that are used to synchronize the market
        # single events exists once for the whole market, building events exist for each building
        single_events = ["market_running", "negotiation"]
        self.single_events = {event: threading.Event() for event in single_events}
        building_events = ["forecast", "optimization", "bid", "grid", "prepared"]
        self.building_events = {event: {str(building_id): threading.Event() for building_id in building_ids}
                                for event in building_events}

        # define how much time each round should take to simulate real time
        self.time_per_round = 5  # seconds

        self.whole_round_times = []
        self.negotiation_times = []

    def run_market(self):

        # wait until the market is started
        self.single_events["market_running"].wait()
        # loop until the global stop event is set or the market is stopped
        while not self.stop_event.is_set() and self.single_events["market_running"].is_set():
            start_time = time.perf_counter()
            self.logger.info("Starting market cycle.")

            # TODO: implement better way to specify sequence of events

            # send message for buildings to calculate forecasts and wait until each building sent a confirmation that it
            # has finished the calculation
            self.logger.info("Waiting for forecast calculation.")
            self.mqtt_client_controller.publish(topic="/building/calculate_forecast")
            self.wait_for_events(events=self.building_events["forecast"], timeout=None)
            reset_events(events=self.building_events["forecast"])

            # send message for buildings to run optimization and wait for the confirmations
            self.logger.info("Forecast calculated. Waiting for optimization.")
            self.mqtt_client_controller.publish(topic="/building/optimize")
            self.wait_for_events(events=self.building_events["optimization"], timeout=None)
            reset_events(events=self.building_events["optimization"])

            # send message to coordinator to start the negotiation and wait for confirmation to be done
            nego_start_time = time.perf_counter()
            self.logger.info("Optimization done. Waiting for negotiation.")
            self.mqtt_client_controller.publish("/coordinator/negotiation")
            self.single_events["negotiation"].wait(timeout=None)
            self.single_events["negotiation"].clear()

            # save time for negotiation for evaluation purposes
            nego_delta_time = time.perf_counter() - nego_start_time
            self.negotiation_times.append(nego_delta_time)

            # send message to buildings to trade with the grid and wait for confirmation
            self.logger.info("Negotiation done. Waiting for agents to trade with grid.")
            self.mqtt_client_controller.publish("/agent/grid")
            self.wait_for_events(events=self.building_events["grid"], timeout=None)
            reset_events(events=self.building_events["grid"])

            # send message to buildings to prepare for the next market cycle and wait for confirmation
            self.logger.info("Grid trade done. Preparing for next market cycle.")
            self.mqtt_client_controller.publish("/building/prepare")
            self.wait_for_events(events=self.building_events["prepared"], timeout=None)
            reset_events(events=self.building_events["prepared"])

            # calculate time for the whole round and wait for the rest of the time to simulate real time
            delta_time = time.perf_counter() - start_time
            self.whole_round_times.append(delta_time)
            wait_time = self.time_per_round - delta_time
            if wait_time > 0:
                self.logger.info(f"Market cycle done in {delta_time} seconds. Waiting for {wait_time} seconds.")
                time.sleep(wait_time)
            else:
                self.logger.info(f"Market cycle done in {delta_time} seconds. No waiting time.")

            # TODO: implement a way to stop the market after a certain time
            if len(self.whole_round_times) > 30 * 24 / 3:
                times_dict = {"whole_round_times": self.whole_round_times, "negotiation_times": self.negotiation_times}
                file = Path(__file__).parent.joinpath(f"times_{time.time()}.p")
                with open(file, "wb") as f:
                    pickle.dump(times_dict, f)
                self.stop_event.set()

        self.logger.info("Market stopped.")

    def on_connect_controller(self, client, userdata, flags, rc):
        client.subscribe(self.topic_controller)
        self.logger.info(f"Controller MQTT client connected and subscribed to {self.topic_controller}.")

    def on_connect_notification_handler(self, client, userdata, flags, rc):
        client.subscribe(self.topic_notification_handler)
        self.logger.info(f"Controller notification MQTT client connected and subscribed to {self.topic_notification_handler}.")

    def on_message_controller(self, client, userdata, message):
        if message.topic == "/controller/start":
            "Received message to start market"
            self.single_events["market_running"].set()
        elif message.topic == "/controller/stop":
            "Received message to stop market"
            self.single_events["market_running"].clear()

    def on_message_notification_handler(self, client, userdata, message):
        """
        Set the corresponding event for the notification received.
        """
        # TODO: implement a better way to match the messages to the events
        match message.topic:
            case "/notification/forecast":
                id_ = message.payload.decode()
                self.logger.debug(f"Received forecast notification for building {id_}")
                if id_ in self.building_events["forecast"]:
                    self.building_events["forecast"][id_].set()
                else:
                    self.logger.warning("Could not set forecast event.")

            case "/notification/optimize":
                id_ = message.payload.decode()
                self.logger.debug(f"Received optimization notification for building {id_}")
                if id_ in self.building_events["optimization"]:
                    self.building_events["optimization"][id_].set()
                else:
                    self.logger.warning("Could not set optimization event.")

            case "/notification/negotiation":
                self.single_events["negotiation"].set()
                self.logger.debug("Received negotiation notification")

            case "/notification/grid":
                id_ = message.payload.decode()
                self.logger.debug(f"Received grid trade notification for agent {id_}")
                if id_ in self.building_events["grid"]:
                    self.building_events["grid"][id_].set()
                else:
                    self.logger.warning("Could not set grid event.")

            case "/notification/prepared":
                id_ = message.payload.decode()
                self.logger.debug(f"Received prepared notification for building {id_}")
                if id_ in self.building_events["prepared"]:
                    self.building_events["prepared"][id_].set()
                else:
                    self.logger.warning("Could not set prepared event.")

            case _:
                pass

    def run_mqtt_client_controller(self):
        if self.stop_event is not None:
            self.mqtt_client_controller.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client_controller.loop_stop()
        else:
            self.mqtt_client_controller.loop_forever()

    def run_mqtt_client_published_handler(self):
        if self.stop_event is not None:
            self.mqtt_client_notification_handler.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client_notification_handler.loop_stop()
        else:
            self.mqtt_client_notification_handler.loop_forever()

    def run(self):
        """
        Run the market controller and start the MQTT clients.
        """
        threads = [threading.Thread(target=self.run_mqtt_client_controller,
                                    name="market controller MQTT client controller"),
                   threading.Thread(target=self.run_mqtt_client_published_handler,
                                    name="market controller MQTT client notification handler"),
                   threading.Thread(target=self.run_market,
                                    name="market controller run market")]
        for thread in threads:
            thread.start()

    def wait_for_events(self, events, timeout):
        start_time = time.time()
        if timeout is None:
            while not all(event.is_set() for event in events.values()):
                time.sleep(0.1)
            self.logger.debug("All events set.")
        else:
            while time.time() - start_time < timeout:
                if all(event.is_set() for event in events.values()):
                    self.logger.debug("All events set.")
                    break
                time.sleep(0.1)


def reset_events(events):
    for event in events.values():
        event.clear()
