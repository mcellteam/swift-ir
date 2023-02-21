#!/usr/bin/env python3

import os
import sys
import logging
import subprocess as sp

try:
    from helpers import get_bindir
except ImportError:
    from src.helpers import get_bindir



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
    return ({'out': cmd_stdout, 'err': cmd_stderr})

if __name__ == '__main__':

    job_script   = sys.argv[0]
    fn           = sys.argv[1]
    out          = sys.argv[2]

    mir_c = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'lib', get_bindir(), 'mir')

    name0 = 'corr_spot_0_' + fn
    name1 = 'corr_spot_1_' + fn
    name2 = 'corr_spot_2_' + fn
    name3 = 'corr_spot_3_' + fn

    mir_script = \
    'B 1024 1024\n' \
    'Z\n' \
    'F %s\n' \
    '96 96 104 104\n' \
    '512 96 312 104\n' \
    '512 512 312 312\n' \
    '96 512 104 312\n' \
    'T\n' \
    '0 1 2\n' \
    '2 3 0\n' \
    'W %s' % (name0, out)

    print(f'mir_script: {mir_script}')
    o = run_command(mir_c, arg_list=[], cmd_input=mir_script)
    print(str(o))


    # mir_script = '''
    # B 1024 1024 \n
    # Z \n
    # F %s \n
    # 96 96 104 104 \n
    # 512 96 312 104 \n
    # 512 512 312 312 \n
    # 96 512 104 312 \n
    # T \n
    # 0 1 2 \n
    # 2 3 0 \n
    # #F %s \n
    # #512 96 0 0 \n
    # #R \n
    # #F %s \n
    # #96 512 0 0 \n
    # #R \n
    # #F %s \n
    # #512 512 0 0 \n
    # #R \n
    # W %s
    # ''' % (name0, name1, name2, name3, out)

    sys.stdout.close()
    sys.stderr.close()
