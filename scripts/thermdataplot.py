#!/usr/bin/python3

import sys
import json
import tempfile
import subprocess
import os
import glob

g_datarepo = '/home/dockes/projets/rpi-control/thermostat/thermdata'

def perr(s):
    print("%s"%s, file=sys.stderr)
def usage():
    perr("Usage: thermdatatoplot.py")
    sys.exit(1)

g_gitcmd = ['git',
            '--work-tree=' + g_datarepo,
            '--git-dir=' + os.path.join(g_datarepo, '.git')
            ]
cmd = g_gitcmd + ['pull', '-q']
subprocess.check_call(cmd)

tmpfile = tempfile.NamedTemporaryFile(delete=False, mode='w')

if len(sys.argv) == 1:
    fnlist = glob.glob(os.path.join(g_datarepo, "*templog"))
else:
    fnlist = []
    for dte in sys.argv[1:]:
        fnlist.append(os.path.join(g_datarepo, dte + "-templog"))
                      
for fn in sorted(fnlist):
    with open(fn, 'r') as f:
        for line in f:
            l = json.loads(line)
            date = l[0]
            temp = l[1]['temp']
            print("%s\t%s" % (date, temp), file=tmpfile.file)
tmpfile.file.close()

filenameopt='filename="' + tmpfile.name + '"'
p1 = subprocess.Popen(['gnuplot', '-p', '-e', filenameopt, '-'],
                       stdin=subprocess.PIPE)

plotprogram=b'''
set xdata time
set timefmt "%Y-%m-%d/%H:%M:%S"

set format x "%d-%m\\n%H:%M"
set grid xtics ytics

# ext
set style line 1 lt 0 lc 'blue'
# cave
set style line 2 lt -1 lc 'red'
# setpoint
set style line 3 lt -1 lc 'green'

#set yrange [10:30]
plot filename using 1:2 with lines 
'''


p1.stdin.write(plotprogram)
p1.stdin.close()
p1.wait()
subprocess.run(['rm', tmpfile.name])
