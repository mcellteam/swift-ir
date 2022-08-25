__all__ = []

print(f'{__name__}')

from . import src
from .src import *
__all__.extend(src.__all__)
__all__.append('src')

def hello_world():
    print("Hello world")

