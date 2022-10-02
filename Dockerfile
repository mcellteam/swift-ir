FROM ubuntu:20.04
RUN apt-get update && apt-get upgrade -y && apt-get install -y python3.9
RUN apt install -y python3-pip
COPY . /code
ENV PATH "/code:$PATH"
# WORKDIR "/code"
# RUN apt install -y git
# RUN git clone https://github.com/mcellteam/swift-ir.git && cd swift-ir && git checkout development_ng
RUN apt install -y libfftw3-dev libfftw3-doc
RUN pip3 install PySide6 PyQtWebEngine qtpy qtawesome pyqtgraph qtconsole
RUN pip3 install numpy psutil tifffile zarr imagecodecs imageio Pillow dask-image tensorstore neuroglancer


# ____DEVELOPER NOTES BELOW THIS LINE____

# BUILD THE IMAGE:
# docker build -t joelyancey/alignem:0.0.1 .