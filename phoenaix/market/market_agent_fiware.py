from typing_extensions import override
import paho.mqtt.client as mqtt
import time
from filip.models.ngsi_v2.context import NamedContextAttribute
from requests.exceptions import HTTPError
from phoenaix.utils import json_schema2context_entity
from phoenaix.config import ROOT_DIR
import json
import copy

from local_energy_market.classes import MarketAgent, BlockBid, Offer, Trade
from phoenaix.data_models import Device, Attribute
from phoenaix.settings import settings
from phoenaix.utils.setup_logger import setup_logger


class MarketAgentFiware(MarketAgent, Device):
    """
    Market agent class for the FIWARE platform based on the local_energy_market. The agent is responsible for the
    communication with the market and the building.
    """
    def __init__(self, agent_id: int, building: "Building", *args, **kwargs):
        self.stop_event = kwargs.get("stop_event", None)

        self.logger = setup_logger(name=f"MarketAgentFiware {agent_id}", cd=None, level="DEBUG")

        MarketAgent.__init__(self, agent_id=agent_id, building=building)
        Device.__init__(self, *args, **kwargs)

        self.mqtt_client = mqtt.Client()
        self.topic = "/agent/#"
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)

        keys = ["bid", "offer"]
        # Initialize the attributes
        self.attributes = {
            key: Attribute(device=self, name=key, initial_value=None) for key in keys
        }

    # Override the methods for sending and receiving data in order to use FIWARE

    @override
    def submit_bid(self):
        """
        Submit the bid by updating the bid attribute in the market agent entity.
        """

        # read the attributes that need to be submitted from the bid that was created by the agent before
        bid_attributes = {
            "prices": self.bid.get_prices(),
            "quantities": self.bid.get_quantities(),
            "meanPrice": self.bid.mean_price,
            "totalQuantity": self.bid.total_quantity,
            "buying": self.bid.buying,
            "selling": self.bid.selling,
            "flexEnergy": self.bid.flex_energy,
            "used": False
        }

        # update the attributes in the bid entity
        self.attributes["bid"].value = bid_attributes
        self.attributes["bid"].push()

    @override
    def receive_offer(self, offer: Offer = None) -> None:
        """
        Collect the offers from the coordinator that are addressed to this agent.
        """
        coordinator_entity = self.cb_client.get_entity_list(entity_types="Coordinator")
        if len(coordinator_entity) != 1:
            raise Exception(
                f"MarketAgent {self.agent_id} found {len(coordinator_entity)} Coordinator entities, expected 1")
        offers = coordinator_entity[0].offers.value
        # Iterate through all offers and create Offer objects for those that are addressed to this agent and not used
        for offer_attrs in offers:
            if offer_attrs["receivingAgentID"] == self.agent_id:
                if offer_attrs["used"]:
                    self.logger.info(f"Offer {offer_attrs} already used, skipping")
                    continue
                self.offer = Offer(
                    offering_agent_id=offer_attrs["offeringAgentID"],
                    receiving_agent_id=offer_attrs["receivingAgentID"],
                    prices=offer_attrs["prices"],
                    quantities=offer_attrs["quantities"],
                    buying=offer_attrs["buying"],
                    selling=offer_attrs["selling"]
                )

    @override
    def publish_counteroffer(self):
        """
        Publish the counteroffer by updating the offer attribute in the market agent entity.
        """
        offer_attributes = {
            "offeringAgentID": self.counteroffer.offering_agent_id,
            "receivingAgentID": self.counteroffer.receiving_agent_id,
            "prices": self.counteroffer.get_prices(),
            "quantities": self.counteroffer.get_quantities(),
            "buying": self.counteroffer.buying,
            "selling": self.counteroffer.selling,
            "used": False
        }
        self.attributes["offer"].value = offer_attributes
        self.attributes["offer"].push()
        self.offer = None

    @override
    def receive_trade(self, trade: Trade = None) -> None:
        """
        Collect the trades from the coordinator that are addressed to this agent.
        """
        coordinator_entity = self.cb_client.get_entity_list(entity_types="Coordinator")
        if len(coordinator_entity) != 1:
            raise Exception(f"MarketAgent {self.agent_id} found {len(coordinator_entity)} Coordinator entities, expected 1")
        trades = coordinator_entity[0].trades.value
        # Iterate through all trades and create Trade objects
        for trade_attrs in trades:
            if trade_attrs["buyer"] == self.agent_id or trade_attrs["seller"] == self.agent_id:
                if trade_attrs["used"]:
                    self.logger.info(f"Trade {trade_attrs} already used, skipping")
                    continue
                trade = Trade(
                    buyer=trade_attrs["buyer"],
                    seller=trade_attrs["seller"],
                    prices=trade_attrs["prices"],
                    quantities=trade_attrs["quantities"]
                )
                # store the trade and adjust the bid accordingly
                self.trades.append(trade)
                self.adjust_bid(trade)


    def on_connect(self, client, userdata, flags, rc) -> None:
        self.logger.info(f"Connected with result code {rc}")
        client.subscribe(self.topic)
        self.logger.info(f"Subscribed to topic {self.topic}")

    def on_message(self, client, userdata, message) -> None:
        """
        Run the corresponding method depending on the topic of the message. A notification message is sent back to the
        market controller after the method is executed.
        """
        match message.topic:
            case "/agent/submit_bid":
                self.logger.debug(f"Agent {self.agent_id}: Received message to submit bid")
                self.submit_bid()
                self.mqtt_client.publish(topic="/notification/bid", payload=f"{self.agent_id}")
            case "/agent/counteroffer":
                self.logger.debug(f"Agent {self.agent_id}: Received message to counteroffer")
                self.receive_offer()
                if self.offer is not None:
                    self.make_counteroffer()
                    self.publish_counteroffer()
                self.mqtt_client.publish(topic=f"/notification/published_offer/{self.agent_id}", qos=1)
            case "/agent/receive_trade":
                self.logger.debug(f"Agent {self.agent_id}: Received message to receive trade")
                self.receive_trade()
                self.mqtt_client.publish(topic="/notification/trade", payload=f"{self.agent_id}")
            case "/agent/grid":
                self.logger.debug(f"Agent {self.agent_id}: Received message to trade with grid")
                self.trade_with_grid()
                self.mqtt_client.publish(topic="/notification/grid", payload=f"{self.agent_id}")
            case _:
                self.logger.warning(f"Agent {self.agent_id}: Received message on unknown topic {message.topic}")

    def run(self):
        if self.stop_event is not None:
            self.mqtt_client.loop_start()
            while not self.stop_event.is_set():
                time.sleep(1)
            self.mqtt_client.loop_stop()
        else:
            self.mqtt_client.loop_forever()
