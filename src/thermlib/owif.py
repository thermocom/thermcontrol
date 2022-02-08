# Note: python-ow is Python2 only.
# See the refs to newer bindings using owserver here:
# https://github.com/owfs/owfs/issues/75

# This module uses the python-ow module from the owfs project to access 1-Wire temperature sensors
# https://github.com/owfs/owfs/
# http://owfs.sourceforge.net/owpython.html

# Note still needs python2 on the climcave odroid
from __future__ import print_function

import ow
import logging
import sys

logger = logging.getLogger(__name__)

host = 'localhost'
port = '4304'
try:
    hp = host + ':' + port
    ow.init(hp)
except Exception as e:
    logger.exception("ow.init(%s) failed", hp)
    raise e

# Utility: the ids used by the TCL code are reverted and include the
# ck at the beginning and the family at the end. e.g:
# '160008027D6BA410'
#
# And by the way, the ids in /sys/bus/w1/devices and the ones used by
# owfs have inverse byte orders, but can be distinguished by the
# period vs dash
# /sys/bus/w1/devices/ : 28-0300a2792076
# /run/owfs/ :           28.762079A20003 
def id_ow(inid):
    outid = ''
    if len(inid) == 16:
        # Old tcl one
        tp = inid[14:16]
        outid = tp + '.'
        for i in range(6):
            base = 2 + 2 * (6-i) - 2
            outid += inid[base : base+2]
    elif inid[2] == '-':
        outid = inid[0:2] + '.'
        for i in range(6):
            base = 3 + 2 * (6-i) - 2
            outid += inid[base : base+2].upper()
    else:
        outid = inid
    return outid

def createSensor(id):
    return ow.Sensor('/' + id_ow(id))

# Return temperature as float
def readtemp(sensorid):
    try:
        sensor = createSensor(sensorid)
        #print("SENSOR: %s : %s" % (sensor, sensor.entryList()),file=sys.stderr)
        logger.debug("readtemp %s -> %s", sensorid, sensor.temperature)
        return float(sensor.temperature)
    except Exception as e:
        logger.exception("Could not read temperature from %s", sensorid)
        raise e
 

##########
if __name__ == '__main__':
    def perr(s):
        print("%s"%s, file=sys.stderr)
    def usage():
        perr("Usage: owif.py <id> <cmd>")
        perr("cmd:")
        perr("  readtemp")
        sys.exit(1)
    if len(sys.argv) <= 2:
        usage()
    id = sys.argv[1]
    cmds = sys.argv[2].split()
    for cmd in cmds:
        perr("cmd %s" % cmd)
        if cmd == "readtemp":
            print("Temp: %.2f" % readtemp(id))
        else:
            usage()
    
    sys.exit(0)
