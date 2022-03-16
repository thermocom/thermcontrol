#!/usr/bin/python3

# A git-based remote control interface.
# Not everything is used by thermostat.py at the moment: it just uses
# the git push/pull methods, but manages the "consigne" file by itself
# and does not use the "actions" methods which were intended for
# things like, e.g. cycling power on a camera.

import logging
import subprocess
import sys
import os
import glob

import thermlib.utils
from thermlib import conftree

logger = logging.getLogger(__name__)

class Gitele(object):
    def __init__(self, conf):
        self.conf = conf
        self.datarepo = self.conf.get("datarepo")
        if not self.datarepo:
            raise Exception("Gitele: no datarepo value set in configuration")
        self.datarepo = os.path.expanduser(self.datarepo)
        self.gitcmd = ['git',
                       '--work-tree=' + self.datarepo,
                       '--git-dir=' + os.path.join(self.datarepo, '.git')
        ]

    def getrepo(self):
        return self.datarepo

    # This is not used by the current client. And will need an adjustment because the config does
    # not support set any more. Will need to use a separate file.
    def _incseq(self):
        s = self.conf.get("giteleseq")
        if not s:
            s = "0"
        seqnum = int(s)
        seqnum += 1
        self.conf.set("giteleseq", str(seqnum))
        return seqnum
        
    def getconf(self):
        return self.conf

    def _try_run_git(self, cmd, read_output = False):
        cmd = self.gitcmd + cmd
        try:
            logger.info("gitele: running: [%s]" % cmd)
            output = "OK"
            if read_output:
                output = subprocess.check_output(cmd)
            else:
                subprocess.check_call(cmd)
            return output
        except Exception as e:
            logger.exception("git command failed: %s", cmd)
            return False
    
    def _readdata(self, path):
        try:
            return conftree.ConfSimple(path, False, False)
        except:
            logger.exception("Could not read %s" % path)
            return None

    def pull(self):
        cmd = ['pull', '-q']
        if not self._try_run_git(cmd):
            return False
        path = os.path.join(self.datarepo, "consigne.py")
        self.consigne = self._readdata(path)
        path = os.path.join(self.datarepo, "status.py")
        self.status = self._readdata(path)
        if not self.consigne or not self.status:
            return False
        return True

    def push(self):
        if not self.pull():
            return False
        cmd = ['status', '-s']
        modified = self._try_run_git(cmd, False)
        if modified == "OK":
            logger.debug("gitele push: repo is unmodified")
            return
        else:
            logger.debug("MODIFIED [%s]" % modified)
        if not self._try_run_git(['add', '.']):
            return
        if not self._try_run_git(['commit', '-q', '-m', 'n']):
            return
        self._try_run_git(['push', '-q'])

    def _actname(self, seqnum):
        return "action_%06d" % seqnum
    def _actseq(self, fn):
        return int(os.path.basename(fn)[7:])        
    def action_add(self, text):
        fn = os.path.join(self.datarepo, self._actname(self._incseq()))
        if os.path.exists(fn):
            raise Exception("gitele addaction: action already exists")
        with open(fn, "w") as f:
            print("%s\n" % text, file=f)
        self._try_run_git(['add', fn])
        return True
    def action_get_all(self):
        fnames = sorted(glob.glob(os.path.join(self.datarepo, "action_*")))
        result = []
        for fn in fnames:
            seq = self._actseq(fn)
            with open(fn, "r") as f:
                result.append((seq, f.read()))
        return result
    def action_confirm_done(self, seqnum, code):
        aname = self._actname(seqnum)
        logger.info("action_confirm_done: %s" % aname)
        fn = os.path.join(self.datarepo, aname)
        self._try_run_git(['rm', '-f', fn])

    def _getvalue(self, isConsigne, name):
        cf = self.consigne if isConsigne else self.status
        return cf.get(name)
    def getconsigne(self, name):
        return self._getvalue(True, name)
    def getstatus(self, name):
        return self._getvalue(False, name)
    def _setvalue(self, isConsigne, name, value, sk=""):
        cf = self.consigne if isConsigne else self.status
        return cf.set(name, value, sk)
    def setconsigne(self, name, value):
        return self._setvalue(True, name, value)
    def setstatus(self, name, value):
        return self._setvalue(False, name, value)

    


#### Main program for trying stuff. Mix of control and remote stuff,
# not usable for anything but tests
if __name__ == '__main__':
    def perr(s):
        print("%s"%s, file=sys.stderr)

    envconfname = 'GITELE_CONFIG'
    confname = None
    if envconfname in os.environ:
        confname = os.environ[envconfname]
    if not confname:
        raise Exception("NO %s in environment" % envconfname)

    conf = conftree.ConfSimple(confname, False, False)
    gitif = Gitele(conf)
    utils.initlog(gitif.getconf())
    gitif.action_add("task-sleep5.py")
    gitif.action_add("task-sleep10.py")
    gitif.action_add("task-sleep130.py")

    sys.exit(0)

    
    # Retrieve new data
    gitif.pull()

    nm = "statusvar"
    gitif.setstatus(nm, "this is a status")
    value = gitif.getstatus(nm)
    if value:
        perr("status value for %s: %s" % (nm,value))
    else:
        perr("No %s variable in status file" % nm)

    nm = "consvar"
    gitif.setconsigne(nm, "this is a consign value")
    value = gitif.getconsigne(nm)
    if value:
        perr("consigne value for %s: %s" % (nm,value))
    else:
        perr("No %s variable in consigne file" % nm)

    actions = gitif.action_get_all()
    print("ACTIONS: %s" % actions)
    for seq, text in actions:
        gitif.action_confirm_done(seq, 0)
    
    # Update remote
    #gitif.push()
