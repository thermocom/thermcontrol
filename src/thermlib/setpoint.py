import os
import sys
import logging
import time

from thermlib import gitele
from thermlib import conftree

logger = logging.getLogger(__name__)

class _SetpointGetterGit(object):
    def __init__(self, config):
        self.setpointfromgit = None
        self.lasttime = 0
        # Fetch every 2 hours.
        self.fetchinterval = 2*60*60
        self.giterrorcnt = 0
        self.maxgiterrors = 60
        self.gitif = gitele.Gitele(conf)
        
    def _fetch_setpoint(self):
        try:
            self.gitif.pull()
        except Exception as e:
            logger.exception("git command failed: %s", e)
            return None
        setpointfile = os.path.join(self.gitif.getrepo(), "consigne")
        try:
            with open(setpointfile, 'r') as f:
                temp = f.read().strip()
        except:
            logger.exception("Could not read %s", setpointfile)
            return None
        try:
            value = float(temp)
            if value < 5.0 or value > 22.0:
                raise Exception("Bad set point %s" % temp)
        except:
            logger.exception("Bad contents in setpointfile")
            return None
        return value

    def get(self):
        now = time.time()
        logger.debug("SetpointGetterGit: get. setpointfromgit %s", self.setpointfromgit)
        if self.setpointfromgit is None or now  > self.lasttime + self.fetchinterval:
            logger.debug("Fetching setpoint")
            self.setpointfromgit = self._fetch_setpoint()
            if not self.setpointfromgit:
                self.giterrorcnt += 1
            else:
                self.giterrorcnt = 0
            if self.giterrorcnt >= self.maxgiterrors:
                # Let the watchdog handle this
                raise Exception("Too many git pull errors, exiting")
            logger.debug("SetpointGetter: got %s", self.setpointfromgit)
            self.lasttime = now
        return self.setpointfromgit

class _SetpointGetterTherm(object):
    def __init__(self, config):
        from thermlib import sensorfact
        self.therm = sensorfact.make_therm(config.as_json(), "thermostat")

    def get(self):
        return self.therm.current()


class SetpointGetter(object):
    def __init__(self, config):
        self.safetemp = 10.0
        tp = config.get("setpointgettertype")
        if tp == "git":
            self.getter = _SetpointGetterGit(config)
        elif tp == "thermostat":
            self.getter = _SetpointGetterTherm(config)
        else:
            raise Exception("SetpointGetter: bad getter type %s" % tp)
        self.tp = tp
        scratchdir = config.get('scratchdir')
        self.uisettingfile = os.path.join(scratchdir, 'ui') if scratchdir else None
        logger.debug("SetpointGetter: uisettingfile is %s" % self.uisettingfile)
        
    def get(self):
        # Always check for a local setting, it overrides the remote
        if self.uisettingfile and os.path.exists(self.uisettingfile):
            try:
                cf = conftree.ConfSimple(self.uisettingfile)
                tmp = cf.get('localsetting')
                if tmp:
                    logger.debug("SetpointGetter: returning %.1f from local ui" % float(tmp))
                    return float(tmp)
            except:
                pass
        setting = self.getter.get()
        if setting:
            logger.debug("SetpointGetter: returning %.1f from %s getter" % (setting, self.tp))
            return setting
        else:
            logger.debug("SetpointGetter: returning %.1f from safe setting" % self.safetemp)
            return self.safetemp
