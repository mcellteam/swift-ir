#!/usr/bin/env python3

'''
Job script to apply affine transformations to a source image, producing an aligned+transformed result.
'''

import os
import sys
import logging
import subprocess as sp
import numpy as np

try:
    from helpers import get_bindir
except ImportError:
    from src.helpers import get_bindir
try:
    from swiftir import applyAffine, reptoshape
except ImportError:
    import src.swiftir

logger = logging.getLogger(__name__)

def run_command(cmd, arg_list=None, cmd_input=None):
    logger.info("\n================== Run Command ==================")
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    # Note: decode bytes if universal_newlines=False in Popen (cmd_stdout.decode('utf-8'))
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    return ({'out': cmd_stdout, 'err': cmd_stderr, 'rc': cmd_proc.returncode})


if (__name__ == '__main__'):
    in_fn = sys.argv[-2]
    out_fn = sys.argv[-1]
    rect = None
    grayBorder = False
    i = 1
    while (i < len(sys.argv) - 4):
        logger.info("Processing option " + sys.argv[i])
        if sys.argv[i] == '-afm':
            afm_list = []
            for n in range(6):
                i += 1
                afm_list.extend([float(sys.argv[i])])
            afm = np.array(afm_list, dtype='float64').reshape((-1, 3))
        elif sys.argv[i] == '-rect':
            rect_list = []
            for n in range(4):
                i += 1
                rect_list.extend([int(sys.argv[i])])
            rect = np.array(rect_list, dtype='int')
        elif sys.argv[i] == '-gray':
            grayBorder = True
        elif sys.argv[i] == '-debug':
            i += 1
            debug_level = int(sys.argv[i])
        else:
            logger.warning("Improper argument list: %s" % str(sys.argv))
            exit(1)
        i += 1

    bb_x, bb_y = rect[2], rect[3]
    p1 = applyAffine(afm, (0,0))  # Transform Origin To Output Space
    p2 = applyAffine(afm, (rect[0], rect[1]))  # Transform BB Lower Left To Output Space
    offset_x, offset_y = p2 - p1  # Offset Is Difference of 'p2' and 'p1'
    a = afm_list[0];  c = afm_list[1];  e = afm_list[2] + offset_x
    b = afm_list[3];  d = afm_list[4];  f = afm_list[5] + offset_y
    mir_c = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'lib', get_bindir(), 'mir')
    # Todo get exact median greyscale value for each image in list, for now just use 128
    mir_script = \
        'B %d %d 1\n' \
        'Z %g\n' \
        'F %s\n' \
        'A %g %g %g %g %g %g\n' \
        'RW %s\n' \
        'E' % (bb_x, bb_y, 128, in_fn, a, c, e, b, d, f, out_fn)
    o = run_command(mir_c, arg_list=[], cmd_input=mir_script)
    # path = os.path.join(os.path.dirname(os.path.dirname(out_fn)), 'mir_commands.dat')
    # with open(path, 'a+') as f:
    #     f.write('\n---------------------------\n' + mir_script + '\n')

    # Python Implementation
    # image_apply_affine(in_fn=in_fn, out_fn=out_fn, afm=afm, rect=rect, grayBorder=grayBorder)
    sys.stdout.write(o['out'])
    sys.stderr.write(o['err'])
    sys.stdout.close()
    sys.stderr.close()
    if o['rc']:
        exit(1)


'''
B 1044 1044 1
Z 128
F R34CA1-BS12.102.tif
A 1.0053 0.00492668 -12.65607 -0.00559248 1.05508 11.5037
RW out_bb.tif
E

'''
