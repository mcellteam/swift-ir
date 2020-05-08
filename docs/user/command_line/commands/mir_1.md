MIR(1)
======
:doctype: manpage

NAME
----
mir - Multi Image Renderer

SYNOPSIS
--------
*mir* [-'options'] ['scriptfile']

DESCRIPTION
-----------
The *mir*(1) command runs the *mir* interpreter on the named file. If no
file is given, *mir* reads from stdin.

OPTIONS
-------

*-r*:: Reverse video. Output image has reverse polarity of input images.

*-g*:: Overlay a grid. If given twice, the input image is ignored.

*-X*:: This affects lines that consist of four numbers.
    With the *-X* flag given, a line ``__x__~1~ _y_~1~ _x_~2~ _y_~2~''
    is interpreted as ``__x__~2~ _y_~2~ _x_~1~ _y_~1~''.

**-N**_n_:: Least points. The result of inferring the affine transformation
    may be rejected (forcing a recalculation) if the average error is too large,
    but only if at least _n_ points were available for the inference process.
    Default value is 4.

**-B**_w_,_h_:: Output width and height in pixels.
    Default: Determined from input.

**-s**:: Show solid triangles instead of normal image output.

**-o**:: Show outline triangles instead of normal image output.

**-i**:: Increase interpolation level:

* Default level is zero: nearest neighbor.
* Level one: bilinear.
* Level two (or more): bicubic.

**-b**:: Save overlap image for later intensity correction.
    Filename is 'input'.back.pgm, where 'input' is the source filename with
    a three letter extension removed.

**-?**:: Enable prompting. (That is, show the text ``Enter a MIR command >''
    when *mir* is ready for command input.)

**-S**_S_~x~^out^,_S_~x~^out^,_S_~x~^in^,_S_~y~^in^:: Scale.
    These scale factors are applied to all vertex coordinates.
    Default values are 1 for all.

**-Z**_n_:: Background gray value for output.
    For unknown reasons, the value is interpreted as a multiple of the 
    _x_~out~ scale in force at the time the option is seen.

**-T**_n_:: Transparent input value.
    Pixels of this color are not copied to output. (Useful for out-of-bounds
    areas.)
     For unknown reasons, the value is interpreted as a multiple of the 
    _x_~out~ scale in force at the time the option is seen.

Options that do not take arguments can be combined. There may not be any
spaces between options and their arguments.

LANGUAGE
--------

The *mir* language consists of single character commands followed by
optional arguments. Multiple commands that do not take arguments may
appear on the same line. Commands are:

**?**:: Show a brief help text about the available commands.

**~**:: Display current transformation matrices.

**X**:: Just like the **-X** command line option.

**I**_n_:: Set interpolation level. (_n_ must be 0, 1, or 2 for nearest
    neighbor, bilinear, or bicubic interpolation.)

**a** MI~00~ MI~01~ MI~02~ MI~10~ MI~11~ MI~12~:: Directly
    specify new ``reverse'' mapping.

**A** MF~00~ MF~01~ MF~02~ MF~10~ MF~11~ MF~12~:: Directly
    specify new ``forward'' mapping.

**G**  MG~00~ MG~01~ MG~02~ MG~10~ MG~11~ MG~12~:: Directly
    specify new ``global'' mapping.

**S** _S_~x~^out^ _S_~x~^out^ _S_~x~^in^ _S_~y~^in^:: Specify scale parameters.
    Equivalent to the ``-S'' command line argument.

**O** _dx_~out~ _dy_~out~ _dx_~in~ _dy_~in~:: Specify pixel offsets.
    Arguments may contain basic math: Addition, subtraction, multiplication,
    division, modulo, power, and parentheses are supported.

**B** _w_~out~ _h_~out~ _bpp_~out~ _w_~tile~ _h_~tile~_ _trans_:: Specify
    output width and height, output bytes per pixel, tile width and height,
    and transparent input value.  _w_~out~ _h_~out~, but not the other
    parameters, are interpreted as multiples of the _x_ and _y_ output scales.
    _bpp_ may be one (8 bits) or two (16 bits).

**D** 'name':: Directory prefix for all filenames. There must be precisely
    one space between the ``D'' and the directory name. The entire rest of the
    line (up to the next newline) is interpreted as the prefix, including any
    spaces.

**F** 'name':: Read a new file. Any number of spaces and tab characters may
    appear between the ``F'' and the filename. The filename may not contain
    any spaces. The actual file loaded is determined by concatenating the
    filename to the current directory prefix (without inserting a slash or
    anything else). The program aborts if no filename is given, but quietly
    substitutes a 1x1 image if the file cannot be read. If this is the first
    image read, the size of the output image is set by the size of the image
    loaded (unless explicitly given by a **B** command or **-B** option).
    Reading a new image does not reset the transformation matrices.

**R**:: Recalculate transformation matrices and place image.
    The effect of this command depends on the number of vertices defined
    before the **R** command is issued.

* If zero, the previously set matrices are not affected.
* If one, the vertex specifies a linear shift on top of existing scaling and/or
    rotation.
* If two, calculates an affine transformation based on the two points and
    a fictional point created as
    (_x_~1~ + _y_~2~ − _y_~1~, _y_~1~ + _x_~1~ − _x_~2~).
* If three or more, calculates an affine transformation. (Only three points
    are _required_; I am not clear on what exactly happens when more than
    three are given.)

**Z** _n_:: Zero the drawing space to the given gray value _n_.

**V**:: Toggle reverse video.

**W** 'name':: Write output image. Any number of spaces and tab characters may
    appear between the ``W'' and the filename. The filename may not contain
    any spaces. The ``directory prefix'' is not used. If tiling is enabled
    (by specifying nonzero _w_~tile~ and _h_~tile~_ to the **B** command),
    the 'name' must contain two `%i` place holders for `sprintf` to insert
    the row and column indices of the tile (both counted from zero).
    Writing an output image does not reset the transformation matrices.

**E**:: Exit the program.

Lines without commands specify vertices. These must be given in
space-separated quads: _x_~out~ _y_~out~ _x_~in~ _y_~in~; one quad per
line. (Unless the **X** command or the **-X** option are in effect, in
which case the quads are of the form _x_~in~ _y_~in~ _x_~out~
_y_~out~.) Basic arithmetic is permitted, but be sure not to use any
spaces inside equations. After evaluation, the current offset (**O**
command) is applied and then (!) the current scale (**S**
command). Any number of quads may appear on consecutive lines. Note
that it is _not_ allowed to intersperse commands between the quads.

If the vertices are followed immediately by an ``R'' or ``A'' command,
they are taken as-is. Otherwise, the next line after the vertices is
ignored, and lines that specify triangles must follow. Triangles are
defined by triplets _i_ _j_ _k_ which must be indices into the previously
defined vertices (counting from zero). Specifying vertices that do not
exist is likely to crash the program.

Triangles may be followed by subsequent commands.

If no **W** command is given ever, the final output is written to stdout
in PGM format.

BUGS
----

The author of this page (Daniel Wagenaar) does not yet fully
understand *mir*.  In particular, the meaning of the various mapping
matrices is not yet entirely clear to him. Nor does he understand what
the triangles are used for. Also, variables can be created and
referenced wherever arithmetic is allowed in the input file, but DAW is
not yet clear on how.

