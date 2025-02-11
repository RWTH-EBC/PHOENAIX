from typing_extensions import override
import paho.mqtt.client as mqtt
import time
from filip.models.ngsi_v2.context import NamedContextAttribute
from requests.exceptions import HTTPError
from deq_demonstrator.utils import json_schema2context_entity
from deq_demonstrator.config import ROOT_DIR
import json
import copy

from local_energy_market.classes import MarketAgent, BlockBid, Offer, Trade
from deq_demonstrator.data_models import Device, Attribute
from deq_demonstrator.settings import settings


class MarketAgentFiware(MarketAgent, Device):
    def __init__(self, agent_id: int, building: "Building", *args, **kwargs):
        MarketAgent.__init__(self, agent_id=agent_id, building=building)
        Device.__init__(self, *args, **kwargs)

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)
        self.topic = "agent/#"

        self.stop_event = kwargs.get("stop_event", None)

        keys = ["prices", "quantities", "meanPrice", "totalQuantity", "buying", "selling", "flexEnergy"]
        # Initialize the attributes
        self.attributes = {
            key: Attribute(device=self, name=key, initial_value=None) for key in keys
        }

        schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / \
                      'schema' / 'Bid.json'
        with open(schema_path) as f:
            data_model = json.load(f)
        try:
            self.cb_client.get_entity(entity_id=f"Bid:DEQ:MVP:{self.agent_id}")
        except HTTPError as err:
            if err.response.status_code == 404:
                entity = json_schema2context_entity(json_schema_dict=data_model,
                                                    entity_id=f"Bid:DEQ:MVP:{self.agent_id}",
                                                    entity_type="Bid")
                self.cb_client.post_entity(entity)

        schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / \
                      'schema' / 'Offer.json'
        with open(schema_path) as f:
            self.offer_data_model = json.load(f)

    # Override the methods for sending and receiving data in order to use FIWARE

    @override
    def submit_bid(self):
        '''
        self.attributes["prices"].value = self.bid.get_prices()
        self.attributes["quantities"].value = self.bid.get_quantities()
        self.attributes["meanPrice"].value = self.bid.mean_price
        self.attributes["totalQuantity"].value = self.bid.total_quantity
        self.attributes["buying"].value = self.bid.buying
        self.attributes["selling"].value = self.bid.selling
        self.attributes["flexEnergy"].value = self.bid.flex_energy

        for attr in self.attributes.values():
            attr.push()

        '''

        bid_attributes = {
            "prices": self.bid.get_prices(),
            "quantities": self.bid.get_quantities(),
            "meanPrice": self.bid.mean_price,
            "totalQuantity": self.bid.total_quantity,
            "buying": self.bid.buying,
            "selling": self.bid.selling,
            "flexEnergy": self.bid.flex_energy
        }

        for key, value in bid_attributes.items():
            if isinstance(value, list):
                attr_type = "Array"
            elif isinstance(value, bool):
                attr_type = "Boolean"
            elif isinstance(value, int) or isinstance(value, float):
                attr_type = "Number"
            else:
                attr_type = "String"

            attribute = NamedContextAttribute(
                name=key,
                type=attr_type,
                value=value
            )
            self.cb_client.update_entity_attribute(
                entity_id=f"Bid:DEQ:MVP:{self.agent_id}",
                attr=attribute
            )

    @override
    def receive_offer(self, offer: Offer=None) -> None:
        offer_entities = self.cb_client.get_entity_list(type_pattern="Offer", id_pattern=f".*:{self.agent_id}$")
        if len(offer_entities) > 1:
            raise Exception("More than one offer received")
        elif len(offer_entities) == 0:
            return
        self.offer = Offer(
            offering_agent_id=offer_entities[0].offeringAgentID.value,
            receiving_agent_id=offer_entities[0].receivingAgentID.value,
            prices=offer_entities[0].prices.value,
            quantities=offer_entities[0].quantities.value,
            buying=offer_entities[0].buying.value,
            selling=offer_entities[0].selling.value
        )

    @override
    def publish_counteroffer(self) -> None:
        try:
            self.cb_client.get_entity(entity_id=f"Offer:DEQ:MVP:{self.counteroffer.offering_agent_id}:{self.counteroffer.receiving_agent_id}")
        except HTTPError as err:
            if err.response.status_code == 404:
                entity = json_schema2context_entity(json_schema_dict=copy.deepcopy(self.offer_data_model),
                                                    entity_id=f"Offer:DEQ:MVP:C:{self.counteroffer.offering_agent_id}:{self.counteroffer.receiving_agent_id}",
                                                    entity_type="Offer")
                self.cb_client.post_entity(entity)

        offer_attributes = {
            "offeringAgentID": self.counteroffer.offering_agent_id,
            "receivingAgentID": self.counteroffer.receiving_agent_id,
            "prices": self.counteroffer.get_prices(),
            "quantities": self.counteroffer.get_quantities(),
            "buying": self.counteroffer.buying,
            "selling": self.counteroffer.selling
        }

        for key, value in offer_attributes.items():
            if isinstance(value, list):
                attr_type = "Array"
            elif isinstance(value, bool):
                attr_type = "Boolean"
            elif isinstance(value, int) or isinstance(value, float):
                attr_type = "Number"
            else:
                attr_type = "String"

            attribute = NamedContextAttribute(
                name=key,
                type=attr_type,
                value=value
            )
            self.cb_client.update_entity_attribute(
                entity_id=f"Offer:DEQ:MVP:C:{self.counteroffer.offering_agent_id}:{self.counteroffer.receiving_agent_id}",
                attr=attribute
            )

    @override
    def receive_trade(self, trade: Trade=None) -> None:
        # Receive the trade from the market
        trade_entities = self.cb_client.get_entity_list(type_pattern="Trade", id_pattern=f".*:{self.agent_id}$")
        trade_entities.extend(
            self.cb_client.get_entity_list(type_pattern="Trade", id_pattern=f".*:{self.agent_id}:.*")
        )
        if len(trade_entities) > 1:
            raise Exception("More than one trade received")
        elif len(trade_entities) == 0:
            return
        trade = Trade(
            buyer=trade_entities[0].buyer.value,
            seller=trade_entities[0].seller.value,
            prices=trade_entities[0].prices.value,
            quantities=trade_entities[0].quantities.value
        )
        self.trades.append(trade)
        self.adjust_bid(trade)

    def on_connect(self, client, userdata, flags, rc) -> None:
        print(f"Connected with result code {rc}")
        client.subscribe(self.topic)
        print(f"Subscribed to topic {self.topic}")

    def on_message(self, client, userdata, message) -> None:
        if message.topic == "agent/submit_bid":
            print(f"Agent {self.agent_id}: Received message to submit bid")
            self.create_bid(self.building.flexibility)
            self.submit_bid()

    def run(self):
        if self.stop_event is not None:
            self.mqtt_client.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client.loop_stop()

        else:
            self.mqtt_client.loop_forever()