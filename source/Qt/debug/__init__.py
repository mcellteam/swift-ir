__all__ = []

print(f'{__name__}')

from . import mod_a
from .mod_a import *
__all__.extend(mod_a.__all__)
__all__.append('mod_a')

# from .mod_a import *

from . import mod_b
from .mod_b import *
__all__.extend(mod_b.__all__)
__all__.append('mod_b')

