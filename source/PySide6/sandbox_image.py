'''


Qt loading large images doc:
https://wiki.qt.io/Loading_Large_Images

PySide6 QImageReader Docs:
https://doc.qt.io/qtforpython/PySide6/QtGui/QImageReader.html
'''


from PySide6.QtGui import QImageReader, QImageIOHandler



allocation_limit = QImageReader.allocationLimit()
print('\nAllocation limit (MB):',allocation_limit)
# print('\n'.join(map(str, allocation_limit)))

supported_image_formats = QImageReader.supportedImageFormats()
print('\nSupported image formats:')
print('\n'.join(map(str, supported_image_formats)))

supported_mime_types = QImageReader.supportedMimeTypes()
print('\nSupported Mime Types:')
print('\n'.join(map(str, supported_mime_types)))


print('Testing QImageReader.setQuality method')
print('quality now is:', QImageReader.quality())
QImageReader.setQuality()
print('quality now is:', QImageReader.quality())




'''

    def imageFormat (device)

    def imageFormat (fileName)

    def imageFormatsForMimeType (mimeType)

    def setAllocationLimit (mbLimit)

    def supportedImageFormats ()

    def supportedMimeTypes ()






NOTES



Chris Kawa Moderators Mar 2, 2015, 9:11 AM
It all comes down to basically one thing - the format the images are in.
First of all do some simple math. A raw full HD image file is 1920x1080*4 bytes in size and you want to load about 30 
of them every second which gives required throughput of over 230MB/s. Not many average HDDs or SSDs can pull that off, 
and loading your images is not the only thing they do every given moment. So a good compressed format is a must.

The other side of the spectrum is how fast can that format be uncompressed on load. Note that QImageReader will not 
only load, but also transform the underlying data format if needed, which might take time. Try to pick a format that's 
internal data is in ready to use format i.e. doesn't need yuv rgb conversion etc.

Also, try to just read the same files using plain old QFile readAll(). Benchmark that and it will tell you how much 
you spend on IO versus processing the image, so that you can choose the format better.
https://forum.qt.io/topic/51838/loading-images-fast


Q: Someone mentioned using QImageReader and load them scaled down, would that be faster? 
A: It depends on the file format but likely yes.

A:
Two things:
1. QtConcurrent::mapped() (taking the path and returning the image)
2. load the images prescaled 
https://www.qtcentre.org/threads/44130-Loading-Images-from-Directory-Faster



''''''

Allocation limit: 128

Supported image formats:
b'bmp'
b'cur'
b'gif'
b'heic'
b'heif'
b'icns'
b'ico'
b'jp2'
b'jpeg'
b'jpg'
b'pbm'
b'pgm'
b'png'
b'ppm'
b'svg'
b'svgz'
b'tga'
b'tif'
b'tiff'
b'wbmp'
b'webp'
b'xbm'
b'xpm'

Supported Mime Types:
b'image/bmp'
b'image/gif'
b'image/heic'
b'image/heif'
b'image/jp2'
b'image/jpeg'
b'image/png'
b'image/svg+xml'
b'image/svg+xml-compressed'
b'image/tiff'
b'image/vnd.microsoft.icon'
b'image/vnd.wap.wbmp'
b'image/webp'
b'image/x-icns'
b'image/x-portable-bitmap'
b'image/x-portable-graymap'
b'image/x-portable-pixmap'
b'image/x-tga'
b'image/x-xbitmap'
b'image/x-xpixmap'

''''''

QImageReader.setQuality()
Sets the quality setting of the image format to quality .

Some image formats, in particular lossy ones, entail a tradeoff between a) visual quality of the resulting image, and b) 
decoding execution time. This function sets the level of that tradeoff for image formats that support it.

In case of scaled image reading, the quality setting may also influence the tradeoff level between visual quality and 
execution speed of the scaling algorithm.

The value range of quality depends on the image format. For example, the “jpeg” format supports a quality range from 0 
(low visual quality) to 100 (high visual quality).


QImageReader.setQuality
Sets the quality setting of the image format to quality .

Some image formats, in particular lossy ones, entail a tradeoff between a) visual quality of the resulting image, and 
b) decoding execution time. This function sets the level of that tradeoff for image formats that support it.

In case of scaled image reading, the quality setting may also influence the tradeoff level between visual quality and 
execution speed of the scaling algorithm.

The value range of quality depends on the image format. For example, the “jpeg” format supports a quality range from 0 
(low visual quality) to 100 (high visual quality).



QImageIOHandler
https://doc.qt.io/qtforpython/PySide6/QtGui/QImageIOHandler.html#more





'''
