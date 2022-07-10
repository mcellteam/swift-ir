#!/usr/bin/env python3
import sys

__all__ = ['print_debug']

debug_level=50

# For now, always use the limited argument version
def print_debug(level, p1=None, p2=None, p3=None, p4=None, p5=None):
    if level <= debug_level:
        if p1 == None:
            sys.stderr.write("" + '\n')
        elif p2 == None:
            sys.stderr.write(str(p1) + '\n')
        elif p3 == None:
            sys.stderr.write(str(p1) + str(p2) + '\n')
        elif p4 == None:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + '\n')
        elif p5 == None:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + str(p4) + '\n')
        else:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + str(p4) + str(p5) + '\n')