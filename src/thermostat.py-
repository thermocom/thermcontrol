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


# Publishing the logs to the origin repo. This can take a long time, so we do it in a separate
# thread
class Publisher(object):
    def __init__(self, gitif, publish_interval = 6 * 3600):
        self.gitif = gitif
        self.publish_interval = publish_interval
        self.last_world_update = 0
        self.update_thread = None

    def tell_the_world(self):
        self.gitif.push()

    def maybe_tell_the_world(self, force=False):
        now = time.time()
        if not force and (now < self.last_world_update + self.publish_interval):
            return
        if self.update_thread and self.update_thread.isAlive():
            log.info("maybe_tell_the_world: previous update not done")
            return
        self.last_world_update = now
        self.update_thread = threading.Thread(target=self.tell_the_world)
        self.update_thread.start()


# Retrieving the temperature from the sensor. If this fails too much, we exit, hoping that a system
# restart (done by the watchdog) will improve things.
class TempGetter(object):
    def __init__(self, thermsensor, tempscratch):
        self.thermsensor = thermsensor
        self.tempscratch = tempscratch
        self.temperrorcnt = 0

    # Retrieve the interior temperature
    def _gettemp(self):
        temp = self.thermsensor.current()
        logger.debug("Current temperature %.1f ", temp)
        if self.tempscratch:
            try:
                with open(self.tempscratch, "w") as f:
                    print("measuredtemp = %.1f" % temp, file=f)
            except:
                pass
        return temp

    def gettemp(self):
        try:
            temp = self._gettemp()
        except:
            logger.error("Could not get temp")
            self.temperrorcnt += 1
            if self.temperrorcnt < 5:
                return None
            else:
                # Exit and let upper layers handle the situation (reboot?)
                logger.critical("Too many temp reading errors, exiting")
                sys.exit(1)
        self.temperrorcnt = 0
        return temp


def pidloop(statelogger, switch, setpointgetter, tempgetter, world_publisher, heatingperiod,
            kp, ki, kd):
    # We loop every minute to test things to do (maybe log, turn off heater or whatever)
    fastloopseconds = 60
    heaterlooploops = heatingperiod / fastloopseconds

    fastloopcount = 0
    heatseconds = 0
    command = 0
    switch.turnoff()
    setpoint = 10.0
    mypidctl = None
    heatperiodstart = time.time()
    sleepresid = 0
    while True:
        fastloopstart = time.time()
        timeinperiod = time.time() - heatperiodstart
        logger.debug("timeinperiod %d heatseconds %d / %d", timeinperiod, heatseconds,
                     heatingperiod)

        # gettemp will exit the process if there are too many errors. The watchdog will then notice
        # and reboot.
        actualtemp = tempgetter.gettemp()
        if actualtemp is None:
            time.sleep(15)
            continue

        setpoint_saved = setpoint
        setpoint = setpointgetter.get()
        if setpoint_saved != setpoint or not mypidctl:
            world_publisher.maybe_tell_the_world(force=True)
            mypidctl = PID.PID(Kp=kp, Ki=ki, Kd=kd, setpoint=setpoint, output_limits=(0, 100),
                               sample_time=None, auto_mode=True, proportional_on_measurement=False)
            logger.debug("PID tunings: Kp %.2f Ki %.2f Kd %.2f" % mypidctl.tunings)
        
        if fastloopcount == 0:
            # Ask PID for the heating duration for the next heater sequence
            command = mypidctl(actualtemp)
            sleepresid = 0
            heatperiodstart = time.time()
            timeinperiod = 0
            # Command is 0-100
            heatseconds = (heatingperiod * command) / 100.0
            if heatseconds < (heatingperiod / 20) or heatseconds < fastloopseconds:
                heatseconds = 0
            if heatseconds > 0.95 * heatingperiod or \
               heatseconds > heatingperiod - fastloopseconds:
                heatseconds = heatingperiod + 10
            logger.debug("New result from PID: heatseconds: %.1f" % heatseconds)
            if heatseconds > 0:
                switch.turnon()
            else:
                switch.turnoff()
        elif switch.current() and timeinperiod >= heatseconds:
            # Time to turn heater off. Does not happen if we're heating full time
            switch.turnoff()
            
        ho = 1 if switch.current() else 0
        p,i,d = mypidctl.components
        statelogger.logstate({"temp":actualtemp, "set": setpoint, "on": ho,
                              "cmd": command, "p" : p, "i" : i, "d": d})

        # Publish our state (git push) from time to time.
        world_publisher.maybe_tell_the_world()
        
        sleepsecs = fastloopseconds - (time.time() - fastloopstart)
        logger.debug("Initial sleepsecs %.1f heatseconds %.1f timeinperiod %.1f" %
                     (sleepsecs, heatseconds, timeinperiod))
        if switch.current():
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


def onoffloop(statelogger, switch, setpointgetter, tempgetter, world_publisher, hysteresis):

    # We never switch on or off for less than 10 minutes.
    cycleminutes = 10
    switch.turnoff()
    onoff = 0
    while True:
        setpoint_saved = setpoint
        setpoint = setpointgetter.get()
        if setpoint_saved != setpoint:
            world_publisher.maybe_tell_the_world(force=True)
            
        # gettemp will have us exit if there are too many errors. The watchdog will then notice
        # and reboot
        actualtemp = tempgetter.gettemp()
        if actualtemp is None:
            time.sleep(15)
            continue

        savedonoff = onoff
        if actualtemp < setpoint - hysteresis and not onoff:
            switch.turnon()
            onoff = 1
        if actualtemp > setpoint + hysteresis and onoff:
            switch.turnoff()
            onoff = 0
        if savedonoff != onoff:
            statelogger.logstate({"temp":actualtemp, "set":setpoint, "on":onoff})

        logger.debug("onoffloop: temp %.1f setpoint %.1f on %d", actualtemp, setpoint, onoff)
        # Publish our state (git push) from time to time. 
        world_publisher.maybe_tell_the_world()
        time.sleep(cycleminutes * 60)

    # End onoff loop


def init():
    conf = utils.initcommon("THERM_CONFIG")

    global logger
    logger = logging.getLogger("thermostat")

    switch = sensorfact.make_switch(conf.as_json(), "switch")

    thermsensor = sensorfact.make_temp(conf.as_json(), "temp")
    scratchdir = conf.get("scratchdir")
    tempscratch = os.path.join(scratchdir, "ctl") if scratchdir else None
    tempgetter = TempGetter(thermsensor, tempscratch)
    
    setpointgetter = setpoint.SetpointGetter(conf)
    gitif = gitele.Gitele(conf)
    statelogger = thermlog.StateLogger(gitif.getrepo())
    world_publisher = Publisher(gitif)

    using_pid = conf.get("using_pid", 0)
    if using_pid:
        heatingperiod = conf.get("heatingperiod", 1800)
        # Using 100.0 means that we go 100% for 1 degree of error. This makes sense if the heating
        # can gain 1 degree in a period.
        kp = conf.get("pid_kp", 100.0)
        # The Ki needs to be somewhat normalized against the (very long) sample period. We use the
        # normalized half kp by default, meaning that the Ki contribution on a single period will be
        # half the kp one. Of course it will go up over multiple periods.
        ki = conf.get("pid_ki", kp / (2.0 * heatingperiod))
        kd = conf.get("pid_kd", 0.0)
    else:
        hysteresis = float(conf.get("hysteresis") or 0.5)

    # Let things initialize a bit
    time.sleep(5)

    switch.turnoff()
    if using_pid:
        pidloop(statelogger, switch, setpointgetter, tempgetter, world_publisher, heatingperiod,
                kp, ki, kd)
    else:
        onoffloop(statelogger, switch, setpointgetter, tempgetter, world_publisher, hysteresis)
        

if __name__ == "__main__":
    init()
