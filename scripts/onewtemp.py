#!/usr/bin/python3

# Example script for using the direct Raspberry PI 1-wire interface (without owfs)
# We don't use this at the moment.

import logging

logger = logging.getLogger(__name__)

def gettemp(id):
    
    try:
        fn = '/sys/bus/w1/devices/' + id + '/w1_slave'
        with open(fn, 'r') as f:
            line = f.readline()
            crc = line.rsplit(' ', 1)[1].replace('\n', '')
            if crc != 'YES':
                raise Exception("Bad crc [%s]" % crc)
            line = f.readline()
            return int(line.rsplit('t=', 1)[1])
    except Exception as e:
        logger.exception("While running: gettemp id %s" % id)
        return 99999


if __name__ == '__main__':
    id = '28-0300a2792076'
    print("Temp : " + '{:.3f}'.format(gettemp(id)/float(1000)))
