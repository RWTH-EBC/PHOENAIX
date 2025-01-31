import pytest
from deq_demonstrator.market.building_fiware import BuildingFiware
from tests.input_data import nodes_basic
from deq_demonstrator.config import ROOT_DIR
import copy
import json

@pytest.fixture
def building():
    schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / \
                  'schema' / 'MarketAgent.json'
    with open(schema_path) as f:
        data_model = json.load(f)
    return BuildingFiware(
        building_id=0,
        nodes=nodes_basic,
        entity_id=f"Building:DEQ:MVP:0",
        entity_type="Building",
        building_ix=0,
        stop_event=None,
        data_model=copy.deepcopy(data_model),
    )

def test_init(building):
    assert building.building_id == 0
    assert building.nodes is not None
    assert building.market_agent.agent_id == 0
    assert building.market_agent.building == building
    assert building.cb_client is not None