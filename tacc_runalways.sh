echo "Purging modules..."
module purge                                                 # purge modules before activating the environment
echo "Activating 'alignTACC' conda env..."
conda activate alignTACC                                        # activate the environment

echo "cd'ing to swift-ir and pulling changes..."
cd $WORK/swift-ir                                            # change to top-level of application directory
git pull                                                     # set your version to the most up-to-date version

echo "Setting QT API environment flag..."
export QT_API=pyside6

echo "Loading swr module..."
ml intel/19.1.1 swr/21.2.5

echo "Loading python_cacher module..."
ml python_cacher


