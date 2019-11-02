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
def id_tcl_to_ow(tclid):
    tp = tclid[14:16]
    id = ''
    for i in range(6):
        base = 2 + 2 * (6-i) - 2
        id += tclid[base : base+2]
    return tp + '.' + id

def createSensor(id):
    if len(id) == 16:
        id = id_tcl_to_ow(sensorid)
    return ow.Sensor('/' + id)

# Return temperature as float
def readtemp(sensorid):
    try:
        sensor = createSensor(sensorid)
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
