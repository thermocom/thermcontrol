#!/bin/sh

thermdatadir=/home/dockes/thermdata
thermwatchtimefile=/tmp/thermwatch.timestamp
templog=${thermdatadir}/`date +%Y-%m-%d`-templog
thermlog=${thermdatadir}/logtherm

set -x

running=`ps ax | grep thermostat.py | grep -v grep`
if test -z "$running"
then
    (date; echo "Rebooting because thermostat.py is not running") \
        >>  ${thermlog}
    rm -f ${thermwatchtimefile}
    /sbin/reboot
fi

# Test on templog updating. Of course this supposes that the watchdog
# runs less often than the temp update. We normally set cron to run
# the watchdog every hour
if test -f ${thermwatchtimefile}; then
    if test ${thermwatchtimefile} -nt ${templog}; then
        (date; echo "Rebooting because ${templog} is not updating") \
            >>  ${thermlog}
        rm -f ${thermwatchtimefile}
        /sbin/reboot
    fi
fi
touch ${thermwatchtimefile}
    
