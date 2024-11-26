#!/usr/bin/python3

import os
import sys
import logging
import time
import threading
import asyncio

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


class PidLoop(object):
    def __init__(self, statelogger, switch, setpointgetter, tempgetter, world_publisher,
                 heatingperiod, kp, ki, kd):
        self.statelogger = statelogger
        self.switch = switch
        self.setpointgetter = setpointgetter
        self.tempgetter = tempgetter
        self.world_publisher = world_publisher
        self.heatingperiod = heatingperiod
        self.kp = kp
        self.ki = ki
        self.kd = kd

        # We loop every minute to test things to do (maybe log, turn off heater or whatever)
        self.fastloopseconds = 60

        self.heatseconds = 0
        self.setpoint = 10.0
        self.command = 0
        self.pidctl = None
        self.turnoffhandle = None
        self.slowhandle = None
        self.switch.turnoff()
        self.heatperiodstart = time.time()
        
    def fastcallback(self):
        # Schedule next call
        loop = asyncio.get_running_loop()
        loop.call_later(self.fastloopseconds, self.fastcallback)

        timeinperiod = time.time() - self.heatperiodstart
        logger.debug("timeinperiod %d heatseconds %d / %d",
                     timeinperiod, self.heatseconds, self.heatingperiod)
    
        # Retrieve the temperature. We do it in the fast loop for logging purposes. gettemp will
        # exit the process if there are too many errors. The watchdog will then notice and reboot.
        self.actualtemp = self.tempgetter.gettemp()
        if self.actualtemp is None:
            return

        # First call or setpoint change: need to create/change the PID object and
        # schedule/reschedule the slow callback
        nsetpoint = self.setpointgetter.get()
        if not self.pidctl or self.setpoint != nsetpoint:
            self.setpoint = nsetpoint
            self.pidctl = PID.PID(Kp=self.kp, Ki=self.ki, Kd=self.kd, setpoint=nsetpoint,
                                  output_limits=(0, 100), sample_time=None,
                                  auto_mode=True, proportional_on_measurement=False)
            logger.debug("PID tunings: Kp %.2f Ki %.2f Kd %.2f" % self.pidctl.tunings)
            if self.slowhandle:
                self.slowhandle.cancel()
            self.slowhandle = loop.call_soon(self.slowcallback)

        # Update the log file
        ho = 1 if self.switch.current() else 0
        p,i,d = self.pidctl.components
        self.statelogger.logstate({"temp": self.actualtemp, "set": self.setpoint, "on": ho,
                                   "cmd": self.command, "p" : p, "i" : i, "d": d})
        # Publish our state (git push) from time to time.
        self.world_publisher.maybe_tell_the_world()
            

    def turnoffcallback(self):
        logger.debug("Turning heater off")
        self.switch.turnoff()
            

    def slowcallback(self):
        # Test needed because turnoffhandle is initially None
        if self.turnoffhandle:
            self.turnoffhandle.cancel()
        # Schedule next call
        loop = asyncio.get_running_loop()
        self.slowhandle = loop.call_later(self.heatingperiod, self.slowcallback)

        # Ask PID for the heating duration for the next heater sequence
        self.command = self.pidctl(self.actualtemp)
        self.heatperiodstart = time.time()
        # Command is 0-100
        self.heatseconds = (self.heatingperiod * self.command) / 100.0

        # Adjust result to avoid short on / off times
        if self.heatseconds < (self.heatingperiod / 20) or self.heatseconds < self.fastloopseconds:
            self.heatseconds = 0
        if self.heatseconds > 0.95 * self.heatingperiod or \
           self.heatseconds > self.heatingperiod - self.fastloopseconds:
            self.heatseconds = self.heatingperiod + 10
        logger.debug("New result from PID: heatseconds: %.1f" % self.heatseconds)

        # Set the switch, possibly scheduling turn off 
        if self.heatseconds > 0:
            self.switch.turnon()
            loop = asyncio.get_running_loop()
            if self.heatseconds < self.heatingperiod:
                self.turnoff_handle = loop.call_later(self.heatseconds, self.turnoffcallback)
        else:
            self.switch.turnoff()
                


async def pidmain(statelogger, switch, setpointgetter, tempgetter, world_publisher,
                  heatingperiod, kp, ki, kd):
    loop = asyncio.get_running_loop()
    callbacks = PidLoop(statelogger, switch, setpointgetter, tempgetter, world_publisher,
                        heatingperiod, kp, ki, kd)
    loop.call_soon(callbacks.fastcallback)
    while True:
        await asyncio.sleep(10000)


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
        asyncio.run(pidmain(statelogger, switch, setpointgetter, tempgetter, world_publisher,
                    heatingperiod, kp, ki, kd))
    else:
        onoffloop(statelogger, switch, setpointgetter, tempgetter, world_publisher, hysteresis)
        

if __name__ == "__main__":
    init()
