#!/usr/bin/env python3

import sys

import argparse
from source.Qt.package import align_swiftir

if __name__ == '__main__':

  parser = argparse.ArgumentParser ()
  parser.add_argument("x", type=int, help="integer value to start the crop in the x direction")
  parser.add_argument("y", type=int, help="integer value to start the crop in the y direction")
  parser.add_argument("w", type=int, help="integer value of the width to crop in the x direction")
  parser.add_argument("h", type=int, help="integer value of the height to crop in the y direction")

  parser.add_argument("infile", help="file name of the original image")
  parser.add_argument("outfile", help="file name of the scaled image")
  arg_space = parser.parse_args ()

  print ( "CROP: " + str(arg_space.x) + " " + str(arg_space.y) + " " + str(arg_space.w) + " " + str(arg_space.h) + " " + arg_space.infile + " " + arg_space.outfile )

  #img = align_swiftir.swiftir.scaleImage (align_swiftir.swiftir.loadImage(arg_space.infile), fac=arg_space.scale)
  #align_swiftir.swiftir.saveImage (img, arg_space.outfile)

  img = align_swiftir.swiftir.extractStraightWindow (align_swiftir.swiftir.loadImage(arg_space.infile), xy=(arg_space.x, arg_space.y), siz=(arg_space.w, arg_space.h))
  align_swiftir.swiftir.saveImage (img, arg_space.outfile)

  sys.stdout.close()
  sys.stderr.close()
