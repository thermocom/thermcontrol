# Note: this used to be based on python-ow which is obsolete and Python2 only.
# We now use pyownet
# https://pyownet.readthedocs.io/en/latest/index.html
# See https://github.com/owfs/owfs/issues/75 for another possibility

from pyownet import protocol
import logging
import sys

logger = logging.getLogger(__name__)

host = 'localhost'
port = 4304
try:
    owproxy = protocol.proxy(host=host, port=port)
except Exception as e:
    logger.exception("protocol.proxy(%s,%d) failed", host, port)
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

# Return temperature as float
def readtemp(id):
    sensorid = id_ow(id)
    try:
        stemp = owproxy.read('/' + sensorid + '/temperature')
        logger.debug("readtemp %s -> %s", sensorid, stemp)
        return float(stemp)
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
