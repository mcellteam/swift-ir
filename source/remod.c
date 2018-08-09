// gcc -O3 -o remod remod.c -lfftw3f -ltiff -ljpeg -lpng -lm
// XXXX double check the skip 0 option
// icc -O3 -m64 -mtune=core2 -msse3 -march=core2 -funroll-all-loops -Wl,-z-ffast-math -o remod remod.c -lfftw3f -ltiff -lm
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "swimio.h"
struct image *im[100000], *outimg;
unsigned int *gral;
unsigned char *outim;
int span; // XXX should make span and skip consistent
int skip = 1; // default is to skip "this" section
int dspan; // dbl span is the actual slice centered range
int nout;
int W, H;
int doends = 1;
int adapt = 0; // normally just div by n rather than iavg -a adaptive

out_gral(char *name) {
	char newname[100], *p;
	char hdr[100];
	int fd, i, min, max;
	float div;
	strcpy(newname, name);
	p = newname;
	while(*p)
		p++;
	p -= 4; // backup over 3 char suffix and its .
	//strcpy(p, "_MDL.pgm");
	strcpy(p, "_MDL.PNG");
	if(strcmp(name, newname) == 0) {
		sprintf("exit <%s> <%s>\n", name, newname);
		exit(1);
	}
	//fd = creat(newname, 0666);
	//sprintf(hdr, "P5\n%d %d\n255\n", W, H);
	//write(fd, hdr, strlen(hdr));
	min = 1000000000;
	max = 0;
	if(adapt) {
		for(i = 0; i < W*H; i++) {
			if(gral[i] > max)
				max = gral[i];
			if(gral[i] < min)
				min = gral[i];
		}
		div = (max-min)/255.;
	} else
		div = dspan+1-skip;
fprintf(stderr, "max %d  min %d  div %f  vs %d %d %d\n",
max, min, div, dspan, skip, dspan+1-skip);
	if(adapt) {
		for(i = 0; i < W*H; i++)
			outim[i] = (gral[i]-min)/div;
	} else {
		for(i = 0; i < W*H; i++)
			outim[i] = gral[i]/div;
	}
	//i = write(fd, outim, W*H);
	write_img(newname, outimg);
fprintf(stderr, "wrote <%s> <%s> %d\n", newname, name, i);
	//close(fd);
}

add_gral(int s) {
	unsigned char *ip = im[s]->pp;
	int i, n = W*H;
//fprintf(stderr, "add %d\n", s);
	for(i = 0; i < n; i++)
		gral[i] += ip[i];
}

sub_gral(int s) {
	unsigned char *ip = im[s]->pp;
	int i, n = W*H;
//fprintf(stderr, "sub %d\n", s);
	for(i = 0; i < n; i++)
		gral[i] -= ip[i];
}

main(int argc, char *argv[]) {
	int i, j, fd, n;
	argc--;
	argv++;
	while(argv[0][0] == '-') {
		if(argv[0][1] == 'e')
			doends = 0;
		if(argv[0][1] == 'a')
			adapt = 1; // like iavg -a
		else {
			if(span == 0)
				span = atoi(argv[0]+1);
			else
				skip = atoi(argv[0]+1);
		}
		argc--;
		argv++;
	}
	dspan = span+span;
fprintf(stderr, "span %d  dspan %d\n", span, dspan);
	im[0] = read_img(argv[0]);
//fprintf(stderr, "read %d <%s>\n", 0, argv[0]);
	W = im[0]->wid;
	H = im[0]->ht;
	gral = malloc(W*H*sizeof(unsigned int));
fprintf(stderr, "img size %dx%d = %d  gral size %ld  buffering %lld\n",
W, H, W*H, W*H*sizeof(unsigned int), W*H*(long long)dspan);
	//outim = malloc(W*H);
	outimg = newimage(W, H, 1);
	outim = outimg->pp;
	add_gral(0);
	for(i = 1; i < argc; i++) {
		im[i] = read_img(argv[i]);
//fprintf(stderr, "read %d <%s>\n", i, argv[i]);
fprintf(stderr, "%d <%s> %d %d\n", i, argv[i], fd, n);
		add_gral(i);
		if(i >= dspan) {
			int k;
			if(i == dspan && doends) for(j = 0; j < span; j++) {
				sub_gral(j);
fprintf(stderr, "out_gral front %s\n", argv[j]);
				out_gral(argv[j]);
				add_gral(j);
			}
			if(skip) for(k = -skip/2; k <= skip/2; k++)
{
fprintf(stderr, "i %d span %d skip %d  k %d = %d\n",
i, span, skip, k, i-span+k);
				sub_gral(i-span+k); // the mid skips
}
			out_gral(argv[i-span]);	// output gral except mid sect
			if(skip) for(k = -skip/2; k <= skip/2; k++)
				add_gral(i-span+k); // add back skips
			sub_gral(i-2*span); // front of rolling window
			free(im[i-2*span]->pp);
			free(im[i-2*span]);
			im[i-2*span] = NULL;
//fprintf(stderr, "1freed %d\n", i-2*span);
		}
	}
// XXX Tue Jan 12 11:25:06 2016 Tail halfspan is coming out above and darker
	if(doends) for(j = i-span; j < i; j++) {
		sub_gral(j);
fprintf(stderr, "out_gral tail %s\n", argv[j]);
		out_gral(argv[j]);
		add_gral(j);
	}
}
