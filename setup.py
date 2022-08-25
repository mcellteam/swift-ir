import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="alignEM",
    version="0.0.1",
    author="Joel Yancey,",
    author_email="joelgyancey@ucla.edu",
    description="AlignEM-SWIFT is a graphical tool for aligning serial section electron micrographs using SWiFT-IR.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mcellteam/swift-ir/tree/development_ng",
    packages=setuptools.find_packages(),
    install_requires=[
            'numpy',
            'psutil',
            'opencv-python-headless',
            'pillow',
            'zarr',
            'tifffile',
            'imagecodecs',
            'neuroglancer',
            'qtconsole',
            'pyqt5',
            'pyqtwebengine',
            'qtpy',
            'qtawesome',
            'pyqtgraph',
            'tqdm'
        ],
    entry_points={
        'console_scripts': [
            'cursive = cursive.tools.cmd:cursive_command',
        ],
    },
    # classifiers=(
    #     "Programming Language :: Python :: 3",
    #     "License :: OSI Approved :: MIT License",
    #     "Operating System :: OS Independent",
    # ),
)