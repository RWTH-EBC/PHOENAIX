from core.data_models import Device
from typing import Any
from filip.models.ngsi_v2.timeseries import TimeSeries
from filip.models.ngsi_v2.base import NamedMetadata
from filip.models.ngsi_v2.context import NamedContextAttribute


class Attribute:
    def __init__(self, 
                 device: Device, 
                 name: str, 
                 initial_value: Any = None,
                 is_array: bool = False):
        self.device = device
        self.name = name
        self.value = initial_value
        self.is_array = is_array

    def pull_history(self, **kwargs) -> TimeSeries:
        """
        Pull the last n timeseries data in this scenario

        Args:
            last_n (int): Request only the last N values.
        """
        return self.device.ql_client.get_entity_attr_by_id(entity_id=self.device.entity_id,
                                                           attr_name=self.name,
                                                           **kwargs)

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

    def push(self, 
             timestamp: str = None):
        """
        Push data to fiware

        Args:
            timestamp: timestamp in ISO8601 format
        """
        metadata = NamedMetadata(
            name="TimeInstant",
            value=timestamp,
            type="DateTime"
        )
        # self.device.cb_client.update_attribute_value(
        #     entity_id=self.device.entity_id,
        #     entity_type=self.device.entity_type,
        #     attr_name=self.name,
        #     value=self.value
        # )
        
        if self.is_array:            
            attribute = NamedContextAttribute(
                name=self.name,
                # TODO solution
                type="Array",
                value=self.value
            )
        else:
            attribute = NamedContextAttribute(
                name=self.name,
                # TODO solution
                type="Number",
                value=self.value,
                metadata=metadata
            )          
        self.device.cb_client.update_entity_attribute(
            entity_id=self.device.entity_id,
            entity_type=self.device.entity_type,
            attr=attribute
        )
