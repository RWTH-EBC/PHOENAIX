import abc
import threading
from core.communication import Gateway, subscription_template
from core.utils import \
    json_schema2context_attributes, \
    json_schema2context_entity
from abc import ABC
from requests.exceptions import HTTPError
from filip.models.ngsi_v2.subscriptions import Subscription


class Device(Gateway, ABC):
    def __init__(self,
                 entity_id: str = None, entity_type: str = None,
                 # attrs_read: dict = None, attrs_write: dict = None,
                 data_model: dict = None,
                 save_history: bool = False,
                 *args, **kwargs):
        """
        Abstract device that interchange data with orion context broker.

        Args:
            entity_id: id of context entity
            entity_type: type of context entity
            data_model: dictionary of the json-schema
            save_history: flag to save the history data. default: False
            *args:
            **kwargs:
        """
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

        if save_history:
            subscription = subscription_template.copy()
            subscription["subject"]["entities"][0]["id"] = self.entity_id
            subscription["subject"]["entities"][0]["type"] = self.entity_type
            self.cb_client.post_subscription(subscription=Subscription(**subscription))


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
        t = threading.Thread(target=self.run, daemon=True, args=args)
        t.start()
