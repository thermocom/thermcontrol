#!/usr/bin/python
from __future__ import print_function

import os
import sys
import logging

import conftree
import owif
import utils
import PID
import gitif

class ConfNull(object):
    def get(self, nm, sk = b''):
        return None
    
def init():
    # Give ntpd a little time to adjust the date.
#    time.sleep(60)

    envconfname = 'THERM_CONFIG'
    confname = None
    if envconfname in os.environ:
        confname = os.environ[envconfname]
    if not confname:
        raise Exception("NO %s in environment" % envconfname)

    conf = conftree.ConfSimple(confname)

    utils.initlog(conf)
    global logger
    logger = logging.getLogger(__name__)

    global g_housetempids
    g_housetempids = conf.get('housetempids').split()
    if not g_housetempids:
        logger.critical("No housetempids defined in configuration")
        sys.exit(1)

    gitif.init(conf)
    
    # Retrieve the target temperature

    # Create the PID controller
    g_pidcontrol = PID.PID(Kp=1.0, Ki=0.0, Kd=0.0,
                           setpoint=0,
                           sample_time=None,
                           output_limits=(0, 100),
                           auto_mode=True,
                           proportional_on_measurement=False):


def gettemp():
    temp = 0.0
    for id in g_housetempids:
        temp += owif.readtemp.gettemp(id)
    return temp / len(g_housetempids)

def main():
    init()

    while True:
        actualtemp = gettemp()
        
if __name__ == '__main__':
    main()
