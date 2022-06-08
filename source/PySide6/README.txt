Howdy! alignEM-SWiFT is a software for cryo-EM image registration. It is under *very* active development.

Please report ANY specific issues that could motivate new fixes or features. Contact:
joel@salk.edu

Rough installation instructions:

conda env create -f environment.yml
conda activate swiftir-env
pip install git+https://github.com/funkelab/funlib.math.git#egg=funlib.math
pip install git+https://github.com/funkelab/funlib.geometry.git#egg=funlib.geometry
pip install git+https://github.com/funkelab/daisy.git#egg=daisy
git clone https://github.com/mcellteam/swift-ir.git  
cd swift-ir
git checkout joel-dev-pyside6
python3 source/PySide6/run.py



