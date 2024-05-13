import json
from pydantic import ConfigDict, BaseModel
from filip.models.ngsi_v2.context import ContextEntityKeyValues


class WeatherStation(BaseModel):
    model_config = ConfigDict(populate_by_name=True,
                              coerce_numbers_to_str=True)  # Pydantic specific settings
    temperature: float = None
    solarDirectRadiation: float = None
    solarDiffuseRadiation: float = None
    cloudCover: int = None


class WeatherStationFIWARE(WeatherStation, ContextEntityKeyValues):
    pass
#
#
# weather_station_schema = WeatherStation.model_json_schema()
# with open("./weather_station_schema.json", "w") as f:
#     json.dump(weather_station_schema, f, indent=2)
#
# weather_station_fiware_schema = WeatherStationFIWARE.model_json_schema()
# with open("./weather_station_fiware_schema.json", "w") as f:
#     json.dump(weather_station_fiware_schema, f, indent=2)
