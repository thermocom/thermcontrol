#!/usr/bin/python
from __future__ import print_function

import os
import sys
import logging
import time

import conftree
import owif
import pioif
import utils
import PID
import gitif
import thermlog

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

    datarepo = conf.get('datarepo')
    if not datarepo:
        logger.critical("No 'datarepo' param in configuration")
        sys.exit(1)
        
    gitif.init(datarepo)
    thermlog.init(datarepo)

    # Retrieve the target temperature
    global g_setpoint
    g_setpoint = gitif.fetch_setpoint()

    gpio_pin = int(conf.get("gpio_pin"))
    if not gpio_pin:
            logger.critical("No fan_pin defined in configuration")
            sys.exit(1)
        global pioif
        import pioif
        pioif.init(gpio_pin)
    pidw()
    # And the PID coefs
    Kp = float(conf.get('pid_kp') or 50.0)
    Ki = float(conf.get('pid_ki') or 20.0)
    Kd = float(conf.get('pid_kd') or 0.0)
    # Create the PID controller
    g_pidcontrol = PID.PID(Kp=Kp, Ki=Ki, Kd=Kd,
                           setpoint=g_setpoint,
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

    minute = 60
    # We loop every minute to test things to do (maybe log, turn off
    # heater or whatever)
    intloopperiod = minute
    # We manage the heater every 30 minutes.
    extloopintloops = 30

    loopcount = 0
    heatminutes = 0
    while True:
        startseconds = int(time.time)
        actualtemp = gettemp()

        if loopcount == 0:
            # Time to decide things
            control = g_pidcontrol(actualtemp)
            # Control is 0-100
            heatminutes = (extloopintloops * control) / 100.0
            if heatminutes < 5:
                heatminutes = 0
            if heatminutes > 0:
                # Turn heater on
        endseconds = int(time.time)
        if endseconds - startseconds < loopperiod:
            time.sleep(loopperiod - (endseconds - startseconds))
        loopcount += 1
        if loopcount > extloopintloops:
            loopcount = 0
            
if __name__ == '__main__':
    main()
