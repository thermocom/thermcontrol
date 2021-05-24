#!/usr/bin/env python3

# Interface for controlling the KUBII relays through the PIO
#
# The Kubii relays we are using are active (switched) when the input
# is shorted to ground, inactive when high impedance or high, so the
# command names and actual GPIO outputs are inverted.
#
# On the pi, needs the python3-rpi.gpio package (apt)

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

class PioIf(object):
    # We do things in several executions. A channel already setup is normal
    def __init__(self, pin):
        self.gpio_pin = pin
        GPIO.setwarnings(False)
        # GPIO.BCM would tell the interface to use chip pin numbers, not connector
        # ones. The latter are more convenient but there are bugs
        # forbidding using pins beyond 26 ! This was supposedly fixed
        # in release 0.5.7 of the python module, but I still can get
        # it to work !
        # To be checked. thermcontrol and climcave work with board pin
        # numbers, the bcm was for the proto with more relays which
        # needed more pins
        GPIO.setmode(GPIO.BOARD)
        #GPIO.setmode(GPIO.BCM)
        self.setup_gpio()
    
    def setup_gpio(self):
        try:
            if machine == "rpi":
                GPIO.setup(self.gpio_pin, GPIO.OUT, initial=GPIO.HIGH)
            else:
                GPIO.setup(self.gpio_pin, GPIO.OUT)
                GPIO.output(self.gpio_pin, True)
        except Exception as e:
            logger.exception("setup_gpio pin %d failed", self.gpio_pin)
            raise e

    def reset_gpio(self):
        try:
            GPIO.cleanup((self.gpio_pin,))
        except Exception as e:
            logger.exception("reset_gpio pin %d failed", self.gpio_pin)
            raise e
        
    def turnon(self):
        try:
            GPIO.output(self.gpio_pin, False)
        except Exception as e:
            logger.exception("turnon pin %d failed", self.gpio_pin)
            raise e

    def turnoff(self):
        try:
            GPIO.output(self.gpio_pin, True)
        except Exception as e:
            logger.exception("turnoff pin %d failed", self.gpio_pin)
            raise e

    def state(self):
        try:
            return 0 if GPIO.input(self.gpio_pin) else 1
        except Exception as e:
            logger.exception("state pin %d failed", self.gpio_pin)
            raise e

##########
if __name__ == '__main__':
    def perr(s):
        print("%s"%s, file=sys.stderr)
    def usage():
        perr("pioif.py: Usage: pioif.py pin <cmd>")
        perr("cmd:")
        perr("  reset, on, off, state")
        sys.exit(1)
    if len(sys.argv) <= 2:
        usage()
    pin = int(sys.argv[1])
    cmds = sys.argv[2].split()
    perr("pin %d" % pin)
    pioif = PioIf(pin)
    for cmd in cmds:
        perr("cmd %s" % cmd)
        if cmd == "reset":
            pioif.reset_gpio()
        elif cmd == "on":
            pioif.turnon()
        elif cmd == "off":
            pioif.turnoff()
        elif cmd == "state":
            print("pin state %d" % pioif.state())
        else:
            usage()
    
    sys.exit(0)
