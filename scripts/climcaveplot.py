#!/usr/bin/python3

import sys
import tempfile
import subprocess
import os
import glob

def perr(s):
    print("%s"%s, file=sys.stderr)
def usage():
    perr("Usage: thermdatatoplot.py")
    sys.exit(1)

if len(sys.argv) != 1:
    usage()

tmpfile = tempfile.NamedTemporaryFile(delete=False, mode='w')
cmd = ["scp", "odroid64:pyclimcave/tempcave.log", tmpfile.name]
subprocess.check_call(cmd)

filenameopt='filename="' + tmpfile.name + '"'
p1 = subprocess.Popen(['gnuplot', '-p', '-e', filenameopt, '-'], stdin=subprocess.PIPE)

plotprogram=b'''
set xdata time
set timefmt "%Y-%m-%d/%H:%M:%S"

set format x "%d/%m\\n%H:%M"
set grid xtics ytics

# ext
set style line 1 lt 0 lc 'blue'
# cave
set style line 2 lt -1 lc 'red'
# setpoint
set style line 3 lt -1 lc 'green'

#set yrange [10:30]
plot filename using 1:3 with lines, '' using 1:4 with lines, '' using 1:2 with lines
'''


p1.stdin.write(plotprogram)
p1.stdin.close()
p1.wait()
subprocess.run(['rm', tmpfile.name])
