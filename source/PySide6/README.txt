Howdy! alignEM-SWiFT is a software for cryo-EM image registration. It is under *very* active development.

Please report ANY specific issues that could motivate new fixes or features. Contact:
joel@salk.edu

-------- Install Python Dependencies --------
To install the required Python packages using pip:
python3 -m pip install numpy psutil opencv-python-headless scikit-image zarr tifffile dask imagecodecs tqdm PySide6
python3 -m pip install git+https://github.com/google/neuroglancer.git#egg=neuroglancer
python3 -m pip install git+https://github.com/funkelab/funlib.math.git#egg=funlib.math
python3 -m pip install git+https://github.com/funkelab/funlib.geometry.git#egg=funlib.geometry
python3 -m pip install git+https://github.com/funkelab/daisy.git#egg=daisy

-------- Clone Repo & Switch Branch --------
git clone https://github.com/mcellteam/swift-ir.git
cd swift-ir
git checkout joel-dev-pyside6

-------- Compile C Binaries --------
MacOS: Precompiled binaries for MacOS are bundled, and will be used automatically
Linux: Compilation requires a software called FFTW. Try:

       sudo apt-get install libjpeg-dev libtiff-dev libpng-dev libfftw3-dev
       # change directories to swift-ir/source/c
       make -f makefile.linux

-------- Run alignEM-SWiFT --------
# navigate to /swift-ir/source/PySide6
python3 run.py



Ubuntu Instructions (courtesy of Vijay):

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

MacOS instructions using .yml:

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
python3 source/PySide6/run.py