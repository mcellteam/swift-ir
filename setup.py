import setuptools
from setuptools import setup, find_packages
# setup(use_scm_version=True)

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="alignem",
    version="0.0.1",
    author="Joel Yancey,",
    author_email="joelgyancey@ucla.edu",
    description="AlignEM-SWIFT is a graphical tool for aligning serial section electron micrographs using SWiFT-IR.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    platforms=["any"],
    url="https://github.com/mcellteam/swift-ir/tree/development_ng",
    # packages=find_packages(),
    packages=setuptools.find_packages(where="./src", exclude=("./tests",)),
    python_requires=">=3.7",
    entry_points={
        "console_scripts": [
            "alignem = alignEM:main",
        ]
    }

)


if __name__=="__main__":
    setup()
