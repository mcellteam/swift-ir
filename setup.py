"""
Setup file for alignem_swift.
Metadata is defined in pyproject.toml (PEP 621).

C extensions are pre-compiled and included in src/lib/bin_darwin/ and src/lib/bin_tacc/.
To build from source, uncomment the ext_modules below and ensure libjpeg headers are available.
"""
from setuptools import setup

# Uncomment to build C extensions from source (requires libjpeg headers):
# from distutils.extension import Extension
# ext_modules = [
#     Extension('src.lib.iavg', ['src/lib/iavg.c']),
#     Extension('src.lib.iscale', ['src/lib/iscale.c']),
#     Extension('src.lib.iscale2', ['src/lib/iscale2.c']),
#     Extension('src.lib.mir', ['src/lib/mir.c']),
#     Extension('src.lib.remod', ['src/lib/remod.c']),
#     Extension('src.lib.swim', ['src/lib/swim.c']),
# ]

if __name__ == "__main__":
    setup()
