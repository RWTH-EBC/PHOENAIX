from typing_extensions import override
import paho.mqtt.client as mqtt
import time

from local_energy_market.classes import MarketAgent, BlockBid, Offer, Trade
from deq_demonstrator.data_models import Device, Attribute
from deq_demonstrator.settings import settings


class MarketAgentFiware(MarketAgent, Device):
    def __init__(self, agent_id: int, building: "Building", *args, **kwargs):
        MarketAgent.__init__(self, agent_id=agent_id, building=building, *args, **kwargs)
        Device.__init__(self, *args, **kwargs)

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)
        self.topic = f"/agent_{agent_id}"

        self.stop_event = kwargs.get("stop_event", None)

        keys = ["prices", "quantities", "meanPrice", "totalQuantity", "buying", "selling", "flexEnergy"]
        # Initialize the attributes
        self.attributes = {
            key: Attribute(device=self, name=key, initial_value=None) for key in keys
        }

    # Override the methods for sending and receiving data in order to use FIWARE

    @override
    def submit_bid(self):
        self.attributes["prices"].value = self.bid.get_prices()
        self.attributes["quantities"].value = self.bid.get_quantities()
        self.attributes["meanPrice"].value = self.bid.mean_price
        self.attributes["totalQuantity"].value = self.bid.total_quantity
        self.attributes["buying"].value = self.bid.buying
        self.attributes["selling"].value = self.bid.selling
        self.attributes["flexEnergy"].value = self.bid.flex_energy

        for attr in self.attributes.values():
            attr.push()

    @override
    def receive_offer(self, offer: Offer) -> None:
        # Receive the offer from the market
        pass

    @override
    def receive_trade(self, trade: Trade) -> None:
        # Receive the trade from the market
        pass

    def on_connect(self, client, userdata, flags, rc) -> None:
        print(f"Connected with result code {rc}")
        client.subscribe(self.topic)
        print(f"Subscribed to topic {self.topic}")

    def on_message(self, client, userdata, message) -> None:
        print(f"Received message '{message.payload.decode()}' on topic '{message.topic}'")

    def run(self):
        if self.stop_event is not None:
            self.mqtt_client.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client.loop_stop()

        else:
            self.mqtt_client.loop_forever()