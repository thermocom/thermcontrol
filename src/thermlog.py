# State logging module for the thermostat.py temperature control program.

import sys
import json
import os
import logging
import datetime
import time

logger = logging.getLogger(__name__)

class StateLogger(object):
    def __init__(self, datarepo, period = 5 * 60):
        self.datarepo = datarepo
        self.period = period
        self.last = 0
        
    # Log the current state parameters, which we receive as a dict. E.g.:
    #  - Measured temperature
    #  - PID output 0-100
    #  - PID Contributing terms (P,I,D)
    #  - Relay state on/off
    def logstate(self, values):
        now = time.time()
        if now - self.last < self.period:
            return
        self.last = now

        dt = datetime.datetime.now()
        day = dt.strftime('%Y-%m-%d')
        tm = datetime.datetime.now().strftime('%Y-%m-%d/%H:%M:%S')

        logfilename = os.path.join(self.datarepo, day + "-templog")

        # Round down float precision to limit size of printed data
        for k in values.keys():
            v = values[k]
            if isinstance(v, float):
                values[k] = round(v, 2)
    
        data = [tm, values]
        line = json.dumps(data)
        try:
            with open(logfilename, 'a') as f:
                print("%s" % line, file=f)
        except:
            logger.exception("Logging temp error")


##########
if __name__ == '__main__':
    def perr(s):
        print("%s"%s, file=sys.stderr)
    logging.basicConfig()
    statelogger = StateLogger("/tmp/datarepo")
    def usage():
        perr("Usage: thermlog.py")
        sys.exit(1)
    if len(sys.argv) != 1:
        usage()
    statelogger.logstate({"temp":20.0, "Pterm":100, "Iterm":20})
    
    sys.exit(0)
