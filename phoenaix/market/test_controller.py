import pytest
from phoenaix.market.market_controller import MarketController
import threading

def test_init():
    controller = MarketController(building_ids=["0", "1", "2"], stop_event=threading.Event())
    controller.run()
    assert controller is not None
    assert controller.mqtt_client_controller is not None
    assert controller.mqtt_client_notification_handler is not None
    controller.stop_event.set()