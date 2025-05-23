import copy
import logging
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt
from typing_extensions import override
from filip.models.ngsi_v2.context import NamedContextAttribute
from requests.exceptions import HTTPError
from deq_demonstrator.utils import json_schema2context_entity
from deq_demonstrator.utils.setup_logger import setup_logger
from deq_demonstrator.config import ROOT_DIR
import json

from local_energy_market.classes import Coordinator, Offer, BlockBid, BidFragment, ResultHandler
from deq_demonstrator.data_models import Device
from deq_demonstrator.settings import settings


class CoordinatorFiware(Coordinator, Device):
    def __init__(self, building_ids, *args, **kwargs):
        self.stop_event = kwargs.get("stop_event", None)
        # Set up the logger
        self.logger = setup_logger(name="CoordinatorFiware", cd=None, level="INFO")
        
        result_handler = ResultHandler(file_name=f"{datetime.now().strftime('%m-%d_%H-%M-%S')}_coordinator")
        Coordinator.__init__(self, result_handler=result_handler)
        Device.__init__(self, *args, **kwargs)

        # Initialize the MQTT client
        self.mqtt_client = mqtt.Client()
        self.topic = "/coordinator/#"
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)

        # Initialize the MQTT client for notification handling
        self.mqtt_client_notification_handler = mqtt.Client()
        self.topic_notification_handler = "/notification/#"
        self.mqtt_client_notification_handler.on_connect = self.on_connect_notification_handler
        self.mqtt_client_notification_handler.on_message = self.on_message_notification_handler
        self.mqtt_client_notification_handler.connect(host=settings.MQTT_HOST,
                                                      port=settings.MQTT_PORT)

        schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / 'schema' / 'Offer.json'
        with open(schema_path) as f:
            self.offer_data_model = json.load(f)

        schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / 'schema' / 'Trade.json'
        with open(schema_path) as f:
            self.trade_data_model = json.load(f)

        self.building_ids = building_ids
        self.bid_events = {str(building_id): threading.Event() for building_id in building_ids}
        self.trade_events = {str(building_id): threading.Event() for building_id in building_ids}
        self.agent_events = {}

    # Override the methods for sending and receiving data in order to use FIWARE
    @override
    def collect_bids(self) -> None:
        """
        Request the agents to send their bids and collect them.
        """
        self.logger.info("Collecting bids")
        # Send notification to the agents to send their bids and wait for them to sent confirmations
        info = self.mqtt_client_notification_handler.publish("/agent/submit_bid")
        self.wait_for_events(events=self.bid_events, timeout=None)
        reset_events(events=self.bid_events)

        # Collect the bids from the agents
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
            # Create the bids from the BidFragments
            for price, quantity in zip(prices, quantities):
                bid_fragment = BidFragment(price=price, quantity=quantity, buying=bid.buying, selling=bid.selling)
                bid.add_bid_fragment(bid_fragment)
            bids.append(bid)
        self.submitted_bids = bids
        self.result_handler.save_bids(id_="c", data=bids)

    def collect_offers(self) -> list[Offer]:
        """
        Collect the offers from the agents and return them.
        """
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
        """
        The offers are published and the agents are notified to send their counteroffers. The counteroffers are
        collected and returned.
        """
        # Create events for each agent that receives an offer to wait for their counteroffers
        self.agent_events = {str(offer.receiving_agent_id): threading.Event() for offer in offers}
        # Publish the offers to the market and notify the agents to send their counteroffers
        self.publish_offers(offers)
        self.mqtt_client_notification_handler.publish("/agent/counteroffer", payload="all")
        # Wait for the agents to send their counteroffers
        self.wait_for_events(events=self.agent_events, timeout=None)
        # Collect the counteroffers from the agents
        return self.collect_offers()

    def publish_offers(self, offers: list[Offer]) -> None:
        """
        Publish the offers to the market.
        """

        for offer in offers:
            # Create a new entity for the offer if it does not exist already
            try:
                self.cb_client.get_entity(entity_id=f"Offer:DEQ:MVP:C:{offer.receiving_agent_id}")
            except HTTPError as err:
                if err.response.status_code == 404:
                    entity = json_schema2context_entity(json_schema_dict=copy.deepcopy(self.offer_data_model),
                                                        entity_id=f"Offer:DEQ:MVP:C:{offer.receiving_agent_id}",
                                                        entity_type="Offer")
                    self.cb_client.post_entity(entity)

            # Map the entity attributes to the offer attributes
            offer_attributes = {
                "offeringAgentID": offer.offering_agent_id,
                "receivingAgentID": offer.receiving_agent_id,
                "prices": offer.get_prices(),
                "quantities": offer.get_quantities(),
                "buying": offer.buying,
                "selling": offer.selling
            }

            # Update the entity attributes
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
        """
        Publish the trades to the market and notify the agents to receive them.
        """
        for trade in self.trades:
            # Create a new entity for the trade if it does not exist already
            try:
                self.cb_client.get_entity(entity_id=f"Trade:DEQ:MVP:{trade.seller}:{trade.buyer}")
            except HTTPError as err:
                if err.response.status_code == 404:
                    entity = json_schema2context_entity(json_schema_dict=copy.deepcopy(self.trade_data_model),
                                                        entity_id=f"Trade:DEQ:MVP:{trade.seller}:{trade.buyer}",
                                                        entity_type="Trade")
                    self.cb_client.post_entity(entity)

            # Map the entity attributes to the trade attributes
            trade_attributes = {
                "buyer": trade.buyer,
                "seller": trade.seller,
                "prices": trade.prices,
                "quantities": trade.quantities
            }
            # Update the entity attributes
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
        self.logger.info("Published trades. Waiting for agents to receive them.")

        # Notify the agents to receive the trades and wait for them to confirm the reception
        self.mqtt_client_notification_handler.publish(topic="/agent/receive_trade")
        self.wait_for_events(events=self.trade_events, timeout=None)
        reset_events(events=self.trade_events)

    @override
    def clear_for_next_round(self) -> None:
        """
        Clear the data for the next round of the market.
        """
        self.trades = []
        self.matches = []
        self.buying_offers = []
        self.selling_offers = []
        self.clear_bids()
        self.clear_fiware_for_next_round()

    def clear_fiware_for_next_round(self):
        """
        Clear the FIWARE context broker for the next round of the market.
        """
        self.cb_client.delete_entities(entities=self.cb_client.get_entity_list(type_pattern="Bid"))
        self.cb_client.delete_entities(entities=self.cb_client.get_entity_list(type_pattern="Offer"))
        self.cb_client.delete_entities(entities=self.cb_client.get_entity_list(type_pattern="Trade"))

    def on_connect(self, client, userdata, flags, rc) -> None:
        self.logger.info(f"Connected with result code {rc}")
        client.subscribe(self.topic)
        self.logger.info(f"Subscribed to topic {self.topic}")

    def on_connect_notification_handler(self, client, userdata, flags, rc) -> None:
        self.logger.info(f"Connected with result code {rc}")
        client.subscribe(self.topic_notification_handler)
        self.logger.info(f"Subscribed to topic {self.topic_notification_handler}")

    def on_message(self, client, userdata, message) -> None:
        match message.topic:
            case "/coordinator/collect_bids":
                self.logger.debug("Received message to collect bids")
                self.collect_bids()
            case "/coordinator/negotiation":
                self.logger.debug("Received message to start negotiation")
                self.run_negotiation()
                self.logger.info("Negotiation done")
                self.mqtt_client.publish(topic="/notification/negotiation", payload="C", qos=1)
            case _:
                self.logger.warning(f"Coordinator received message on unknown topic {message.topic}")

    def on_message_notification_handler(self, client, userdata, message) -> None:
        match message.topic:
            case topic if "/notification/published_offer" in topic:
                self.logger.debug("Received message that an agent has published an offer")
                agent = topic.split("/")[-1]
                if agent in self.agent_events:
                    self.agent_events[agent].set()
            case "/notification/bid":
                id_ = message.payload.decode()
                self.logger.debug(f"Received bid notification for agent {id_}")
                self.bid_events[id_].set() if id_ in self.bid_events else self.logger.warning("Could not set bid event.")
            case "/notification/trade":
                id_ = message.payload.decode()
                self.logger.debug(f"Received trade notification for agent {id_}")
                self.trade_events[id_].set() if id_ in self.trade_events else self.logger.warning("Could not set trade event.")
            case _:
                pass

    def run_mqtt_client(self):
        """
        Run the MQTT client.
        """
        if self.stop_event is not None:
            self.mqtt_client.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client.loop_stop()
        else:
            self.mqtt_client.loop_forever()

    def run_mqtt_client_notification_handler(self):
        """
        Run the MQTT client for notification handling.
        """
        if self.stop_event is not None:
            self.mqtt_client_notification_handler.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client_notification_handler.loop_stop()

        else:
            self.mqtt_client_notification_handler.loop_forever()

    def run(self):
        """
        Create and start the threads for the MQTT client and the notification handler.
        """
        threads = [threading.Thread(target=self.run_mqtt_client,
                                    name="Coordinator MQTT Client"),
                   threading.Thread(target=self.run_mqtt_client_notification_handler,
                                    name="Coordinator MQTT Client Notification Handler")]
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
