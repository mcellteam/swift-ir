// gcc -Wno-implicit -o test_libs -O3 -m64 -msse3 test_libs.c -ltiff -ljpeg -lpng -lfftw3f -lm
// ./test_libs [image [image ...]]
// Each image will be opened and processed

#include <fftw3.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/time.h>
#include "swimio.h"

#include "debug.h"


int main(int argc, char *argv[]) {

	if ( (argc<=1) || (strcmp(argv[1],"--help")==0) ) {
		printf ( "\n" );
		printf ( "\n" );
		printf ( "Usage:\n" );
		printf ( "\n" );
		//          ----------- argv[0] -------argv[1]--
		printf ( "  test_libs [image [image ...]]\n" );
		printf ( "\n" );
		printf ( " Where:\n" );
		printf ( "\n" );
		printf ( "   Each image will be opened and processed ...\n" );
		exit(0);
	}

  int file_num;
  char outname[100];
  for (file_num=1; file_num<argc; file_num++) {
    printf ( "  File: %s", argv[file_num] );
    if ( strcmp ( strrchr(argv[file_num],'.'), ".png" ) == 0 ) printf ( " is a PNG image" );
    if ( strcmp ( strrchr(argv[file_num],'.'), ".jpg" ) == 0 ) printf ( " is a JPG image" );
    if ( strcmp ( strrchr(argv[file_num],'.'), ".tif" ) == 0 ) printf ( " is a TIF image" );
    printf ( "\n" );
    struct image *img;
    img = read_img(argv[file_num]);
    printf ( "    Image is %d x %d\n", img->wid, img->ht );
    sprintf ( outname, "out_%d%s", file_num, strrchr(argv[file_num],'.') );
		write_img(outname, img);
    sprintf ( outname, "out_j%d.jpg", file_num );
		write_img(outname, img);
  }

  int N;
  N = 32;
  double pi = 4 * atan(1.0);
  double f = 8 * pi;

  printf ( "FFT of %d samples of cos(%f * n / N) + sin(%f * n / N)\n", N, f, 3*f );

  fftwf_complex *in, *out;
  fftwf_plan p;
  in  = (fftwf_complex*) fftwf_malloc ( sizeof(fftwf_complex) * N );
  out = (fftwf_complex*) fftwf_malloc ( sizeof(fftwf_complex) * N );
  int in_index;
  for (in_index=0; in_index<N; in_index++) {
    in[in_index][0] = cos(f*in_index/N) + sin(3*f*in_index/N);
    in[in_index][1] = 0;
  }
  p = fftwf_plan_dft_1d ( N, in, out, FFTW_FORWARD, FFTW_ESTIMATE );
  fftwf_execute(p);
  for (in_index=0; in_index<N; in_index++) {
    printf ( "    %8.4f %8.4f\n", out[in_index][0], out[in_index][1] );
  }
  fftwf_destroy_plan(p);
  fftwf_free(in);
  fftwf_free(out);

	return(0);
}
