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
        # See https://www.eclipse.org/paho/index.php?page=clients/python/docs/index.php#network-loop
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

def _confget(conf, param, default):
    return conf[param] if param in conf else default

# Note that this supposes that the MQTT Gateway is configured to use node names in topics (which I
# think is the default), and that no names are actually set. Else we'd need to either use the name
# or the numeric value instead of nodeID_xx.
def _make_topic(prefix, nodeid, cc, endpoint, property, propertyKey=None):
    topic = "%s/nodeID_%d/%d/%d/%s" % (prefix, nodeid, cc, endpoint, property)
    if propertyKey:
        topic += "/%s" % propertyKey
    return topic

# Note that the property name and propertyKey values can have several entries in the config so we
# get the config key to use to retrieve them as input. OTOH node id and command class are always
# under the same key, so we don't need to be told
def _make_topic_from_config(cf, cfpk, cfpkk=None):
    return _make_topic(_confget(cf, "prefix", "zwave"), cf["nodeid"], cf["cc"], cf["endpoint"],
                       cf[cfpk], _confget(cf, cfpkk, None))
        

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
        self.prefix = _confget(myconfig,"prefix", "zwave")
        self.nodeid = myconfig["nodeid"]
        self.cc = myconfig["cc"]
        self.endpoint = myconfig["endpoint"]

    def current(self):
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
        loopcnt = 30
        loopslp = 0.1
        for i in range(loopcnt):
            time.sleep(loopslp)
            if self.current() == state:
                return True
            print("DOing some IO", file=sys.stderr)
        raise Exception("Switch: not %s after %d S" % (state, int(loopcnt*loopslp)))


class ThermostatSetpoint(object):
    def __init__(self, config, myconfig):
        if "cc" not in myconfig:
            myconfig["cc"] = 67
        if "setpoint" not in myconfig:
            myconfig["setpoint"] = 1
        mqttconfig = config["mqttclient"]
        port = mqttconfig["port"] if "port" in mqttconfig else 1883
        self.client = _get_client(mqttconfig["clientid"], mqttconfig["host"], port)
        self.topic = _make_topic_from_config(myconfig, "property_current", "setpoint")
        self.client.subscribe(self.topic)

    def current(self):
        global _values
        if self.topic in _values:
            data = json.loads(_values[self.topic])
            dt = datetime.datetime.fromtimestamp(data["time"]/1000)
            logger.debug("ThermostatSetpoint:%s value %s (%s)", self.topic, data["value"], dt)
            return data["value"]
        else:
            logger.debug("ThermostatSetpoint: no data yet for %s", self.topic)
            return False


##############
if __name__ == "__main__":
    import utils
    import os
    import sys
    import logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s:%(lineno)d: %(message)s')
    confname = None
    envconfname = "THERM_CONFIG"
    confname = os.environ[envconfname]
    if not confname:
        raise Exception("NO %s in environment" % envconfname)
    cf = utils.Config(confname).as_json()
    mycf = cf["thermostat"]
    setpoint = ThermostatSetpoint(cf, mycf)
    time.sleep(2)
    print("Setpoint: %f" % setpoint.current())
    
