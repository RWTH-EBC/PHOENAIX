import copy
import threading
import time
import pickle
import json

from deq_demonstrator.market.coordinator_fiware import CoordinatorFiware
from deq_demonstrator.market.building_fiware import BuildingFiware
from deq_demonstrator.market.market_controller import MarketController

from deq_demonstrator.utils.fiware_utils import clean_up
from deq_demonstrator.config import ROOT_DIR


def run_coordinator(building_ids, stop_event):
    """
    Set up the coordinator.
    """
    # load the data model schema for the coordinator
    schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / 'schema' / 'Coordinator.json'
    with open(schema_path) as f:
        data_model = json.load(f)

    # create the coordinator
    coordinator = CoordinatorFiware(
        building_ids=building_ids, # list of all building ids required for communication
        entity_id="Coordinator:DEQ:MVP:000",
        entity_type="Coordinator",
        building_ix=0,
        data_model=copy.deepcopy(data_model),
        stop_event=stop_event
    )
    coordinator.run()


def run_buildings(stop_event, building_ix, nodes):
    """
    Set up the building.
    """
    # load the data model schema for the building
    schema_path = ROOT_DIR / 'deq_demonstrator' / 'data_models' / 'schema' / 'MarketAgent.json'
    with open(schema_path) as f:
        data_model = json.load(f)

    # create the building
    building = BuildingFiware(
        building_id=building_ix,
        nodes=nodes,
        entity_id=f"MarketAgent:DEQ:MVP:{building_ix}",
        entity_type="MarketAgent",
        building_ix=building_ix,
        stop_event=stop_event,
        data_model=copy.deepcopy(data_model),
    )
    building.run()


def run_controller(building_ids, stop_event):
    """
    Set up the market controller.
    """
    # create the market controller
    controller = MarketController(building_ids=building_ids, stop_event=stop_event)
    controller.run()


def set_up(stop_event):
    """
    Set up the environment with all the necessary components.
    Each component is run in a separate thread. The threads are started and returned.
    """
    # clear the FIWARE context broker and quantumleap
    clean_up()

    building_ids = list(range(9))

    # list with all threads
    threads = []

    # set up the coordinator
    t = threading.Thread(target=run_coordinator, args=[building_ids, stop_event], name="coordinator")
    threads.append(t)
    t.start()
    print("Started coordinator")

    # load the nodes with the building data
    with open(ROOT_DIR / 'data' / '01_input' / '06_building_nodes' / 'test_nodes.p', 'rb') as f:
        nodes = pickle.load(f)

    # set up the buildings
    for building_ix in building_ids:
        t = threading.Thread(target=run_buildings, args=[stop_event, building_ix, nodes[building_ix]],
                             name=f"building_{building_ix}")
        threads.append(t)
        t.start()
        time.sleep(2)
    print("Started buildings")

    # set up the market controller
    t = threading.Thread(target=run_controller, args=[building_ids, stop_event], name="controller")
    threads.append(t)
    t.start()
    print("Started controller")

    return threads


def main():
    """
    Main function to set up and run the market.
    """
    # create a stop event to signal all threads to stop
    stop_event = threading.Event()
    # set up all components
    threads = set_up(stop_event=stop_event)

    time.sleep(1)  # wait for all components to start
    print("All components started. \n"
          "Send a MQTT message to /controller/start to start the market. \n"
          "Stop the market by sending a message to /controller/stop.")

    # loop to keep the main thread alive, stopping all threads when a KeyboardInterrupt is received or stop_event is set
    while not stop_event.is_set():
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
