#!/usr/bin/env python3
'''
Python SWiFT-IR job script - calls loadImage, saveImage, and scaleImage.
'''

import sys
import logging
import argparse
from swiftir import scaleImage, loadImage, saveImage

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("s", type=int, help="integer value to s image")
    parser.add_argument("infile", help="file name of the original image")
    parser.add_argument("outfile", help="file name of the scaled image")
    arg_space = parser.parse_args()
    logger.info("Scale: " + str(arg_space.scale) + " " + arg_space.infile + " " + arg_space.outfile)
    img = scaleImage(loadImage(arg_space.infile), fac=arg_space.scale)
    saveImage(img, arg_space.outfile)
    sys.stdout.close()
    sys.stderr.close()


