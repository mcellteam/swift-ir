Howdy! alignEM-SWiFT is a software for cryo-EM image registration. It is under *very* active development.

Please report ANY specific issues that could motivate new fixes or features. Contact:
joel@salk.edu

Rough installation instructions:

conda env create -f environment.yml
conda activate swiftir-env
pip install git+https://github.com/funkelab/funlib.math.git#egg=funlib.math
pip install git+https://github.com/funkelab/funlib.geometry.git#egg=funlib.geometry
pip install git+https://github.com/funkelab/daisy.git#egg=daisy
pip install neuroglancer
pip install imagecodecs
git clone https://github.com/mcellteam/swift-ir.git
cd swift-ir
git checkout joel-dev-pyside6
# precompiled c binaries are provided for MacOS
# For Linux, install FFTW:
#   sudo apt-get install libfftw3-dev
#   make -f makefile.linux
#   cd "source/c"
#   make -f makefile.linux
# Once the binaries are compiled:
python3 source/PySide6/run.py

#---------------- pip ----------------

To install the necessary packages using pip:
python3 -m pip install numpy psutil opencv-python-headless scikit-image neuroglancer zarr tifffile dask imagecodecs tqdm PySide6

#---------------- Dependencies List ----------------

python3 (v3.9 recommended)
pyside6
numpy
skimage (scikit-image)
imagecodecs
tifffile
zarr
dask
cv2 (opencv-python-headless)
PIL
tqdm
neuroglancer
    Recommended installation:
    pip install git+https://github.com/google/neuroglancer.git#egg=neuroglancer
daisy (https://github.com/funkelab/daisy)
    Recommended installation:
    pip install git+https://github.com/funkelab/funlib.math.git#egg=funlib.math
    pip install git+https://github.com/funkelab/funlib.geometry.git#egg=funlib.geometry
    pip install git+https://github.com/funkelab/daisy.git#egg=daisy





