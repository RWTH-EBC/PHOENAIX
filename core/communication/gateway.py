from filip.clients.ngsi_v2.iota import IoTAClient
from filip.clients.ngsi_v2.cb import ContextBrokerClient
from filip.clients.ngsi_v2.quantumleap import QuantumLeapClient
from paho.mqtt.client import MQTTv5, Client, MQTT_CLEAN_START_FIRST_ONLY
import requests
from core.settings import settings


class Gateway:
    def __init__(self,
                 entity_type: str = None,
                 entity_id: str = None,
                 *args, **kwargs):
        # MQTT client
        self.mqtt_client = Client(protocol=MQTTv5)
        if settings.MQTT_USER:
            self.mqtt_client.username_pw_set(username=settings.MQTT_USER, password=settings.MQTT_PASSWORD)
        if settings.MQTT_TLS:
            self.mqtt_client.tls_set()
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT,
                                 clean_start=MQTT_CLEAN_START_FIRST_ONLY
                                 )

        # Fiware header
        # TODO any other restriction?
        self.scenario_name = settings.SCENARIO_NAME

        # TODO each gateway one client?
        # IoTAgent Client
        s1 = requests.Session()
        self.iota_client = IoTAClient(url=settings.IOTA_URL, fiware_header=settings.fiware_header, session=s1)

        # CB Client
        s2 = requests.Session()
        self.cb_client = ContextBrokerClient(url=settings.CB_URL, fiware_header=settings.fiware_header, session=s2)

        # QL Client
        s3 = requests.Session()
        self.ql_client = QuantumLeapClient(url=settings.QL_URL, fiware_header=settings.fiware_header, session=s3)

    def health_check(self):
        self.mqtt_client.publish(topic="health/check", payload="health check")
        self.cb_client.get_version()
        self.iota_client.get_version()
        self.ql_client.get_version()


if __name__ == '__main__':
    gateway = Gateway()
    gateway.health_check()
