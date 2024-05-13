from pydantic import ConfigDict, BaseModel
from typing import Optional
from filip.models.ngsi_v2.context import ContextEntityKeyValues


class MPC(BaseModel):
    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)
    relativePower1: Optional[float] = None
    relativePower2: Optional[float] = None
    relativePower3: Optional[float] = None
    SOCpred1: Optional[float] = None
    SOCpred2: Optional[float] = None
    SOCpred3: Optional[float] = None


class MPCFIWARE(MPC, ContextEntityKeyValues):
    pass
