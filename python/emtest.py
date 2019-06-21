#!/usr/bin/env python3

import swiftir
import numpy as np
import matplotlib.pyplot as plt

orig = swiftir.loadImage('emtest.jpg')
muck = swiftir.loadImage('emtest-persp.jpg')

def showdiff(ima, imb):
    err = ima.astype('float32') - imb.astype('float32')
    err = err[100:-100,100:-100]
    print('rms image error = ', np.sqrt(np.mean(err*err)))
    blk = ima<imb
    dif = ima - imb
    dif[blk] = imb[blk] - ima[blk]
    plt.clf()
    plt.imshow(dif, cmap='gray')
    plt.show()

showdiff(orig, muck)

pa = np.zeros((2,20))
for x in range(5):
    for y in range(4):
        pa[0, x + 5*y] = 300 + 350*x
        pa[1, x + 5*y] = 320 + 350*y  

afm = swiftir.identityAffine()
pmov = pa
psta = pa
sta = swiftir.stationaryPatches(muck, psta, 512)
mov = swiftir.movingPatches(orig, pmov, afm, 512)
(dp, ss, snr) = swiftir.multiSwim(sta, mov, wht=-.5)
psta = psta - dp
(afm, err, n) = swiftir.mirIterate(psta, pmov)
psta = swiftir.movingToStationary(afm, pmov)
print(err)
mcki = swiftir.affineImage(afm, orig)
showdiff(muck, mcki)

AGAIN = False
if AGAIN:
    sta = swiftir.stationaryPatches(muck, psta, 512)
    mov = swiftir.movingPatches(orig, pmov, afm, 512)
    (dp, ss, snr) = swiftir.multiSwim(sta, mov, wht=-.5)
    psta = psta - dp
    (afm, err, n) = swiftir.mirIterate(psta, pmov)
    psta = swiftir.movingToStationary(afm, pmov)
    print(err)
    mcki = swiftir.affineImage(afm, orig)
    showdiff(muck, mcki)

sta = swiftir.stationaryPatches(muck, psta, 512)
mov = swiftir.movingPatches(orig, pa, afm, 512)
(dp, ss, snr) = swiftir.multiSwim(sta, mov, wht=-.5)

