# INSTRUCTIONS TO RUN AlignEM-SWiFT ON Lonestar6 AT TACC
# (DEPLOYMENT BY CONDA ENVIRONMENT STRATEGY)

# NOTES:
#     CONNECT TO Lonestar6 THROUGH THE VIS PORTAL. CHOOSE DCV SESSION.
#     PURGE MODULES (HAVE NO MODULES LOADED) WHEN CREATING OR ACTIVATING A CONDA ENV

#######################################
DO ONCE
#######################################
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
module purge                                                 # purge modules before creating the environment
conda env create --name=TACC01 --file tacc.yml python=3.9    # create the environment described in 'tacc.yml'

#######################################
DO EVERY TIME
#######################################
(1) ACTIVATE THE CONDA ENVIRONMENT
module purge                                                 # purge modules before activating the environment
conda activate TACC01                                        # activate the environment

(2) FETCH & PULL THE LATEST AlignEM-SWiFT
cd $WORK/swift-ir                                            # change to top-level of application directory
git fetch                                                    # fetch the latest AlignEM-SWiFT changes
git pull                                                     # set your version to the most up-to-date version

(3) LOAD THE NECESSARY TACC MODULES
ml gcc/11.2.0  impi/19.0.9 fftw3/3.3.10                      # 'ml' is a TACC alias for 'module load'

(4) RUN AlignEM-SWiFT
python3 alignEM.py

