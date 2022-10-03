# INSTRUCTIONS TO RUN AlignEM-SWiFT ON Lonestar6 AT TACC
# (DEPLOYMENT BY CONDA ENVIRONMENT STRATEGY)

# NOTES:
#     CONNECT TO Lonestar6 THROUGH THE VIS PORTAL. CHOOSE DCV SESSION.
#     PURGE MODULES (HAVE NO MODULES LOADED) WHEN CREATING OR ACTIVATING A CONDA ENV

#######################################
DO ONCE
#######################################
# (1) INSTALL+INITIALIZE MINICONDA
wget https://docs.conda.io/en/latest/miniconda.html#linux-installers
bash Miniforge3-Linux-x86_64.sh #correct the path
source ~/.bashrc
conda config --set auto_activate_base false  # prevents automatic activation of conda base env (interferes with DCV)

# (2) CLONE AlignEM-SWiFT
cdw # CLONE INTO WORK DIRECTORY
git clone https://github.com/mcellteam/swift-ir.git
cd swift-ir/
git checkout development_ng  # use 'git status' to check that you are on the correct branch

# (3) CREATE CONDA ENVIRONMENT
module purge  # purge modules before creating the environment (!)
conda env create --name=TACC01 --file-tacc.yml python=3.9

#######################################
DO EVERY TIME
#######################################
# (1) ACTIVATE THE CONDA ENVIRONMENT
module purge  # purge modules before activating the environment
conda activate TACC01

# (2) FETCH & PULL THE LATEST AlignEM-SWiFT
cd $WORK/swift-ir
git checkout development_ng  # only if necessary
git fetch
git pull

# (3) LOAD THE NECESSARY MODULES (ONLY AFTER ACTIVATING CONDA ENV)
ml gcc/11.2.0  impi/19.0.9 fftw3/3.3.10 python_cacher/1.2  # 'ml' is a TACC alias for 'module load'

# (4) RUN THE APP ('alignEM.py' is the entry point to AlignEM-SWiFT)
python3 alignEM.py

