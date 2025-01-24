import pytest
import json
from deq_demonstrator.market.coordinator import CoordinatorFiware
from deq_demonstrator.config import ROOT_DIR

@pytest.fixture
def coordinator():
    schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / \
                  'schema' / 'Coordinator.json'
    with open(schema_path) as f:
        data_model = json.load(f)

    return CoordinatorFiware(result_handler=None,
        entity_id="Coordinator:DEQ:MVP:000",
        entity_type="Coordinator",
        building_ix=0,
        data_model=data_model
    )

def test_init(coordinator):
    assert coordinator is not None

def test_collect_bids(coordinator):
    bid = coordinator.collect_bids()
    assert bid is not None