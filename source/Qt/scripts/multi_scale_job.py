#!/usr/bin/env python3

import sys
from scripts import align_swiftir

if __name__ == '__main__':
  # Args: self source_image s1 t1 s2 t2 s3 t3
  # Where s# is a scale value and t# is a target image name
  if  not ( (2 * int(len(sys.argv) / 2)) == len(sys.argv) ):
    print ( "Error: " + arv[0] + " requires parameters of the form: source_image [scale_value target_image]...")
  else:
    # Read the source image
    source_image_file_name = sys.argv[1]
    source_image = align_swiftir.swiftir.loadImage(source_image_file_name)

    # Build a list of scale/image pairs for each target image
    m = sys.argv[2:]
    scale_target_pair_list = [[m[2*i],m[(2*i)+1]] for i in range(int(len(m)/2)) ]

    for arg_pair in scale_target_pair_list:
      scaled_image = align_swiftir.swiftir.scaleImage (source_image, fac=int(arg_pair[0]))
      align_swiftir.swiftir.saveImage (scaled_image, arg_pair[1])
