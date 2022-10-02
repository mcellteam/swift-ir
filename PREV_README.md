# SWiFT-IR

## Signal Whitening Fourier Transform Image Registration

### Developed by Art Wetzel, Pittsburgh Supercomputing Center

* **[User Documentation](docs/user/README.md)**
* **[Development Documentation](docs/development/README.md)**
* **[Running on TACC](docs/tacc/README.md)**
* **[Neuroglancer Documentation](https://github.com/joelyancey/neuroglancer#readme)**


### Original unaligned images:

![Unaligned Images](tests/unaligned.gif?raw=true "Unaligned Images")


### Images aligned with SWiFT-IR:

![Aligned Images](tests/aligned.gif?raw=true "Aligned Images")

# AlignEM-SWiFT
AlignEM-SWiFT is a graphical extension of SWiFT for aligning serial section electron micrographs.
Soon we will publish to PyPi for convenient 'pip' installation. This branch may not be stable.
Please report any feedback, suggestions, or bugs to joel@salk.edu.

Supported Python Versions:
Version 3.9+ (recommended),
Version 3.7+ (minimum)

#### 1) Get AlignEM-SWiFT

    git clone https://github.com/mcellteam/swift-ir.git
    cd swift-ir
    git fetch origin development_ng  # Fetch the branch!
    git checkout development_ng      # Switch Branch!

#### 2) Compile C Binaries (Linux Only, requires FFTW):

    sudo apt-get install libjpeg-dev libtiff-dev libpng-dev libfftw3-dev
    make -f makefile.linux  # from swift-ir/alignEM/lib

#### 3) Install Dependencies & Run:
    # Using Pipenv:
    pipenv install
    pipenv run python3 alignEM.py

    # Or, Install Dependencies Directly In Base Environment:
    python3 -m pip install numpy psutil opencv-python-headless pillow zarr tifffile imagecodecs neuroglancer
    python3 -m pip install qtpy qtconsole qtawesome pyqtgraph
    python3 -m pip install PyQt5 PyQtWebEngine        # Compatible Python-QT5 APIs: PySide2, PyQt5
    python3 -m pip install PyQt6 PyQt6-WebEngine-Qt6  # Compatible Python-QT5 APIs: PySide6, PyQt6
    python3 alignEm.py

#### Runtime Options:
    python3 alignEM.py
    python3 alignEM.py --api pyqt5    # Run with 'pyqt5' Python-Qt API (Qt5)
    python3 alignEM.py --api pyside2  # Run with 'pyside2' Python-Qt API (Qt5)
    python3 alignEM.py --api pyqt6    # Run with 'pyqt6' Python-Qt API (Qt6)
    python3 alignEM.py --api pyside6  # Run with 'pyside6' Python-Qt API (Qt6)
    python3 alignEM.py --loglevel     # Set verbosity (1-5, default: 2)

#### Ubuntu Instructions (Courtesy of Vijay):

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

#### CentOS8 Instructions:

    git clone git@github.com:mcellteam/swift-ir.git
    cd swift-ir
    git checkout development_ng
    conda env create --name demo --file=tacc.yml
    conda activate demo
    module load python_cacher/1.2
    python3 alignEM.py


