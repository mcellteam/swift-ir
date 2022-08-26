# import setuptools
# from setuptools import find_packages  # or find_namespace_packages
from setuptools import setup, find_packages
# setup(use_scm_version=True)

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="src",
    version="0.0.3",
    author="Joel Yancey,",
    author_email="joelgyancey@ucla.edu",
    description="AlignEM-SWIFT is a graphical tool for aligning serial section electron micrographs using SWiFT-IR.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    platforms=["any"],
    url="https://github.com/mcellteam/swift-ir/tree/development_ng",
    packages=find_packages(),
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "alignem = alignEM:main",
        ]
    }

)


if __name__=="__main__":
    setup()
