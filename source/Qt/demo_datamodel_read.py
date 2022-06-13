#!/usr/bin/env python3
import hashlib
import time

fn = './demo_datamodel.json'
f = open(fn,'r')
d = f.read()
f.close()

for i in range(10):
  d+=d

chksum = hashlib.md5(d.encode('utf-8')).hexdigest()

#chksum = hashlib.md5(open(fn,'r+').read()).hexdigest()

print('number of chars in %s:  %d  md5_chksum: %s' % (fn,len(d),chksum))


#f.close()
