#!/usr/bin/env python3

import time
import random

if __name__ == '__main__':
  tname = str(time.time() + (0.001*random.random()) ).replace('.','_') + ".tmp"
  print ( "tname = " + tname )
  f = open(tname,'w')
  f.write ( tname )
  f.close()