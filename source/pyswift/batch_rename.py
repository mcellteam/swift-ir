#!/usr/bin/env python3

import sys
import os
import glob

fl = sorted(glob.glob('*'))

fsl = [ f.split('.') for f in fl ]
fnl = ([ '%s.%03d.%s' % (s[0],int(s[1]),s[2]) for s in fsl ])

for i in range(len(fl)):
  os.rename(fl[i],fnl[i])


