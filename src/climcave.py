#!/usr/bin/python3

# Climcave: control the cellar temperature by actionning the fans.

import os
import sys
import logging
import math
import datetime
import time
import subprocess

from thermlib import conftree
from thermlib import utils
from thermlib import owif

# Log the current temperatures and fan state.
def logstate(exC, inC, fanB):
    global g_templog
    try:
        with open(g_templog, 'a') as f:
            datestring = datetime.datetime.now().strftime('%Y-%m-%d/%H:%M:%S')
            tC = targetC()
            fanB = int(fanB) + 14
            print("%s\t%.2f\t%.2f\t%.2f\t%d" % (datestring, tC, exC, inC, fanB),
                  file=f)
    except:
        logger.exception("Logging temp error")

def fanon():
    if g_using_t2ss:
        t2ssif.fanon()
    else:
        pioif.turnon()

def fanoff():
    if g_using_t2ss:
        t2ssif.fanoff()
    else:
        pioif.turnoff()

def fanstate():
    if g_using_t2ss:
        return t2ssif.fanstate()
    else:
        return pioif.state()

def turnoffandsleep(s):
    global g_loopsleepsecs
    fanoff()
    logerr.debug("Sleeping: %s", s)
    time.sleep(g_loopsleepsecs)
    return 0


# We can't hope to keep a constant temp. If we try, we'll follow the
# external temp in periods where the target cant't be reached. So we
# try to set realistic targets depending on the season
def targetC(day=0):
    if not day:
        day = int(datetime.date.today().strftime("%j"))

    # +-2C sine around 16.5C, low 15Feb
    target = 16.5 - 2 * math.cos(((day - 45.0)/182.5) * 3.1416)
    return target


def init():
    # Give ntpd a little time to adjust the date.
    time.sleep(60)
    
    conf = utils.initcommon('CLIMCAVE_CONFIG')
    global logger
    logger = logging.getLogger(__name__)

    global g_templog
    g_templog = conf.get('templog')

    global g_idtempext
    g_idtempext = conf.get('idtempext')
    global g_idtempint
    g_idtempint = conf.get('idtempint')
    if not g_idtempext or not g_idtempint:
        logger.critical(
            "No idtempext or idtempint defined in configuration")
        sys.exit(1)

    global g_using_t2ss
    g_using_t2ss = conf.get('using_t2ss')
    if g_using_t2ss:
        idctl1 = conf.get('idctl1')
        if not idctl1:
            logger.critical("No idctl1 defined in configuration")
            sys.exit(1)
        import t2ssif
        t2ssif.init(idctl1)
    else:
        gpio_pin = int(conf.get("gpio_pin"))
        if not gpio_pin:
            logger.critical("No gpio_pin defined in configuration")
            sys.exit(1)
        from thermlib.pioif import PioIf
        global pioif
        pioif = PioIf({}, {"gpio_pin":gpio_pin})



####################
##### MAIN program

init()

# Wake up every 5 mn
g_loopsleepsecs = 300

# Temp hysteresis
hyster = 0.05
# Minimum time we stay on or off (loopsleepms will be used if it's bigger)
minsecs = 120

## Current state:
# Last time we changed : the epoch
lastchange = 0
# Current fan state: off
currentstate = 0

while True:
    # Get external and internal temperatures
    try:
        tempext = owif.readtemp(g_idtempext)
        tempint = owif.readtemp(g_idtempint)
        logger.debug("tempext: %s, tempint: %s", tempext, tempint)
    except:
        logger.exception("climcave: could not read temperatures")
        # In any case, try to turn the fan off
        currentstate = turnoffandsleep("Couldn't read temp")
        continue

    ##### Read actual device state in case it's not what we think
    try:
        state = fanstate()
    except:
        currentstate = turnoffandsleep("Couldn't read device state")
        continue
    if state != currentstate:
        logger.info("State read from device differs from expected")
        currentstate = state

    target= targetC()

    # Compute desired state: turn off if inside too cool, on if too warm, 
    desiredstate = currentstate
    if currentstate == 1 and tempint < target - hyster:
        desiredstate = 0
    if currentstate == 0 and tempint > target + hyster:
        desiredstate = 1
    # stay off anyway if it's too warm outside
    if tempext > tempint - 1:
        desiredstate = 0

    now = time.time()
    if currentstate != desiredstate and now - lastchange > minsecs:
        try:
            if desiredstate:
                fanon()
            else:
                fanoff()
        except:
            currentstate = turnoffandsleep("Couldn't set outputs")
            continue
        currentstate = desiredstate
        lastchange = now
        #### Check device state after setting it
        try:
            actualstate = fanstate()
        except:
            currentstate = turnoffandsleep(
                "Couldn't read device state after setting")
            continue
        if actualstate != currentstate:
            currentstate = turnoffandsleep(
                "Measured device state %s differs from expected (%s)" %
                (actualstate, currentstate))
            continue

    logstate(tempext, tempint, currentstate)

    # Sleep
    time.sleep(g_loopsleepsecs)
