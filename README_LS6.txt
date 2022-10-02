# INSTRUCTIONS TO RUN AlignEM-SWiFT ON Lonestar6 AT TACC
# (DEPLOYMENT BY CONDA ENVIRONMENT STRATEGY)
# CONNECT TO Lonestar6 USING A DCV SESSION

# INSTALL MINICONDA
wget https://docs.conda.io/en/latest/miniconda.html#linux-installers
bash Miniconda3-latest-Linux-x86_64.sh #correct the path
source ~/.bashrc
conda config --set auto_activate_base false

# CLONE AlignEM-SWiFT
git clone https://github.com/mcellteam/swift-ir.git
cd swift-ir/
git checkout development_ng

# CREATE CONDA ENVIRONMENT
conda env create --name=TACC01 --file-tacc.yml
conda activate TACC01

# LOAD THE NECESSARY MODULES (ONLY AFTER CREATING CONDA ENV)
ml gcc/11.2.0  impi/19.0.9 fftw3/3.3.10 python_cacher/1.2

# RUN THE APP
python3 alignEM.py