# Logging module for the thermostat.py temperature control program.

from __future__ import print_function

import sys
import json
import os
import logging
import datetime

logger = logging.getLogger(__name__)

def init(datarepo):
    global g_datarepo
    g_datarepo = datarepo

# Log the current state:
# - Measured temperature
# - PID output 0-100
# - PID Contributing terms (P,I,D)
# - Relay state on/off
# We take an array as input and output it as json
def logstate(values):
    dt = datetime.datetime.now()
    day = dt.strftime('%Y-%m-%d')
    tm = datetime.datetime.now().strftime('%Y-%m-%d/%H:%M:%S')

    logfilename = os.path.join(g_datarepo, day + "-templog")

    # round down float precision to limit size of printed data
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
    datarepo = '/tmp/datarepo'
    init(datarepo)
    def usage():
        perr("Usage: thermlog.py")
        sys.exit(1)
    if len(sys.argv) != 1:
        usage()
    logstate({"temp":20.0, "Pterm":100, "Iterm":20})
    
    sys.exit(0)
