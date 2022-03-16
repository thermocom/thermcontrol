#!/usr/bin/python3
import sys
import time
import datetime
import json
import logging

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

_values = {}
_client = None

def _on_message(client, userdata, message):
    logger.debug("topic %s qos %s retain %s payload %s", 
                 message.topic, message.qos, message.retain, message.payload.decode("utf-8"))
    global _values
    _values[message.topic] = message.payload
    
def _get_client(id, host, port=1883):
    global _client
    if not _client:
        _client = mqtt.Client(client_id=id, clean_session=True)
        _client.on_message = _on_message
        _client.connect(host, port=port)
        _client.loop_start()
    return _client

def _set_value(client, nodeid, cc, endpoint, property, value):
    # The following is documented here:
    # https://zwave-js.github.io/zwavejs2mqtt/#/guide/mqtt?id=api-call-examples  # Set values
    # But it is not consistent with the general description, and it does not seem to work.
    # topic_set = "zwave/nodeID_%d/%d/%d/%s/set" % (nodeid, cc, endpoint, property)

    # Use this instead:
    topic_set = "zwave/_CLIENTS/ZWAVE_GATEWAY-thermcontroly/api/writeValue/set"

    pmessage = {
        "args" : [
            {"nodeId": nodeid,
             "commandClass": cc,
             "endpoint": endpoint,
             "property": property
            },
            value
        ]
    }
    smessage = json.dumps(pmessage)
    logger.debug("Publishing to [%s] message [%s]", topic_set, smessage)
    client.publish(topic_set, smessage)

def _make_topic(prefix, nodeid, cc, endpoint, property):
    return "%s/nodeID_%d/%d/%d/%s" % (prefix, nodeid, cc, endpoint, property)

def _make_topic_from_config(cf, pk):
    return _make_topic(cf["prefix"], cf["nodeid"], cf["cc"], cf["endpoint"], cf[pk])
        
class Temp(object):
    def __init__(self, config, myconfig):
        if "cc" not in myconfig:
            myconfig["cc"] = 49
        mqttconfig = config["mqttclient"]
        port = mqttconfig["port"] if "port" in mqttconfig else 1883
        self.client = _get_client(mqttconfig["clientid"], mqttconfig["host"], port)
        self.topic = _make_topic_from_config(myconfig, "property_current")
        self.client.subscribe(self.topic)

    def current(self):
        global _values
        if self.topic in _values:
            data = json.loads(_values[self.topic])
            dt = datetime.datetime.fromtimestamp(data["time"]/1000)
            logger.debug("Temp:%s value %f (%s)", self.topic, data["value"], dt)
            return data["value"]
        else:
            logger.debug("Temp: no data yet for %s", self.topic)
            return 20.0
        
class Switch(object):
    def __init__(self, config, myconfig):
        if "cc" not in myconfig:
            myconfig["cc"] = 37
        mqttconfig = config["mqttclient"]
        port = mqttconfig["port"] if "port" in mqttconfig else 1883
        self.client = _get_client(mqttconfig["clientid"], mqttconfig["host"], port)
        self.topic = _make_topic_from_config(myconfig, "property_current")
        self.client.subscribe(self.topic)
        self.prefix = myconfig["prefix"]
        self.nodeid = myconfig["nodeid"]
        self.cc = myconfig["cc"]
        self.endpoint = myconfig["endpoint"]

    def state(self):
        global _values
        if self.topic in _values:
            data = json.loads(_values[self.topic])
            dt = datetime.datetime.fromtimestamp(data["time"]/1000)
            logger.debug("Switch:%s value %s (%s)", self.topic, data["value"], dt)
            return data["value"]
        else:
            logger.debug("Switch: no data yet for %s", self.topic)
            return False
    def turnon(self):
        self.set(True)
    def turnoff(self):
        self.set(False)
    def set(self, state):
        property = "targetValue"
        _set_value(self.client, self.nodeid, self.cc,self.endpoint, property, state)

def toggle_switch1(client):
    nodeid = 8
    cc = 37
    endpoint = 0
    property = "targetValue"
    set_value(client, nodeid, cc, endpoint, property, True)
    time.sleep(10)
    set_value(client, nodeid, cc, endpoint, property, False)
