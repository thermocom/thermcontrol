#!/usr/bin/python
from __future__ import print_function

import os
import sys
import logging
import time
import threading

import conftree
import owif
import pioif
import utils
import PID
import gitif
import thermlog

# Main heating sequence in seconds: one half-hour
g_heatingperiod = 1800

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

    # Pid here is the process id, nothing to do with the control loop
    pidfile = conf.get('pidfile')
    if not pidfile:
        pidfile = '/tmp/thermostat.pid'
    utils.pidw(pidfile)

    global g_housetempids
    g_housetempids = conf.get('housetempids').split()
    if not g_housetempids:
        logger.critical("No housetempids defined in configuration")
        sys.exit(1)

    datarepo = conf.get('datarepo')
    if not datarepo:
        logger.critical("No 'datarepo' param in configuration")
        sys.exit(1)

    global g_uisettingfile, g_tempscratch
    scratchdir = conf.get('scratchdir')
    if scratchdir:
        g_uisettingfile = os.path.join(scratchdir, 'ui')
        g_tempscratch = os.path.join(scratchdir, 'ctl')
    else:
        g_uisettingfile = None
        g_tempscratch = None
    
    gitif.init(datarepo)
    thermlog.init(datarepo)

    gpio_pin = int(conf.get("gpio_pin"))
    if not gpio_pin:
        logger.critical("No fan_pin defined in configuration")
        sys.exit(1)
    pioif.init(gpio_pin)

    # Are we using a PID controller or an on/off
    global g_using_pid, g_heatingperiod
    g_using_pid = int(conf.get("using_pid") or 0)
    if g_using_pid:
        #  PID coefs
        global g_kp, g_ki, g_kd
        # Using 100.0 means that we go 100% for 1 degrees of
        # error. This makes sense if the heating can gain 1 degree in
        # a period (1/2 hour).
        g_kp = float(conf.get('pid_kp') or 100.0)
        # The Ki needs to be somewhat normalized against the (very
        # long) sample period. We use the normalized half kp by
        # default, meaning that the Ki contribution on a single period
        # will be half the kp one. Of course it will go up over
        # multiple periods.
        g_ki = float(conf.get('pid_ki') or g_kp/(2.0*g_heatingperiod))
        g_kd = float(conf.get('pid_kd') or 0.0)
    else:
        global g_hysteresis
        g_hysteresis = float(conf.get('hysteresis') or 0.5)


class SetpointGetter(object):
    def __init__(self):
        self.safetemp = 10.0
        self.setpointfromgit = None
        self.lasttime = 0
        # Fetch every 2 hours.
        self.fetchinterval = 2*60*60
        self.giterrorcnt = 0
        self.maxgiterrors = 60
        
    def get(self):
        # Always check for a local setting, it overrides the remote
        if g_uisettingfile and os.path.exists(g_uisettingfile):
            try:
                cf = conftree.ConfSimple(g_uisettingfile)
                tmp = cf.get('localsetting')
                if tmp:
                    return float(tmp)
            except:
                pass
        now = time.time()
        logger.debug("SetpointGetter: get. setpointfromgit %s",
                     self.setpointfromgit)
        if self.setpointfromgit is None or \
               now  > self.lasttime + self.fetchinterval:
            logger.debug("Fetching setpoint")
            self.setpointfromgit = gitif.fetch_setpoint()
            if not self.setpointfromgit:
                self.giterrorcnt += 1
            else:
                self.giterrorcnt = 0
            if self.giterrorcnt >= self.maxgiterrors:
                # Let the watchdog handle this
                logger.critical("Too many git pull errors, exiting")
                pioif.turnoff()
                sys.exit(1)
            logger.debug("SetpointGetter: got %s", self.setpointfromgit)
            self.lasttime = now
        return self.setpointfromgit or self.safetemp

setpoint_getter = SetpointGetter()

### Publishing the logs to the origin repo
def tell_the_world():
    gitif.send_updates()

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

# Retrieve the interior temperature, possibly by averaging several
# sensors
def gettemp():
    temp = 0.0
    for id in g_housetempids:
        temp += owif.readtemp(id)
    temp = temp / len(g_housetempids)
    if g_tempscratch:
        try:
            with open(g_tempscratch, 'w') as f:
                print("measuredtemp = %.2f" % temp, file=f)
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
    global world_publisher
    minute = 60
    # We loop every minute to test things to do (maybe log, turn off
    # heater or whatever)
    fastloopseconds = minute
    # How many fast loops in a heater period: we manage the heater
    # every 30 minutes.
    global g_heatingperiod
    heaterlooploops = int(g_heatingperiod/fastloopseconds)

    fastloopcount = 0
    heatminutes = 0
    command = 0.0
    heateron = False
    setpoint = 10.0
    mypidctl = None
    while True:
        startseconds = time.time()
        logger.debug("fastloopcount %d heatminutes %d",
                     fastloopcount, heatminutes)

        # trygettemp will have us exit if there are too many
        # errors. The watchdog will then notice and reboot.
        actualtemp = trygettemp()
        if actualtemp is None:
            time.sleep(15)
            continue

        setpoint_saved = setpoint
        setpoint = setpoint_getter.get()
        if setpoint_saved != setpoint or not mypidctl:
            world_publisher.maybe_tell_the_world(force=True)
            mypidctl = create_pid(setpoint)
            logger.debug("PID tunings: Kp %.2f Ki %.2f Kd %.2f" %
                         mypidctl.tunings)
                             
        if fastloopcount == 0:
            # Ask PID for the heating duration for the next heater sequence
            command = mypidctl(actualtemp)
            # Command is 0-100
            heatminutes = int((heaterlooploops * command) / 100.0)
            if heatminutes < 5:
                heatminutes = 0
            if heatminutes > heaterlooploops - 5:
                heatminutes = heaterlooploops
            if heatminutes > 0:
                pioif.turnon()
                heateron = True
            else:
                pioif.turnoff()
                heateron = False
        elif fastloopcount == heatminutes:
            # Time to turn heater off. Note that if heatminutes is
            # >= extloopinloops, we don't turn off during this cycle
            pioif.turnoff()
            heateron = False
            
        if (fastloopcount % 5) == 0:
            # Log stuff every 5 minutes
            ho = 1 if heateron else 0
            p,i,d = mypidctl.components
            thermlog.logstate({'temp':actualtemp, 'set': setpoint, 'on': ho,
                               'cmd': command, 'p' : p, 'i' : i, 'd': d})

        # Publish our state (git push) from time to time.
        world_publisher.maybe_tell_the_world()
        
        sleepsecs = fastloopseconds - (time.time() - startseconds)
        if sleepsecs > 0:
            logger.debug("Sleeping %s seconds", sleepsecs)
            time.sleep(sleepsecs)
        fastloopcount += 1
        if fastloopcount >= heaterlooploops:
            fastloopcount = 0

    # End PIDloop


def onoffloop():
    global g_hysteresis, world_publisher

    # We never switch on or off for less than 10 minutes.
    cycleminutes = 10
    pioif.turnoff()
    onoff = 0
    while True:
        setpoint_saved = setpoint
        setpoint = setpoint_getter.get()
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
            pioif.turnon()
            onoff = 1
        if actualtemp > setpoint + g_hysteresis and onoff:
            pioif.turnoff()
            onoff = 0
        if savedonoff != onoff:
            thermlog.logstate({'temp':actualtemp, 'set':setpoint, 'on':onoff})

        logger.debug("onoffloop: temp %.2f setpoint %.2f on %d",
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
