# INSTRUCTIONS TO RUN AlignEM-SWiFT ON Lonestar6 AT TACC
# (DEPLOYMENT BY CONDA ENVIRONMENT STRATEGY)

# NOTES:
#     CONNECT TO Lonestar6 THROUGH THE VIS PORTAL. CHOOSE DCV SESSION.
#     PURGE MODULES (HAVE NO MODULES LOADED) WHEN CREATING OR ACTIVATING A CONDA ENV

#######################################
# DO ONCE
#######################################

echo "Setting things up..."

echo "Changing to WORK directory..."
cd $WORK

echo "Getting Miniforge (conda) installer..."
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh

echo "Running Miniforge (conda) installer w/ default options..."
curl -LO https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
sh $WORK/Miniforge3-Linux-x86_64.sh -b
$WORiK/miniforge3/condabin/conda init

echo "Sourcing .bashrc..."
source ~/.bashrc

echo "Turning off annoying conda base environment so DCV will work..."
conda config --set auto_activate_base false

echo "Cloning AlignEM-SWiFT..."
git clone https://github.com/mcellteam/swift-ir.git

echo "Changing directory to swift-ir..."
cd swift-ir/

echo "Checking out development_ng branch..."
git checkout development_ng

echo "Purging modules..."
module purge

echo "Creating Conda environment from tacc.yml..."
conda env create --name=TACC01 --file tacc_old.yml python=3.9

echo "Adding alignEM.py to PATH..."
echo 'export PATH="$PATH:$WORK/swift-ir/alignEM.py"' >> ~/.bashrc

#######################################
# DO EVERY TIME
#######################################
# module purge
# conda activate TACC01
# cd $WORK/swift-ir
# git fetch
# git pull
# ml gcc/11.2.0  impi/19.0.9 fftw3/3.3.10
# python3 alignEM.py
