from filip.models.base import DataType
from filip.models.ngsi_v2.context import NamedContextAttribute

JSONSchemaMap = {
    "string": DataType.TEXT.value,
    "number": DataType.NUMBER.value,
    "integer": DataType.INTEGER.value,
    "object": DataType.STRUCTUREDVALUE.value,
    "array": DataType.ARRAY.value,
    "boolean": DataType.BOOLEAN.value
}


def json_schema2fiware(json_schema_dict: dict):
    fiware_dict = {}
    for attr_name in json_schema_dict:
        fiware_dict[attr_name] = NamedContextAttribute(name=attr_name,
                                                       type=JSONSchemaMap[
                                                           json_schema_dict[attr_name]["type"]
                                                       ])
    return fiware_dict

