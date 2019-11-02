from __future__ import print_function

import logging
import subprocess
import sys
import os

logger = logging.getLogger(__name__)

def init(conf):
    global g_datarepo
    g_datarepo = conf.get('datarepo')
    if not g_datarepo:
        logger.critical("No 'datarepo' param in configuration")
        raise Exception("No 'datarepo' param in configuration")
    global g_gitcmd
    g_gitcmd = ['git',
                '--work-tree=' + g_datarepo,
                '--git-dir=' + os.path.join(g_datarepo, '.git')
                ]

def fetch_setpoint():
    defaultvalue = 10.0
    cmd = g_gitcmd + ['pull', '-q']
    try:
        subprocess.check_call(cmd)
    except:
        logger.exception("git command failed: %s", cmd)
        return defaultvalue
    tempfile = os.path.join(g_datarepo, "consigne")
    try:
        with open(tempfile, 'r') as f:
            temp = f.read().strip()
    except:
        logger.exception("Could not read %s", tempfile)
        return defaultvalue
    try:
        value = float(temp)
        if value < 5.0 or value > 22.0:
            raise Exception("Bad set point %s" % temp)
    except:
        logger.exception("Bad contents in tempfile")
        return defaultvalue
    return value

def _try_run_git(cmd):
    try:
        logging.error("RUNNING [%s]" % cmd)
        subprocess.check_call(cmd)
        return True
    except Exception as e:
        logger.exception("git command failed: %s", cmd)
        return False
    
def send_updates():
    try:
        modified = subprocess.check_output(g_gitcmd + ['status', '-s'])
    except:
        logger.exception("git command failed: %s", cmd)
        return
    if not modified:
        return
    if not _try_run_git(g_gitcmd + ['add', '.']):
        return
    if not _try_run_git(g_gitcmd + ['commit', '-m', 'n']):
        return
    _try_run_git(g_gitcmd + ['push', '-q'])

    
##########
if __name__ == '__main__':
    logging.basicConfig()
    import conftree
    conf = conftree.ConfSimple("therm_config")
    init(conf)
    def perr(s):
        print("%s"%s, file=sys.stderr)
    def usage():
        perr("Usage: gitif.py <cmd>")
        perr("cmd:")
        perr("  setpoint")
        sys.exit(1)
    if len(sys.argv) != 2:
        usage()
    cmd = sys.argv[1]
    if cmd == "setpoint":
        print("Temp: %.2f" % fetch_setpoint())
    elif cmd == "update":
        send_updates()
    else:
        usage()
    
    sys.exit(0)
