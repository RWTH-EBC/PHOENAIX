import requests
from filip.clients.ngsi_v2.cb import ContextBrokerClient
from deq_demonstrator.settings import settings


s = requests.Session()
cb_client = ContextBrokerClient(url=settings.CB_URL, fiware_header=settings.fiware_header, session=s)