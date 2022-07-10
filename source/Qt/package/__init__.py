__all__ = []

print(f'{__name__}')

from . import src
from .src import *
__all__.extend(src.__all__)
__all__.append('src')

# from .src import python_swiftir
# from .src.python_swiftir import *
# __all__.extend(src.python_swiftir.__all__)
# __all__.append('src.python_swiftir')









