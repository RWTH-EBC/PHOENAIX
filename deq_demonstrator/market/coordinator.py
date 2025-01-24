import time

import paho.mqtt.client as mqtt
from typing_extensions import override

from local_energy_market.classes import Coordinator, Offer, BlockBid
from deq_demonstrator.data_models import Device
from deq_demonstrator.settings import settings


class CoordinatorFiware(Coordinator, Device):
    def __init__(self, *args, **kwargs):
        Coordinator.__init__(self,*args, **kwargs)
        Device.__init__(self,*args, **kwargs)

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)
        self.topic = "/coordinator"

        self.stop_event = kwargs.get("stop_event", None)

    # Override the methods for sending and receiving data in order to use FIWARE

    @override
    def collect_bids(self) -> list[BlockBid]:
        agents = self.cb_client.get_entity_list(type_pattern="Building")
        bids = []
        for agent in agents:
            agent_attributes = self.cb_client.get_entity_attributes(entity_id=agent.id)
            bid = BlockBid(agent_id=agent.id)
            bid.set_prices(agent_attributes["prices"])
            bid.set_quantities(agent_attributes["quantities"])
            bid.mean_price = agent_attributes["meanPrice"]
            bid.total_quantity = agent_attributes["totalQuantity"]
            bid.buying = agent_attributes["buying"]
            bid.selling = agent_attributes["selling"]
            bid.flex_energy = agent_attributes["flexEnergy"]
            bids.append(bid)
        return bids

    @override
    def publish_offers_and_receive_counteroffers(self, offers: list[Offer]) -> list[Offer]:
        # Publish the offers to the market and receive the counteroffers
        return offers

    @override
    def publish_trades(self) -> None:
        # Publish the trades to the market
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