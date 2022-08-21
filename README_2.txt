Howdy! AlignEM-SWiFT is a software being developed for graphical serial section electron micrograph alignment or
"registration". It is in constant flux, but becoming more stable each and every day. Soon--hopefully--we will
have a better packaged version using setuptools. Eventually we will publish to PyPi.

Below are some notes I took on installation, they are not correct. They are not complete, exact, or anything more than
suggestions, and is probably not up to date. You can use any of the following Python-Qt APIs (PySide6, PySide2,
PyQt5, or PyQt6) by passing in the option --api at the command line when you run the program. Verbosity can be set
using the options -v, -vv, or -vvv.

Contact: joel@salk.edu. This branch may not be stable.

Supported Python Version:
Version 3.9+ (recommended)
Version 3.7+ (minimum)

1) Get AlignEM-SWiFT
    git clone https://github.com/mcellteam/swift-ir.git
    cd swift-ir
    git checkout joel-dev-alignem  # Switch Branch!

2) Compile C Binaries (Linux Only):
    # Compiling the C Binaries requires FFTW:
    sudo apt-get install libjpeg-dev libtiff-dev libpng-dev libfftw3-dev
    make -f makefile.linux  # from swift-ir/alignEM/lib

3) Install Dependencies & Run:
    # Using Pipenv:
    pipenv install
    pipenv run python alignEM.py

    # Or, Install Dependencies Directly In Base Environment:
    python -m pip install numpy psutil opencv-python-headless pillow zarr tifffile imagecodecs neuroglancer qtconsole
    python -m pip install PyQt5 PyQtWebEngine        # Compatible Python-QT5 APIs: PySide2, PyQt5
    python -m pip install PyQt6 PyQt6-WebEngine-Qt6  # Compatible Python-QT5 APIs: PySide6, PyQt6
    python alignEm.py

Run (Options):
    python alignEM.py
    python alignEM.py --api pyqt5    # Run with 'pyqt5' Python-Qt API (Qt5)
    python alignEM.py --api pyside2  # Run with 'pyside2' Python-Qt API (Qt5)
    python alignEM.py --api pyqt6    # Run with 'pyqt6' Python-Qt API (Qt6)
    python alignEM.py --api pyside6  # Run with 'pyside6' Python-Qt API (Qt6)
    python alignEM.py -v             # Verbosity -v, -vv, -vvv

Ubuntu Instructions (Courtesy of Vijay):

sudo apt-get install libjpeg-dev libtiff-dev libpng-dev libfftw3-dev
conda create -n swift_env -c conda-forge python=3.9
conda activate swift_env
sudo pip install --upgrade pip
git clone https://github.com/mcellteam/swift-ir.git
cd swift-ir
git checkout joel-dev-alignem
pip install PySide2 neuroglancer zarr opencv-python-headless psutils tifffile
# Compile C code! Example Compilation for MacOS:
#   cd swift-ir/lib
#   rm -r bin_linux
#   mkdir bin_linux
#   make -f makefile.linux

CentOS 7 Tips:

curl -sL https://rpm.nodesource.com/setup_13.x | bash -
sudo yum install -y nodejs
yum install gcc-c++ make    # may need to install build tools