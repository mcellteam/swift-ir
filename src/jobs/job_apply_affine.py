#!/usr/bin/env python3

'''
Job script to apply affine transformations to a source image, producing an aligned+transformed result.
'''

import logging
import os
import platform
import subprocess as sp
import sys

import numpy as np

try:
    from src.utils.swiftir import applyAffine, reptoshape
except Exception as e:
    print(e)
    try:
        from swiftir import applyAffine, reptoshape
    except Exception as e:
        print(e)


logger = logging.getLogger(__name__)

def run_command(cmd, arg_list=None, cmd_input=None):
    # logger.info("\n================== Run Command ==================")
    cmd_arg_list = [cmd]
    if arg_list != None:
        cmd_arg_list = [a for a in arg_list]
        cmd_arg_list.insert(0, cmd)
    # Note: decode bytes if universal_newlines=False in Popen (cmd_stdout.decode('utf-8'))
    cmd_proc = sp.Popen(cmd_arg_list, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, universal_newlines=True)
    cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)
    # logger.info(f"\nSTDOUT:\n{cmd_stdout}\n\nSTDERR:\n{cmd_stderr}\n")
    return ({'out': cmd_stdout, 'err': cmd_stderr, 'rc': cmd_proc.returncode})



def get_bindir() -> str:
    '''Checks operating system. Returns the operating system-dependent
    file_path to where SWiFT-IR binaries should exist'''
    bindir = ''
    error = 'Operating System Could Not Be Resolved'
    if is_tacc():     bindir = 'bin_tacc'
    elif is_mac():    bindir = 'bin_darwin'
    elif is_linux():  bindir = 'bin_linux'
    else:
        logger.warning(error)
    assert len(bindir) > 0
    return bindir

def is_tacc() -> bool:
    '''Checks if the program is running on a computer at TACC. Returns a boolean.'''
    node = platform.node()
    if '.tacc.utexas.edu' in node:  return True
    else:                           return False


def is_linux() -> bool:
    '''Checks if the program is running on a Linux OS. Returns a boolean.'''
    system = platform.system()
    if system == 'Linux':  return True
    else:                  return False


def is_mac() -> bool:
    '''Checks if the program is running on macOS. Returns a boolean.'''
    system = platform.system()
    if system == 'Darwin':  return True
    else:                   return False


def run_mir(task):
    in_fn = task[0]
    out_fn = task[1]
    rect = task[2]
    cafm = task[3]
    border = task[4]

    # Todo get exact median greyscale value for each image in list, for now just use 128
    mir_c = os.path.join(os.path.split(os.path.realpath(__file__))[0], '../lib', get_bindir(), 'mir')

    bb_x, bb_y = rect[2], rect[3]
    # afm = np.array(cafm)
    # logger.info(f"cafm: {str(cafm)}")
    afm = np.array([cafm[0][0], cafm[0][1], cafm[0][2], cafm[1][0], cafm[1][1], cafm[1][2]], dtype='float64').reshape((-1, 3))
    # logger.info(f'afm: {str(afm.tolist())}')
    p1 = applyAffine(afm, (0,0))  # Transform Origin To Output Space
    p2 = applyAffine(afm, (rect[0], rect[1]))  # Transform BB Lower Left To Output Space
    offset_x, offset_y = p2 - p1  # Offset Is Difference of 'p2' and 'p1'
    a = cafm[0][0]
    c = cafm[0][1]
    e = cafm[0][2] + offset_x
    b = cafm[1][0]
    d = cafm[1][1]
    f = cafm[1][2] + offset_y

    mir_script = \
        'B %d %d 1\n' \
        'Z %g\n' \
        'F %s\n' \
        'A %g %g %g %g %g %g\n' \
        'RW %s\n' \
        'E' % (bb_x, bb_y, border, in_fn, a, c, e, b, d, f, out_fn)
    o = run_command(mir_c, arg_list=[], cmd_input=mir_script)



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

    run_mir(bb_x, bb_y, in_fn, out_fn, a, c, e, b, d, f, border=128)


'''
B 1044 1044 1
Z 128
F R34CA1-BS12.102.tif
A 1.0053 0.00492668 -12.65607 -0.00559248 1.05508 11.5037
RW out_bb.tif
E

'''
