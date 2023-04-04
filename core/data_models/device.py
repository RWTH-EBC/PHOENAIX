from core.communication import Gateway
from core.utils import json_schema2fiware


class Device(Gateway):
    def __init__(self,
                 entity_id: str, entity_type: str,
                 attrs_read: dict = None, attrs_write: dict = None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.health_check()

        # id and type
        self.entity_type = entity_type
        self.entity_id = entity_id

        # attributes to be read
        self.attrs_read = json_schema2fiware(attrs_read) if attrs_read else {}

        # attributes to be uploaded
        self.attrs_write = json_schema2fiware(attrs_write) if attrs_write else {}

    def read_attrs(self):
        for attr_name in self.attrs_read:
            self.attrs_read[attr_name].value = self.cb_client.get_attribute_value(entity_id=self.entity_id,
                                                                                  attr_name=attr_name,
                                                                                  entity_type=self.entity_type)

    def write_attrs(self):
        for attr_name in self.attrs_write:
            self.cb_client.update_attribute_value(entity_id=self.entity_id,
                                                  attr_name=self.attrs_read[attr_name],
                                                  value=self.attrs_read[attr_name].value)
