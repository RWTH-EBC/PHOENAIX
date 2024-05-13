from pydantic import ConfigDict, BaseModel
from typing import Optional
from filip.models.ngsi_v2.context import ContextEntityKeyValues


class Boiler(BaseModel):
    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)
    supplyTemperature: Optional[float] = None
    gasConsumption: Optional[float] = None
    heatingPowerSetpoint: Optional[float] = None


class BoilerFIWARE(Boiler, ContextEntityKeyValues):
    pass
