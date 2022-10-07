#!/usr/bin/env python3
'''
Job script which calls loadImage, saveImage, and affineImage (affineImage originally relied on cv2 for applying
the affine transformation)
'''
import os
import sys
import logging
import platform
import subprocess as sp
import numpy as np
# from PIL import Image
import zarr
# import tifffile

logger = logging.getLogger(__name__)

def run_command(cmd, arg_list=None, cmd_input=None):
    logger.debug("\n================== Run Command ==================")
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    logger.debug("  Running command: " + str(cmd_arg_list))
    logger.debug("   Passing Data\n==========================\n" + str(cmd_input) + "==========================\n")
    # Note: decode bytes if universal_newlines=False in Popen (cmd_stdout.decode('utf-8'))
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    logger.debug("Command output: \n\n" + cmd_stdout + "==========================\n")
    logger.error("Command error: \n\n" + cmd_stderr + "==========================\n")
    logger.debug("=================================================\n")
    return ({'out': cmd_stdout, 'err': cmd_stderr})


# def image_apply_affine(in_fn=None, out_fn=None, afm=None, rect=None, grayBorder=False):
#     logger.critical("image_apply_affine afm: " + str(afm))
#     in_img = loadImage(in_fn)
#     logger.critical("Transforming " + str(in_fn))
#     logger.critical("    afm = " + str(afm))
#     logger.critical("    rect = " + str(rect))
#     logger.critical("    grayBorder = " + str(grayBorder))
#     out_img = affineImage(afm, in_img, rect=rect, grayBorder=grayBorder)
#     logger.critical("  saving transformed image as: " + str(out_fn))
#     try:
#         saveImage(out_img, out_fn)
#     except Exception:
#         logger.warning("An Exception Occurred Running 'saveImage'")
#         logger.warning(traceback.format_exc())


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
    # in_fn = sys.argv[-2] # Input File Name
    # out_fn = sys.argv[-1] # Output File Name
    in_fn = sys.argv[-4]  # Input File Name
    out_fn = sys.argv[-3]  # Output File Name
    zarr_grp = sys.argv[-2]  # Zarr Group
    ID = int(sys.argv[-1])
    rect = None
    grayBorder = False

    # Image.MAX_IMAGE_PIXELS = 1_000_000_000_000

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

    # if sys.argv[i] == '-rect':
    #     bb_x = rect[2]
    #     bb_y = rect[3]
    #     offset_x = rect[0]
    #     offset_y = rect[1]
    # else:
    #     offset_x = 0
    #     offset_y = 0

    bb_x = rect[2]
    bb_y = rect[3]
    offset_x = rect[0]
    offset_y = rect[1]

    # in_fn
    # out_fn
    a = afm_list[0]
    c = afm_list[1]
    e = afm_list[2] + offset_x
    b = afm_list[3]
    d = afm_list[4]
    f = afm_list[5] + offset_y

    my_path = os.path.split(os.path.realpath(__file__))[0]

    system = platform.system()
    node = platform.node()
    if system == 'Darwin':
        mir_c = my_path + '/lib/bin_darwin/mir'
    elif system == 'Linux':
        if '.tacc.utexas.edu' in node:
            mir_c = my_path + '/lib/bin_tacc/mir'
        else:
            mir_c = my_path + '/lib/bin_linux/mir'

    mir_script = \
        'B %d %d 1\n' \
        'Z 128\n' \
        'F %s\n' \
        'A %g %g %g %g %g %g\n' \
        'RW %s\n' \
        'E' % (bb_x, bb_y, in_fn, a, c, e, b, d, f, out_fn)
    o = run_command(mir_c, arg_list=[], cmd_input=mir_script)


    # if sys.argv[i] == '-rect':
    #     #TODO Use pillow to store median greyscale value for each image in list, for now just use 128
    #     mir_script = \
    #         'B %d %d 1\n' \
    #         'Z 128\n' \
    #         'F %s\n' \
    #         'A %g %g %g %g %g %g\n' \
    #         'RW %s\n' \
    #         'E' % (bb_x, bb_y, in_fn, a, c, e, b, d, f, out_fn)
    #     o = run_command(mir_c, arg_list=[], cmd_input=mir_script)
    # else:
    #     mir_script = \
    #         'F %s\n' \
    #         'Z 128\n' \
    #         'A %g %g %g %g %g %g\n' \
    #         'RW %s\n' \
    #         'E' % (in_fn, a, c, e, b, d, f, out_fn)
    #     o = run_command(mir_c, arg_list=[], cmd_input=mir_script)




    # Python Implementation
    # try:
    #     image_apply_affine(in_fn=in_fn, out_fn=out_fn, afm=afm, rect=rect, grayBorder=grayBorder)
    # except Exception:
    #     logger.warning("An Exception Occurred Running 'image_apply_affine'")
    #     logger.warning(traceback.format_exc())


    '''
    im = Image.open('/Users/joelyancey/glanceEM_SWiFT/test_projects/test93/scale_4/img_aligned/R34CA1-BS12.109.tif')
    /Users/joelyancey/miniconda3/envs/alignENV/lib/python3.9/site-packages/PIL/TiffImagePlugin.py:845: 
    UserWarning: Corrupt EXIF data.  Expecting to read 4 bytes but only got 0. 
    
    '''


    # dimx = bb_x
    # dimy = bb_y
    dimx = rect[2]
    dimy = rect[3]

    # try:
    #     im = Image.open(out_fn)
    # except Exception as e:
    #     print("Error on image: ", out_fn)
    #     print(e)

    import tifffile
    im = tifffile.imread(out_fn)
    # im = Image.open(out_fn)
    # im = tifffile.imread(out_fn)
    logger.critical('out_fn = %s' % out_fn)
    store = zarr.open(zarr_grp)
    # print('ID = %s' % str(ID))
    # print(store.info)

    store[ID, :, :] = im
    store.attrs['_ARRAY_DIMENSIONS'] = ["z", "y", "x"]

    sys.stdout.close()
    sys.stderr.close()


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