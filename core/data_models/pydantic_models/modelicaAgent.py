from pydantic import ConfigDict, BaseModel
from typing import Optional, List
from filip.models.ngsi_v2.context import ContextEntityKeyValues


class ModelicaAgent(BaseModel):
    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)
    thermalDemand0: Optional[float] = None
    thermalDemand1: Optional[float] = None
    thermalDemand2: Optional[float] = None
    thermalDemand3: Optional[float] = None
    thermalDemand4: Optional[float] = None
    thermalDemand0_prev: Optional[List] = None
    thermalDemand1_prev: Optional[List] = None
    thermalDemand2_prev: Optional[List] = None
    thermalDemand3_prev: Optional[List] = None
    thermalDemand4_prev: Optional[List] = None
    sinTime: Optional[List] = None
    SOC1: Optional[float] = None
    SOC2: Optional[float] = None
    SOC3: Optional[float] = None


class ModelicaAgentFIWARE(ModelicaAgent, ContextEntityKeyValues):
    pass
