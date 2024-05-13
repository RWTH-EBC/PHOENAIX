from pydantic import ConfigDict, BaseModel
from typing import Optional
from filip.models.ngsi_v2.context import ContextEntityKeyValues


class ThermalEnergyStorage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)
    temperatureUpper: Optional[float] = None
    temperatureMiddle: Optional[float] = None
    temperatureLower: Optional[float] = None
    stateOfCharge: Optional[float] = None


class ThermalEnergyStorageFIWARE(ThermalEnergyStorage, ContextEntityKeyValues):
    pass
