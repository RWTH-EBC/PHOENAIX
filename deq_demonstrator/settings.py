from pydantic import Field, AnyUrl
from pydantic_settings import BaseSettings
from dotenv import find_dotenv
from filip.models.base import FiwareHeader
from deq_demonstrator.config import ROOT_DIR
from pathlib import Path


class Settings(BaseSettings):
    # MQTT settings
    MQTT_HOST: str = Field(env="MQTT_HOST", default="localhost")
    MQTT_PORT: int = Field(env="MQTT_PORT", default=1883)
    MQTT_USER: str = Field(env="MQTT_USER", default="")
    MQTT_PASSWORD: str = Field(env="MQTT_PASSWORD", default="")
    MQTT_TLS: bool = Field(env="MQTT_TLS", default=False)

    # FIWARE settings
    CB_URL: AnyUrl = Field(env="CB_URL", default="http://localhost:1026")
    QL_URL: AnyUrl = Field(env="QL_URL", default="http://localhost:8668")
    IOTA_URL: AnyUrl = Field(env="IOTA_URL", default="http://localhost:4041")

    # Test scenario settings
    # TODO what else setting should be define here?
    SCENARIO_NAME: str = Field(env="SCENARIO_NAME")
    N_HORIZON: int = Field(env='N_HORIZON')
    TIMESTEP: int = Field(env='TIMESTEP')
    NORM_POWER: int = Field(env='NORM_POWER')
    CYCLE_TIME: int = Field(env='CYCLE_TIME')

    @property
    def fiware_header(self):
        return FiwareHeader(service=self.SCENARIO_NAME.strip().lower(),
                            service_path="/")

    class Config:
        case_sensitive = False
        env_file = find_dotenv(ROOT_DIR / '.env')
        env_file_encoding = "utf-8"


settings = Settings()
