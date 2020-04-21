#!/usr/bin/env python3

import time
import random

import argparse
import align_swiftir

if __name__ == '__main__':

  parser = argparse.ArgumentParser ()
  parser.add_argument("scale", type=int, help="integer value to scale image")
  parser.add_argument("infile", help="file name of the original image")
  parser.add_argument("outfile", help="file name of the scaled image")
  arg_space = parser.parse_args ()

  print ( "SCALE: " + str(arg_space.scale) + " " + arg_space.infile + " " + arg_space.outfile )

  img = align_swiftir.swiftir.scaleImage (align_swiftir.swiftir.loadImage(arg_space.infile), fac=arg_space.scale)
  align_swiftir.swiftir.saveImage (img, arg_space.outfile)
