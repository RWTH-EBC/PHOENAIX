from filip.models.base import DataType, FiwareHeader
from filip.models.ngsi_v2.context import NamedContextAttribute, ContextEntity
from filip.utils.cleanup import clear_context_broker
from core.settings import settings

JSONSchemaMap = {
    "string": DataType.TEXT.value,
    "number": DataType.NUMBER.value,
    "integer": DataType.INTEGER.value,
    "object": DataType.STRUCTUREDVALUE.value,
    "array": DataType.ARRAY.value,
    "boolean": DataType.BOOLEAN.value
}


def json_schema2context_attributes(json_schema_dict: dict):
    attrs_dict = {}
    for attr_name in json_schema_dict:
        attrs_dict[attr_name] = NamedContextAttribute(name=attr_name,
                                                      type=JSONSchemaMap[
                                                          json_schema_dict[attr_name]["type"]
                                                      ])
    return attrs_dict


def json_schema2context_entity(json_schema_dict: dict,
                               entity_id: str,
                               entity_type: str):
    entity = ContextEntity(id=entity_id, type=entity_type)

    json_schema_dict_attrs: dict = json_schema_dict["properties"]
    json_schema_dict_attrs.pop("id")
    json_schema_dict_attrs.pop("type")

    attrs_dict = json_schema2context_attributes(json_schema_dict_attrs)
    attrs = [attrs_dict[attr_name] for attr_name in attrs_dict]

    entity.add_attributes(attrs)

    return entity


def clean_up():
    """
    Clean up all the entities/registrations/subscriptions for this scenario
    """
    service = settings.SCENARIO_NAME
    clear_context_broker(url=settings.CB_URL,
                         fiware_header=FiwareHeader(service=service, service_path="/"))
