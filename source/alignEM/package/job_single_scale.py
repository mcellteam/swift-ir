#!/usr/bin/env python3

import sys
import argparse
from swiftir import loadImage
from swiftir import saveImage
from swiftir import scaleImage

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("scale", type=int, help="integer value to scale image")
    parser.add_argument("infile", help="file name of the original image")
    parser.add_argument("outfile", help="file name of the scaled image")
    arg_space = parser.parse_args()

    print("job_single_scale | SCALE: " + str(arg_space.scale) + " " + arg_space.infile + " " + arg_space.outfile)

    img = scaleImage(loadImage(arg_space.infile), fac=arg_space.scale)
    saveImage(img, arg_space.outfile)

    sys.stdout.close()
    sys.stderr.close()
