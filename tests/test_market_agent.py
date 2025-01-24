import pytest
import json
import copy
from deq_demonstrator.market.building import BuildingFiware
from local_energy_market.classes import BlockBid, BidFragment
from tests.input_data import nodes_basic
from deq_demonstrator.config import ROOT_DIR


@pytest.fixture
def market_agent():
    schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / \
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

def test_init(market_agent):
    assert market_agent is not None
    assert market_agent.agent_id == 0

def test_submit_bid(market_agent):
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