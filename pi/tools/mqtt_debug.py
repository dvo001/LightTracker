#!/usr/bin/env python3
import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc):
    print('connected', rc)
    client.subscribe('dev/+/#')

def on_message(client, userdata, msg):
    print(msg.topic, msg.payload.decode())

c = mqtt.Client()
c.on_connect = on_connect
c.on_message = on_message
c.connect('localhost',1883)
c.loop_forever()
