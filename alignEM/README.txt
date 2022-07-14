Howdy! AlignEM-SWiFT is a software being developed for graphical serial section electron micrograph alignment or
"registration". It is in constant flux, but becoming more stable each and every day. Soon--hopefully--we will
have a better packaged version using setuptools. Eventually we will publish to PyPi.

Below are some notes I took on installation, they are not correct. They are not complete, exact, or anything more than
suggestions, and is probably not up to date. You can use any of the following Python-Qt APIs (PySide6, PySide2,
PyQt5, or PyQt6) by passing in the option --api at the command line when you run the program like this:

{# main.py is the script to run to launch the program.}
{python3 main --api pyqt6}

Contact: joel@salk.edu. This branch may not be stable.

-------- Install Python --------
Version 3.9+ (recommended)
Version 3.7+ (minimum)

-------- Install Pipenv --------
curl https://raw.githubusercontent.com/pypa/pipenv/master/get-pipenv.py | python

-------- Install Python Dependencies --------
To install the required Python packages using pip:
python3 -m pip install --upgrade pips
python3 -m pip install neuroglancer numpy psutil opencv-python-headless scikit-image zarr tifffile dask imagecodecs tqdm PySide6
python3 -m pip install git+https://github.com/funkelab/funlib.math.git#egg=funlib.math
python3 -m pip install git+https://github.com/funkelab/funlib.geometry.git#egg=funlib.geometry
python3 -m pip install git+https://github.com/funkelab/daisy.git#egg=daisy

-------- Clone Repo & Switch Branch --------
git clone https://github.com/mcellteam/swift-ir.git
cd swift-ir
git checkout joel-dev-alignem

-------- Compile C Binaries --------
MacOS: Precompiled binaries for MacOS are bundled, xand will be used automatically
Linux: Compilation requires a software called FFTW. Try:

       sudo apt-get install libjpeg-dev libtiff-dev libpng-dev libfftw3-dev
       # change directories to swift-ir/source/c
       make -f makefile.linux

-------- Run alignEM-SWiFT --------
# navigate to /swift-ir/source/Qt
python3 run.py

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
git checkout joel-dev-alignem
pip install psutils PySide6 scikit-image dask neuroglancer zarr matplotlib opencv-python imagecodecs
and lastly compile c code!git

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
git checkout joel-dev-alignem
cd alignEM
python3 main # <-- Command to Run AlignEM-SWiFT

CentOS 7 Tips:

curl -sL https://rpm.nodesource.com/setup_13.x | bash -
sudo yum install -y nodejs
yum install gcc-c++ make    # may need to install build tools