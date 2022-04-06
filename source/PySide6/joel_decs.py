"""
from joel_decs import timeit, profileit, dumpit, traceit, countit

refs:
https://github.com/fabianlee/blogcode/blob/master/python/inspect_func_test_decorator.py

"""

import sys, argparse, time, inspect, logging, functools, tracemalloc

# BAD  -FAILS ON SOME FUNCTIONS
def countit(func):
    """
    A decorator that counts and prints the number of times a function has been executed
    https://stackoverflow.com/questions/739654/how-to-make-function-decorators-and-chain-them-together
    """
    def wrapper(*args, **kwargs):
        wrapper.count = wrapper.count + 1
        res = func(*args, **kwargs)
        print("  countit: {0} has been used: {1}x".format(func.__name__, wrapper.count))
        return res
    wrapper.count = 0
    return wrapper

#thsi may have caused error
def timeit(func):
    """ Returns execution time """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()

        # Call the actual function
        res = func(*args, **kwargs)

        duration = time.perf_counter() - start
        # print(f'[{wrapper.__name__}] took {duration * 1000} ms')      # milliseconds
        print(f'[{wrapper.__name__}] took {duration} s')              # seconds
        return res

    return wrapper


def profileit(func):
    """Measure performance of a function"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
      tracemalloc.start()
      start_time = time.perf_counter()
      res = func(*args, **kwargs)
      duration = time.perf_counter() - start_time
      current, peak = tracemalloc.get_traced_memory()
      tracemalloc.stop()

      print("\nFunction:             {func.__name__} ({func.__doc__})"
            f"\nMemory usage:         {current / 10**6:.6f} MB"
            f"\nPeak memory usage:    {peak / 10**6:.6f} MB"
            f"\nDuration:             {duration:.6f} sec"
            f"\n{'-'*40}"
      )
      return res
    return wrapper



def dumpit(func):
    """
    Decorator to print function call details.

    This includes parameters names and effective values.
    https://stackoverflow.com/questions/6200270/decorator-that-prints-function-call-details-parameters-names-and-effective-valu
    """

    def wrapper(*args, **kwargs):
        func_args = inspect.signature(func).bind(*args, **kwargs).arguments
        func_args_str = ", ".join(map("{0[0]} = {0[1]!r}".format, func_args.items()))
        print("dumpit: ", end='')
        print(f"{func.__module__}.{func.__qualname__} ( {func_args_str} )")
        return func(*args, **kwargs)

    return wrapper



class StackTrace(object):
    def __init__(self, with_call=True, with_return=False,
                       with_exception=False, max_depth=-1):
        self._frame_dict = {}
        self._options = set()
        self._max_depth = max_depth
        if with_call: self._options.add('call')
        if with_return: self._options.add('return')
        if with_exception: self._options.add('exception')

    def __call__(self, frame, event, arg):
        ret = []
        if event == 'call':
            back_frame = frame.f_back
            if back_frame in self._frame_dict:
                self._frame_dict[frame] = self._frame_dict[back_frame] + 1
            else:
                self._frame_dict[frame] = 0

        depth = self._frame_dict[frame]

        if event in self._options\
          and (self._max_depth<0\
               or depth <= self._max_depth):
            ret.append(frame.f_code.co_name)
            ret.append('[%s]'%event)
            if event == 'return':
                ret.append(arg)
            elif event == 'exception':
                ret.append(repr(arg[0]))
            ret.append('in %s line:%s'%(frame.f_code.co_filename, frame.f_lineno))
        if ret:
            print("%s%s"%('  '*depth, '\t'.join([str(i) for i in ret])))

        return self

trace_indent = 0
def traceit(f):
    """
    https://cscheid.net/2017/12/11/minimal-tracing-decorator-python-3.html
    """

    sig = inspect.signature(f)
    def do_it(*args, **kwargs):
        global trace_indent
        ws = ' ' * (trace_indent * 2)
        print("%sENTER %s: " % (ws, f.__name__))
        for ix, param in enumerate(sig.parameters.values()):
            print("%s    %s: %s" % (ws, param.name, args[ix]))
        trace_indent += 1
        result = f(*args, **kwargs)
        trace_indent -= 1
        print("%sEXIT %s (returned %s)" % (ws, f.__name__, result))
        return result
    return do_it

