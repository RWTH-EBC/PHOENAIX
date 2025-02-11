import pytest
import json
from deq_demonstrator.market.coordinator_fiware import CoordinatorFiware
from deq_demonstrator.config import ROOT_DIR
from deq_demonstrator.utils.fiware_utils import clean_up
from local_energy_market.classes import Offer, Trade
import requests
from filip.clients.ngsi_v2.cb import ContextBrokerClient
from deq_demonstrator.settings import settings
from filip.models.ngsi_v2.context import NamedContextAttribute, ContextEntity
import numpy as np
import paho.mqtt.client as mqtt
import threading

@pytest.fixture(autouse=True)
def clean(request):
    clean_up()
    request.addfinalizer(clean_up)

@pytest.fixture
def cb_client():
    s = requests.Session()
    return ContextBrokerClient(url=settings.CB_URL, fiware_header=settings.fiware_header, session=s)

@pytest.fixture
def mock_agent_mqtt_client():
    class MockAgentMqttClient:
        def __init__(self):
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_message = self.on_message
            self.mqtt_client.connect(host=settings.MQTT_HOST,
                                     port=settings.MQTT_PORT)
            self.topic = "/agent/#"
            self.mqtt_client.loop_start()
        def on_connect(self, client, userdata, flags, rc):
            client.subscribe(self.topic)
        def on_message(self, client, userdata, message):
            if message.topic == "/agent/counteroffer":
                self.mqtt_client.publish("/coordinator/published_offer/1")
                self.mqtt_client.publish("/coordinator/published_offer/2")
    return MockAgentMqttClient()

@pytest.fixture
def coordinator():
    schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / \
                  'schema' / 'Coordinator.json'
    with open(schema_path) as f:
        data_model = json.load(f)

    coordinator = CoordinatorFiware(result_handler=None,
        entity_id="Coordinator:DEQ:MVP:000",
        entity_type="Coordinator",
        building_ix="C",
        data_model=data_model,
        stop_event=threading.Event()
    )

    coordinator.run()
    return coordinator

def test_init(coordinator):
    assert coordinator is not None

def test_collect_bids(cb_client, coordinator):
    data = {
        "id": "Bid:DEQ:MVP:001",
        "type": "Bid",
        "prices": {"type": "array", "value": [0.1, 0.2, 0.3]},
        "quantities": {"type": "array", "value": [1.1, 2.2, 3.3]},
        "meanPrice": {"type": "number", "value": 0.2},
        "totalQuantity": {"type": "number", "value": 6.6},
        "buying": {"type": "boolean", "value": True},
        "selling": {"type": "boolean", "value": False},
        "flexEnergy": {"type": "number", "value": 0.5}
    }
    bid = ContextEntity(**data)
    cb_client.post_entity(bid)
    coordinator.collect_bids()
    bids = coordinator.submitted_bids
    assert bids[0].agent_id == "Bid:DEQ:MVP:001"
    assert bids[0].get_prices() == [0.1, 0.2, 0.3]
    assert bids[0].get_quantities() == [1.1, 2.2, 3.3]
    assert np.isclose(bids[0].mean_price, 0.2)
    assert np.isclose(bids[0].total_quantity, 6.6)
    assert bids[0].buying == True
    assert bids[0].selling == False
    assert bids[0].flex_energy == 0.5

def test_publish_offers(coordinator, cb_client):
    offer1 = Offer(offering_agent_id=1, receiving_agent_id=2, quantities=[1.1, 2.2, 3.3], prices=[0.1, 0.2, 0.3], buying=True, selling=False)
    offer2 = Offer(offering_agent_id=3, receiving_agent_id=4, quantities=[1.1, 2.2, 3.3], prices=[0.1, 0.2, 0.3], buying=False, selling=True)
    offers = [offer1, offer2]
    coordinator.publish_offers(offers)

    entities = cb_client.get_entity_list(type_pattern="Offer")
    assert len(entities) == 2
    assert entities[0].id == "Offer:DEQ:MVP:C:2"
    assert entities[1].id == "Offer:DEQ:MVP:C:4"
    entity_offer1 = cb_client.get_entity_attributes(entity_id="Offer:DEQ:MVP:C:2")
    entity_offer2 = cb_client.get_entity_attributes(entity_id="Offer:DEQ:MVP:C:4")

    assert entity_offer1["prices"].value == [0.1, 0.2, 0.3]
    assert entity_offer1["quantities"].value == [1.1, 2.2, 3.3]
    assert entity_offer1["buying"].value == True
    assert entity_offer1["selling"].value == False
    assert entity_offer1["offeringAgentID"].value == 1
    assert entity_offer1["receivingAgentID"].value == 2

    assert entity_offer2["prices"].value == [0.1, 0.2, 0.3]
    assert entity_offer2["quantities"].value == [1.1, 2.2, 3.3]
    assert entity_offer2["buying"].value == False
    assert entity_offer2["selling"].value == True
    assert entity_offer2["offeringAgentID"].value == 3
    assert entity_offer2["receivingAgentID"].value == 4

def test_publish_trades(coordinator, cb_client):
    trade1 = Trade(buyer=1, seller=2, quantities=[1.1, 2.2, 3.3], prices=[0.1, 0.2, 0.3])
    trade2 = Trade(buyer=3, seller=4, quantities=[1.1, 2.2, 3.3], prices=[0.1, 0.2, 0.3])
    coordinator.trades = [trade1, trade2]
    coordinator.publish_trades()

    entities = cb_client.get_entity_list(type_pattern="Trade")
    assert len(entities) == 2
    assert entities[0].id == "Trade:DEQ:MVP:2:1"
    assert entities[1].id == "Trade:DEQ:MVP:4:3"

    entity_trade1 = cb_client.get_entity_attributes(entity_id="Trade:DEQ:MVP:2:1")
    entity_trade2 = cb_client.get_entity_attributes(entity_id="Trade:DEQ:MVP:4:3")

    assert entity_trade1["prices"].value == [0.1, 0.2, 0.3]
    assert entity_trade1["quantities"].value == [1.1, 2.2, 3.3]
    assert entity_trade1["buyer"].value == 1
    assert entity_trade1["seller"].value == 2

    assert entity_trade2["prices"].value == [0.1, 0.2, 0.3]
    assert entity_trade2["quantities"].value == [1.1, 2.2, 3.3]
    assert entity_trade2["buyer"].value == 3
    assert entity_trade2["seller"].value == 4

def test_publish_offers_and_receive_counteroffers(coordinator, cb_client, mock_agent_mqtt_client):
    offer1 = Offer(offering_agent_id=3, receiving_agent_id=1, quantities=[1.1, 2.2, 3.3], prices=[0.1, 0.2, 0.3],
                   buying=True, selling=False)
    offer2 = Offer(offering_agent_id=4, receiving_agent_id=2, quantities=[1.1, 2.2, 3.3], prices=[0.1, 0.2, 0.3],
                   buying=False, selling=True)
    offers = [offer1, offer2]

    returned_offers = coordinator.publish_offers_and_receive_counteroffers(offers)
    mock_agent_mqtt_client.mqtt_client.loop_stop()
    coordinator.stop_event.set()

    assert len(returned_offers) == 2

