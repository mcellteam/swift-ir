echo "Purging modules..."
module purge
echo "Activating conda environment..."
conda activate TACC05
echo "Loading modules..."
module load gcc/11.2.0  impi/19.0.9 fftw3/3.3.10
echo "Listing modules..."
module list
