#!/usr/bin/env python
from __future__ import print_function

# Interface for controlling the KUBII relays through the PIO
#
# The Kubii relays we are using are active (switched) when the input
# is shorted to ground, inactive when high impedance or high, so the
# command names and actual GPIO outputs are inverted.

import sys
import time
import logging
import os

logger = logging.getLogger(__name__)

# the python "platform" module is not really helpful to determine the
# machine type. Rely in /boot files instead
if os.path.exists("/boot/meson64_odroidc2.dtb"):
    machine = "odroidc2"
else:
    machine = "rpi"
    
try:
    if machine == "rpi":
        import RPi.GPIO as GPIO
    elif machine == "odroidc2":
        import Odroid.GPIO as GPIO
    else:
        raise Exception("Unknown machine %s" %machine)
except Exception as err:
    logger.critical("Error importing RPi.GPIO!: %s", err)
    sys.exit(1)

# We do things in several executions. A channel already setup is normal
def init(pin):
    global gpio_pin
    gpio_pin = pin
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    setup_gpio()
    
def setup_gpio():
    try:
        if machine == "rpi":
            GPIO.setup(gpio_pin, GPIO.OUT, initial=GPIO.HIGH)
        else:
            GPIO.setup(gpio_pin, GPIO.OUT)
            GPIO.output(gpio_pin, True)
    except Exception as e:
        logger.exception("setup_gpio failed", hp)
        raise e

def reset_gpio():
    try:
        GPIO.cleanup((gpio_pin,))
    except Exception as e:
        logger.exception("reset_gpio pin %d failed", gpio_pin)
        raise e
        
def turnon():
    try:
        GPIO.output(gpio_pin, False)
    except Exception as e:
        logger.exception("turnnon pin %d failed", gpio_pin)
        raise e

def turnoff():
    try:
        GPIO.output(gpio_pin, True)
    except Exception as e:
        logger.exception("turnoff pin %d failed", gpio_pin)
        raise e

def state():
    try:
        if GPIO.input(gpio_pin):
            return 0
        else:
            return 1
    except Exception as e:
        logger.exception("state pin %d failed", gpio_pin)
        raise e

##########
if __name__ == '__main__':
    def perr(s):
        print("%s"%s, file=sys.stderr)
    def usage():
        perr("pioif.py: Usage: pioif.py pin <cmd>")
        perr("cmd:")
        perr("  reset, turnon, turnoff, state")
        sys.exit(1)
    if len(sys.argv) <= 2:
        usage()
    pin = int(sys.argv[1])
    cmds = sys.argv[2].split()
    perr("pin %d" % pin)
    init(pin)
    for cmd in cmds:
        perr("cmd %s" % cmd)
        if cmd == "reset":
            reset_gpio()
        elif cmd == "turnon":
            turnon()
        elif cmd == "turnoff":
            turnoff()
        elif cmd == "state":
            print("pin state %d" % state())
        else:
            usage()
    
    sys.exit(0)
