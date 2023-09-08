import abc
import threading
from core.communication import Gateway
from core.utils import \
    json_schema2context_attributes, \
    json_schema2context_entity
from abc import ABC
from requests.exceptions import HTTPError


class Device(Gateway, ABC):
    def __init__(self,
                 entity_id: str = None, entity_type: str = None,
                 # attrs_read: dict = None, attrs_write: dict = None,
                 data_model: dict = None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.health_check()

        # id and type
        self.entity_type = entity_type
        self.entity_id = entity_id

        # # attributes to be read
        # self.attrs_read = json_schema2context_attributes(attrs_read) if attrs_read else {}
        #
        # # attributes to be uploaded
        # self.attrs_write = json_schema2context_attributes(attrs_write) if attrs_write else {}

        # check entity, if not exist create one
        try:
            self.cb_client.get_entity(entity_id=self.entity_id)
        except HTTPError as err:
            if err.response.status_code == 404:
                entity = json_schema2context_entity(json_schema_dict=data_model,
                                                    entity_id=self.entity_id,
                                                    entity_type=self.entity_type)
                self.cb_client.post_entity(entity)

    # def read_attrs(self):
    #     for attr_name in self.attrs_read:
    #         self.attrs_read[attr_name].value = self.cb_client.get_attribute_value(entity_id=self.entity_id,
    #                                                                               attr_name=attr_name,
    #                                                                               entity_type=self.entity_type)
    #
    # def write_attrs(self):
    #     for attr_name in self.attrs_write:
    #         # TODO update has some problem
    #         # self.cb_client.update_attribute_value(entity_id=self.entity_id,
    #         #                                       attr_name=attr_name,
    #         #                                       value=self.attrs_read[attr_name].value)
    #         self.cb_client.update_entity_attribute(entity_id=self.entity_id,
    #                                                attr=self.attrs_read[attr_name])

    @abc.abstractmethod
    def run(self):
        """
        The calculation cycle of each module
        """
        return

    def run_in_thread(self, *args):
        """Create a new client for the topic"""
        t = threading.Thread(target=self.run, args=args)
        t.start()
