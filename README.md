# SWiFT-IR

## Signal Whitening Fourier Transform Image Registration




### A.mir
```
B 469 344 1
F Aaperture.PNG
R
W w.ppm
```

### cpng.mir
```
F C.png
R
W e01.ppm
```

### d.mir
```
F 1-dna.png
R
W w.ppm
```

### e.mir
```
B 720 476 3
# After viewing the e05.ppm file then uncomment the following F,R lines to use
# water0 as a background with the, now hard to see, water1 triangles over top.
F water0.jpg
R
F water1.jpg
84 86 129 104 # this is vertex 0
83 151 105 272
175 106 300 135
295 160 602 272 # this is vertex 3
T # You can make better matches locally with more points and triangulation.
0 1 2 # Use 3 vertex numbers to make a triangle.
1 2 3 # a second triangle sharing 2 of the same points (and hence an edge)
W e05.ppm

# Each triangle is affine so multiple triangles build a piecewise affine image.
# There is more but this is the core of mir that I use over and over again
# to generate aligned outputs like the fish.  Generating the points is
# the SWiFT registration process but mir is the part we should initialy
# replicate as part of the VVFS and naturally apply OpenCV + GPGPU speedups.
# the most intensive per pixel is mir.c hline() along with hrect() and
# dtri() which call hline() to do the lowest level output generation.

# add two more examples show O and S
```

### e00.mir
```
F water0.jpg
R
W e00.ppm
```

### e01.mir
```
# You can put '#' comments in most (but probably not all) places.
# Most mir commands are indicated by a single letter like F for input file.
F water0.jpg # spaces and tabs before and after the name are ignored
100 150 120 90 # four numbers on one or spaced out on multiple lines
# indicate, first, an output X Y and then an input XY that should
# be drawn at the corresponding output position
# this example effectively moves the image down 60 pixels and left 20 pixels
# the default output size is simply the size of the first input file
# and the background defaults to 0 == black
R # R says to draw the entire input file as a rectangle
W e01.ppm # W says write to the specified output file.
# Unputs may be 8 bit grayscale or RGB color ppm, pgm, jpg and tif
# outputs are currently just 8 bit ppm, pgm and tif.
# I'll add png shortly.
```

### e02.mir
```
B 800 500 3 # Change (and keep) the output bounding box to 800x500 3 byte RGB
# change the 3 to 1 and see what happens
Z 128 # change the backgroud to mid gray
# for RGB this hits all 3 channels and should be extended to do separate values
F water0.jpg
100 150 120 90
200 250 180 120 # adding another set of coordinates accomplishes rotation
# and scale to simultaneously satisfy the constraints of both positions
# Hence, 8 numbers completely specify repositioning along with rotation+scale
RW e02.ppm # RW is very common and is usually combined as shown 
```

### e03.mir
```
B 800 500 3
# X # for number sets in the reverse input output order use X to eXchange them
F water0.jpg
100 150 120 90
200 250 180 120
50 60 100 50.5 # 3 point correspondeces, note floading is OK, specify affine
# transforms. Affines include position, rotation, scale and shear but no other
# bending. If you give more than 3 correspondences then the result will be
# the minimal RMS error affine.  Mir tries, and usually succeeds, to eliminate
# highly inconsistent corresponces and get rid of outliers.
RF water1.jpg # you can continue with any number of additional inputs
# that all overwrite the same output - hence Multiple Image Rendering == MIR
570 110 350 240
660 182 660 25
RF water2.jpg # note that RF does the previous rectangle & then reads new input
450 250 0 0
725 140 720 486 # these last 2 lines reposition opposite corners of water2
RW e03.ppm
```

### E04.mir
```
#F water0.jpg
#R
F water1.jpg
77 77 124 88
296 107 599 128
185 172 418 358
RW e04.ppm
# Matching 3 points of water1 onto water0 overlays an affine approximation.
# Since the camera positions were different this is a very rough fit.
```

### e05.mir
```
B 720 476 3
# After viewing the e05.ppm file then uncomment the following F,R lines to use
# water0 as a background with the, now hard to see, water1 triangles over top.
# F water0.jpg
# R
F water1.jpg
84 86 129 104 # this is vertex 0
83 151 105 272
175 106 300 135
295 160 602 272 # this is vertex 3
T # You can make better matches locally with more points and triangulation.
0 1 2 # Use 3 vertex numbers to make a triangle.
1 2 3 # a second triangle sharing 2 of the same points (and hence an edge)
W e05.ppm

# Each triangle is affine so multiple triangles build a piecewise affine image.
# There is more but this is the core of mir that I use over and over again
# to generate aligned outputs like the fish.  Generating the points is
# the SWiFT registration process but mir is the part we should initialy
# replicate as part of the VVFS and naturally apply OpenCV + GPGPU speedups.
# the most intensive per pixel is mir.c hline() along with hrect() and
# dtri() which call hline() to do the lowest level output generation.

# add two more examples show O and S
```

### g.mir
```
F g.pgm
R
W w.png
```

### gpng.mir
```
F g.png
R
W e00.ppm
```

### jout.mir
```
B 2560 1520 1 1024 1024 255
Z 256
F s06588_mdl.jpg
0 0 0 0
RW j_%02d_%02d.jpg
```

### p.mir
```
F water0.jpg
R
W w.png
```

### test_50_51_iter1.sw
```
swim -i 2  -x +2000 -y +2000  Tile_r1-c1_LM9R5CA1series_050.tif 12288 12288 Tile_r1-c1_LM9R5CA1series_051.tif 12021.1 12082.6
swim -i 2  -x +2000 -y -2000  Tile_r1-c1_LM9R5CA1series_050.tif 12288 12288 Tile_r1-c1_LM9R5CA1series_051.tif 12021.1 12082.6
swim -i 2  -x -2000 -y +2000  Tile_r1-c1_LM9R5CA1series_050.tif 12288 12288 Tile_r1-c1_LM9R5CA1series_051.tif 12021.1 12082.6
swim -i 2  -x -2000 -y -2000  Tile_r1-c1_LM9R5CA1series_050.tif 12288 12288 Tile_r1-c1_LM9R5CA1series_051.tif 12021.1 12082.6
```

### test_50_51.sw.mir
```
F Tile_r1-c1_LM9R5CA1series_051.tif
14288 14288  13995.8 14120.3
14288 10288  14026.3 10108.9
10288 14288  10022.2 14085.3
10288 10288  10059.8 10077.8
RW test_50_51.JPG
```

### test_50_51_iter2.sw.mir
```
F Tile_r1-c1_LM9R5CA1series_051.tif
14288 14288 13995.3 14119.6
14288 10288 14032 10103.8
10288 14288 10025.8 14081.6
10288 10288 10060.6 10075
RW test_50_51_iter2.sw.JPG
```