// gcc -O -o iavg iavg.c -ljpeg -ltiff -lpng
// recheck if 16 bit is really right
// icc -o iavg iavg.c -O3 -ip -xSSE4.2 -no-prec-div -unroll-agressive -m64 -Wl,-z-ffast-math -ltiff -lfftw3f
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <jpeglib.h>
#include <tiffio.h>
#include "swimio.h"

#include "debug.h"

struct image *im0, *im1;

int verbose = 0;

int mode = -1;
int pcount = 4;
unsigned int *intimg;
unsigned char *cntimg; // make it an int later for bigger stacks XXX
unsigned char *minimg, *maximg;
int reversevid;
int ignore;

char *modest[] = {
	"avg", // 0
	"max-min", // 1
	"min", // 2
	"max", // 3
	"hdiffs", // 4
	"stack", // 5 = output volume with no headers between layers
	"integral", // 6 = output integral volume with no headers between layers
	"pixelavg" // average only non 0 pixels - uses big counter array
};

int *clut;
int black = 0, white = 255, edge = 0;
int hv_hists, add, sub;
int quiet;
unsigned int hist[256], min = 4000000000, max = 0;
int *v_hist, *h_hist;
float xrampl = 1., xramph = 1.;
float yrampl = 1., yramph = 1.;

int main(int argc, char* argv[]) {
	int n = 1, i, x, y, size;
	if (verbose) print_args ( "main:", argc, argv );

	if ( (argc<=1) || (strcmp(argv[1],"--help")==0) ) {
		printf ( "\n" );
		printf ( "\n" );
		printf ( "Usage:\n" );
		printf ( "\n" );
		//          ----------- argv[0] -------argv[1]--
		printf ( "  iavg [Options] ImageName\n" );
		printf ( "\n" );
		printf ( " Where:\n" );
		printf ( "\n" );
		printf ( "  Options:\n" );
		printf ( "    -r: reverse video\n" );
		printf ( "    -e: fill black top edge for newjosh WRE's\n" );
		printf ( "    -h: hv_hists\n" );
		printf ( "    -q: more quiet\n" );
		printf ( "    -a: mode = 0\n" );
		printf ( "    -s: mode = 5\n" );
		printf ( "    -i: mode = 6\n" );
		printf ( "    -p: mode = 7\n" );
		printf ( "    -p#: mode = 7 pcount = #\n" );
		printf ( "    -#: mode = #\n" );
		printf ( "    -m: xramph and xrampl\n" );
		printf ( "    -+: add = 1\n" );
		printf ( "    --: sub = 1\n" );
		printf ( "    -b #: black = #+2\n" );
		printf ( "    -w #: white = #+2\n" );
		exit(0);
	}

	while(argv[1][0] == '-') {
		if (verbose) print_args ( "main (top while loop):", argc, argv );
//fprintf(stderr, "arg %s\n", argv[1]);
		if(argv[1][1] == 'r')
			reversevid = 1;
		else if(argv[1][1] == 'e')
			edge++; // fill black top edge for newjosh WRE's
		else if(argv[1][1] == 'h')
			hv_hists = 1;
		else if(argv[1][1] == 'q')
			quiet++;
		else if(argv[1][1] == 's')
			mode = 5;
		else if(argv[1][1] == 'i')
			mode = 6;
		else if(argv[1][1] == 'm')
			{
				xramph = 1.143;
				xramph = 1 + (xramph - 1)/2;
				xrampl = 1/xramph;
			}
		else if(argv[1][1] == 'a')
			mode = 0;
		else if(argv[1][1] == '+')
			add = 1;
		else if(argv[1][1] == '-')
			sub = 1;
		else if(argv[1][1] == 'b')
			{
			//fprintf(stderr, "black %s\n", argv[1]+2);
						black = atoi(argv[1]+2);
			//fprintf(stderr, "set to %d\n", black);
			}
		else if(argv[1][1] == 'w')
			{
			//fprintf(stderr, "white %s\n", argv[1]+2);
			white = atoi(argv[1]+2);
			//fprintf(stderr, "set to %d\n", white);
			}
		else if(argv[1][1] == 'p')
			{
				mode = 7;
				if(argv[1][2])
					pcount = atoi(argv[1]+2);
				if(!quiet)
					fprintf(stderr, "pcount thresh %d\n", pcount);
			}
		else
			{
				mode = atoi(argv[1]+1);
				if(!quiet)
					fprintf(stderr, "mode %d = %s\n", mode, modest[mode]);
			}
		fprintf(stderr, "advance\n");
		argv++;
		argc--;
	}
	if (verbose) printf ( "Args after parsing options: " );
	if (verbose) print_args ( "  ", argc, argv );

	//fprintf(stderr, "bw %d %d\n", black, white);
	if(black != 0 || white != 255) {
		int i;
		float d;
		d = 255./(white - black);
		//fprintf(stderr, "d %d %f\n", (white - black), d);
		clut = malloc(256*sizeof(int));
		if(white > black) {
			for(i = 0; i < black; i++)
				clut[i] = 0;
			for(i = white; i < 256; i++)
				clut[i] = 255;
			for(i = black; i <= white; i++)
				if(i >= 0 && i < 256)
					clut[i] = d*(i-black)+.5;
		} else {
			for(i = 0; i < white; i++)
				clut[i] = 255;
			for(i = black; i < 256; i++)
				clut[i] = 0;
			for(i = white; i < black; i++)
				clut[i] = d*(i-black)+.5;
		}
		//for(i = 0; i < 256; i++)
		//fprintf(stderr, "clut[%d] = %d\n", i, clut[i]);
	}
	//fprintf(stderr, "im0 = read_img\n");
	im0 = read_img(argv[1]);
	if(!quiet)
		fprintf(stderr, "%d: %s  %d %d %d\n", n, argv[1], im0->wid, im0->ht, im0->bpp);
	size = im0->ht * im0->wid * im0->bpp;
	intimg = malloc(size*sizeof(unsigned int));
	minimg = malloc(size*sizeof(unsigned char));
	maximg = malloc(size*sizeof(unsigned char));
	cntimg = malloc(size*sizeof(unsigned char)); // non 0 pixel counter

	//fprintf(stderr, "edge %d\n", edge);
	if(edge) { // fill newjosh/W??/WRE tops with top nonblack value
		//fprintf(stderr, "fill top %d %d\n", im0->wid, im0->ht);
		int x, y, yb, nbv;
		for(x = 0; x < im0->wid; x++) {
			for(yb = 0; yb < im0->ht && im0->pp[x+yb*im0->wid] == 0; yb++);
				;
			nbv = im0->pp[x+yb*im0->wid]; // non black val
			//if(yb) fprintf(stderr, "x %d  yb %d  nbv %d\n", x, yb, nbv);
			for(y = 0; y < yb; y++)
				im0->pp[x+y*im0->wid] = nbv;
		}
	}
	fprintf(stderr, "xramph %g\n", xramph);
	if(xramph != 1.0) {
		float m, ml = xrampl, dm = (xramph-xrampl)/im0->wid;
		fprintf(stderr, "xramp %g %g  dm %g\n", xrampl, xramph, dm);
		for(y = 0; y < im0->ht; y++)
			for(m = ml, x = 0; x < im0->wid; x++, m += dm)
				im0->pp[x+y*im0->wid] = m*im0->pp[x+y*im0->wid];
	}
	//fprintf(stderr, "initial hv_hists %d\n", hv_hists);
	if(hv_hists) { // fill newjosh/W??/WRE tops with top nonblack value
		//fprintf(stderr, "fill top %d %d\n", im0->wid, im0->ht);
		int x, y, v;
		v_hist = malloc(256*im0->wid*sizeof(int));
		h_hist = malloc(256*im0->ht*sizeof(int));
		for(y = 0; y < im0->ht; y++) {
			for(x = 0; x < im0->wid; x++) {
				v = im0->pp[x+y*im0->wid];
				h_hist[y*256 + v]++;
				v_hist[x*256 + v]++;
			}
		}
	}
	for(i = 0; i < size; i++) {
		int v = im0->pp[i];
		if(reversevid) {
			v = 0xFF & (255-v);
			im0->pp[i] = v;
		}
		if(clut) // could do reversevid this way too
			v = clut[v];
		hist[v]++;
		if(mode == 4) {
			v = im0->pp[i-1] - im0->pp[i+1];
			if(v < 0)
				v = -v;
		}
		intimg[i] = v;
		minimg[i] = v;
		maximg[i] = v;
	}
	if(mode == 5)
		ignore = write(1, im0->pp, size);
	else if(mode == 6)
		ignore = write(1, intimg, size*sizeof(int));
	argc -= 2;
	argv += 2;
	if(sub) {
		reversevid ^= 1;
		add = 1;
	}
	while(argc > 0) {
		free(im0->pp);
		free(im0);
		im0 = read_img(argv[0]);
		if(!quiet)
			fprintf(stderr, "%d: %s  %d %d %d\n", n, argv[0], im0->wid, im0->ht, im0->bpp);
		if(size != im0->ht*im0->wid*im0->bpp) {
			fprintf(stderr, "old size %d -- break\n", size);
			break;
			//exit(1);
		}
		n++;
		if(xramph != 1.0) {
			float m, ml = xrampl, dm = (xramph-xrampl)/im0->wid;
			fprintf(stderr, "xramp %g %g  dm %g\n", xrampl, xramph, dm);
			for(y = 0; y < im0->ht; y++)
				for(m = ml, x = 0; x < im0->wid; x++, m += dm)
					im0->pp[x+y*im0->wid] = m*im0->pp[x+y*im0->wid];
		}
		//fprintf(stderr, "hv_hists %d %d\n", n, hv_hists);
		if(hv_hists) {
			int x, y, v;
			for(y = 0; y < im0->ht; y++)
				for(x = 0; x < im0->wid; x++) {
					v = im0->pp[x+y*im0->wid];
					h_hist[y*256 + v]++;
					v_hist[x*256 + v]++;
				}
		}
		for(i = 0; i < size; i++) {
			int v = im0->pp[i];
			if(reversevid) {
				v = 0xFF&(255-v);
				im0->pp[i] = v;
			}
			if(clut) // could do reversevid this way too
				v = clut[v];
			hist[v]++;
			if(mode == 4) {
				v = im0->pp[i-1] - im0->pp[i+1];
				if(v < 0)
					v = -v;
			}
			intimg[i] += v;
			if(v < minimg[i])
				minimg[i] = v;
			if(v > maximg[i])
				maximg[i] = v;
			if(v)
				cntimg[i]++;
		}
		if(mode == 5)
			ignore = write(1, im0->pp, size);
		else if(mode == 6)
			ignore = write(1, intimg, size*sizeof(unsigned int));
		else if(mode == 7) {
			char hdr[100];
			int fd = creat("pixcnt.pgm", 0666);
			sprintf(hdr, "P5\n%d %d\n255\n", im0->wid, im0->ht);
			ignore = write(fd, hdr, strlen(hdr));
			ignore = write(fd, cntimg, size*sizeof(unsigned char));
		}
		argc--;
		argv++;
	}
	if(quiet <= 1)
		fprintf(stderr, "%d source images\n", n);
	switch(mode) {
	case 0: // -a
		/*
		for(i = 0; i < 256; i++)
			if(hist[i])
				break;
		min  = i;
		for( ; i < 256; i++)
			if(hist[i])
				max = i;
		fprintf(stderr, "minmax %d %d\n", min, max);
		for(i = 0; i < size; i++)
			im0->pp[i] = 255.0*(im0->pp[i]-min)/(max-min);
		*/
		// XXXX not fixed for RGB color
		//fprintf(stderr, "starting minmax %d %d\n", min, max);
		for(i = 0; i < size; i++)
			if(intimg[i] > max)
				max = intimg[i];
			else if(intimg[i] < min)
				min = intimg[i];
		//fprintf(stderr, "minmax %d %d\n", min, max);
		for(i = 0; i < size; i++)
			im0->pp[i] = 255.99*(intimg[i]-min)/(max-min);
		break;
	case 1:		// max - min
		for(i = 0; i < size; i++)
	       		im0->pp[i] = maximg[i] - minimg[i];
		break;
	case 2:		// min
		for(i = 0; i < size; i++)
	       		im0->pp[i] = minimg[i];
		break;
	case 3:		// max
		for(i = 0; i < size; i++)
	       		im0->pp[i] = maximg[i];
		break;
	case 5:
		break;
	case 7:		// pixel count average // "apodize edge to mid gray
		for(i = 0; i < size; i++)
			if(cntimg[i] >= 4) // get arg from cmd line
	       			im0->pp[i] = intimg[i] / cntimg[i];
			else
				im0->pp[i] = 150;  /// XXX compute this!!!
		break;
	default:	// else use avg mode
		if(add)
			n = 1;
		for(i = 0; i < size; i++)
			im0->pp[i] = intimg[i] / n;
		break;
	}
	if(mode == 5 || mode == 6)
		return(0);
	if(im0->bpp == 3)
		printf("P6\n%d %d\n255\n", im0->wid, im0->ht);
	else if(im0->bpp == 2)
		printf("P5\n%d %d\n65535\n", im0->wid, im0->ht);
	else
		printf("P5\n%d %d\n255\n", im0->wid, im0->ht);
	fflush(stdout);
	ignore = write(1, im0->pp, size);
	//fprintf(stderr, "final hv_hists %d\n", hv_hists);
	if(hv_hists) {
		int fd, x, y, max;
		unsigned char line[256];
		fd = creat("xy_hists.pgm", 0666);
		//fprintf(stderr, "fd %d\n", fd);
		sprintf(line, "P5\n%d %d\n255\n", 256, im0->wid+im0->ht);
		ignore = write(fd, line, strlen(line));
		for(y = 0; y < im0->ht; y++) {
			unsigned int *ip = &h_hist[y*256];
			if((y%69) == 0) {
				fprintf(stderr, "y %d\n", y);
				for(x = 0; x < 256; x++) fprintf(stderr, "%d %d\n", x, ip[x]);
			}
			for(max = x = 0; x < 256; x++)
				if(ip[x] > max)
					max = ip[x];
			for(x = 0; x < 256; x++)
				line[x] = ip[x] * 256./max;
			ignore = write(fd, line, 256);
		}
		for(x = 0; x < im0->wid; x++) {
			unsigned int *ip = &v_hist[x*256];
			for(max = y = 0; y < 256; y++)
				if(ip[y] > max)
					max = ip[y];
			for(y = 0; y < 256; y++)
				line[y] = ip[y] * 256./max;
			ignore = write(fd, line, 256);
		}
		close(fd);
	}
	return(0);
}
