#!/usr/bin/env python3

import os
from task_queue import OutputQueue
import sys
import signal
import subprocess as sp

# This is monotonic (0 to 100) with the amount of output:
debug_level = 0  # A larger value prints more stuff

def print_debug ( level, p1=None, p2=None, p3=None, p4=None ):
    global debug_level
    if level <= debug_level:
      if p1 == None:
        print ( "" )
      elif p2 == None:
        print ( str(p1) )
      elif p3 == None:
        print ( str(p1) + str(p2) )
      elif p4 == None:
        print ( str(p1) + str(p2) + str(p3) )
      else:
        print ( str(p1) + str(p2) + str(p3) + str(p4) )


def is_windows ():

    if os.name.startswith('posix'):
      return False
    if os.name.startswith('nt'):
      return True

    if sys.platform.startswith('win'):
      return True
    if sys.platform.startswith('cygwin'):
      return True
    if sys.platform.startswith('linux'):
      return False
    if sys.platform.startswith('darwin'):
      return False
    if sys.platform.startswith('freebsd'):
      return False
    if sys.platform.startswith('sunos'):
      return False


def parse_quoted_args_posix ( s ):
    # Turn a string of quoted arguments into a list of arguments
    # This code handles escaped quotes (\") and escaped backslashes (\\)
    print_debug ( 3, "parse_quoted_args_posix got " + s )
    args = []
    next = ""
    inquote = False
    escaped = False
    i = 0
    while i < len(s):
        if s[i] == '"':
            if escaped:
                next += '"'
                escaped = False
            else:
                if inquote:
                    args.append ( next )
                    next = ""
                inquote = not inquote
        elif s[i] == '\\':
            if escaped:
                next += '\\'
                escaped = False
            else:
                escaped = True
        else:
            if inquote:
                next += s[i]
        i += 1
    if len(next) > 0:
        args.append ( next )
    return args


def parse_quoted_args_windows ( s ):
	# Turn a string of quoted arguments into a list of arguments
	print_debug ( 3, "parse_quoted_args_windows got " + s )
	args = []
	next = ""
	inquote = False
	escaped = False
	i = 0
	while i < len(s):
		if s[i] == '"':
			if inquote:
				args.append ( next )
				next = ""
			inquote = not inquote
		else:
			if inquote:
				next += s[i]
		i += 1
	if len(next) > 0:
		args.append ( next )
	print_debug ( 3, "parse_quoted_args_windows returning " + str(args) )
	return args

def convert_for_windows ( cmds ):
	wcmds = []
	for cmd in cmds:
		if cmd.upper().startswith ( "C:" ):
			wcmds.append ( "c:\\" + cmd[2:] )
		else:
			wcmds.append ( cmd )
	return ( wcmds )



if __name__ == '__main__':

  if is_windows():

      wd = sys.argv[1]
      if sys.version_info.major == 3:
        cmd = input()
        args = input()
      else:
        cmd = raw_input()
        args = raw_input()

      if debug_level > 4: sys.stdout.write('\n\nMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM\n')
      if debug_level > 4: sys.stdout.write('Running task_wrapper.py with \n  cmd: {0}   \n  args: {1}   \n  wd: {2}\n'.format(cmd, args, wd))

      cmd_list = []
      if (cmd.strip()[0] == '"') and (cmd.strip()[-1] == '"'):
        if debug_level > 4: sys.stdout.write("\nUsing quoted command syntax with cmd:\n " + cmd )
        # Using quoted command syntax, so remove quotes before adding
        cmd_list.extend ( parse_quoted_args_windows(cmd.strip()) )
      else:
        if debug_level > 4: sys.stdout.write("\nUsing string command syntax\n")
        # Just add the string as before
        cmd_list.append(cmd)

      if (args.strip()[0] == '"') and (args.strip()[-1] == '"'):
        if debug_level > 4: sys.stdout.write("\nUsing quoted arg syntax\n")
        cmd_list.extend ( parse_quoted_args_windows ( args.strip() ) )
        # Using quoted arguments syntax (space separated list of strings), so remove quotes before adding
        # cmd_list.append ( cmd.strip()[1:-1] )
      else:
        if debug_level > 4: sys.stdout.write("\nUsing string arg syntax\n")
        # Just add the strings split by spaces as before
        cmd_list.extend(args.split())

      if debug_level > 4: sys.stdout.write ( "\nNormal cmd_list: " + str(cmd_list) )
      cmd_list = convert_for_windows ( cmd_list )
      if debug_level > 4: sys.stdout.write ( "\nWindows cmd_list: " + str(cmd_list) )

      if debug_level > 4: sys.stdout.write('\nMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM\n\n\n')

      proc = sp.Popen(cmd_list, cwd=wd, bufsize=1, shell=False, close_fds=False, stdout=sp.PIPE, stderr=sp.PIPE)

      def sig_handler(signum, frame):
        if debug_level > 4: sys.stdout.write('\nSending signal: {0} to child PID: {1}\n'.format(signum, proc.pid))
        sys.stdout.flush()
        proc.send_signal(signum)
        if debug_level > 4: sys.stdout.write('\nTerminated task_wrapper.py\n')
        sys.stdout.flush()
        exit(15)

      signal.signal(signal.SIGTERM, sig_handler)

      output_q = OutputQueue()
      rc, res = output_q.run_proc(proc,passthrough=True)

      exit(abs(rc))

  else:

      wd = sys.argv[1]
      if sys.version_info.major == 3:
        cmd = input()
        args = input()
      else:
        cmd = raw_input()
        args = raw_input()

      if debug_level > 4: sys.stdout.write('\n\nMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM\n')
      if debug_level > 4: sys.stdout.write('Running task_wrapper.py with \n  cmd: {0}   \n  args: {1}   \n  wd: {2}\n'.format(cmd, args, wd))

      cmd_list = []
      if (cmd.strip()[0] == '"') and (cmd.strip()[-1] == '"'):
        if debug_level > 4: sys.stdout.write("\nUsing quoted command syntax with cmd:\n " + cmd )
        # Using quoted command syntax, so remove quotes before adding
        cmd_list.extend ( parse_quoted_args_posix(cmd.strip()) )
      else:
        if debug_level > 4: sys.stdout.write("\nUsing string command syntax\n")
        # Just add the string as before
        cmd_list.extend(cmd.split())

      if len(args.split()):
        if (args.strip()[0] == '"') and (args.strip()[-1] == '"'):
          if debug_level > 4: sys.stdout.write("\nUsing quoted arg syntax\n")
          cmd_list.extend ( parse_quoted_args_posix(args.strip()) )
          # Using quoted arguments syntax (space separated list of strings), so remove quotes before adding
          # cmd_list.append ( cmd.strip()[1:-1] )
        else:
          if debug_level > 4: sys.stdout.write("\nUsing string arg syntax\n")
          # Just add the strings split by spaces as before
          cmd_list.extend(args.split())

      if debug_level > 4: sys.stdout.write ( "\nFinal cmd_list: " + str(cmd_list) )

      if debug_level > 4: sys.stdout.write('\nMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM\n\n\n')

      proc = sp.Popen(cmd_list, cwd=wd, bufsize=1, shell=False, close_fds=False, stdout=sp.PIPE, stderr=sp.PIPE)

#      proc = sp.Popen(['echo "this is it" > foo_5.txt'], cwd=wd, bufsize=1, shell=True, close_fds=False, stdout=sp.PIPE, stderr=sp.PIPE)

      def sig_handler(signum, frame):
        if debug_level > 4: sys.stdout.write('\nSending signal: {0} to child PID: {1}\n'.format(signum, proc.pid))
        sys.stdout.flush()
        proc.send_signal(signum)
        if debug_level > 4: sys.stdout.write('\nTerminated task_wrapper.py\n')
        sys.stdout.flush()
        exit(15)

      signal.signal(signal.SIGTERM, sig_handler)

      output_q = OutputQueue()
      rc, res = output_q.run_proc(proc,passthrough=True)

      exit(abs(rc))

