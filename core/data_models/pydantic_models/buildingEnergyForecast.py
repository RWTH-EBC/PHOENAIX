from pydantic import ConfigDict, BaseModel
from typing import List, Optional
from filip.models.ngsi_v2.context import ContextEntityKeyValues


class BuildingEnergyForecast(BaseModel):
    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)
    electricityDemand: Optional[List] = None
    heatingDemand: Optional[List] = None
    coolingDemand: Optional[List] = None
    dhwDemand: Optional[List] = None
    pvPower: Optional[List] = None
    horizon: Optional[float] = None


class BuildingEnergyForecastFIWARE(BuildingEnergyForecast, ContextEntityKeyValues):
    pass
