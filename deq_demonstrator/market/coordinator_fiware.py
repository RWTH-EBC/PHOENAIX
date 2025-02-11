import copy
import time

import paho.mqtt.client as mqtt
from typing_extensions import override
from filip.models.ngsi_v2.context import NamedContextAttribute
from requests.exceptions import HTTPError
from deq_demonstrator.utils import json_schema2context_entity
from deq_demonstrator.config import ROOT_DIR
import json

from local_energy_market.classes import Coordinator, Offer, BlockBid, BidFragment
from deq_demonstrator.data_models import Device
from deq_demonstrator.settings import settings


class CoordinatorFiware(Coordinator, Device):
    def __init__(self, *args, **kwargs):
        Coordinator.__init__(self,*args, **kwargs)
        Coordinator.__init__(self)
        Device.__init__(self,*args, **kwargs)

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)
        self.topic = "/coordinator"

        self.stop_event = kwargs.get("stop_event", None)

        schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / \
                      'schema' / 'Offer.json'
        with open(schema_path) as f:
            self.offer_data_model = json.load(f)

        schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / \
                      'schema' / 'Trade.json'
        with open(schema_path) as f:
            self.trade_data_model = json.load(f)


    # Override the methods for sending and receiving data in order to use FIWARE

    @override
    def collect_bids(self) -> list[BlockBid]:
        bid_entities = self.cb_client.get_entity_list(type_pattern="Bid")
        bids = []
        for bid_entity in bid_entities:
            bid_attrs = self.cb_client.get_entity_attributes(entity_id=bid_entity.id)
            bid = BlockBid(agent_id=bid_entity.id)
            prices = bid_attrs["prices"].value
            quantities = bid_attrs["quantities"].value
            bid.buying = bid_attrs["buying"].value
            bid.selling = bid_attrs["selling"].value
            bid.flex_energy = bid_attrs["flexEnergy"].value

            for price, quantity in zip(prices, quantities):
                bid_fragment = BidFragment(price=price, quantity=quantity, buying=bid.buying, selling=bid.selling)
                bid.add_bid_fragment(bid_fragment)
            bids.append(bid)
        return bids

    @override
    def publish_offers_and_receive_counteroffers(self, offers: list[Offer]) -> list[Offer]:
        # Publish the offers to the market and receive the counteroffers
        self.publish_offers(offers)
        return offers

    def publish_offers(self, offers: list[Offer]) -> None:
        # Publish the offers to the market


        for offer in offers:

            try:
                self.cb_client.get_entity(entity_id=f"Offer:DEQ:MVP:C:{offer.receiving_agent_id}")
            except HTTPError as err:
                if err.response.status_code == 404:
                    entity = json_schema2context_entity(json_schema_dict=copy.deepcopy(self.offer_data_model),
                                                        entity_id=f"Offer:DEQ:MVP:C:{offer.receiving_agent_id}",
                                                        entity_type="Offer")
                    self.cb_client.post_entity(entity)

            offer_attributes = {
                "offeringAgentID": offer.offering_agent_id,
                "receivingAgentID": offer.receiving_agent_id,
                "prices": offer.get_prices(),
                "quantities": offer.get_quantities(),
                "buying": offer.buying,
                "selling": offer.selling
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
                    entity_id=f"Offer:DEQ:MVP:C:{offer.receiving_agent_id}",
                    attr=attribute
                )

    @override
    def publish_trades(self) -> None:
        # Publish the trades to the market
        for trade in self.trades:

            try:
                self.cb_client.get_entity(entity_id=f"Trade:DEQ:MVP:{trade.seller}:{trade.buyer}")
            except HTTPError as err:
                if err.response.status_code == 404:
                    entity = json_schema2context_entity(json_schema_dict=copy.deepcopy(self.trade_data_model),
                                                        entity_id=f"Trade:DEQ:MVP:{trade.seller}:{trade.buyer}",
                                                        entity_type="Trade")
                    self.cb_client.post_entity(entity)

            trade_attributes = {
                "buyer": trade.buyer,
                "seller": trade.seller,
                "prices": trade.prices,
                "quantities": trade.quantities
            }

            for key, value in trade_attributes.items():
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
                    entity_id=f"Trade:DEQ:MVP:{trade.seller}:{trade.buyer}",
                    attr=attribute
                )

    def clear_fiware_for_next_round(self):
        # Clear the FIWARE context broker for the next step
        self.cb_client.delete_entities(type_pattern="Bid")
        self.cb_client.delete_entities(type_pattern="Offer")
        self.cb_client.delete_entities(type_pattern="Trade")

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