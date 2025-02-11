import copy
import threading
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
    def __init__(self, building_ids, *args, **kwargs):
        Coordinator.__init__(self)
        Device.__init__(self,*args, **kwargs)

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)
        self.topic = "/coordinator/#"
        self.topic_notification_handler = "/notification/#"

        self.mqtt_client_notification_handler = mqtt.Client()
        self.mqtt_client_notification_handler.on_connect = self.on_connect_notification_handler
        self.mqtt_client_notification_handler.on_message = self.on_message_notification_handler
        self.mqtt_client_notification_handler.connect(host=settings.MQTT_HOST,
                                                      port=settings.MQTT_PORT)


        self.stop_event = kwargs.get("stop_event", None)
        self.agent_events = {}

        schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / \
                      'schema' / 'Offer.json'
        with open(schema_path) as f:
            self.offer_data_model = json.load(f)

        schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / \
                      'schema' / 'Trade.json'
        with open(schema_path) as f:
            self.trade_data_model = json.load(f)

        self.building_ids = building_ids
        self.bid_events = {str(building_id): threading.Event() for building_id in building_ids}
        self.trade_events = {str(building_id): threading.Event() for building_id in building_ids}


    # Override the methods for sending and receiving data in order to use FIWARE

    @override
    def collect_bids(self) -> None:
        print("Collecting bids")
        info = self.mqtt_client_notification_handler.publish("/agent/submit_bid")
        self.wait_for_events(events=self.bid_events, timeout=None)
        self.reset_events(events=self.bid_events)

        bid_entities = self.cb_client.get_entity_list(type_pattern="Bid")
        bids = []
        for bid_entity in bid_entities:
            bid_attrs = self.cb_client.get_entity_attributes(entity_id=bid_entity.id)
            agent_id = bid_entity.id.split(":")[-1]
            bid = BlockBid(agent_id=agent_id)
            prices = bid_attrs["prices"].value
            quantities = bid_attrs["quantities"].value
            bid.buying = bid_attrs["buying"].value
            bid.selling = bid_attrs["selling"].value
            bid.flex_energy = bid_attrs["flexEnergy"].value

            for price, quantity in zip(prices, quantities):
                bid_fragment = BidFragment(price=price, quantity=quantity, buying=bid.buying, selling=bid.selling)
                bid.add_bid_fragment(bid_fragment)
            bids.append(bid)
        self.submitted_bids = bids

    def collect_offers(self, offer: Offer=None) -> list[Offer]:
        offer_entities = self.cb_client.get_entity_list(type_pattern="Offer")
        offers = []
        for offer_entity in offer_entities:
            offers.append(Offer(
                offering_agent_id=offer_entity.offeringAgentID.value,
                receiving_agent_id=offer_entity.receivingAgentID.value,
                prices=offer_entity.prices.value,
                quantities=offer_entity.quantities.value,
                buying=offer_entity.buying.value,
                selling=offer_entity.selling.value
            ))
        self.cb_client.delete_entities(offer_entities)
        return offers

    @override
    def publish_offers_and_receive_counteroffers(self, offers: list[Offer]) -> list[Offer]:
        self.agent_events = {str(offer.receiving_agent_id): threading.Event() for offer in offers}
        # Publish the offers to the market and receive the counteroffers
        self.publish_offers(offers)
        self.mqtt_client_notification_handler.publish("/agent/counteroffer", payload="all")
        self.wait_for_events(events=self.agent_events, timeout=None)
        return self.collect_offers()

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
        print("Published trades. Waiting for agents to receive them.")
        self.mqtt_client_notification_handler.publish(topic="/agent/receive_trade")
        self.wait_for_events(events=self.trade_events, timeout=None)
        self.reset_events(events=self.trade_events)

    @override
    def clear_for_next_round(self) -> None:
        self.trades = []
        self.matches = []
        self.buying_offers = []
        self.selling_offers = []
        self.clear_bids()
        self.clear_fiware_for_next_round()

    def clear_fiware_for_next_round(self):
        # Clear the FIWARE context broker for the next step
        self.cb_client.delete_entities(entities=self.cb_client.get_entity_list(type_pattern="Bid"))
        self.cb_client.delete_entities(entities=self.cb_client.get_entity_list(type_pattern="Offer"))
        self.cb_client.delete_entities(entities=self.cb_client.get_entity_list(type_pattern="Trade"))

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

    def on_connect(self, client, userdata, flags, rc) -> None:
        print(f"Connected with result code {rc}")
        client.subscribe(self.topic)
        print(f"Subscribed to topic {self.topic}")

    def on_connect_notification_handler(self, client, userdata, flags, rc) -> None:
        print(f"Connected with result code {rc}")
        client.subscribe(self.topic_notification_handler)
        print(f"Subscribed to topic {self.topic_notification_handler}")

    def on_message(self, client, userdata, message) -> None:
        if message.topic == "/coordinator/collect_bids":
            print("Received message to collect bids")
            self.collect_bids()
        elif message.topic == "/coordinator/negotiation":
            print("Received message to start negotiation")
            self.run_negotiation()
            print("Negotiation done")
            self.mqtt_client.publish(topic="/notification/negotiation", payload="C")

    def on_message_notification_handler(self, client, userdata, message) -> None:
        if "/notification/published_offer" in message.topic:
            print("Received message that an agent has published an offer")
            agent = message.topic.split("/")[-1]
            if agent in self.agent_events:
                self.agent_events[agent].set()
        elif message.topic == "/notification/bid":
            id_ = message.payload.decode()
            print(f"Received bid notification for agent {id_}")
            self.bid_events[id_].set() if id_ in self.bid_events else print("Could not set bid event.")
        elif message.topic == "/notification/trade":
            id_ = message.payload.decode()
            print(f"Received trade notification for agent {id_}")
            self.trade_events[id_].set() if id_ in self.trade_events else print("Could not set trade event.")

    def run_mqtt_client(self):
        if self.stop_event is not None:
            self.mqtt_client.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client.loop_stop()

        else:
            self.mqtt_client.loop_forever()

    def run_mqtt_client_notification_handler(self):
        if self.stop_event is not None:
            self.mqtt_client_notification_handler.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client_notification_handler.loop_stop()

        else:
            self.mqtt_client_notification_handler.loop_forever()

    def run(self):
        threads = []
        mqtt_client_thread = threading.Thread(target=self.run_mqtt_client)
        threads.append(mqtt_client_thread)
        mqtt_client_notification_handler_thread = threading.Thread(target=self.run_mqtt_client_notification_handler)
        threads.append(mqtt_client_notification_handler_thread)
        for thread in threads:
            thread.start()
