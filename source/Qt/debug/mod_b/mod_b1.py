import numpy as np
from .mod_b0 import mod_b0_f


__all__ = ['mod_b1_f']

def mod_b1_f(*args):

    tmp0 = mod_b0_f(*args)
    tmp1 = args[0] / tmp0

    return tmp1