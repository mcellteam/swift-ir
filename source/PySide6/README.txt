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

To install the required Python packages using pip:
python3 -m pip install numpy psutil opencv-python-headless scikit-image zarr tifffile dask imagecodecs tqdm PySide6
python3 -m pip install git+https://github.com/google/neuroglancer.git#egg=neuroglancer
python3 -m pip install git+https://github.com/funkelab/funlib.math.git#egg=funlib.math
python3 -m pip install git+https://github.com/funkelab/funlib.geometry.git#egg=funlib.geometry
python3 -m pip install git+https://github.com/funkelab/daisy.git#egg=daisy



#---------------- Ubuntu instructions (courtesy of Vijay) ----------------

sudo apt-get install libjpeg-dev libtiff-dev libpng-dev libfftw3-dev
conda create -n swift_env -c conda-forge python=3.9
conda activate swift_env
pip install git+https://github.com/funkelab/funlib.math.git#egg=funlib.math
pip install git+https://github.com/funkelab/funlib.geometry.git#egg=funlib.geometry
pip install git+https://github.com/funkelab/daisy.git#egg=daisy
git clone https://github.com/mcellteam/swift-ir.git
cd swift-ir
git checkout joel-dev-pyside6
pip install psutils PySide6 scikit-image dask neuroglancer zarr matplotlib opencv-python imagecodecs
and lastly compile c code!



