#!/usr/bin/python3

import os
import sys
import logging
import time
import threading

from thermlib import conftree
from thermlib import utils
from thermlib import PID
from thermlib import gitele
from thermlib import sensorfact
from thermlib import setpoint

import thermlog

def init():
    # Give ntpd a little time to adjust the date.
#    time.sleep(60)

    conf = utils.initcommon('THERM_CONFIG')
    global logger
    logger = logging.getLogger("thermostat")

    global g_tempscratch
    scratchdir = conf.get('scratchdir')
    g_tempscratch = os.path.join(scratchdir, 'ctl') if scratchdir else None

    global g_setpoint_getter
    g_setpoint_getter = setpoint.SetpointGetter(conf)

    global gitif
    gitif = gitele.Gitele(conf)
    thermlog.init(gitif.getrepo())

    global g_temp
    g_temp = sensorfact.make_temp(conf.as_json(), "temp")

    global g_switch
    g_switch = sensorfact.make_switch(conf.as_json(), "switch")

    global g_heatingperiod
    g_heatingperiod = conf.get("heatingperiod", 1800)

    # Are we using a PID controller or an on/off
    global g_using_pid
    g_using_pid = conf.get("using_pid", 0)
    if g_using_pid:
        #  PID coefs
        global g_kp, g_ki, g_kd
        # Using 100.0 means that we go 100% for 1 degree of error. This makes sense if the heating
        # can gain 1 degree in a period.
        g_kp = conf.get("pid_kp", 100.0)
        # The Ki needs to be somewhat normalized against the (very long) sample period. We use the
        # normalized half kp by default, meaning that the Ki contribution on a single period will be
        # half the kp one. Of course it will go up over multiple periods.
        g_ki = conf.get("pid_ki", g_kp/(2.0*g_heatingperiod))
        g_kd = conf.get("pid_kd", 0.0)
    else:
        global g_hysteresis
        g_hysteresis = float(conf.get('hysteresis') or 0.5)
    # Let things initialize a bit
    time.sleep(5)
    g_switch.turnoff()

### Publishing the logs to the origin repo
def tell_the_world():
    gitif.push()

class Publisher(object):
    def __init__(self):
        self.last_world_update = 0
        self.update_thread = None
        self.publish_interval = 6 * 3600
    def maybe_tell_the_world(self, force=False):
        now = time.time()
        if not force and (now < self.last_world_update + self.publish_interval):
            return
        if self.update_thread and self.update_thread.isAlive():
            log.info("maybe_tell_the_world: previous update not done")
            return
        self.last_world_update = now
        self.update_thread = threading.Thread(target=tell_the_world)
        self.update_thread.start()

world_publisher = Publisher()


#### Build a PID controller
def create_pid(setpoint):
    return PID.PID(
        Kp=g_kp, Ki=g_ki, Kd=g_kd,
        setpoint=setpoint,
        sample_time=None,
        output_limits=(0, 100),
        auto_mode=True,
        proportional_on_measurement=False)

# Retrieve the interior temperature
def gettemp():
    temp = g_temp.current()
    logger.debug("Current temperature %.1f ", temp)
    if g_tempscratch:
        try:
            with open(g_tempscratch, 'w') as f:
                print("measuredtemp = %.1f" % temp, file=f)
        except:
            pass
    return temp

temperrorcnt = 0
def trygettemp():
    global temperrorcnt
    try:
        temp = gettemp()
    except:
        logger.error("Could not get temp")
        temperrorcnt += 1
        if temperrorcnt < 5:
            return None
        else:
            # Exit and let upper layers handle the situation (reboot?)
            logger.critical("Too many temp reading errors, exiting")
            sys.exit(1)
    temperrorcnt = 0
    return temp


def pidloop():
    global world_publisher, g_heatingperiod
    # We loop every minute to test things to do (maybe log, turn off heater or whatever)
    fastloopseconds = 60
    heaterlooploops = g_heatingperiod / fastloopseconds

    fastloopcount = 0
    heatseconds = 0
    command = 0
    g_switch.turnoff()
    setpoint = 10.0
    mypidctl = None
    heatperiodstart = time.time()
    sleepresid = 0
    while True:
        fastloopstart = time.time()
        timeinperiod = time.time() - heatperiodstart
        logger.debug("timeinperiod %d heatseconds %d / %d", timeinperiod, heatseconds,
                     g_heatingperiod)

        # trygettemp will have us exit if there are too many
        # errors. The watchdog will then notice and reboot.
        actualtemp = trygettemp()
        if actualtemp is None:
            time.sleep(15)
            continue

        setpoint_saved = setpoint
        setpoint = g_setpoint_getter.get()
        if setpoint_saved != setpoint or not mypidctl:
            world_publisher.maybe_tell_the_world(force=True)
            mypidctl = create_pid(setpoint)
            logger.debug("PID tunings: Kp %.2f Ki %.2f Kd %.2f" % mypidctl.tunings)
                             
        
        if fastloopcount == 0:
            # Ask PID for the heating duration for the next heater sequence
            command = mypidctl(actualtemp)
            sleepresid = 0
            heatperiodstart = time.time()
            timeinperiod = 0
            # Command is 0-100
            heatseconds = (g_heatingperiod * command) / 100.0
            if heatseconds < (g_heatingperiod / 20) or heatseconds < fastloopseconds:
                heatseconds = 0
            if heatseconds > 0.95 * g_heatingperiod or \
               heatseconds > g_heatingperiod - fastloopseconds:
                heatseconds = g_heatingperiod + 10
            logger.debug("New result from PID: heatseconds: %.1f" % heatseconds)
            if heatseconds > 0:
                g_switch.turnon()
            else:
                g_switch.turnoff()
        elif g_switch.current() and timeinperiod >= heatseconds:
            # Time to turn heater off. Does not happen if we're heating full time
            g_switch.turnoff()
            
        if (int(timeinperiod/60) % 5) == 0:
            # Log stuff every 5 minutes
            ho = 1 if g_switch.current() else 0
            p,i,d = mypidctl.components
            thermlog.logstate({'temp':actualtemp, 'set': setpoint, 'on': ho,
                               'cmd': command, 'p' : p, 'i' : i, 'd': d})

        # Publish our state (git push) from time to time.
        world_publisher.maybe_tell_the_world()
        
        sleepsecs = fastloopseconds - (time.time() - fastloopstart)
        logger.debug("Initial sleepsecs %.1f heatseconds %.1f timeinperiod %.1f" %
                     (sleepsecs, heatseconds, timeinperiod))
        if g_switch.current():
            if heatseconds > 0 and sleepsecs > heatseconds - timeinperiod:
                sleepresid = sleepsecs - (heatseconds - timeinperiod)
                if sleepresid < 0:
                    sleepresid = 0
                else:
                    sleepsecs -= sleepresid
                    logger.debug("Sleepsecs too big. sleepresid %.1f sleepsecs %.1f" %
                                 (sleepresid,sleepsecs))
        elif sleepresid > 0:
            sleepsecs += sleepresid
            sleepresid = 0
        if sleepsecs > 0:
            # logger.debug("Sleeping %.1f seconds", sleepsecs)
            time.sleep(sleepsecs)
        fastloopcount += 1
        if fastloopcount >= heaterlooploops:
            fastloopcount = 0

    # End PIDloop


def onoffloop():
    global g_hysteresis, world_publisher

    # We never switch on or off for less than 10 minutes.
    cycleminutes = 10
    g_switch.turnoff()
    onoff = 0
    while True:
        setpoint_saved = setpoint
        setpoint = g_setpoint_getter.get()
        if setpoint_saved != setpoint:
            world_publisher.maybe_tell_the_world(force=True)
            
        # trygettemp will have us exit if there are too many
        # errors. The watchdog will then notice and reboot
        actualtemp = trygettemp()
        if actualtemp is None:
            time.sleep(15)
            continue

        savedonoff = onoff
        if actualtemp < setpoint - g_hysteresis and not onoff:
            g_switch.turnon()
            onoff = 1
        if actualtemp > setpoint + g_hysteresis and onoff:
            g_switch.turnoff()
            onoff = 0
        if savedonoff != onoff:
            thermlog.logstate({'temp':actualtemp, 'set':setpoint, 'on':onoff})

        logger.debug("onoffloop: temp %.1f setpoint %.1f on %d",
                     actualtemp, setpoint, onoff)
        # Publish our state (git push) from time to time. 
        world_publisher.maybe_tell_the_world()
        time.sleep(cycleminutes * 60)

    # End onoff loop


def main():
    init()
    if g_using_pid:
        pidloop()
    else:
        onoffloop()
        

if __name__ == '__main__':
    main()
