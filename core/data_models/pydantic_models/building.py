from pydantic import ConfigDict, BaseModel
from typing import List, Optional
from filip.models.ngsi_v2.context import ContextEntityKeyValues


class Building(BaseModel):
    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)
    electricityConsumption: Optional[float] = None
    gasConsumption: Optional[float] = None
    residualPower: Optional[float] = None
    demandPrediction: Optional[List] = None


class BuildingFIWARE(Building, ContextEntityKeyValues):
    pass
