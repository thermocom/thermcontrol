from __future__ import print_function

import logging
import subprocess
import sys
import os

logger = logging.getLogger(__name__)

def init(datarepo):
    global g_datarepo
    g_datarepo = datarepo
    global g_gitcmd
    g_gitcmd = ['git',
                '--work-tree=' + g_datarepo,
                '--git-dir=' + os.path.join(g_datarepo, '.git')
                ]

def fetch_setpoint():
    cmd = g_gitcmd + ['pull', '-q']
    try:
        subprocess.check_call(cmd)
    except:
        logger.exception("git command failed: %s", cmd)
        return None
    tempfile = os.path.join(g_datarepo, "consigne")
    try:
        with open(tempfile, 'r') as f:
            temp = f.read().strip()
    except:
        logger.exception("Could not read %s", tempfile)
        return None
    try:
        value = float(temp)
        if value < 5.0 or value > 22.0:
            raise Exception("Bad set point %s" % temp)
    except:
        logger.exception("Bad contents in tempfile")
        return None
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
    if not _try_run_git(g_gitcmd + ['commit', '-q', '-m', 'n']):
        return
    _try_run_git(g_gitcmd + ['push', '-q'])

    
##########
if __name__ == '__main__':
    def perr(s):
        print("%s"%s, file=sys.stderr)
    logging.basicConfig()
    import conftree
    conf = conftree.ConfSimple("therm_config")
    datarepo = conf.get('datarepo')
    if not datarepo:
        perr("No 'datarepo' param in configuration")
        sys.exit(1)
    init(datarepo)
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
