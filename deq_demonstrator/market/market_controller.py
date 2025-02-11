import paho.mqtt.client as mqtt
import time
from deq_demonstrator.settings import settings
import threading

class MarketController:

    def __init__(self, ids: list[str], *args, **kwargs):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)
        self.topic = "/controller/#"

        self.topic_notification_handler = "/notification/#"
        self.mqtt_client_notification_handler = mqtt.Client()
        self.mqtt_client_notification_handler.on_connect = self.on_connect_notification_handler
        self.mqtt_client_notification_handler.on_message = self.on_message_notification_handler
        self.mqtt_client_notification_handler.connect(host=settings.MQTT_HOST,
                                                     port=settings.MQTT_PORT)

        self.ids = ids

        self.stop_event = kwargs.get("stop_event", None)

        self.market_running_event = threading.Event()

        self.forecast_events = {str(id_): threading.Event() for id_ in ids}
        self.optimize_events = {str(id_): threading.Event() for id_ in ids}
        self.bid_events = {str(id_): threading.Event() for id_ in ids}
        self.negotiation_event = threading.Event()
        self.grid_events = {str(id_): threading.Event() for id_ in ids}
        self.building_prepared_events = {str(id_): threading.Event() for id_ in ids}

        self.time_per_round = 2 # seconds


    def run_market(self):

        self.market_running_event.wait()

        while not self.stop_event.is_set() and self.market_running_event.is_set():
            start_time = time.time()
            print("Starting market cycle.")
            print("Waiting for forecast calculation.")
            self.mqtt_client.publish(topic="/building/calculate_forecast")
            self.wait_for_events(events=self.forecast_events, timeout=None)
            self.reset_events(events=self.forecast_events)

            print("Forecast calculated. Waiting for optimization.")
            self.mqtt_client.publish(topic="/building/optimize")
            self.wait_for_events(events=self.optimize_events, timeout=None)
            self.reset_events(events=self.optimize_events)

            #print("Optimization done. Waiting for bid submission.")
            #self.mqtt_client.publish("/agent/submit_bid")
            #self.wait_for_events(events=self.bid_events, timeout=None)
            #self.reset_events(events=self.bid_events)

            print("Optimization done. Waiting for negotiation.")
            self.mqtt_client.publish("/coordinator/negotiation")
            self.negotiation_event.wait(timeout=None)
            self.negotiation_event.clear()

            print("Negotiation done. Waiting for agents to trade with grid.")
            self.mqtt_client.publish("/agent/grid")
            self.wait_for_events(events=self.grid_events, timeout=None)
            self.reset_events(events=self.grid_events)

            print("Grid trade done. Preparing for next market cycle.")
            self.mqtt_client.publish("/building/prepare")
            self.wait_for_events(events=self.building_prepared_events, timeout=None)
            self.reset_events(events=self.building_prepared_events)

            delta_time = time.time() - start_time
            wait_time = self.time_per_round - delta_time
            if wait_time > 0:
                print(f"Market cycle done in {delta_time} seconds. Waiting for {wait_time} seconds.")
                time.sleep(wait_time)
            else:
                print(f"Market cycle done in {delta_time} seconds. No waiting time.")

        print("Market stopped.")


    def wait_for_events(self, events, timeout):
        start_time = time.time()
        if timeout is None:
            while not all(event.is_set() for event in events.values()):
                time.sleep(0.1)
            print("All events set.")
        else:
            while time.time() - start_time < timeout:
                if all(event.is_set() for event in events.values()):
                    print("All events set.")
                    break
                time.sleep(0.1)

    def reset_events(self, events):
        for event in events.values():
            event.clear()

    def on_connect(self, client, userdata, flags, rc):
        client.subscribe(self.topic)
        print(f"Controller MQTT client connected and subscribed to {self.topic}.")

    def on_connect_notification_handler(self, client, userdata, flags, rc):
        client.subscribe(self.topic_notification_handler)
        print(f"Controller MQTT client connected and subscribed to {self.topic_notification_handler}.")

    def on_message(self, client, userdata, message):
        if message.topic == "/controller/start":
            "Received message to start market"
            self.market_running_event.set()
        elif message.topic == "/controller/stop":
            "Received message to stop market"
            self.market_running_event.clear()

    def on_message_notification_handler(self, client, userdata, message):
        if message.topic == "/notification/forecast":
            id_ = message.payload.decode()
            print(f"Received forecast notification for building {id_}")
            self.forecast_events[id_].set() if id_ in self.forecast_events else print("Could not set forecast event.")

        elif message.topic == "/notification/optimize":
            id_ = message.payload.decode()
            print(f"Received optimization notification for building {id_}")
            self.optimize_events[id_].set() if id_ in self.optimize_events else print("Could not set optimization event.")

        #elif message.topic == "/notification/bid":
        #    id_ = message.payload.decode()
        #    print(f"Received bid notification for agent {id_}")
        #    self.bid_events[id_].set() if id_ in self.bid_events else print("Could not set bid event.")

        elif message.topic == "/notification/negotiation":
            self.negotiation_event.set()
            print("Received negotiation notification")

        elif message.topic == "/notification/grid":
            id_ = message.payload.decode()
            print(f"Received grid trade notification for agent {id_}")
            self.grid_events[id_].set() if id_ in self.grid_events else print("Could not set grid event.")

        elif message.topic == "/notification/prepared":
            id_ = message.payload.decode()
            print(f"Received prepared notification for building {id_}")
            self.building_prepared_events[id_].set() if id_ in self.building_prepared_events else print("Could not set prepared event.")

    def run_mqtt_client(self):
        if self.stop_event is not None:
            self.mqtt_client.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client.loop_stop()

        else:
            self.mqtt_client.loop_forever()

    def run_mqtt_client_published_handler(self):
        if self.stop_event is not None:
            self.mqtt_client_notification_handler.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client_notification_handler.loop_stop()

        else:
            self.mqtt_client_notification_handler.loop_forever()

    def run(self):
        controller_treads = []
        mqtt_client_thread = threading.Thread(target=self.run_mqtt_client)
        controller_treads.append(mqtt_client_thread)
        mqtt_client_published_handler_thread = threading.Thread(target=self.run_mqtt_client_published_handler)
        controller_treads.append(mqtt_client_published_handler_thread)
        market_thread = threading.Thread(target=self.run_market)
        controller_treads.append(market_thread)
        for thread in controller_treads:
            thread.start()
