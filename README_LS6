# INSTRUCTIONS TO RUN AlignEM-SWiFT ON Lonestar6 AT TACC
# (DEPLOYMENT BY CONDA ENVIRONMENT STRATEGY)

# NOTES:
#     CONNECT TO Lonestar6 THROUGH THE VIS PORTAL. CHOOSE DCV SESSION.
#     PURGE MODULES (HAVE NO MODULES LOADED) WHEN CREATING OR ACTIVATING A CONDA ENV

========================== ALIGNEM-SWIFT THE EASY WAY ======


Do Once --------------------------------------

cdw
git clone https://github.com/mcellteam/swift-ir.git
cd swift-ir/
git checkout development_ng
source tacc_runonce

Do Every Time --------------------------------

cd $WORK/swift-ir
source tacc_runalways
align



========================== ALIGNEM-SWIFT THE HARD WAY ======

Do Once --------------------------------------

(1) INSTALL+INITIALIZE MINICONDA
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh                              # Adds special conda instructions to '.bashrc'
source ~/.bashrc                                             # Reruns your '.bashrc' script 
conda config --set auto_activate_base false                  # prevents automatic activation of conda base emv

(2) CLONE AlignEM-SWiFT
cdw                                                          # change directory to 'work' partition
git clone https://github.com/mcellteam/swift-ir.git          # clone the AlignEM-SWiFT source code
cd swift-ir/                                                 # change directory to top-level of application
git checkout development_ng                                  # Note: 'git status' will tell you your current branch

(3) CREATE CONDA ENVIRONMENT
module purge
conda env remove -n alignTACC                                # remove the env if created previously
conda env create --name=alignTACC --file tacc.yml python=3.9 # create the environment described in 'tacc.yml'


Do Every Time --------------------------------

(1) ACTIVATE THE CONDA ENVIRONMENT
module purge                                                 # purge modules before activating the environment
conda activate alignTACC                                        # activate the environment

(2) FETCH & PULL THE LATEST AlignEM-SWiFT
cd $WORK/swift-ir                                            # change to top-level of application directory
git pull                                                     # set your version to the most up-to-date version

(3) SET QT API
export QT_API=pyside6

(4) LOAD MODULES
ml intel/19.1.1 swr/21.2.5 python_cacher

(5) RUN THE APPLICATION
swr numactl --preferred=1 python3 alignEM.py

