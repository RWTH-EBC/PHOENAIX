from core.data_models import Device
from typing import Any


class Attribute:
    def __init__(self, device: Device, name: str, initial_value: Any = None):
        self.device = device
        self.name = name
        self.value = initial_value

    def pull(self):
        """
        Pull data from fiware
        """
        # TODO add error handling
        self.value = self.device.cb_client.get_attribute_value(
            entity_id=self.device.entity_id,
            entity_type=self.device.entity_type,
            attr_name=self.name
        )

    def push(self):
        """
        Push data to fiware
        """
        self.device.cb_client.update_attribute_value(
            entity_id=self.device.entity_id,
            entity_type=self.device.entity_type,
            attr_name=self.name,
            value=self.value
        )
