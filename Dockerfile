FROM ubuntu:20.04
RUN apt-get update && apt-get upgrade -y && apt-get install -y python3.9
RUN apt install python3-pip
RUN pip3 install numpy psutil tifffile zarr imagecodecs imageio Pillow dask-image tensorstore neuroglancer
RUN pip3 install PySide6 PyQtWebEngine qtpy qtawesome pyqtgraph qtconsole
COPY swift-ir/ /code/swift-ir
RUN chmod +rx /code/swiftir
ENV PATH "/code:$PATH"