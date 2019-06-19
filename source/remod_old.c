// gcc -O3 -o remod_old remod_old.c -lfftw3f -ltiff -ljpeg -lpng -lm
// icc -O3 -m64 -mtune=core2 -msse3 -march=core2 -funroll-all-loops -Wl,-z-ffast-math -o remod_old remod_old.c -lfftw3f -ltiff -lm
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "swimio.h"
struct image *im[100000];
unsigned int *gral;
unsigned char *outim;
int span = 20;
int dspan; // dbl span is the actual slice centered range
int nout;
int W, H;
int doends = 1;

void out_gral(char *name) {
	char newname[100], *p;
	char hdr[100];
	int fd, i, /*div = 2*span,*/ min, max;
	float div = 2*span;
//fprintf(stderr, "outgral %s\n", name);
	//sprintf(newname, "NGRAL%04d.PGM", nout++);
	strcpy(newname, name);
	p = newname;
	while(*p)
		p++;
	p -= 4; // backup over 3 char suffix and its .
	strcpy(p, "_MDL.pgm");
/*
	while(*p && *p != 's' && *p != 'S')
		p++;
	if(*p)
		strcpy(p, "NGRAL.pgm");
	else
		strcpy(p, "_GRAL.pgm");
*/
	if(strcmp(name, newname) == 0) {
		sprintf("exit <%s> <%s>\n", name, newname);
		exit(1);
	}
	fd = creat(newname, 0666);
	sprintf(hdr, "P5\n%d %d\n255\n", W, H);
	i = write(fd, hdr, strlen(hdr));
	//for(i = 0; i < W*H; i++)
		//outim[i] = gral[i]/div;
	min = 1000000000;
	max = 0;
	for(i = 0; i < W*H; i++) {
		if(gral[i] > max)
			max = gral[i];
		if(gral[i] < min)
			min = gral[i];
	}
	div = (max-min)/255.99999;
//fprintf(stderr, "max %d  min %d  div %f\n", max, min, div);
	for(i = 0; i < W*H; i++)
		outim[i] = (gral[i]-min)/div;
	i = write(fd, outim, W*H);
fprintf(stderr, "wrote <%s> <%s> %d\n", newname, name, i);
	close(fd);
}

void add_gral(int s) {
	unsigned char *ip = im[s]->pp;
	int i, n = W*H;
//fprintf(stderr, "add %d\n", s);
	for(i = 0; i < n; i++)
		gral[i] += ip[i];
}

void sub_gral(int s) {
	unsigned char *ip = im[s]->pp;
	int i, n = W*H;
//fprintf(stderr, "sub %d\n", s);
	for(i = 0; i < n; i++)
		gral[i] -= ip[i];
}

int main(int argc, char *argv[]) {
	int i, j, fd, n;
	argc--;
	argv++;
	while(argv[0][0] == '-') {
		if(argv[0][1] == 'e')
			doends = 0;
		else
			span = atoi(argv[0]+1);
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
	outim = malloc(W*H);
	add_gral(0);
	for(i = 1; i < argc; i++) {
		im[i] = read_img(argv[i]);
//fprintf(stderr, "read %d <%s>\n", i, argv[i]);
fprintf(stderr, "%d <%s> %d %d\n", i, argv[i], fd, n);
		add_gral(i);
		if(i >= dspan) {
			if(i == dspan && doends) for(j = 0; j < span; j++) {
				sub_gral(j);
				out_gral(argv[j]);
				add_gral(j);
			}
			sub_gral(i-span); // the mid span sect
			out_gral(argv[i-span]);	// output gral except mid sect
			add_gral(i-span); // add mid back
			sub_gral(i-2*span); // front of rolling window
			free(im[i-2*span]->pp);
			free(im[i-2*span]);
			im[i-2*span] = NULL;
//fprintf(stderr, "1freed %d\n", i-2*span);
		}
	}
	if(doends) for(j = i-span; j < i; j++) {
		sub_gral(j);
		out_gral(argv[j]);
		add_gral(j);
	}
	return(0);
}

