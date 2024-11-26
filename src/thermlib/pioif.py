#!/usr/bin/env python3

# Interface for controlling the KUBII relays through the PIO on a Raspberry PI or an Odroid C2
#
# The Kubii relays we are using are active (switched on) when the input is shorted to ground,
# inactive when the pin is high impedance or high, so the command names and actual GPIO outputs are
# inverted.
#
# On the Pi, needs the python3-rpi.gpio package (apt)
#
# The module defines a PioIf object which controls a single PIO pin. Multiple objects can be used
# to control more pins
import sys
import time
import logging
import os
import fnmatch

logger = logging.getLogger(__name__)

# The python "platform" module is not really helpful to determine the
# machine type. Rely on /boot files instead.
machine = "unknown"
_bootfiles = os.listdir("/boot")
for f in _bootfiles:
    if fnmatch.fnmatch(f, "*meson64*"):
        machine = "odroid"
        break
    elif fnmatch.fnmatch(f, "bcm*-rpi*"):
        machine = "rpi"
        break

try:
    if machine == "rpi":
        import RPi.GPIO as GPIO
    elif machine == "odroid":
        import Odroid.GPIO as GPIO
    else:
        raise Exception("Unknown machine %s" %machine)
except Exception as err:
    logger.critical("Error importing GPIO module for %s: %s" % (machine, err))
    sys.exit(1)

class PioIf(object):
    # We do things in several executions. A channel already setup is normal
    def __init__(self, config, myconfig):
        GPIO.setwarnings(False)
        # GPIO.BCM would tell the interface to use chip pin numbers, not connector
        # ones. The latter are more convenient but there are bugs
        # forbidding using pins beyond 26 ! This was supposedly fixed
        # in release 0.5.7 of the python module, but I still can get
        # it to work !
        # To be checked. thermcontrol and climcave work with board pin
        # numbers, the bcm was for the proto with more relays which
        # needed more pins
        self.gpio_mode = GPIO.BOARD
        if "gpio_mode" in myconfig and "gpio_mode" == "bcm":
            self.gpio_mode = GPIO.BCM
        GPIO.setmode(self.gpio_mode)
        self.gpio_pin = myconfig["gpio_pin"]
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

    def current(self):
        try:
            return 0 if GPIO.input(self.gpio_pin) else 1
        except Exception as e:
            logger.exception("state pin %d failed", self.gpio_pin)
            raise e
    # Compat
    def state(self):
        return current(self)

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
    pioif = PioIf({}, {"gpio_pin": pin})
    for cmd in cmds:
        perr("cmd %s" % cmd)
        if cmd == "reset":
            pioif.reset_gpio()
        elif cmd == "on":
            pioif.turnon()
        elif cmd == "off":
            pioif.turnoff()
        elif cmd == "state":
            print("pin state %d" % pioif.current())
        else:
            usage()
    
    sys.exit(0)
