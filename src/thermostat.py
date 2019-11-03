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
        
    gitif.init(datarepo)
    thermlog.init(datarepo)

    gpio_pin = int(conf.get("gpio_pin"))
    if not gpio_pin:
        logger.critical("No fan_pin defined in configuration")
        sys.exit(1)
    pioif.init(gpio_pin)

    # Retrieve the target temperature
    get_setpoint()

    # And the PID coefs
    global g_kp, g_ki, g_kd
    g_kp = float(conf.get('pid_kp') or 50.0)
    g_ki = float(conf.get('pid_ki') or 20.0)
    g_kd = float(conf.get('pid_kd') or 0.0)
    # Create the PID controller
    create_pid()

def get_setpoint():
    global g_setpoint
    g_setpoint = gitif.fetch_setpoint()


def tell_the_world():
    gitif.send_updates()
    
last_world_update = 0
update_thread = None
publish_interval = 6 * 3600
def maybe_tell_the_world():
    global last_world_update, update_thread, publish_interval
    now = time.time()
    if now < last_world_update + publish_interval:
        return
    if update_thread and update_thread.isAlive():
        log.info("maybe_tell_the_world: previous update not done")
        return
    last_world_update = now
    update_thread = threading.Thread(target=tell_the_world)
    update_thread.start()
    
def create_pid():
    global g_pidcontrol
    g_pidcontrol = PID.PID(
        Kp=g_kp, Ki=g_ki, Kd=g_kd,
        setpoint=g_setpoint,
        sample_time=None,
        output_limits=(0, 100),
        auto_mode=True,
        proportional_on_measurement=False)
        
def gettemp():
    temp = 0.0
    for id in g_housetempids:
        temp += owif.readtemp(id)
    return temp / len(g_housetempids)


def main():
    init()

    minute = 60
    # We loop every minute to test things to do (maybe log, turn off
    # heater or whatever)
    innerloopseconds = minute
    # We manage the heater every 30 minutes.
    extloopinnerloops = 30

    loopcount = 0
    heatminutes = 0
    command = 0.0
    heateron = False
    temperrorcnt = 0
    while True:
        startseconds = int(time.time())

        try:
            actualtemp = gettemp()
        except:
            logger.error("Could not get temp")
            temperrorcnt += 1
            if temperrorcnt < 5:
                time.sleep(minute)
                continue
            else:
                # Exit and let upper layers handle the situation (reboot?)
                logger.critical("Too many temp reading errors, exiting")
                sys.exit(1)
        temperrorcnt = 0
        
        if loopcount == 0:
            # Call PID to decide the heating duration for the next half hour
            setpoint_saved = g_setpoint
            get_setpoint()
            if setpoint_saved != g_setpoint:
                create_pid()
            command = g_pidcontrol(actualtemp)
            # Command is 0-100
            heatminutes = (extloopinnerloops * command) / 100.0
            if heatminutes < 5:
                heatminutes = 0
            if heatminutes > extloopinnerloops - 5:
                heatminutes = extloopinnerloops
            if heatminutes > 0:
                # Turn heater on
                pioif.turnon()
                heateron = True
        elif loopcount == heatminutes:
            # Time to turn heater off. Note that if heatminutes is
            # >= extloopinloops, we don't turn off during this cycle
            pioif.turnoff()
            heateron = False
            
        if (loopcount % 5) == 0:
            # Log stuff every 5 minutes
            ho = 1 if heateron else 0
            p,i,d = g_pidcontrol.components
            thermlog.logstate({'temp':actualtemp, 'set': g_setpoint, 'on': ho,
                               'cmd': command, 'p' : p, 'i' : i, 'd': d})

        # Publish our state from time to time. 
        maybe_tell_the_world()
        
        endseconds = int(time.time())
        if endseconds - startseconds < innerloopseconds:
            time.sleep(innerloopseconds - (endseconds - startseconds))
        loopcount += 1
        if loopcount >= extloopinnerloops:
            loopcount = 0

    # End mainloop

    
if __name__ == '__main__':
    main()
