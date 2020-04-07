#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h> //
#include <sys/stat.h> //
#include <fcntl.h> //
#include <string.h>
#include <strings.h>
#include <math.h>
#include <ctype.h>
#include <jpeglib.h>
#include <tiffio.h>
#include <png.h>

#define uchar unsigned char
#define ushort unsigned short

int print_args ( char *prefix, int argc, char* argv[] ) {
  int i;
  printf ( "%s\n", prefix );
  for (i=0; i<argc; i++) {
    printf ( "  Arg[%d] = %s\n", i, argv[i] );
  }
  return (0);
}
