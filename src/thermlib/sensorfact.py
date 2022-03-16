#!/usr/bin/python3

import json
import sys

def make_temp(config, tempsensorname):
    tempconfig = config[tempsensorname]
    if tempconfig["type"] == "zwavejs2mqtt":
        from thermlib import zwavejs2mqtt
        temp = zwavejs2mqtt.Temp(config, tempconfig)
    elif tempconfig["type"] == "onewire":
        from thermlib import owif
        temp = owif.Temp(config, tempconfig)
    else:
        raise Exception("Unknown temp type %s" % tempconfig["type"])
    return temp

def make_switch(config, switchsensorname):
    switchconfig = config[switchsensorname]
    if switchconfig["type"] == "zwavejs2mqtt":
        from thermlib import zwavejs2mqtt
        switch = zwavejs2mqtt.Switch(config, switchconfig)
    elif switchconfig["type"] == "gpio":
        from thermlib import pioif
        switch = pioif.PioIf(config, switchconfig)
    else:
        raise Exception("Unknown temp type %s" % switchconfig["type"])
    return switch



if __name__ == '__main__':
    from thermlib import utils
    import time
    def trace(s):
        print("%s" % s, file=sys.stderr)
    confname = "therm-bureau.json"
    confobj = utils.Config(confname)
    config = confobj.as_json()
    # print("%s" % json.dumps(config))
    temp = make_temp(config, "temp")
    time.sleep(2)
    print("Temp: %f" % temp.current())
    switch = make_switch(config, "switch")
    switch.turnon()
    time.sleep(3)
    switch.turnoff()
    time.sleep(3)
