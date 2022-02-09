#!/usr/bin/python3
#
# Controlling a T2SS 2-channel I/O module, which can't be procurred any more, so this is history.
# https://www.embeddeddatasystems.com/T2SS--2-Channel-IO-Module-1-Wire-Expansion-Card-Discontinued_p_34.html
# Replaced by direct PIO control of a relay board, but we miss the feedback (sensing the actual
# output from the relay)

# If a t2ss appeared again, this would need to be updated for the new owif interface using pyownet


import logging
import sys

import owif

logger = logging.getLogger(__name__)

def init(idctl):
    global g_idctl1
    g_idctl1 =idctl

def setoutputs(id, iv1, iv2):
    all = ''
    if iv1:
        all += '1'
    else:
        all += '0'
    all += ','
    if iv2:
        all += '1'
    else:
        all += '0'
    try:
        sensor = owif.createSensor(id)
        logger.debug("setoutputs %s -> %s", id, all)
        sensor.__setattr__('PIO_ALL', all)
    except Exception as e:
        logger.exception("Could not set outputs on  %s", id)
        raise e

def readio(id):
    try:
        sensor = owif.createSensor(id)
        val = {'OutputA': int(sensor.__getattr__('PIO_A')),
               'OutputB': int(sensor.__getattr__('PIO_B')),
               'InputA':  int(sensor.__getattr__('sensed_A')),
               'InputB':  int(sensor.__getattr__('sensed_B')),
               'LatchA':  int(sensor.__getattr__('latch_A')),
               'LatchB':  int(sensor.__getattr__('latch_B'))}
        logger.debug("readio %s -> %s", id, val)
        return val
    except Exception as e:
        logger.exception("Could not read io on  %s", id)
        raise e

def fanoff():
    setoutputs(g_idctl1, 0, 0)

def fanon():
    setoutputs(g_idctl1, 1, 0)
    
def fanstate():
    state = readio(g_idctl1)
    return state['InputB']

##########
if __name__ == '__main__':
    import conftree
    confname = "/home/dockes/.climcave_config"
    def perr(s):
        print("%s" % s, file=sys.stderr)
    def usage():
        perr("t2ssif.py: Usage: t2ssif.py <cmd>")
        perr("cmd:")
        perr("  fanstate")
        sys.exit(1)
    if len(sys.argv) != 2:
        usage()
    cmd = sys.argv[1]
    conf = conftree.ConfSimple(confname)
    idctl1 = conf.get('idctl1')
    if not idctl1:
        perr("No idctl1 defined in %s" % confname)
        sys.exit(1)
    
    init(idctl1)
    if cmd == "fanstate":
        print("fan state %d" % fanstate())
    else:
        usage()
    
    sys.exit(0)
