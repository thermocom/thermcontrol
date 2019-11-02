import logging

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
                        format='%(name)s:%(lineno)d::%(message)s')
