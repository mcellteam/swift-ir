Howdy! AlignEM-SWiFT is a software for serial section electron micrograph alignment ("registration").

AlignEM-SWiFT is under active development and becoming more stable by the day.

Please report any specific issues that may motivate fixes or new features.

Contact: joel@salk.edu

-------- Supported Python Version --------
Version 3.9+ (recommended)
Version 3.7+ (minimum)



-------- Packages List --------
numpy
psutil
tifffile
zarr
imagecodecs
scikit-image
tqdm
matplotlib
opencv-python-headless (or opencv-python)
dask
qtpy
qtawesome
pyqt5 (or: pyqt6 | pyside2 | pyside6)
pyqtwebengine-qt5 (or pyqtwebengine for Qt6 API)
neuroglancer
python3 -m pip install git+https://github.com/funkelab/funlib.math.git#egg=funlib.math
python3 -m pip install git+https://github.com/funkelab/funlib.geometry.git#egg=funlib.geometry
python3 -m pip install git+https://github.com/funkelab/daisy.git#egg=daisy
-------- (example) Install Pipenv and install using Pipfile --------
curl https://raw.githubusercontent.com/pypa/pipenv/master/get-pipenv.py | python

-------- (example) Install Python Dependencies with Pip --------
To install the required Python packages using pip:
python3 -m pip install --upgrade pips
python3 -m pip install neuroglancer numpy psutil opencv-python-headless scikit-image zarr tifffile dask imagecodecs tqdm qtpy qtawesome
python3 -m pip install pyqt6 pyqtwebengine
(or: python3 -m pip install pyqt5 pyqtwebengine-qt5)
python3 -m pip install git+https://github.com/funkelab/funlib.math.git#egg=funlib.math
python3 -m pip install git+https://github.com/funkelab/funlib.geometry.git#egg=funlib.geometry
python3 -m pip install git+https://github.com/funkelab/daisy.git#egg=daisy

-------- Clone AlignEM-SWIFT Repo & Switch to Branch --------
git clone https://github.com/mcellteam/swift-ir.git
cd swift-ir
git checkout joel-dev-pyside6

-------- Compile C Binaries (Important!) --------
MacOS: Precompiled binaries for MacOS are bundled, xand will be used automatically
Linux: Compilation requires a software called FFTW. Try:

       sudo apt-get install libjpeg-dev libtiff-dev libpng-dev libfftw3-dev
       # change directories to swift-ir/source/c
       make -f makefile.linux

-------- Run AlignEM-SWiFT --------
python3 source/Qt/main.py

Run with any Python+Qt API:
Example:
python3 source/Qt/main.py --api pyqt6
python3 source/Qt/main.py --api pyqt5
python3 source/Qt/main.py --api pside6
python3 source/Qt/main.py --api pyside2

-----------------------------------
-----------------------------------

Ubuntu Instructions (courtesy of Vijay):

sudo apt-get install libjpeg-dev libtiff-dev libpng-dev libfftw3-dev
conda create -n swift_env -c conda-forge python=3.9
conda activate swift_env
sudo pip install --upgrade pip
pip install git+https://github.com/funkelab/funlib.math.git#egg=funlib.math
pip install git+https://github.com/funkelab/funlib.geometry.git#egg=funlib.geometry
pip install git+https://github.com/funkelab/daisy.git#egg=daisy
git clone https://github.com/mcellteam/swift-ir.git
cd swift-ir
git checkout joel-dev-pyside6
pip install neuroglancer numpy psutil opencv-python-headless scikit-image zarr tifffile dask imagecodecs tqdm PySide6 qtpy qtawesome matplotlib
and lastly compile c code!

MacOS Tips:

conda env create -f environment.yml
conda activate swiftir-env
python3 -m pip install --upgrade pip
pip install git+https://github.com/funkelab/funlib.math.git#egg=funlib.math
pip install git+https://github.com/funkelab/funlib.geometry.git#egg=funlib.geometry
pip install git+https://github.com/funkelab/daisy.git#egg=daisy
pip install neuroglancer
pip install imagecodecs
git clone https://github.com/mcellteam/swift-ir.git
cd swift-ir
git checkout joel-dev-pyside6
python3 source/Qt/run.py

CentOS 7 Tips:

curl -sL https://rpm.nodesource.com/setup_13.x | bash -
sudo yum install -y nodejs
yum install gcc-c++ make    # may need to install build tools