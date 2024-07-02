import paho.mqtt.publish as publish
from deq_demonstrator.settings import settings

def start():
    publish.single(topic='/mpc',
                   hostname=settings.MQTT_HOST,
                   port=settings.MQTT_PORT)
    
if __name__ == '__main__':
    start()    

