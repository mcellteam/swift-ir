#!/usr/bin/env python3

import sys
import os
import glob
import numpy as np
# from swiftir import remod
import os
os.environ["OPENCV_IO_MAX_IMAGE_PIXELS"] = (pow(2,32)-1).__str__()
import numpy as np
import cv2

print('Running remod.py...')


def loadImage(ifn, stretch=False):
    '''LOADIMAGE - Load an image for alignment work
    img = LOADIMAGE(ifn) loads the named image, which can then serve as
    either the “stationary” or the “moving” image.
    Images are always converted to 8 bits. Optional second argument STRETCH
    enables contrast stretching. STRETCH may be given as a percentage,
    or simply as True, which implies 0.1%.
    The current implementation can only read from the local file system.
    Backends for http, DVID, etc., would be a useful extension.'''
    if type(stretch)==bool and stretch:
        stretch = 0.1
    img = cv2.imread(ifn, cv2.IMREAD_ANYDEPTH + cv2.IMREAD_GRAYSCALE)
    if stretch:
        N = img.size
        ilo = int(.01*stretch*N)
        ihi = int((1-.01*stretch)*N)
        vlo = np.partition(img.reshape(N,), ilo)[ilo]
        vhi = np.partition(img.reshape(N,), ihi)[ihi]
        nrm = np.array([255.999/(vhi-vlo)], dtype='float32')
        img[img<vlo] = vlo
        img = ((img-vlo) * nrm).astype('uint8')
    return img

def saveImage(img, ofn, qual=None, comp=1):
    '''SAVEIMAGE - Save an image
    SAVEIMAGE(img, ofn) saves the image IMG to the file named OFN.
    Optional third argument specifies jpeg quality as a number between
    0 and 100, and must only be given if OFN ends in ".jpg". Default
    is 95.'''
    if qual is None:
        ext = os.path.splitext(ofn)[-1]
        if (ext == '.tif') or (ext == '.tiff') or (ext == '.TIF') or (ext == '.TIFF'):
            if comp != None:
                # code 1 means uncompressed tif
                # code 5 means LZW compressed tif
                cv2.imwrite(ofn, img, (cv2.IMWRITE_TIFF_COMPRESSION, comp))
            else:
                # Use default
                cv2.imwrite(ofn, img)
        else:
            cv2.imwrite(ofn, img)
    else:
        cv2.imwrite(ofn, img, (cv2.IMWRITE_JPEG_QUALITY, qual))

#def remod(ifns, ofnbase, halfwidth=10, halfexclwidth=0, topbot=False,
def remod(ifns, ofns, halfwidth=10, halfexclwidth=0, topbot=False,
          TEST=False):
    print('remod:')
    '''REMOD - Create reference images from a stack
    REMOD(ifns, ofnbase) loads all the images in IFNS (not all at once)
    and produces output images that are a box car average of nearby images
    with the central image excluded.
    Optional third argument HALFWIDTH specifies the width of the box car
    to be 2*HALFWIDTH+1. HALFWIDTH defaults to 10.
    Optional fourth argument HALFEXCLWIDTH specifies the number of
    excluded images as 2*HALFEXCLWIDTH+1. HALFEXCLWIDTH defaults to zero,
    so only one central image is excluded.
    Optional fifth argument TOPBOT specifies that images near the top and
    bottom should be calculated, even though they do not have enough
    neighbors to calculate the average over a full box car.
    OFNBASE may be a string with a single '%i' or equivalent in it to
    receive the image number or it may be a function that takes an integer
    and returns a string. Numbering of images is along IFNS: with
    HALFWIDTH=10 and TOPBOT=False, the first saved image has number 10.'''
    # Magic argument TEST, when True, redefines the loadImage function
    # to simply return 10*the number of the image and redefines the saveImage
    # function to print out some stats.
    stack = []
    Z = 2*halfwidth
    N = len(ifns)
    abovesum = None
    belowsum = None
    nabove = 0
    nbelow = 0
    keepin = halfwidth - halfexclwidth

    def idx(k):
        return k % Z

    if TEST:
        def loadTestImage(ifn):
            return 10*ifn

        def saveTestImage(img, ofn):
            print('save image. ofn=', ofn)
            print('abovesum = ', abovesum, 'nabove=', nabove)
            print('belowsum = ', belowsum, 'nbelow=', nbelow)
            print('image = ', img)
        loader = loadTestImage
        saver = saveTestImage
    else:
        loader = loadImage
        saver = saveImage

    def writeImage(k):
        print('writeImage:')
        print(type(belowsum))
        img = belowsum.copy()
        if not abovesum is None:
            img += abovesum
        img /= nabove+nbelow
        '''
        if cur_method(ofnbase)==str:
            ofn = ofnbase % k
        else:
            ofn = ofnbase(k)
        '''
        ofn = ofns[k]
        print('remod writing image: %s' % (ofn))
        saver(img.astype('uint8'), ofn)

    print('N = %d' % N)
    for k in range(N):
        print('Loop, k=%d' % k)
        if nbelow >= keepin:
            belowsum -= stack[idx(k - keepin)]
            nbelow -= 1

        nwimg = loader(ifns[k]).astype('float32')

        if belowsum is None:
            belowsum = nwimg.copy()
        else:
            belowsum += nwimg
        nbelow += 1

        if k>=halfwidth:
            if k>=Z or topbot:
                writeImage(k-halfwidth)

        if nabove >= keepin:
            abovesum -= stack[idx(k-Z)]
            nabove -= 1
        if k>=halfwidth+halfexclwidth:
            if abovesum is None:
                abovesum = stack[idx(k - halfwidth - halfexclwidth)].copy()
            else:
                abovesum += stack[idx(k - halfwidth - halfexclwidth)]
            nabove += 1

        if k<Z:
            stack.append(nwimg)
        else:
            stack[idx(k)] = nwimg

    if topbot:
        for k in range(N, N+halfwidth):
            if nbelow>0:
                belowsum -= stack[idx(k - keepin)]
                nbelow -= 1
            writeImage(k-halfwidth)
            abovesum -= stack[idx(k - Z)]
            abovesum += stack[idx(k - halfwidth - halfexclwidth)]



if __name__ == '__main__':
  print("Running " + __file__ + ".__main__()")
  if (len(sys.argv) < 3):
    sys.stderr.write('\nUsage: %s halfwidth image_file_glob output_dir \n' % (sys.argv[0]))
    sys.stderr.write('           Compute local gral running average images for input image stack.\n')
    sys.stderr.write('           The gral images are written to new files \n')
    sys.stderr.write('           with same names in output_dir\n\n')
    sys.stderr.write('           Example: %s 10 "mydir/*.tif" outputdir \n\n' % sys.argv[0])
    exit(1)

    # halfwidth = int(sys.argv[1])
    halfwidth = 10
    # fn_pat = sys.argv[2]
    # out_dir = sys.argv[3]
    out_dir = '~/scratch/remod_out'

    # halfwidth = 10
    # fn_pat = '../../swift-ir_tests/LM9R5CA1_1024/images_aligned_s24_3/*.jpg'
    # out_dir = '../../swift-ir_tests/LM9R5CA1_1024/images_aligned_s24_3_MDL'

    # ifns = sorted(glob.glob(fn_pat))
    # ifns = sorted(glob.glob("~/glanceem_swift/test_images/r34_tifs/*.tif"))
    ifns = sorted(glob.glob("/Users/joelyancey/glanceem_swift/test_images/r34_tifs/*.tif"))

    print('\n'.join(ifns))

    # ofns = [ '%s/%s_MDL.jpg' % (out_dir, os.path.splitext(os.path.split(ofn)[-1])[0]) for ofn in ifns]
    ofns = ['%s/%s_MDL.jpg' % (out_dir, os.path.splitext(os.path.split(ofn)[-1])[0]) for ofn in ifns]

    remod(ifns, ofns, halfwidth=halfwidth, topbot=True)

    #  python3 remod_script.py  10 "~/glanceem_swift/test_images/r34_tifs/*.tif" ~/scratch/remod_out