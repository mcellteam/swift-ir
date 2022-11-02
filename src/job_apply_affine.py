#!/usr/bin/env python3
'''
Job script which calls loadImage, saveImage, and affineImage (affineImage originally relied on cv2 for applying
the affine transformation)
'''
import os
import sys
import logging
import subprocess as sp
from PIL import Image
import zarr
import numpy as np
# import tifffile
try:
    from helpers import is_tacc, is_linux, is_mac
except ImportError:
    from src.helpers import is_tacc, is_linux, is_mac
try:
    import config as cfg
except ImportError:
    import src.config as cfg
try:
    import swiftir
except ImportError:
    import src.swiftir

logger = logging.getLogger(__name__)

def run_command(cmd, arg_list=None, cmd_input=None):
    logger.info("\n================== Run Command ==================")
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    # logger.info("  Running command: " + str(cmd_arg_list))
    # logger.info("   Passing Data\n==========================\n" + str(cmd_input) + "==========================\n")
    # Note: decode bytes if universal_newlines=False in Popen (cmd_stdout.decode('utf-8'))
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    # logger.info("Command output: \n\n" + cmd_stdout + "==========================\n")
    # logger.error("Command error: \n\n" + cmd_stderr + "==========================\n")
    # logger.info("=================================================\n")
    return ({'out': cmd_stdout, 'err': cmd_stderr})




def print_command_line_syntax(args):
    logger.debug('Usage: %s [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name' % (args[0]))
    logger.debug('Description:')
    logger.debug('  Apply 2D affine matrix to input image file')
    logger.debug('  with optional bounding rectangle and gray border.')
    logger.debug('  Result is written to output image file.')
    logger.debug('Options:')
    logger.debug('  -rect 0 0 100 100   : x_min y_min x_max y_max bounding rectangle')
    logger.debug('  -gray               : output with gray border')
    logger.debug('  -debug #            : # = debug level (0-100, larger numbers produce more output)')
    logger.debug('Arguments:')
    logger.debug('  -afm 1 0 0 0 1 0    : the 2D affine matrix')
    logger.debug('  in_file_name        : input image file name (opened for reading only)')
    logger.debug('  out_file_name       : output image file name (opened for writing and overwritten)')

if (__name__ == '__main__'):
    # len(sys.argv) = 16
    if (len(sys.argv) < 4):
        print_command_line_syntax(sys.argv)
        exit(1)
    in_fn = sys.argv[-4]  # Input File Name
    out_fn = sys.argv[-3]  # Output File Name
    zarr_grp = sys.argv[-2]  # Zarr Group
    ID = int(sys.argv[-1])
    rect = None
    grayBorder = False

    # Scan arguments (excluding program name and last 2 file names)
    i = 1
    # while (i < len(sys.argv) - 2):
    while (i < len(sys.argv) - 4):
        logger.info("Processing option " + sys.argv[i])
        if sys.argv[i] == '-afm':
            afm_list = []
            # Extend afm_list using the next 6 args
            for n in range(6):
                i += 1  # Increment to get the argument
                afm_list.extend([float(sys.argv[i])])
            afm = np.array(afm_list, dtype='float64').reshape((-1, 3))
        elif sys.argv[i] == '-rect':
            rect_list = []
            # Extend rect_list using the next 4 args
            for n in range(4):
                i += 1  # Increment to get the argument
                rect_list.extend([int(sys.argv[i])])
            rect = np.array(rect_list, dtype='int')
        elif sys.argv[i] == '-gray':
            grayBorder = True
            # No need to increment i because no additional arguments were taken
        elif sys.argv[i] == '-debug':
            i += 1  # Increment to get the argument
            debug_level = int(sys.argv[i])
        else:
            logger.warning("Improper argument list: %s" % str(sys.argv))
            print_command_line_syntax(sys.argv)
            exit(1)
        i += 1  # Increment to get the next option



    if not cfg.USE_OPENCV:
        bb_x, bb_y = rect[2], rect[3]
        offset_x, offset_y = rect[0], rect[1]

        a = afm_list[0]
        c = afm_list[1]
        e = afm_list[2] + offset_x
        b = afm_list[3]
        d = afm_list[4]
        f = afm_list[5] + offset_y

        my_path = os.path.split(os.path.realpath(__file__))[0]

        if is_tacc():   mir_c = my_path + '/lib/bin_tacc/mir'
        elif is_mac():  mir_c = my_path + '/lib/bin_darwin/mir'
        else:           mir_c = my_path + '/lib/bin_linux/mir'

        # TODO Use pillow to store median greyscale value for each image in list, for now just use 128
        mir_script = \
            'B %d %d 1\n' \
            'Z 128\n' \
            'F %s\n' \
            'A %g %g %g %g %g %g\n' \
            'RW %s\n' \
            'E' % (bb_x, bb_y, in_fn, a, c, e, b, d, f, out_fn)
        o = run_command(mir_c, arg_list=[], cmd_input=mir_script)

        path = os.path.join(os.path.dirname(os.path.dirname(out_fn)), 'mir_commands.dat')
        with open(path, 'a+') as f:
            f.write('\n---------------------------\n' + mir_script + '\n')

    # Python Implementation
    # try:
    #     image_apply_affine(in_fn=in_fn, out_fn=out_fn, afm=afm, rect=rect, grayBorder=grayBorder)
    # except Exception:
    #     logger.warning("An Exception Occurred Running 'image_apply_affine'")
    #     logger.warning(traceback.format_exc())

    dimx, dimy = rect[2], rect[3]
    # im = tifffile.imread(out_fn)
    Image.MAX_IMAGE_PIXELS = 1_000_000_000_000
    store = zarr.open(zarr_grp)
    # print(store.info)
    store[ID, :, :] = np.flip(Image.open(out_fn), axis=1)
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]
    sys.stdout.close()
    sys.stderr.close()

# Todo ask Art about this...
# im = Image.open('/Users/joelyancey/glanceEM_SWiFT/test_projects/test93/scale_4/img_aligned/R34CA1-BS12.109.tif')
# /Users/joelyancey/miniconda3/envs/alignENV/lib/python3.9/site-packages/PIL/TiffImagePlugin.py:845:
# UserWarning: Corrupt EXIF data.  Expecting to read 4 bytes but only got 0.

'''
B 1044 1044 1
Z 128
F R34CA1-BS12.102.tif
A 1.0053 0.00492668 -12.65607 -0.00559248 1.05508 11.5037
RW out_bb.tif
E
    

/Users/joelyancey/glanceem_swift/alignEM/src/job_python_apply_affine.py
-gray
-rect
-3
-3
-3
1030
1030
-afm
1.0053000450134277
0.004926680121570826
-2.3439199924468994
-0.005592479836195707
1.0550800561904907
1.5037000179290771
'''

