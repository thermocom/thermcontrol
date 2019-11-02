#!/usr/bin/python
from __future__ import print_function
import os
import sys
import logging
import math
import datetime
import time
import subprocess

import conftree
import utils
import owif

# Log the current temperatures and fan state.
def logstate(exC, inC, fanB):
    global g_templog
    try:
        with open(g_templog, 'a') as f:
            datestring = datetime.datetime.now().strftime('%Y-%m-%d/%H:%M:%S')
            tC = targetC()
            fanB = int(fanB) + 14
            print("%s %.2f %.2f %.2f %d" % (datestring, tC, exC, inC, fanB),
                  file=f)
    except:
        logger.exception("Logging temp error")

def fanon():
    if g_using_t2ss:
        t2ssif.fanon()
    else:
        pioif.fanon()

def fanoff():
    if g_using_t2ss:
        t2ssif.fanoff()
    else:
        pioif.fanoff()

def fanstate():
    if g_using_t2ss:
        return t2ssif.fanstate()
    else:
        return pioif.fanstate()

def turnoffandsleep(s):
    global g_loopsleepsecs
    fanoff()
    loggerr.debug("Sleeping: %s", s)
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


def pidw():
    global g_pidfile
    data = None
    try:
        with open(g_pidfile, 'r') as f:
            data = f.read()
    except:
        pass
    if data:
        pid = data.strip()
	pso = subprocess.check_output(['ps', '-e'])
	beg = pid + ' '
        for line in pso.split("\n"):
            if line.startswith(beg):
		logger.warning("Already running. pid: %s" % pid)
		sys.exit(1)
    with open(g_pidfile, 'w') as f:
        print("%d" % os.getpid(), file=f)

def init():
    # Give ntpd a little time to adjust the date.
    time.sleep(60)
    
    envconfname = 'CLIMCAVE_CONFIG'
    confname = None
    if envconfname in os.environ:
        confname = os.environ[envconfname]
    if not confname:
        raise Exception("NO %s in environment" % envconfname)

    conf = conftree.ConfSimple(confname)

    utils.initlog(conf)
    global logger
    logger = logging.getLogger(__name__)

    global g_templog
    g_templog = conf.get('templog')
    global g_pidfile
    g_pidfile = conf.get('pidfile')
    if not g_pidfile:
        g_pidfile = os.path.join(os.path.dirname(g_templog), 'climcave.pid')
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
        fan_pin = int(conf.get("fan_pin"))
        if not fan_pin:
            logger.critical("No fan_pin defined in configuration")
            sys.exit(1)
        global pioif
        import pioif
        pioif.init(fan_pin)
    pidw()



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
