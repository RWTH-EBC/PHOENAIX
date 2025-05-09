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
    """
    Market agent class for the FIWARE platform based on the local_energy_market. The agent is responsible for the
    communication with the market and the building.
    """
    def __init__(self, agent_id: int, building: "Building", *args, **kwargs):
        self.stop_event = kwargs.get("stop_event", None)

        MarketAgent.__init__(self, agent_id=agent_id, building=building)
        Device.__init__(self, *args, **kwargs)

        self.mqtt_client = mqtt.Client()
        self.topic = "/agent/#"
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)

        keys = ["prices", "quantities", "meanPrice", "totalQuantity", "buying", "selling", "flexEnergy"]
        # Initialize the attributes
        self.attributes = {
            key: Attribute(device=self, name=key, initial_value=None) for key in keys
        }

        # Create a bid entity from the data model
        schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / 'schema' / 'Bid.json'
        with open(schema_path) as f:
            data_model = json.load(f)
        self.bid_entity = json_schema2context_entity(json_schema_dict=data_model,
                                                     entity_id=f"Bid:DEQ:MVP:{self.agent_id}",
                                                     entity_type="Bid")

        schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / 'schema' / 'Offer.json'
        with open(schema_path) as f:
            self.offer_data_model = json.load(f)

    # Override the methods for sending and receiving data in order to use FIWARE

    @override
    def submit_bid(self):
        # Create a new bid entity from the data model if it does not exist yet
        try:
            self.cb_client.get_entity(entity_id=f"Bid:DEQ:MVP:{self.agent_id}")
        except HTTPError as err:
            if err.response.status_code == 404:
                self.cb_client.post_entity(self.bid_entity)

        # read the attributes that need to be submitted from the bid that was created by the agent before
        bid_attributes = {
            "prices": self.bid.get_prices(),
            "quantities": self.bid.get_quantities(),
            "meanPrice": self.bid.mean_price,
            "totalQuantity": self.bid.total_quantity,
            "buying": self.bid.buying,
            "selling": self.bid.selling,
            "flexEnergy": self.bid.flex_energy
        }

        # update the attributes in the bid entity
        # TODO: maybe faster to update all attributes at once?
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
    def receive_offer(self, offer: Offer = None) -> None:
        """
        Receive the offer from the market that is addressed to this agent.
        """
        # all offers that are addressed to this agent are received, offers are specified in the form of
        # Offer:DEQ:MVP:O:<offering_agent_id>:<receiving_agent_id>
        offer_entities = self.cb_client.get_entity_list(type_pattern="Offer", id_pattern=f".*:{self.agent_id}$")
        # there should be only one offer at a time, otherwise an exception is raised
        if len(offer_entities) > 1:
            raise Exception("More than one offer received")
        elif len(offer_entities) == 0:
            return
        # create the offer object from the received entity
        self.offer = Offer(
            offering_agent_id=offer_entities[0].offeringAgentID.value,
            receiving_agent_id=offer_entities[0].receivingAgentID.value,
            prices=offer_entities[0].prices.value,
            quantities=offer_entities[0].quantities.value,
            buying=offer_entities[0].buying.value,
            selling=offer_entities[0].selling.value
        )
        # delete the offer entity from the context broker to make sure it is not used again
        self.cb_client.delete_entity(entity_id=offer_entities[0].id, entity_type="Offer")

    @override
    def publish_counteroffer(self) -> None:
        offer_id = f"Offer:DEQ:MVP:C:{self.counteroffer.offering_agent_id}:{self.counteroffer.receiving_agent_id}"
        # Create a new offer entity from the data model if it does not exist yet
        try:
            self.cb_client.get_entity(entity_id=offer_id)
        except HTTPError as err:
            if err.response.status_code == 404:
                entity = json_schema2context_entity(json_schema_dict=copy.deepcopy(self.offer_data_model),
                                                    entity_id=offer_id,
                                                    entity_type="Offer")
                self.cb_client.post_entity(entity)

        # read the attributes that need to be submitted from the counteroffer that was created by the agent before
        offer_attributes = {
            "offeringAgentID": self.counteroffer.offering_agent_id,
            "receivingAgentID": self.counteroffer.receiving_agent_id,
            "prices": self.counteroffer.get_prices(),
            "quantities": self.counteroffer.get_quantities(),
            "buying": self.counteroffer.buying,
            "selling": self.counteroffer.selling
        }

        # update the attributes in the offer entity
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
                entity_id=offer_id,
                attr=attribute
            )
        self.offer = None

    @override
    def receive_trade(self, trade: Trade = None) -> None:
        """
        Receive the trade from the market that is addressed to this agent.
        """
        # all trades in which the agent occurs are received, trades are specified in the form of
        # Trade:DEQ:MVP:T:<buying_agent_id>:<selling_agent_id>
        trade_entities = self.cb_client.get_entity_list(type_pattern="Trade", id_pattern=f".*:{self.agent_id}$")
        trade_entities.extend(
            self.cb_client.get_entity_list(type_pattern="Trade", id_pattern=f".*:{self.agent_id}:.*")
        )
        # there should be only one trade at a time, otherwise an exception is raised
        if len(trade_entities) > 1:
            raise Exception("More than one trade received")
        elif len(trade_entities) == 0:
            return
        # create the trade object from the received entity
        trade = Trade(
            buyer=trade_entities[0].buyer.value,
            seller=trade_entities[0].seller.value,
            prices=trade_entities[0].prices.value,
            quantities=trade_entities[0].quantities.value
        )
        # store the trade and adjust the bid accordingly
        self.trades.append(trade)
        self.adjust_bid(trade)

    def on_connect(self, client, userdata, flags, rc) -> None:
        print(f"Connected with result code {rc}")
        client.subscribe(self.topic)
        print(f"Subscribed to topic {self.topic}")

    def on_message(self, client, userdata, message) -> None:
        """
        Run the corresponding method depending on the topic of the message. A notification message is sent back to the
        market controller after the method is executed.
        """
        match message.topic:
            case "/agent/submit_bid":
                print(f"Agent {self.agent_id}: Received message to submit bid")
                self.submit_bid()
                self.mqtt_client.publish(topic="/notification/bid", payload=f"{self.agent_id}")
            case "/agent/counteroffer":
                print(f"Agent {self.agent_id}: Received message to counteroffer")
                self.receive_offer()
                if self.offer is not None:
                    self.make_counteroffer()
                    self.publish_counteroffer()
                self.mqtt_client.publish(topic=f"/notification/published_offer/{self.agent_id}", qos=1)
            case "/agent/receive_trade":
                print(f"Agent {self.agent_id}: Received message to receive trade")
                self.receive_trade()
                self.mqtt_client.publish(topic="/notification/trade", payload=f"{self.agent_id}")
            case "/agent/grid":
                print(f"Agent {self.agent_id}: Received message to trade with grid")
                self.trade_with_grid()
                self.mqtt_client.publish(topic="/notification/grid", payload=f"{self.agent_id}")
            case _:
                print(f"Agent {self.agent_id}: Received message on unknown topic {message.topic}")

    def run(self):
        if self.stop_event is not None:
            self.mqtt_client.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client.loop_stop()
        else:
            self.mqtt_client.loop_forever()
