import copy
import threading
import time
from pathlib import Path
import pickle
import json

from deq_demonstrator.market.coordinator_fiware import CoordinatorFiware
from deq_demonstrator.market.building_fiware import BuildingFiware
from deq_demonstrator.market.market_controller import MarketController

from deq_demonstrator.utils.fiware_utils import clean_up
from deq_demonstrator.config import ROOT_DIR

def run_coordinator(building_ids, stop_event):
    schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / \
                  'schema' / 'Coordinator.json'
    with open(schema_path) as f:
        data_model = json.load(f)

    coordinator = CoordinatorFiware(
        building_ids=building_ids,
        entity_id="Coordinator:DEQ:MVP:000",
        entity_type="Coordinator",
        building_ix=0,
        data_model=copy.deepcopy(data_model),
        stop_event=stop_event
    )
    coordinator.run()

def run_buildings(stop_event, building_ix, nodes):
    schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / \
                  'schema' / 'MarketAgent.json'
    with open(schema_path) as f:
        data_model = json.load(f)

    building = BuildingFiware(
        building_id=building_ix,
        nodes=nodes,
        entity_id=f"Building:DEQ:MVP:{building_ix}",
        entity_type="Building",
        building_ix=building_ix,
        stop_event=stop_event,
        data_model=copy.deepcopy(data_model),
    )
    building.run()

def run_controller(building_ids, stop_event):
    controller = MarketController(ids=building_ids, stop_event=stop_event)
    controller.run()

def main():
    clean_up()

    stop_event = threading.Event()
    building_ids = list(range(6))

    threads = []
    t = threading.Thread(target=run_coordinator, args=[building_ids, stop_event], name="coordinator")
    threads.append(t)
    t.start()

    print("Started coordinator")

    input_data_path = Path(__file__).parents[1] / 'data' / '01_input'

    with open(input_data_path / '06_building_nodes' / 'nodes_test_scenario_1.p', 'rb') as f:
        nodes = pickle.load(f)


    for building_ix in building_ids:
        t = threading.Thread(target=run_buildings, args=[stop_event, building_ix, nodes[building_ix]],
                             name=f"building_{building_ix}")
        threads.append(t)
        t.start()

    print("Started buildings")

    t = threading.Thread(target=run_controller, args=[building_ids, stop_event], name="controller")
    threads.append(t)
    t.start()

    print("Started controller")

    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print("KeyboadInterrupt received, stopping threads...")
            stop_event.set()
            break

    for t in threads:
        t.join()


if __name__ == '__main__':
    main()