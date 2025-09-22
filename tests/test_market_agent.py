import pytest
from unittest.mock import patch
import json
import copy
from phoenaix.market.building_fiware import BuildingFiware
from local_energy_market.classes import BlockBid, BidFragment, Offer
from tests.input_data import nodes_basic
from phoenaix.config import ROOT_DIR
from phoenaix.utils.fiware_utils import clean_up
import requests
from filip.clients.ngsi_v2.cb import ContextBrokerClient
from phoenaix.settings import settings
from filip.models.ngsi_v2.context import NamedContextAttribute, ContextEntity

@pytest.fixture
def cb_client():
    s = requests.Session()
    return ContextBrokerClient(url=settings.CB_URL, fiware_header=settings.fiware_header, session=s)

@pytest.fixture
def market_agent():
    schema_path = ROOT_DIR / 'phoenaix' / 'data_models' / \
                  'schema' / 'MarketAgent.json'
    with open(schema_path) as f:
        data_model = json.load(f)

    building = BuildingFiware(
        building_id=0,
        nodes=nodes_basic,
        entity_id=f"Building:DEQ:MVP:0",
        entity_type="Building",
        building_ix=0,
        stop_event=None,
        data_model=copy.deepcopy(data_model)
    )
    return building.get_agent()

@pytest.fixture(autouse=True)
def clean(request):
    clean_up()
    request.addfinalizer(clean_up)

def test_init(market_agent):
    assert market_agent is not None
    assert market_agent.agent_id == 0

def test_submit_bid(market_agent, cb_client):
    bid_fragments = [BidFragment(price=0.1, quantity=1, buying=True, selling=False),
                     BidFragment(price=0.2, quantity=2, buying=True, selling=False),
                     BidFragment(price=0.3, quantity=3, buying=True, selling=False)]

    bid = BlockBid(agent_id=0)
    for fragment in bid_fragments:
        bid.add_bid_fragment(fragment)
    bid.set_flex_energy(0.5)
    market_agent.bid = bid
    market_agent.submit_bid()
    assert market_agent is not None

    bid_entity = cb_client.get_entity_attributes(entity_id="Bid:DEQ:MVP:0")
    assert bid_entity["prices"].value == [0.1, 0.2, 0.3]
    assert bid_entity["quantities"].value == [1, 2, 3]
    assert bid_entity["buying"].value == True
    assert bid_entity["selling"].value == False

    bid_fragments = [BidFragment(price=0.2, quantity=2, buying=False, selling=True),
                     BidFragment(price=0.3, quantity=3, buying=False, selling=True),
                     BidFragment(price=0.4, quantity=4, buying=False, selling=True)]

    bid = BlockBid(agent_id=0)
    for fragment in bid_fragments:
        bid.add_bid_fragment(fragment)
    bid.set_flex_energy(0.4)
    market_agent.bid = bid
    market_agent.submit_bid()
    assert market_agent is not None
    bid_entity = cb_client.get_entity_attributes(entity_id="Bid:DEQ:MVP:0")
    assert bid_entity["prices"].value == [0.2, 0.3, 0.4]
    assert bid_entity["quantities"].value == [2, 3, 4]
    assert bid_entity["buying"].value == False
    assert bid_entity["selling"].value == True

def test_receive_offer(market_agent, cb_client):
    data = {
        "id": "Offer:DEQ:MVP:C:0",
        "type": "Offer",
        "prices": {"type": "array", "value": [0.1, 0.2, 0.3]},
        "quantities": {"type": "array", "value": [1.1, 2.2, 3.3]},
        "buying": {"type": "boolean", "value": True},
        "selling": {"type": "boolean", "value": False},
        "offeringAgentID": {"type": "number", "value": "1"},
        "receivingAgentID": {"type": "number", "value": "0"}
    }
    bid = ContextEntity(**data)
    cb_client.post_entity(bid)
    market_agent.receive_offer()
    offer_entities = cb_client.get_entity_list(type_pattern="Offer")
    assert market_agent.offer is not None
    assert market_agent.offer.offering_agent_id == 1
    assert market_agent.offer.receiving_agent_id == 0
    assert market_agent.offer.get_prices() == [0.1, 0.2, 0.3]
    assert market_agent.offer.get_quantities() == [1.1, 2.2, 3.3]
    assert market_agent.offer.buying == True
    assert market_agent.offer.selling == False
    assert len(offer_entities) == 0

def test_publish_counteroffer(market_agent):
    clean_up()
    market_agent.counteroffer = Offer(offering_agent_id=0, receiving_agent_id=1,
                                      quantities=[1.1, 2.2, 3.3], prices=[0.1, 0.2, 0.3],
                                      buying=True, selling=False)
    market_agent.publish_counteroffer()

def test_receive_trade(market_agent, cb_client):
    data = {
        "id": "Trade:DEQ:MVP:1:0",
        "type": "Trade",
        "prices": {"type": "array", "value": [0.1, 0.2, 0.3]},
        "quantities": {"type": "array", "value": [1.1, 2.2, 3.3]},
        "buyer": {"type": "number", "value": 1},
        "seller": {"type": "number", "value": 0}
    }
    trade = ContextEntity(**data)
    cb_client.post_entity(trade)
    bid_fragments = [BidFragment(price=0.1, quantity=2, buying=False, selling=True),
                     BidFragment(price=0.2, quantity=4, buying=False, selling=True),
                     BidFragment(price=0.3, quantity=4, buying=False, selling=True)]

    bid = BlockBid(agent_id=0)
    for fragment in bid_fragments:
        bid.add_bid_fragment(fragment)
    bid.set_flex_energy(0.5)
    market_agent.bid = bid

    with patch.object(market_agent, 'adjust_bid', return_value=None):
        market_agent.receive_trade()
    assert len(market_agent.trades) == 1
    assert market_agent.trades[0].buyer == 1
    assert market_agent.trades[0].seller == 0
    assert market_agent.trades[0].prices == [0.1, 0.2, 0.3]
    assert market_agent.trades[0].quantities == [1.1, 2.2, 3.3]