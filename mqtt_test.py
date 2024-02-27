from core.settings import settings
import paho.mqtt.client as mqtt
import time
import threading
import paho.mqtt.publish as publish


class Class1:
    def __init__(self) -> None:
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)
        
        self.topic = '/class1'
        self.mqtt_client.loop_forever()
        
    def _publish(self):
        mqtt_client = mqtt.Client()
        mqtt_client.connect(host=settings.MQTT_HOST,
                            port=settings.MQTT_PORT)
        mqtt_client.publish('/class2')
        mqtt_client.disconnect()
        
    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected {self.__class__.__name__} with result code "+str(rc))
        client.subscribe(self.topic)
        
    def on_message(self, client, userdata, msg):
        print('EBC1', flush=True)
        threading.Thread(target=self._publish).start()
        #self.mqtt_client.publish('/class2')
        print('EBC2', flush=True)
        time.sleep(5)
        print('EBC3', flush=True)
        
        
class Class2:
    def __init__(self) -> None:
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)
        
        self.topic = '/class2'
        self.mqtt_client.loop_forever()
        
    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected {self.__class__.__name__} with result code "+str(rc))
        client.subscribe(self.topic)
        
    def on_message(self, client, userdata, msg):
        print('Hello')
        
class Class3:
    def __init__(self) -> None:
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(host=settings.MQTT_HOST,
                                 port=settings.MQTT_PORT)
        
        self.topic = '/class3'
        self.mqtt_client.loop_forever()
        
        
    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected {self.__class__.__name__} with result code "+str(rc))
        client.subscribe(self.topic)
        
    def on_message(self, client, userdata, msg):
        print('Test', flush=True)
        
        
        
if __name__ == '__main__':
    def run_cl1():
        cl1 = Class1()
        
    def run_cl2():
        cl2 = Class2()
        
    def run_cl3():
        cl3 = Class3()
        
    threading.Thread(target=run_cl1).start()
    time.sleep(0.1)
    threading.Thread(target=run_cl2).start()
    time.sleep(0.1)

    publish.single(topic='/class1',
                   hostname=settings.MQTT_HOST,
                   port=settings.MQTT_PORT)
    # time.sleep(2)
    # publish.single(topic='/class2',
    #                hostname=settings.MQTT_HOST,
    #                port=settings.MQTT_PORT)
    
    
        
        

