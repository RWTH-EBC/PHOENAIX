from pydantic import ConfigDict, BaseModel
from filip.models.ngsi_v2.context import ContextEntityKeyValues


class TemperatureSensor(BaseModel):
    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)
    temperature: float


class TemperatureSensorFIWARE(TemperatureSensor, ContextEntityKeyValues):
    pass
