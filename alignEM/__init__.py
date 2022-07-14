__all__ = []

print(f'{__name__}')

from . import package
from .package import *
# __all__.extend(package.__all__)
__all__.append('package')

# from . import config
# from .config import *
# __all__.extend(config.__all__)