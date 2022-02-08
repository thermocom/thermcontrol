
# Note still needs python2 on the climcave odroid
from __future__ import print_function

import logging
import sys
import os
import subprocess

from thermlib import conftree

def initlog(conf):
    logfilename = conf.get('logfilename') or "/tmp/therm_log.txt"
    loglevel = conf.get('loglevel') or 2
    loglevel = int(loglevel)
    if loglevel > 5:
        loglevel = 5
    if loglevel < 1:
        loglevel = 1 
    llmap = {1:logging.CRITICAL, 2:logging.ERROR, 3:logging.WARNING,
             4:logging.INFO, 5:logging.DEBUG}
    loglevel = llmap[loglevel] if loglevel in llmap else logging.WARNING
    logging.basicConfig(filename=logfilename, level=loglevel,
                        format='%(asctime)s - %(name)s:%(lineno)d: %(message)s')

def pidw(pidfile):
    data = None
    try:
        with open(pidfile, 'r') as f:
            data = f.read()
    except:
        pass
    if data:
        pid = data.strip()
        pso = subprocess.check_output(['ps', '-e']).decode('utf-8')
        beg = pid + " "
        for line in pso.split("\n"):
            if line.startswith(beg):
                logger.warning("Already running. pid: %s" % pid)
                sys.exit(1)
    with open(pidfile, "w") as f:
        print("%d" % os.getpid(), file=f)

# Common initialisation part for control / remote
def initcommon(envconfname):
    confname = None
    if envconfname in os.environ:
        confname = os.environ[envconfname]
    if not confname:
        raise Exception("NO %s in environment" % envconfname)

    # We open the config rw because we may need to store stuff in there
    conf = conftree.ConfSimple(confname, readonly=False)

    initlog(conf)
    global logger
    logger = logging.getLogger(__name__)

    # Avoid multiple instances
    pidfile = conf.get('pidfile')
    if not pidfile:
        # If pidfile is not set by the configuration, we use the first
        # part of the environment variable name
        pidfile = os.path.join('/tmp', envconfname.split('_')[0])

    pidw(pidfile)
                        
    return conf
