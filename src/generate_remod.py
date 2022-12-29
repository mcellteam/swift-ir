#!/usr/bin/env python3

import sys
import os
import glob
import swiftir

if ( __name__ == '__main__'):

    if (len(sys.argv) < 3):
        sys.stderr.write('\nUsage: %s halfwidth image_file_glob output_dir \n' % (sys.argv[0]))
        sys.stderr.write('           Compute local gral running average images for input image stack.\n')
        sys.stderr.write('           The gral images are written to new files \n')
        sys.stderr.write('           with same names in output_dir\n\n')
        exit(1)

    halfwidth = int(sys.argv[1])
    fn_pat = sys.argv[2]
    out_dir = sys.argv[3]

    # halfwidth = 10
    # fn_pat = '../../swift-ir_tests/LM9R5CA1_1024/images_aligned_s24_3/*.jpg'
    # out_dir = '../../swift-ir_tests/LM9R5CA1_1024/images_aligned_s24_3_MDL'

    ifns = sorted(glob.glob(fn_pat))

    ofns = ['%s/%s_MDL%s' % (out_dir, os.path.splitext(os.path.basename(ofn))[0],
                             os.path.splitext(os.path.basename(ofn))[1]) for ofn in ifns]

    swiftir.remod(ifns, ofns, halfwidth=halfwidth, topbot=True)

    #  python3 src/generate_remod.py  10 "/Users/joelyancey/glanceem_swift/test_images/r34_tifs/*.tif" ~/scratch/remod_out