import numpy as np
from ..mod_a.mod_a0 import mod_a0_f


__all__ = ['mod_b0_f']

def mod_b0_f(*args):

    tmp0 = mod_a0_f(*args)
    tmp1 = args[0] * tmp0
    
    return tmp1