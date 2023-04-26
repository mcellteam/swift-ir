from pkg_resources import get_distribution, DistributionNotFound
try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    pass  # package is not installed

__all__ = []

print(f'{__name__}')

from . import alignem
from .alignem import main
# __all__.extend(main.__all__)

from . import src
from .src import *
__all__.extend(src.__all__)
__all__.append('src')







