// fix missing triangle bug
// MIR: Multiple Image Rendering
// playing with mir

// gcc -O3 -o mir mir.c -ljpeg -ltiff -lpng -lwebp -lm
// add transparency value
// allow aritimetic in B
// option for overlapping tiles with spacing and hex row offset by 1/2
// demand read of accessed tiles
// proviee write-time transforms for scale, ROI, rot etc - really full affine
// mir tile reads via %d %d names or do it as norml mir positioning (warpping??)
//  F name_%02d_%02d.pgm 5 7 # 35tiles in 5X 7Y pattern size det from read
// optimize for read only on first actual use
// how to control tile size padding vs truncation on last RC
// reconsider what to do with missing input files - currently writes blank
// Beware currently using both Zval > 255 and trans --- recheck this XXX
// B X O and Z from cmd line ... make Z for RGB color too
// bytes/pix default to first image type
// specified ouput polygons
// affine values to stdout
// estimate corner affines for top level quad triangulation
// insert A for local aafine to use
// A cmdline for global output transform
// black overflow -i -i on affine-steps.pgm
// can two or more sets of affine be separated automatically???
// remove 0's to reserve as an averaging marker
// needs flat and dark correction
// add direct rot and scale input and output
// nearest 16.4 ticks/p, bilin 50 t/p, cubic 198 t/p
// M outmul inmul
// offset regions to make tiling outputs
// if no B then use size of first image
// fix R to take input or output bounds
// reach into corners and edges that may have poor corr support
// finish color bilin and cubic interpolations
// accumulate to buffer mode as in iavg -p etc
// ticks for nearest 16.4 t/p, bilin 50 t/p, cubic 198 t/p
// XXX cubic has rect border bug
// needs flat and dark correction
// add direct rot and scale input
// add arithmetic - particularly for RC raster stepping
// fix for progressive output
// delayed reads and stored transforms for arb on the fly region rendering
// dynamic B growth
// output trimming

// icc -o mir mir.c -O3 -ip -xSSE4.2 -no-prec-div -unroll-agressive -m64 -Wl,-z-ffast-math -ltiff -lfftw3f
// gcc -o mir mir.c -O3 -m64 -mtune=core2 -msse3 -march=core2 -funroll-all-loops -Wl,-z-ffast-math -lfftw3f -ljpeg -ltiff -lm
// 51.95user 79.02system 2:21.32elapsed 92%CPU

#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "swimio.h"

// #include "debug.h" // AWW did this come from Bob ? do this inline instead
int print_args ( char *prefix, int argc, char* argv[] ) {
  int i;
  printf ( "%s\n", prefix );
  for (i=0; i<argc; i++) {
    printf ( "  Arg[%d] = %s\n", i, argv[i] );
  }
  return (0);
}

struct image *inimg, *outimg, outtile;

typedef unsigned long long ticks; // the cycle counter is 64 bits
static __inline__ ticks getticks(void) {  // read CPU cycle counter
  unsigned a, d;
  asm volatile ("rdtsc":"=a" (a), "=d"(d));
  return ((ticks) a) | (((ticks) d) << 32);
}

ticks t_ticks, hl_ticks, hr_ticks, tri_ticks, aff_ticks, r_ticks, w_ticks;
ticks total_ticks, micros0, micros1;
int total_pixels;

#define	VL	4                   // vector len 6 can be x0,y0, x1, y1, bright, cont XXX 6 fail
#define	NVERTS 60000
int gflag;                      // overlay grid - ignore input image if flaged twice
int sflag;                      // show solid triangles
int oflag;                      // outline triangles
int iflag = 0;                  // interpolation level nearest=0, linear=1, cubic=2
int bflag = 0;                  // save overlap image for later intensity correction calculation
int trival;
int quadval;
float vert[NVERTS][VL];
int nverts;
int oxmin = 1000000, oxmax, oymin = 1000000, oymax;
#define	NTRI	20000
int tri[NTRI][3];
int ntris;
#define	NQUAD	20000
int quad[NQUAD][4];
int nquads;
int dotris;
int doquads;
/* float v0[] = { 18028, 17936, 18127, 19040 }; */
unsigned char lut[512];
int Zval;

unsigned char *obase;
unsigned char *backp;           // the back fill buffer XXXX recheck uses for this Ap2016
char backname[1024];
int owid, oht, obpp, rv;        // rv for reverse video
int twid, tht, padtwid = 1, padtht = 1; // tile size for W file_%d_%d outputs
int iwid, iht, ibpp;
int trans = -1;                 // tranparency "color"
unsigned char *idat;
int exchange;                   // exchange io order

float hv0[VL], hv1[VL];
float dv0[VL], dv1[VL];
float iscalex = 1, oscalex = 1, iscaley = 1, oscaley = 1; // ??? what is oscalex
float ioffx, ooffx, ioffy, ooffy;

float ethresh = 3.0;            // default error threshold XXX add to args
int leastpts = 4;               // default least points after affine rejection XXX add to args
void affine(int, float *, float, int);
void affine_inverse(float *, float *);
float mg[2][3] = { 1, 0, 0, 0, 1, 0 };  // global mapping - init identity
float mgi[2][3] = { 1, 0, 0, 0, 1, 0 }; // global map inverse - init identity
float mf[2][3] = { 1, 0, 0, 0, 1, 0 };  // mapping solution
float mi[2][3] = { 1, 0, 0, 0, 1, 0 };  // inverse mapping solution

long npix;                      // keep track of output pixel count as FYI stat
int verbose = 0;
int skipval = -1;

void hline(int y, int x0, int x1) {
  int i, x, ix, iy, V;
  double y1, tf, df, tx, ty;
  unsigned char *p, *oip = obase + y * (long)owid * obpp;
  // fprintf(stderr, "hline %d: %d %d   bpp %d %d\n", y, x0, x1, ibpp, obpp);
  if (y < 0 || y >= oht)
    return;
  hl_ticks -= getticks();
  if (x0 > x1) {
    i = x0;
    x0 = x1;
    x1 = i;
  }
  if (x1 >= owid)
    x1 = owid - 1;
  if (x0 < 0)
    x0 = 0;                     // AWW
  npix += 1 + x1 - x0;
  if (oflag) {                  // roughly outline triangles
    fprintf(stderr, "*** oflag %d\n", oflag);
    oip[x0] ^= 128;
    if (x1 != x0)
      oip[x1] ^= 128;
    hl_ticks += getticks();
    return;
  }
  if (sflag) {
    V = 101001 * trival + 63 + y + x1;  // very crude pseudo random
    fprintf(stderr, "*** sflag %d  V %d\n", sflag, V);
    V += V >> 6;
    V = y;
    for (x = x0; x <= x1; x++)
      oip[x] = V;
    hl_ticks += getticks();
    return;
  }
  tx = x0 * mf[0][0] + y * mf[0][1] + mf[0][2]; // affine of start point
  ty = x0 * mf[1][0] + y * mf[1][1] + mf[1][2];
  if (iflag == 0) {             // nearest pixel
    tx += .5;                   // half pixel correction only needed for nearest
    ty += .5;
    //fprintf(stderr, "txy %g %g  x0 x1  %d %d\n", tx, ty, x0, x1);
    if (obpp == 1 && ibpp == 1)
      for (x = x0; x <= x1; x++, tx += mf[0][0], ty += mf[1][0]) {
        ix = tx;
        iy = ty;
        if (ix < 0 || iy < 0 || ix >= iwid || iy >= iht)
          continue;
        V = idat[iy * iwid + ix];
        //if(oip[x] == 0 || oip[x] == 150) // XXX kludge for full placements.pgm AWW
        if (V == skipval)       // skip black input - for out of bounds
          continue;
        if (backp)
          backp[iy * iwid + ix] = oip[x]; // copy from prev output to backp
        oip[x] = lut[V + 128];
    } else if (obpp == 3 && ibpp == 3)
      for (x = x0; x <= x1; x++, tx += mf[0][0], ty += mf[1][0]) {
        ix = tx;
        iy = ty;
        if (ix < 0 || iy < 0 || ix >= iwid || iy >= iht)
          continue;
        oip[3 * x + 0] = lut[idat[3 * (iy * iwid + ix) + 0] + 128];
        oip[3 * x + 1] = lut[idat[3 * (iy * iwid + ix) + 1] + 128];
        oip[3 * x + 2] = lut[idat[3 * (iy * iwid + ix) + 2] + 128];
    } else if (obpp == 3 && ibpp == 1)
      for (x = x0; x <= x1; x++, tx += mf[0][0], ty += mf[1][0]) {
        ix = tx;
        iy = ty;
        if (ix < 0 || iy < 0 || ix >= iwid || iy >= iht)
          continue;
        oip[3 * x + 0] = lut[idat[iy * iwid + ix] + 128];
        oip[3 * x + 1] = lut[idat[iy * iwid + ix] + 128];
        oip[3 * x + 2] = lut[idat[iy * iwid + ix] + 128];
    } else if (obpp == 1 && ibpp == 3)
      for (x = x0; x <= x1; x++, tx += mf[0][0], ty += mf[1][0]) {
        int R, G, B;
        ix = tx;
        iy = ty;
        if (ix < 0 || iy < 0 || ix >= iwid || iy >= iht)
          continue;
        R = lut[idat[3 * (iy * iwid + ix) + 0] + 128];
        G = lut[idat[3 * (iy * iwid + ix) + 1] + 128];
        B = lut[idat[3 * (iy * iwid + ix) + 2] + 128];
        // .3989*R + .587*G + .114*B
        oip[x] = (19589 * R + 38470 * G + 7471 * B) >> 16;
    } else if (obpp == 2 && ibpp == 2)
      for (x = x0; x <= x1; x++, tx += mf[0][0], ty += mf[1][0]) {
        unsigned short *sip, *sop;
        sip = (unsigned short *)idat;
        sop = (unsigned short *)oip;
        ix = tx;
        iy = ty;
        if (ix < 0 || iy < 0 || ix >= iwid || iy >= iht)
          continue;
        V = sip[iy * iwid + ix];
        //if(oip[x] == 0 || oip[x] == 150) // XXX kludge for full placements.pgm AWW
        if (V == 0 && skipval)  // skip black input - for out of bounds
          continue;
        if (backp)
          backp[iy * iwid + ix] = oip[x]; // copy from prev output to backp
        sop[x] = V;
        //oip[x] = lut[V+128];
      }
    hl_ticks += getticks();
    return;
  }
  if (iflag == 1) {             // bilinear interpolation
    //fprintf(stderr, "txy %g %g  x0 x1  %d %d  bpp %d %d\n",
    //tx, ty, x0, x1, ibpp, obpp);
    if (ibpp != 1 || obpp != 1) {
      fprintf(stderr, "EXIT\n");
      exit(1);
    }
    for (x = x0; x <= x1; x++, tx += mf[0][0], ty += mf[1][0]) {
      double f0, f1, f2, f3, frx, fry;
      ix = tx;
      iy = ty;
      if (ix < 0 || iy < 0 || ix >= iwid || iy >= iht)
        continue;
      frx = tx - ix;
      fry = ty - iy;
      f0 = (1 - frx) * (1 - fry);
      f1 = frx * (1 - fry);
      f2 = (1 - frx) * fry;
      f3 = frx * fry;
      //V = f0 * iimg[iy][ix] + f1 * iimg[iy][ix+1] +
      //f2 * iimg[iy+1][ix] + f3 * iimg[iy+1][ix+1];
      V = f0 * idat[iy * iwid + ix] + f1 * idat[iy * iwid + ix + 1] +
          f2 * idat[(iy + 1) * iwid + ix] + f3 * idat[(iy + 1) * iwid + ix + 1];
      if (V == 0 && skipval)    // skip black input - for out of bnds
        continue;
      oip[x] = lut[V + 128];
    }
    hl_ticks += getticks();
    return;
  }
  // cubic interpolation
  for (x = x0; x <= x1; x++, tx += mf[0][0], ty += mf[1][0]) {
    double f0, f1, f2, f3, frx, fry;
    ix = tx;
    iy = ty;
    if (ix < 1 || iy < 1 || ix >= iwid - 1 || iy >= iht - 1)
      continue;
    frx = tx - ix;
    fry = ty - iy;
    //p = &iimg[iy-1][ix-1];
    p = &idat[(iy - 1) * iwid + ix - 1];
    f0 = p[1] + 0.5 * frx * (p[2] - p[0] + frx * (2.0 * p[0] -
                                                  5.0 * p[1] + 4.0 * p[2] - p[3] +
                                                  frx * (3.0 * (p[1] - p[2]) + p[3] - p[0])));
    //p = &iimg[iy-0][ix-1];
    p = &idat[iy * iwid + ix - 1];
    f1 = p[1] + 0.5 * frx * (p[2] - p[0] + frx * (2.0 * p[0] -
                                                  5.0 * p[1] + 4.0 * p[2] - p[3] +
                                                  frx * (3.0 * (p[1] - p[2]) + p[3] - p[0])));
    //p = &iimg[iy+1][ix-1];
    p = &idat[(iy + 1) * iwid + ix - 1];
    f2 = p[1] + 0.5 * frx * (p[2] - p[0] + frx * (2.0 * p[0] -
                                                  5.0 * p[1] + 4.0 * p[2] - p[3] +
                                                  frx * (3.0 * (p[1] - p[2]) + p[3] - p[0])));
    //p = &iimg[iy+2][ix-1];
    p = &idat[(iy + 2) * iwid + ix - 1];
    f3 = p[1] + 0.5 * frx * (p[2] - p[0] + frx * (2.0 * p[0] -
                                                  5.0 * p[1] + 4.0 * p[2] - p[3] +
                                                  frx * (3.0 * (p[1] - p[2]) + p[3] - p[0])));
    V = f1 + 0.5 * fry * (f2 - f0 + fry * (2.0 * f0 - 5.0 * f1 + 4.0 * f2 - f3 + fry * (3.0 * (f1 - f2) + f3 - f0)));
    if (V == 0)
      continue;
    oip[x] = lut[V + 128];
  }
  hl_ticks += getticks();
}

void hrect(int minx, int miny, int maxx, int maxy) {
  int y, ignore;
  //fprintf(stderr, "hrect  %d %d  %d %d\n", minx, miny, maxx, maxy);
  hr_ticks -= getticks();
  for (y = miny; y <= maxy; y++)
    hline(y, minx, maxx);
  hr_ticks += getticks();
  if (backp) {
    int fd;
    char hdr[100];
    fd = creat(backname, 0666);
    //fprintf(stderr, "*** backname <%s> %d\n", backname, fd);
    sprintf(hdr, "P5\n%d %d\n255\n", iwid, iht);
    if (fd) {
      ignore = write(fd, hdr, strlen(hdr));
      ignore = write(fd, backp, iwid * iht);
      close(fd);
    }
  }
  //fprintf(stderr, "hrect done\n");
}
// Art's old Pitt IS2780 graphics class 2D elementary matrix arith with Stu
float mdet(float *a) {
	float d =
	a[1]*a[5] - a[2]*a[4] - a[3]*a[1] + a[3]*a[2] + a[0]*a[4] - a[0]*a[5];
	return(d);
}

void minv(float *v, float *a) {
	float d = mdet(a), rd = 1/d;
	v[0] = (a[4]*a[8]-a[5]*a[7]);
	v[1] = -(a[1]*a[8]-a[2]*a[7]);
	v[2] = (a[1]*a[5]-a[2]*a[4]);
	v[3] = -(a[3]*a[8]-a[5]*a[6]);
	v[4] = (a[0]*a[8]-a[2]*a[6]);
	v[5] = -(a[0]*a[5]-a[2]*a[3]);
	v[6] = (a[3]*a[7]-a[4]*a[6]);
	v[7] = -(a[0]*a[7]-a[1]*a[6]);
	v[8] = (a[0]*a[4]-a[1]*a[3]);
}

void mznorm(float *o, float *i) {
	float s = 1./i[8];
	int j;
	for(j = 0; j < 9; j++)
		o[j] = i[j] * s;
}

void mmul(float *r, float *a, float *b) {
	int i, j, k;
	for(i = 0; i < 3; i++) {
		for(j = 0; j < 3; j++) {
			r[3*i+j] = 0;
			for(k = 0; k < 3; k++)
				r[3*i+j] += a[3*i+k] * b[j+3*k];
		}
	}
}

void mprint(char s, float *fp, int n) {
	int i;
	printf("%c:", s);
	for(i = 0; i < 9; i++)
		//printf(" %g", fp[i]);
		printf(" %7.4f", fp[i]);
	printf("\n");
}
//

#define	STRLENS 1024
char prefix[STRLENS];
char fname[STRLENS];
char fullname[STRLENS];
char outname[STRLENS];
char line[STRLENS];

struct quad {
        float x0, y0;
        float x1, y1;
        float x2, y2;
        float x3, y3;
};

/* assumes regular orientation and integer rectangular output */
// irregular in to rectangular out
void qmap(struct image *ip0, struct quad *qp0, struct image *ip1, struct quad *qp1) {
	unsigned char *op;
	int i, j, sx, sy, x, y, nx, ny, v;
	float fx, fy, fra, fry0, fry1, frx0, frx1;
	micros0 = getticks();
	ny = qp1->y2 - qp1->y0;
	nx = qp1->x1 - qp1->x0;
	//op = ip1->pp + qp1->y0*ip1->ydelta + qp1->x0; // NOT with floats!
	sx = qp1->x0;	// integer start x
	sy = qp1->y0;	// integer start y
fprintf(stderr, "xy  %g %g ... %d %d\n", qp1->x0, qp1->y0, x, y);
	op = ip1->pp + sy*ip1->ydelta + sx;
fprintf(stderr, "qp0\n");
fprintf(stderr, "  %g %g   \t", qp0->x0, qp0->y0);
fprintf(stderr, "  %g %g\n", qp0->x1, qp0->y1);
fprintf(stderr, "  %g %g   \t", qp0->x2, qp0->y2);
fprintf(stderr, "  %g %g\n", qp0->x3, qp0->y3);
fprintf(stderr, "qp1\n");
fprintf(stderr, "  %g %g   \t", qp1->x0, qp1->y0);
fprintf(stderr, "  %g %g\n", qp1->x1, qp1->y1);
fprintf(stderr, "  %g %g   \t", qp1->x2, qp1->y2);
fprintf(stderr, "  %g %g\n", qp1->x3, qp1->y3);
fprintf(stderr, "y %d ny %d x %d nx %d\n", y, ny, x, nx);
// test the assumption of a rectangular output region
if(qp1->y0 != qp1->y1) fprintf(stderr, "Y0**** %g %g\n", qp1->y0, qp1->y0);
if(qp1->y2 != qp1->y3) fprintf(stderr, "Y2**** %g %g\n", qp1->y2, qp1->y3);
if(qp1->x0 != qp1->x2) fprintf(stderr, "X0**** %g %g\n", qp1->x0, qp1->x2);
if(qp1->x1 != qp1->x3) fprintf(stderr, "X1**** %g %g\n", qp1->x1, qp1->x3);
// the following are OK for warping
if(qp0->y0 != qp0->y1) fprintf(stderr, "Y1**** %g %g\n", qp0->y0, qp0->y1);
if(qp0->y2 != qp0->y3) fprintf(stderr, "Y3**** %g %g\n", qp0->y2, qp0->y3);
if(qp0->x0 != qp0->x2) fprintf(stderr, "X2**** %g %g\n", qp0->x0, qp0->x2);
if(qp0->x1 != qp0->x3) fprintf(stderr, "X3**** %g %g\n", qp0->x1, qp0->x3);
fprintf(stderr, "diffs %g %g   %g %g  ratios  X  %g   Y %g\n",
qp0->x1 - qp0->x0, qp1->x1 - qp1->x0, qp0->y2 - qp0->y0, qp1->y2 - qp1->y0, 
(qp0->x1 - qp0->x0)/( qp1->x1 - qp1->x0), (qp0->y2 - qp0->y0)/( qp1->y2 - qp1->y0));
	for(i = 0; i < ny; i++) {
// fprintf(stderr, "tile %d oht %d sy %d i %d sum %d\n", ntile, oht, sy, i, sy+i);
		if(sy+i >= oht) break;
		fra = i / (float)ny;
		fry0 = qp0->y0 + (qp0->y2 - qp0->y0) * fra;
		fry1 = qp0->y1 + (qp0->y3 - qp0->y1) * fra;
		frx0 = qp0->x0 + (qp0->x2 - qp0->x0) * fra;
		frx1 = qp0->x1 + (qp0->x3 - qp0->x1) * fra;
// fprintf(stderr, "i %3d %10g  frx %g %g  \tfry %g %g\n",
// i, fra, frx0, frx1, fry0, fry1);
		for(j = 0; j < nx; j++) {
//fprintf(stderr, "tile %d owd %d sx %d  j %d  sum %d\n", ntile, owd, sx, j, sx+j);
//if(sx+j >= owd) break;
#define	BLIN	// bilinear
#ifdef	BLIN
			int v0, v1, v2, v3;
			float xf, yf, f0, f1, f2, f3;
#endif
			//fy = fry0 + (fry1 - fry0) * j / (nx - 1);
			//fx = frx0 + (frx1 - frx0) * j / (nx - 1);
			fy = fry0 + (fry1 - fry0) * j / nx;
			fx = frx0 + (frx1 - frx0) * j / nx;
//fprintf(stderr, " fx  %g  fy %g\n", fx, fy);
			y = fy;
			x = fx;
#ifdef	BLIN
			yf = fy - y;
			xf = fx - x;
			f0 = (1-xf) * (1-yf);
			f1 = xf * (1-yf);
			f2 = (1-xf) * yf;
			f3 = xf * yf;
			v0 = ip0->pp[y*ip0->ydelta+x];
			v1 = ip0->pp[y*ip0->ydelta+(x+1)];
			v2 = ip0->pp[(y+1)*ip0->ydelta+x];
			v3 = ip0->pp[(y+1)*ip0->ydelta+(x+1)];
			v = f0*v0 + f1*v1 + f2*v2 + f3*v3 + 0.5;
#else
			v = ip0->pp[y*ip0->ydelta+x];	// near
//if((j&7) == 0 || (i&7) == 0) ip0->pp[y*ip0->ydelta+x] = 255;
#endif
			op[j] = v;
		}
		op += ip1->ydelta;
	}
	micros1 = getticks();
	total_ticks += (micros1-micros0);
	i = (nx+1)*(ny+1);
	total_pixels += i;
fprintf(stderr, "%lld/%d = %g/pix\n", micros1-micros0, i,
((double)micros1-micros0)/i);
//if(++calls >= 3) exit(1);
}

void dquad(float *v0, float *v1, float *v2, float *v3) {
	int x, y;
	struct quad inq, outq;
	unsigned char *p, *oip = obase + y * (long)owid * obpp;
  fprintf(stderr, "dquad %d: %g %g  %g %g  %g %g  %g %g\n", quadval,
  v0[0], v0[1], v1[0], v1[1], v2[0], v2[1], v3[0], v3[1]);
  fprintf(stderr, "\t%g %g  %g %g  %g %g  %g %g\n",
  v0[2], v0[3], v1[2], v1[3], v2[2], v2[3], v3[2], v3[3]);
	for(y = v0[1]; y < v2[1]; y++) {
		unsigned char *oip = obase + y * (long)owid * obpp;
		for(x = v0[0]; x < v1[0]; x++)
			oip[x] = 128;
	}

// clockwise to morton order // why was there a # on this cmt ??? AWW
                inq.x0 = v0[2];
                inq.y0 = v0[3];
                inq.x1 = v1[2];
                inq.y1 = v1[3];
                inq.x2 = v3[2];
                inq.y2 = v3[3];
                inq.x3 = v2[2];
                inq.y3 = v2[3];

                outq.x0 = v0[0];
                outq.y0 = v0[1];
                outq.x1 = v1[0];
                outq.y1 = v1[1];
                outq.x2 = v3[0];
                outq.y2 = v3[1];
                outq.x3 = v2[0];
                outq.y3 = v2[1];

	qmap(inimg, &inq, outimg, &outq);
	quadval++;
}

void dtri(float *v0, float *v1, float *v2) {
  float *tp, x0, y0, x1, y1;
  float tx0, tx1, ty0, ty1;
  float afargs[3][4];
  double f0, f1, dx0, dx1, dx2, dy0, dy1, dy2;
  int i;
  float A[9], B[9], I[9], M[9], R[9];
  /*
  fprintf(stderr, "dtri %d: %g %g  %g %g  %g %g\n", trival,
  v0[0], v0[1], v1[0], v1[1], v2[0], v2[1]);
  fprintf(stderr, "\t%g %g  %g %g  %g %g\n",
  v0[2], v0[3], v1[2], v1[3], v2[2], v2[3]);
  */
  tri_ticks -= getticks();
  for (i = 0; i < 4; i++) {     // XXX should 4 really be VL???
    afargs[0][i] = v0[i];
    afargs[1][i] = v1[i];
    afargs[2][i] = v2[i];
  }
  A[0] = v0[0];
  A[1] = v1[0];
  A[2] = v2[0];
  A[3] = v0[1];
  A[4] = v1[1];
  A[5] = v2[1];
  A[6] = 1;
  A[7] = 1;
  A[8] = 1;
  mprint('A', A, 9);
  B[0] = v0[2];
  B[1] = v1[2];
  B[2] = v2[2];
  B[3] = v0[3];
  B[4] = v1[3];
  B[5] = v2[3];
  B[6] = 1;
  B[7] = 1;
  B[8] = 1;
  mprint('B', B, 9);
  minv(I, A);
  mprint('I', I, 9);
  mmul(M, B, I);
  mprint('M', M, 9);
  mznorm(R, M);
  mprint('R', R, 9);
  mf[0][0] = R[0];
  mf[0][1] = R[1];
  mf[0][2] = R[2];
  mf[1][0] = R[3];
  mf[1][1] = R[4];
  mf[1][2] = R[5];
  affine_inverse(&mi[0][0], &mf[0][0]);
  printf("%s AF  %g %g %g  %g %g %g\n", fname, mi[0][0], mi[0][1], mi[0][2], mi[1][0], mi[1][1], mi[1][2]);
  printf("%s AI  %g %g %g  %g %g %g\n", fname, mf[0][0], mf[0][1], mf[0][2], mf[1][0], mf[1][1], mf[1][2]);
  //affine(3, &afargs[0][0], ethresh, leastpts); // previous AWW
  if (v1[1] < v0[1]) {
    tp = v0;
    v0 = v1;
    v1 = tp;
  }
  if (v2[1] < v0[1]) {
    tp = v0;
    v0 = v2;
    v2 = tp;
  }
  if (v2[1] < v1[1]) {
    tp = v1;
    v1 = v2;
    v2 = tp;
  }
  dx0 = v1[0] - v0[0];
  dy0 = v1[1] - v0[1];
  dx1 = v2[0] - v1[0];
  dy1 = v2[1] - v1[1];
  dx2 = v2[0] - v0[0];
  dy2 = v2[1] - v0[1];
  for (y0 = (int)(v0[1] + .5); y0 <= (int)(v1[1] + .5); y0++) {
    f0 = (v1[1] - y0) / dy0;
    f1 = (v2[1] - y0) / dy2;
    if (f0 < 0) {
      fprintf(stderr, "reset %g to 0\n", f0);
      f0 = 0;
    }
    for (i = 0; i < VL; i++) {
      hv0[i] = (1 - f0) * v1[i] + f0 * v0[i];
      hv1[i] = (1 - f1) * v2[i] + f1 * v0[i];
    }
    if (f0 <= 1 && f1 <= 1)
      hline(y0 + .5, hv0[0] + .5, hv1[0] + .5);
  }
  for (; y0 <= (int)(v2[1] + .5); y0++) {
    f0 = (y0 - v1[1]) / dy1;
    f1 = (y0 - v0[1]) / dy2;
    for (i = 0; i < VL; i++) {
      hv0[i] = (1 - f0) * v1[i] + f0 * v2[i];
      hv1[i] = (1 - f1) * v0[i] + f1 * v2[i];
    }
    if (f0 <= 1 && f1 <= 1)
      hline(y0 + .5, hv0[0] + .5, hv1[0] + .5);
  }
  trival++;
  tri_ticks += getticks();
}

void set_lut() {
  int i, v;
  for (i = 0; i < 512; i++) {
    if (rv)
      v = 255 - (i - 128);
    else
      v = i - 128;
    if (v < 0)
      v = 0;
    if (v > 255)
      v = 255;
    lut[i] = v;
  }
}

#define	STSIZE	15
static int pstack[STSIZE];
static double vstack[STSIZE];
static int sp, prec[256];
static double var[26];

void doop(int op) {
  // fprintf(stderr, "doop sp %d - pstack %c %c %c\n",
  // sp, pstack[sp-3], pstack[sp-2], pstack[sp-1]);
  if (pstack[sp - 1] == 'V') {
    // fprintf(stderr, "lookup sp-1 %c\t", (int)vstack[sp-1]);
    vstack[sp - 1] = var[(int)vstack[sp - 1] - 'a'];
    // fprintf(stderr, "-> %g\n", vstack[sp-1]);
    pstack[sp - 1] = '#';
  }
  if (op != '=' && pstack[sp - 3] == 'V') {
    // fprintf(stderr, "lookup sp-3 %c\t", (int)vstack[sp-3]);
    vstack[sp - 3] = var[(int)vstack[sp - 3] - 'a'];
    // fprintf(stderr, "-> %g\n", vstack[sp-3]);
    pstack[sp - 3] = '#';
  }
  if (sp < 0)
    exit(1);
  switch (op) {                 /* do the indicated operation */
  case '+':
    vstack[sp - 3] = vstack[sp - 3] + vstack[sp - 1];
    break;
  case '-':
    vstack[sp - 3] = vstack[sp - 3] - vstack[sp - 1];
    break;
  case '*':
    vstack[sp - 3] = vstack[sp - 3] * vstack[sp - 1];
    break;
  case '/':
    vstack[sp - 3] = vstack[sp - 3] / vstack[sp - 1];
    break;
  case '%':
    vstack[sp - 3] = (long)vstack[sp - 3] % (long)vstack[sp - 1];
    break;
  case '^':
    vstack[sp - 3] = pow(vstack[sp - 3], vstack[sp - 1]);
    break;
  case '=':
    // fprintf(stderr, "= %c %c %g\n", pstack[sp-3], (int)vstack[sp-3], vstack[sp-1]);
    var[(int)vstack[sp - 3] - 'a'] = vstack[sp - 1];
    vstack[sp - 3] = vstack[sp - 1];
    pstack[sp - 3] = '#';
    break;
  }
  // fprintf(stderr, "doop %c -> %g\n", op, vstack[sp-3]);
  sp -= 2;                      /* used 3 slots to make 1 */
}

void reducepar() {
  // fprintf(stderr, "reducepar sp %d\n", sp);
  while (pstack[sp - 2] != '(')
    doop(pstack[sp - 2]);
  sp--;                         /* account for the ( slot */
  // fprintf(stderr, "final pstack %c\n", pstack[sp]);
  if (pstack[sp] == 'V') {
    vstack[sp] = var[(int)vstack[sp] - 'a'];
    // fprintf(stderr, "lookup %d = %g\n", (int)vstack[sp], vstack[sp]);
    pstack[sp] = '#';
  }
  vstack[sp - 1] = vstack[sp];  /* move the value down one */
}

double eval_expr(char *s) {
  char *p = s;
  int i, unary = 1;
  if (prec['+'] == 0) {
    prec['='] = 1;              /* set up prec values */
    prec['+'] = prec['-'] = 2;
    prec['*'] = prec['/'] = prec['%'] = 3;
    prec['^'] = 4;
  }
  sp = 0;
  pstack[sp++] = '(';           /* preinsert ( as sentinel */
  //fprintf(stderr, "eval %s\n", p);
  for (;;) {
    char c = *p++;
    // for(i = 0; i < sp; i++) {
    // if(pstack[i] == 'V') fprintf(stderr, "i %d %c %c %g\n",
    // i, pstack[i], (int)vstack[i], var[(int)vstack[i]]);
    // else fprintf(stderr, "i %d %c %g\n", i, pstack[i], vstack[i]);
    // }
    // fprintf(stderr, "c %d <%c>\n", c, c);
    if (isalpha(c)) {
      pstack[sp] = 'V';
      vstack[sp] = c;
      // fprintf(stderr, "stacked var %c\n", c);
      sp++;
    }
    if (isdigit(c) || c == '.') {
      pstack[sp] = '#';         /* stack its type */
      if (c != '.') {
        vstack[sp] = c - '0';   /* and value */
        while (isdigit(*p)) {
          vstack[sp] *= 10;
          vstack[sp] += *p - '0';
          p++;
        }
      } else {
        vstack[sp] = 0.;
        p--;
      }
      if (*p == '.') {
        double fr = 1.;
        p++;
        while (isdigit(*p)) {
          fr *= .1;
          // fprintf(stderr, "fr %g <%c> %g\n", fr, *p, vstack[sp]);
          vstack[sp] += fr * (*p - '0');
          p++;
        }
      }
      // fprintf(stderr, "testunary# %d %g\n", unary, vstack[sp]);
      if (unary < 1)
        vstack[sp] = -vstack[sp];
      // fprintf(stderr, "final # %g\n", vstack[sp]);
      sp++;
      unary = 1;
    } else if (c == '(')
      pstack[sp++] = '(';       /* stack type - no value */
    else if (c == ')' || (c == 0 && sp > 1) || (c == ';' && sp > 1))
      reducepar();              /* reduce back to a '(' */
    else if (prec[c] == 2 && pstack[sp - 1] == '(') {
      if (c == '-')
        unary = -unary;
    } else if (prec[c] == 2 && prec[pstack[sp - 1]]) {
      if (c == '-')
        unary = -unary;
    } else if (prec[c]) {       /* its an OP */
      // fprintf(stderr, "on OP stack %c\n", pstack[sp-1]);
      if (sp > 3)               /* do a high prec stacked op */
        if (prec[pstack[sp - 2]] >= prec[c])
          doop(pstack[sp - 2]);
      pstack[sp++] = c;         /* stack the new op */
      c = *p;
      if (c == '-') {
        unary = -unary;
        // fprintf(stderr, "reset unary %d\n", unary);
        p++;
      }
      if (c == '+')
        p++;
    }
    if (c == 0) {
      if (sp == 1) {            /* this should be TRUE! */
        // fprintf(stderr, "eval_expr <%s> %g\n", s, vstack[0]);
        return (vstack[0]);
      } else
        printf("Error - sp was %d\n", sp);
        // fprintf(stderr, "at return p <%s>\n", p);
      if (sp != 1)
        fprintf(stderr, "Error - sp was %d\n", sp);
      return (vstack[0]);
    }
  }
  // fprintf(stderr, "fallout p <%s>\n", p);
}


int ndraw, nwrite;

int prompt = 0;

int main(int argc, char *argv[]) {
  FILE *fp;
  int c, i, j, x, y, *trp, *qup, pushed, sv;
  int box_xmin, box_ymin, box_xmax, box_ymax;
  float *vp, det, fx, fy;
  t_ticks -= getticks();

  if (verbose)
    print_args("top of main:", argc, argv);

  argc--;
  argv++;
  while (argc > 0 && argv[0][0] == '-') {
    int flagp = 1;
    while (argv[0][flagp]) {
      //fprintf(stderr, "arg %s\n", &argv[0][flagp]);
      switch (argv[0][flagp]) {
      case 'r':                // reverse video
        rv++;
        break;
      case 'g':                // grid
        gflag++;
        break;
      case 'S':
        sv = sscanf(argv[0] + 2, "%g,%g,%g,%g\n", &oscalex, &oscaley, &iscalex, &iscaley);
        fprintf(stderr, "cmdline scale of %s\n", argv[0] + 2);
        fprintf(stderr, "cmdline scale %g %g %g %g\n", oscalex, oscaley, iscalex, iscaley);
        break;
      case 'X':
        exchange ^= 1;
        break;
      case 'Z':
        {
          char *p = &argv[0][flagp];
          Zval = atoi(p + 1);
          fprintf(stderr, "Zval %d  atoi %d  oscalex %g\n", Zval, atoi(p + 1), oscalex);
          while (argv[0][flagp])
            flagp++;
          flagp--;              // XXX awkward
        }
        break;
      case 'T':                // transparent input value
        {
          char *p = &argv[0][flagp];
          skipval = atoi(p + 1);
          fprintf(stderr, "skipval %d  atoi %d  oscalex %g\n", skipval, atoi(p + 1), oscalex);
          while (argv[0][flagp])
            flagp++;
          flagp--;              // XXX awkward
        }
        break;
      case 'N':
        leastpts = 1000;
        {
          char *p = &argv[0][flagp];
          leastpts = atoi(p + 1);
          fprintf(stderr, "lastpts %d  atoi %d\n", Zval, atoi(p + 1));
          while (argv[0][flagp])
            flagp++;
          flagp--;              // XXX awkward
        }
        break;
      case 'B':
        {
          char *p = &argv[0][flagp];
          owid = atoi(p + 1) * oscalex;
          //fprintf(stderr, "owid %d\n", owid);
          while (*p && *p != ',')
            p++;
          oht = atoi(p + 1) * oscaley;
          //fprintf(stderr, "oht %d\n", oht);
          while (argv[0][flagp])
            flagp++;
          //fprintf(stderr, "owid %d oht %d flagp %d -> %d\n",
          //owid, oht, flagp, argv[0][flagp]);
          flagp--;              // XXX awkward
        }
        break;
      case 's':                // solid triangles
        sflag++;
        break;
      case 'o':                // outline triangles
        oflag++;
        break;
      case 'i':                // interpolation level
        iflag++;
        break;
      case 'v':                // enable verbose that Bom had extended // AWW
        verbose = 1;
        break;
      case 'b':
        bflag++;                // save overwrite for intens corr.
        break;
      case '?':
        prompt = 1;             // Enable the prompting
        break;
      }
      flagp++;
    }
    argv++;
    argc--;
  }
  //fprintf(stderr, "argc %d  gflag %d sflag %d\n", argc, gflag, sflag);
  //if(argc > 0) fprintf(stderr, "argv0 -> %s\n", argv[0]);
  if (argc > 0) {
    // man 2 open:
    //
    //   int open(const char *pathname, int flags);
    //
    //   Given a pathname for a file, open() returns a file descriptor, a small,
    //   nonnegative integer for use in subsequent system calls (read(2), write(2),
    //   lseek(2), fcntl(2), etc.).  The file descriptor returned by a successful
    //   call will be the  lowest-numbered file descriptor not currently open for
    //   the process.
    //
    //   ... the access mode values O_RDONLY, O_WRONLY, and O_RDWR do  not  specify
    //   individual  bits.  Rather, they define the low order two bits of flags, and
    //   are defined respectively as 0, 1, and 2.
    //
    // man 3 stdin:
    //
    //   On program startup, the integer file descriptors associated with the streams
    //   stdin, stdout, and stderr are 0, 1, and 2, respectively.
    //
    // According to the previous descriptions, closing file handle "0" appears to
    // free that file descriptor which means that it will be the next (lowest-numbered)
    // file descriptor used by a subsequent "open" call. This appears to be the file
    // descriptor of "stdin" for the process which allows "stdin" to be remapped to
    // the newly opened file. This essentially reassigns stdin from the terminal to
    // this newly opened file. So subsequent "getchar" calls will read from this file.
    close(0);
    i = open(argv[0], 0);
    if (i != 0) {
      fprintf(stderr, "open of <%s> as stdin failed\n", argv[0]);
      exit(1);
    }
    c = getchar();
    //fprintf(stderr, "stdin is <%s> c is %d <%c>\n", argv[0], c, c);
    ungetc(c, stdin);
  }
  set_lut();

  if (verbose)
    print_args("End of argument processing loop:", argc, argv);

  // ?
  for (;;) {
    if (prompt)
      printf("Enter a MIR command (? for help) > ");
    if ((c = getchar()) == EOF || c == 'E')
      break;
    //fprintf(stderr, "switch <%c>\n", c);
    switch (c) {
    case '?':
      printf("\nMIR is Multiple Image Rendering\n");
      printf("\n");
      printf("Commands:\n");
      printf("  ? for Help\n");
      printf("  ~ to show mappings\n");
      printf("  X for eXchange\n");
      printf("  I for interpolation 0, 1, 2\n");
      printf("  a new reverse mapping: mi00 mi01 mi02  mi10 mi11 mi12 \n");
      printf("  A new forward mapping: mf00 mf01 mf02  mf10 mf11 mf12 \n");
      printf("  G new global mapping:  mg00 mg01 mg02  mg10 mg11 mg12 \n");
      printf("  S scale multipliers: oscalex oscaley iscalex iscaley\n");
      printf("  O offsets: ooffx ooffy ioffx ioffy\n");
      printf("  B bounds of output region: owid oht obpp twid tht trans\n");
      printf("  D directory prefix for all input file names\n");
      printf("  F read a new file\n");
      printf("  R fill bounding box rect from src file & current mf[][]\n");
      printf("  Z zero the drawing space\n");
      printf("  V reverse video?\n");
      printf("  W write a file?\n");
      printf("  # for comment to end of line\n");
      printf("  E to Exit\n");
      continue;
    case 'X':
      //fprintf(stderr, "eXchange\n");
      exchange ^= 1;
      continue;
    case '#':                  // its a comment to end of current line
      while ((i = getchar()) != EOF && i != '\n') ;
      continue;
    case '~':                  // its a comment to end of current line
      printf ( "\n" );
      printf ( "  mf: [ %g %g %g   %g %g %g ]\n", mf[0][0], mf[0][1], mf[0][2], mf[1][0], mf[1][1], mf[1][2] );
      printf ( "  mi: [ %g %g %g   %g %g %g ]\n", mi[0][0], mi[0][1], mi[0][2], mi[1][0], mi[1][1], mi[1][2] );
      printf ( "  mg: [ %g %g %g   %g %g %g ]\n", mg[0][0], mg[0][1], mg[0][2], mg[1][0], mg[1][1], mg[1][2] );
      continue;
    case 'I':                  // interpolation 0, 1, 2
      sv = scanf("%d\n", &iflag);
      continue;
    case 'a':                  // read a new reverse mapping
      sv = scanf("%f %f %f  %f %f %f\n", &mi[0][0], &mi[0][1], &mi[0][2], &mi[1][0], &mi[1][1], &mi[1][2]);
      affine_inverse(&mf[0][0], &mi[0][0]);
      continue;                 //
    case 'A':                  // read a new forward mapping
      sv = scanf("%f %f %f  %f %f %f\n", &mf[0][0], &mf[0][1], &mf[0][2], &mf[1][0], &mf[1][1], &mf[1][2]);
      affine_inverse(&mi[0][0], &mf[0][0]);
      continue;                 //
    case 'G':                  // read a new global mapping
      sv = scanf("%f %f %f  %f %f %f\n", &mg[0][0], &mg[0][1], &mg[0][2], &mg[1][0], &mg[1][1], &mg[1][2]);
      affine_inverse(&mgi[0][0], &mg[0][0]);
      continue;                 //
    case 'S':                  // scale multipliers - should it be 'M'?
      sv = scanf("%f %f %f %f\n", // same order as verts
                 &oscalex, &oscaley, &iscalex, &iscaley);
      fprintf(stderr, "scales %g %g  %g %g\n", oscalex, oscaley, iscalex, iscaley);
      continue;
    case 'O':                  // offsets
#ifdef	OLD
      sv = scanf("%f %f %f %f\n", // same order as verts
                 &ooffx, &ooffy, &ioffx, &ioffy);
#endif
      {
#define	LLEN 1000
        char line[LLEN + 1], *p, *e0, *e1, *e2, *e3;
        if (!fgets(line, LLEN, stdin))
          exit(1);
        //fprintf(stderr, "line <%s>\n", line);
        p = line;
        while (*p == ' ')
          p++;
        e0 = p;
        while (*p != ' ')
          p++;
        *p++ = 0;
        e1 = p;
        while (*p != ' ')
          p++;
        *p++ = 0;
        e2 = p;
        while (*p != ' ')
          p++;
        *p++ = 0;
        e3 = p;
        while (*p != '\n')
          p++;
        *p++ = 0;
        //fprintf(stderr, "exprs <%s> <%s> <%s> <%s>\n", e0, e1, e2, e3);
        ooffx = eval_expr(e0);
        ooffy = eval_expr(e1);
        ioffx = eval_expr(e2);
        ioffy = eval_expr(e3);
      }
      fprintf(stderr, "offs %g %g  %g %g\n", ooffx, ooffy, ioffx, ioffy);
      continue;
    case 'B':                  // bounds of output region
      if (outimg) {
        free(outimg->pp);
        free(outimg);
        obase = NULL;
        outimg = NULL;
      }
      sv = scanf("%d %d %d %d %d %d\n", &owid, &oht, &obpp, &twid, &tht, &trans);
      owid *= oscalex;
      oht *= oscaley;
      if (twid < 0) {
        twid = -twid;
        padtwid = 0;
      }
      if (tht < 0) {
        tht = -tht;
        padtht = 0;
      }
      //twid *= oscalex; /// XXX leave it as unscaled output pixels
      //tht *= oscaley;
      fprintf(stderr, "output dims %d x %d  %d bytes  tile %d %d\n",
		owid, oht, obpp, twid, tht);
      //outimg = newimage(owid, oht, obpp); // delay until 1st input
      //obase = outimg->pp;
      continue;
    case 'D':                  // directory prefix for all input file names
      getchar();                // skip space
      if (scanf("%s\n", prefix) != 1)
        exit(1);
      //if(!fgets(prefix, STRLENS, stdin))
      //fgets(prefix, STRLENS, stdin);
      //fprintf(stderr, "prefix <%s>\n", prefix);
      continue;
    case 'F':                  // read a new file
      r_ticks -= getticks();
      while ((c = getchar()) == ' ' || c == '\t') // skip spaces
        ;
      ungetc(c, stdin);
      if (!fgets(fname, STRLENS, stdin))
        exit(1);
      for (i = 0; i < STRLENS && fname[i]; i++)
        if (fname[i] == '\n' || fname[i] == ' ') {
          fname[i] = 0;
          break;
        }
      strcpy(fullname, prefix);
      strcat(fullname, fname);
      if(verbose) fprintf(stderr, "fullname <%s>\n", fullname);
      if (gflag < 2 /* && sflag == 0 */ ) {
        if (inimg) {
          free(inimg->pp);
          free(inimg);
          inimg = NULL;
          idat = NULL;
        }
        inimg = read_img(fullname);
        if (!inimg) {
          fprintf(stderr, "read failed %s\n", fullname);
          idat = (unsigned char *)"AAAAAAAAAAAAAAAAAAAAAAAAAA";
          iwid = 1;
          iht = 1;
          ibpp = 1;
          //exit(0);
        } else {
          char hdr[50];
          int fd;
          idat = inimg->pp;
          iwid = inimg->wid;
          iht = inimg->ht;
          ibpp = inimg->bpp;
          //fprintf(stderr, "%dx%d %d\n", iwid, iht, ibpp);
          if (!obase) {
            if (owid == 0)
              owid = iwid;
            if (oht == 0)
              oht = iht;
            if (obpp == 0)      // if not in B spec...
              obpp = ibpp;
            //fprintf(stderr, "owid %d oht %d obpp %d\n", owid, oht, obpp);
            outimg = newimage(owid, oht, obpp);
            obase = outimg->pp;
            if (Zval)
              memset(obase, Zval > 255 ? 255 : Zval, obpp * (long)owid * oht);
          }
          //fprintf(stderr, "ibpp %d  Zval %d\n", ibpp, Zval);
          if (ibpp == 1 && Zval > 255) {
            /// Kludge to use 255 as PNG transparent demotes actual 255's to 254's
            int i;
            fprintf(stderr, "Transparency kludge using 255 background fill\n");
            for (i = 0; i < iwid * iht; i++)
              if (idat[i] == 255)
                idat[i] = 254;
          }
          //fprintf(stderr, "outimg %p\n", outimg);
          /*
          fprintf(stderr, "idat 0x%lx w %d  ht %d bpp %d\n", idat, iwid, iht, ibpp);
          fd = creat("chkinput.pgm", 0666);
          sprintf(hdr, "P%d\n%d %d\n255\n", (ibpp==3)?6:5, iwid, iht);
          write(fd, hdr, strlen(hdr));
          write(fd, idat, iwid*iht*ibpp);
          close(fd);
          */
          if (bflag) {
            int i;
            strcpy(backname, fullname);
            //fprintf(stderr, "orig <%s>\n", backname);
            char *p = backname;
            while (*p)
              p++;
            p -= 3;
            //fprintf(stderr, "suff <%s>\n", p);
            strcpy(p, "bak.pgm");
            //fprintf(stderr, "back <%s> 0x%lx\n", backname, backp);
            if (!backp) {
              int i;
              backp = (unsigned char *)malloc(iwid * iht);
              //  fprintf(stderr, "new %d=%dx%d backp 0x%lx\n", iwid*iht, iwid, iht, backp);
            }
            //fprintf(stderr, "bzero %d=%dx%d from 0x%lx\n", iwid*iht, iwid, iht, backp);
            for (i = 0; i < iwid * iht; i++) {
              backp[i] = 0;
              // failed at 20488175/10240000
              if ((i & 0xFFFFF) == 0)
                fprintf(stderr, "%d\n", i);
            }
            bzero(backp, iwid * iht);
            //fprintf(stderr, "zeroed\n");
          }
        }
        //if(inimg)
        //fprintf(stderr, "wid %d  ht %d bpp %d\n", inimg->wid, inimg->ht, inimg->bpp);
      }
      r_ticks += getticks();
      continue;
      // XXX AWW fix single point - or perhaps no point R with scale factors
	case 'R': // fill bounding box rect from src file & current mf[][]
      //fprintf(stderr, "R %d verts file %s - wh %d %d\n", nverts, fname, iwid, iht);
      // XXX 2 vect rot + scale
      // XXX rather than bounding box just split into 2 tris
      // XXX maybe for 3 corner case use faster direct trans rather than affine()
      // what about nverts == 0 with an existing affine???
      if (nverts == 0) {        // keep and use current affine;
        fprintf(stderr, "use current af  %g %g %g  %g %g %g\n",
                mf[0][0], mf[0][1], mf[0][2], mf[1][0], mf[1][1], mf[1][2]);
        fprintf(stderr, "and current ai  %g %g %g  %g %g %g\n",
                mi[0][0], mi[0][1], mi[0][2], mi[1][0], mi[1][1], mi[1][2]);
      } else if (nverts == 1) { // changed to use affine shape + 1 point
        float keep[6];
        float ikeep[6];
        float newx, newy;
        //  fprintf(stderr, "nverts is 1\n");
        //  fprintf(stderr, "vert0   %g %g  %g %g\n",
        //  vert[0][0], vert[0][1], vert[0][2], vert[0][3]);
        //  fprintf(stderr, "old af  %g %g %g  %g %g %g\n",
        //  mf[0][0], mf[0][1], mf[0][2], mf[1][0], mf[1][1], mf[1][2]);
        //fprintf(stderr, "*** newx %g = %g - %g\n", newx, vert[0][2], vert[0][0]);
        // fprintf(stderr, "*** newy %g = %g - %g\n", newy, vert[0][3], vert[0][1]);
#define nomapx(x,y) (x + mf[0][2])
#define nomapy(x,y) (y + mf[1][2])
#define remapx(x,y) (x*mf[0][0] + y*mf[0][1] + mf[0][2])
#define remapy(x,y) (x*mf[1][0] + y*mf[1][1] + mf[1][2])
#define iremapx(x,y) (x*mi[0][0] + y*mi[0][1] + mi[0][2])
#define iremapy(x,y) (x*mi[1][0] + y*mi[1][1] + mi[1][2])
        mf[0][2] = mf[1][2] = mi[0][2] = mi[1][2] = 0;
        newx = nomapx(vert[0][2], vert[0][3]) - remapx(vert[0][0], vert[0][1]);
        newy = nomapy(vert[0][2], vert[0][3]) - remapy(vert[0][0], vert[0][1]);
        mf[0][2] = newx;
        mf[1][2] = newy;
        affine_inverse(&mi[0][0], &mf[0][0]);
      } else if (nverts == 2) {
        float a, b, c, d, dx0, dy0, dx1, dy1, m, s;
        //fprintf(stderr, "v0  %g %g %g %g\n", vert[0][0], vert[0][1], vert[0][2], vert[0][3]);
        //fprintf(stderr, "v1  %g %g %g %g\n", vert[1][0], vert[1][1], vert[1][2], vert[1][3]);
        /*
	        dx0 = vert[0][0] - vert[1][0];
	        dy0 = vert[0][1] - vert[1][1];
        fprintf(stderr, "dxy0  %g %g\n", dx0, dy0);
	        dx1 = vert[0][2] - vert[1][2];
	        dy1 = vert[0][3] - vert[1][3];
        fprintf(stderr, "dxy1  %g %g\n", dx1, dy1);
	        a = sqrt(dx0*dx0 + dy0*dy0);
	        b = sqrt(dx1*dx1 + dy1*dy1);
	        m = a/b;
        fprintf(stderr, "ab  %g %g ... scale %g\n", a, b, m);
	        d = dx0*dx1 + dy0*dy1; // dot
	        c = d / (a * b); // div mag(a)*mag(b)
	        s = sqrt(1 - c*c); // sin from cos
        fprintf(stderr, "csd  %g %g  %g\n", c, s, d);
        fprintf(stderr, "acos %g  asin %g  === %g %g\n",
        acos(c), asin(s), 180*acos(c)/3.14159, 180*asin(s)/3.14159);
	        mf[0][0] = c; mf[0][1] = -s, mf[0][2] = vert[0][0] - vert[0][2];
	        mf[1][0] = s; mf[1][1] = c; mf[1][2] = vert[0][1] - vert[0][3];
	        affine_inverse(&mi[0][0], &mf[0][0]);
        */
        // thats not quite right so try a fictional point method...
        vert[2][0] = vert[0][0] - (vert[0][1] - vert[1][1]);
        vert[2][1] = vert[0][1] + (vert[0][0] - vert[1][0]);
        vert[2][2] = vert[0][2] - (vert[0][3] - vert[1][3]);
        vert[2][3] = vert[0][3] + (vert[0][2] - vert[1][2]);
        //fprintf(stderr, "fiction  %g %g  %g %g\n",
        //vert[2][0], vert[2][1], vert[2][2], vert[2][3]);
        affine(3, &vert[0][0], ethresh, leastpts);
      } else if (nverts >= 3)   // set mf according to the given points
        affine(nverts, &vert[0][0], ethresh, leastpts);

      // fprintf(stderr, "after nverts %d selections\n", nverts);
      // fprintf(stderr, "old mf  %g %g %g  %g %g %g\n",
      // mf[0][0], mf[0][1], mf[0][2], mf[1][0], mf[1][1], mf[1][2]);
      // fprintf(stderr, "old mi  %g %g %g  %g %g %g\n",
      // mi[0][0], mi[0][1], mi[0][2], mi[1][0], mi[1][1], mi[1][2]);
      // fprintf(stderr, "iwid %d  iht %d\n", iwid, iht);

      box_xmin = box_xmax = 0 * mi[0][0] + 0 * mi[0][1] + mi[0][2];
      box_ymin = box_ymax = 0 * mi[1][0] + 0 * mi[1][1] + mi[1][2];
      if(verbose) fprintf(stderr, "corners  %d %d  ", box_xmin, box_ymin);
      x = iwid * mi[0][0] + 0 * mi[0][1] + mi[0][2];
      y = iwid * mi[1][0] + 0 * mi[1][1] + mi[1][2];
      fprintf(stderr, "exterior corns %d %d  ", x, y);
      if (x < box_xmin)
        box_xmin = x;
      if (y < box_ymin)
        box_ymin = y;
      if (x > box_xmax)
        box_xmax = x;
      if (y > box_ymax)
        box_ymax = y;
      x = iwid * mi[0][0] + iht * mi[0][1] + mi[0][2];
      y = iwid * mi[1][0] + iht * mi[1][1] + mi[1][2];
      fprintf(stderr, "%d %d  ", x, y);
      if (x < box_xmin)
        box_xmin = x;
      if (y < box_ymin)
        box_ymin = y;
      if (x > box_xmax)
        box_xmax = x;
      if (y > box_ymax)
        box_ymax = y;
      x = 0 * mi[0][0] + iht * mi[0][1] + mi[0][2];
      y = 0 * mi[1][0] + iht * mi[1][1] + mi[1][2];
      fprintf(stderr, "%d %d\n", x, y);
      if (x < box_xmin)
        box_xmin = x;
      if (y < box_ymin)
        box_ymin = y;
      if (x > box_xmax)
        box_xmax = x;
      if (y > box_ymax)
        box_ymax = y;
      //fprintf(stderr, "box  %d %d %d %d\n", box_xmin, box_ymin, box_xmax, box_ymax);
      hrect(box_xmin, box_ymin, box_xmax, box_ymax);
      ndraw++;
      continue;
    case 'Z':                  // zero the drawing space
      sv = scanf("%d\n", &Zval);  // preserve if not reset
      //fprintf(stderr, "sv %d Z %d onto %d %d %d = %ld -> %p\n",
      //sv, Zval, owid, oht, obpp, owid*(long)oht*obpp, obase);
      if (obase) {
        ndraw = 0;
        if (obpp == 1)          // single 8 bit channel
          memset(obase, Zval > 255 ? 255 : Zval, owid * (long)oht);
        else if (obpp == 2) {   // single 16 bit channel
          int n;
          unsigned short *sp = (unsigned short *)obase;
          for (n = 0; n < owid * (long)oht; n++)
            sp[n] = Zval;
        }
        if (bflag)              // always zero to make background diffs.
          bzero(obase, owid * oht * obpp);
      }
      //fprintf(stderr, "ZOK %d\n", Zval);
      continue;
    case 'V':
      rv ^= 1;
      set_lut();
      //fprintf(stderr, "*** reverse video rv = %d\n", rv);
      continue;
    case 'W':
      //fprintf(stderr, "at W owht %d %d  bpp %d  twht %d %d  trans %d\n",
      //owid, oht, obpp, twid, tht, trans);
      //printf("P5\n%d %d\n255\n", iwid, iht); fflush(stdout); write(1, idat, iwid*iht);
      w_ticks -= getticks();
      while ((c = getchar()) == ' ' || c == '\t') /// skip spaces
        ;
      ungetc(c, stdin);
      if (!fgets(outname, STRLENS, stdin))
        exit(1);
      for (i = 0; i < STRLENS && outname[i]; i++)
        if (outname[i] == '\n' || outname[i] == ' ') {
          outname[i] = 0;
          break;
        }
      //if(npix > 100)
      if (twid && tht) {
        int x, y, tx, ty, ntx, nty, npct = 0, pad = Zval;
        char tilename[1000], *p;
        unsigned char *tbuf, *ip, *op;
        if (pad > 255)
          pad = 255;
        if(verbose) fprintf(stderr, "Zval %d  pad %d\n", Zval, pad);
        for (p = outname; *p; p++)
          if (*p == '%')
            npct++;
        if(verbose) fprintf(stderr, "npct %d\n", npct);
        if (npct != 2)
          goto notile;
        outtile.ht = tht;
        outtile.wid = twid;
        outtile.ydelta = twid;
        outtile.trans = trans;
        outtile.bpp = outimg->bpp;
        tbuf = malloc(twid * tht * outtile.bpp);
        outtile.pp = tbuf;
        ntx = (owid + (twid - 1)) / twid;
        nty = (oht + (tht - 1)) / tht;
fprintf(stderr, "output %dx%d tiles size %dx%d %d from %p\n",
   ntx, nty, outtile.ht, outtile.wid, outtile.bpp, outtile.pp);
        for (ty = 0; ty < nty; ty++) {
          for (tx = 0; tx < ntx; tx++) {
            int thistht = tht, thistwid = twid, rv;
            thistwid = outimg->wid - tx * twid;
            if (thistwid > twid)
              thistwid = twid;
            thistht = outimg->ht - ty * tht;
            if (thistht > tht)
              thistht = tht;
            sprintf(tilename, outname, ty, tx);
if(verbose) fprintf(stderr, "tx %d ty %d <%s>  src ydelta %d  %p  %d %d\n",
tx, ty, tilename, outimg->ydelta, outimg->pp, thistwid, thistht);
            // XXX fix partial edge tile cases
            outtile.ht = thistht;
            outtile.wid = thistwid;
            op = tbuf;
            if (thistwid < twid && padtwid)
              outtile.wid = twid;
            for (y = 0; y < thistht; y++) {
              ip = outimg->pp;
              ip += ty * tht * outimg->ydelta;
              ip += y * outimg->ydelta;
              ip += tx * twid;
              //if(y <= 10)
              //fprintf(stderr, "tile %d %d  y %d  %p %p\n", ty, tx, y, ip, op);
              for (x = 0; x < thistwid; x++)
                op[x] = ip[x];
              if (thistwid < twid && padtwid) {
                while (x < twid)
                  op[x++] = pad;
                op += twid;
              } else
                op += thistwid;
            }
            if (y < tht && padtht) {
              int i;
              if (padtwid)
                thistwid = twid;
              outtile.ht = tht;
              i = 0;
              while (i < (tht - y) * thistwid)
                op[i++] = pad;
            }
            rv = write_img(tilename, &outtile);
		if(rv < 0)
			fprintf(stderr, "write_img err %d %s\n", rv, tilename);
          }
        }
        free(tbuf);
      } else {
 notile:
        if (backp)
          fprintf(stderr, "Skip write %s\n", outname);
        else {
	  int rv;
          outimg->trans = trans;
          rv = write_img(outname, outimg);
          fprintf(stderr, "Wrote %s  rv %d\n", outname, rv);
        }
      }
      nwrite++;
      w_ticks += getticks();
      continue;
    }
    ungetc(c, stdin);
    vp = &vert[0][0];
    nverts = 0;
    for (;;) {
      char str0[500];
      char str1[500];
      char str2[500];
      char str3[500];
      i = getchar();
      if (i == '#') {
        while ((i = getchar()) != EOF && i != '\n') ;
        continue;
      }
      ungetc(i, stdin);
      if (!isdigit(i) && i != '-' && i != '+') {
//		fprintf(stderr, "+++++++break nondig %c %d\n", i, i);
        dotris = doquads = 0;
	if(i == 'T')
		dotris++;
	else if(i == 'Q')
		doquads++;
	else if(i != '\n' && i != 'R')	// AWW silent skip newline and Rect
		fprintf(stderr, "unknown mode char <%c>\n", i);
        break;
      }
      i = scanf("%s %s %s %s\n", str0, str1, str2, str3);
      if(verbose) fprintf(stderr, "i %d <%s> <%s> <%s> <%s>\n",
		i, str0, str1, str2, str3);
      if (exchange) {
        vp[2] = eval_expr(str0);
        vp[3] = eval_expr(str1);
        vp[0] = eval_expr(str2);
        vp[1] = eval_expr(str3);
      } else {
        vp[0] = eval_expr(str0);
        vp[1] = eval_expr(str1);
        vp[2] = eval_expr(str2);
        vp[3] = eval_expr(str3);
      }
      if(verbose) fprintf(stderr, "vp %f %f %f %f\n",
		vp[0], vp[1], vp[2], vp[3]);
      /*
		      if(exchange) // XXX AWW revisit why I tried this
			      i = scanf("%f %f %f %f\n", vp+2, vp+3, vp, vp+1);
		      else
			      i = scanf("%f %f %f %f\n", vp, vp+1, vp+2, vp+3);
      */
      if (i != 4)
        break;
      // in-out scaling before and indep of global xform
      vp[0] += ooffx;
      vp[1] += ooffy;
      vp[2] += ioffx;
      vp[3] += ioffy;
if(verbose) fprintf(stderr, "unscaled iverts %g %g %g %g\n",
		vp[0], vp[1], vp[2], vp[3]);
      vp[0] *= oscalex;
      vp[1] *= oscaley;
      vp[2] *= iscalex;
      vp[3] *= iscaley;
if(verbose) fprintf(stderr, "\tscaled %g %g %g %g\n",
		vp[0], vp[1], vp[2], vp[3]);
      // global transform of destination points
      fx = vp[0] * mg[0][0] + vp[1] * mg[0][1] + mg[0][2];
      fy = vp[0] * mg[1][0] + vp[1] * mg[1][1] + mg[1][2];
      vp[0] = fx;
      vp[1] = fy;
      //fprintf(stderr, "\t%g %g %g %g\n", vp[0], vp[1], vp[2], vp[3]);
      vp += 4;
      nverts++;
    }
if(verbose) fprintf(stderr, "nverts %d\n", nverts);
    c = getchar();
    ungetc(c, stdin);
if(verbose)
	fprintf(stderr, "pushback <%c> %d\n", c, c); // supressed AWW
    if (c == 'R' || c == 'A')   // XXX A no longer works since R does dtri
      continue;
    while ((i = getchar()) != EOF && i != '\n') ;
    /* */
    for (i = 0; i < nverts; i++)
      fprintf(stderr, "%d: %g %g %g %g\n", i, vert[i][0], vert[i][1], vert[i][2], vert[i][3]);
    /* */
if(dotris) {
fprintf(stderr, "in dotris\n");
    trp = &tri[0][0];
    ntris = 0;
    for (;;) {
      //fprintf(stderr, "triloop ntris %d\n", ntris);
      i = getchar();
      if (i == '#') {
      //fprintf(stderr, "on cmt\n");
        while ((i = getchar()) != EOF && i != '\n') ;
        continue;
      }
      ungetc(i, stdin);
      pushed = i;
      //fprintf(stderr, "pushed <%c>\n", pushed);
      i = scanf("%d %d %d\n", trp, trp + 1, trp + 2);
      //fprintf(stderr, "scan %d\n", i);
      if (i != 3)
        break;
      trp += 3;
      ntris++;
    }
fprintf(stderr, "ntris %d\n", ntris);
}
if(doquads) {
fprintf(stderr, "in doquads\n");
    qup = &quad[0][0];
    ntris = 0;
    for (;;) {
      //fprintf(stderr, "quadloop nquads %d\n", nquads);
      i = getchar();
      if (i == '#') {
      //fprintf(stderr, "on cmt\n");
        while ((i = getchar()) != EOF && i != '\n') ;
        continue;
      }
      ungetc(i, stdin);
      pushed = i;
      //fprintf(stderr, "pushed <%c>\n", pushed);
      i = scanf("%d %d %d %d\n", qup, qup + 1, qup + 2, qup + 3);
      //fprintf(stderr, "scan %d\n", i);
      if (i != 4)
        break;
      qup += 4;
      nquads++;
    }
fprintf(stderr, "nquads %d\n", nquads);
}
    for (i = 0; i < ntris; i++) {
fprintf(stderr, "%d: %d %d %d\n", i, tri[i][0], tri[i][1], tri[i][2]);
      for (j = 0; j < 3; j++) {
        x = vert[tri[i][j]][0];
        y = vert[tri[i][j]][1];
        if (x < oxmin)
          oxmin = x;
        if (y < oymin)
          oymin = y;
        if (x > oxmax)
          oxmax = x;
        if (y > oymax)
          oymax = y;
      }
    }
oxmin = 1000000; oxmax = 0; oymin = 1000000; oymax = 0;
    for (i = 0; i < nquads; i++) {
fprintf(stderr, "q  %d: %d %d %d %d\n", i,
quad[i][0], quad[i][1], quad[i][2], quad[i][3]);
      for (j = 0; j < 4; j++) {
        x = vert[quad[i][j]][0];
        y = vert[quad[i][j]][1];
fprintf(stderr, "qv %d,%d  %d %d\n", i, j, x, y);
        if (x < oxmin)
          oxmin = x;
        if (y < oymin)
          oymin = y;
        if (x > oxmax)
          oxmax = x;
        if (y > oymax)
          oymax = y;
      }
    }
if(verbose) // usually supress this AWW
fprintf(stderr, "q output bound %d %d  %d %d\n", oxmin, oymin, oxmax, oymax);
#define	GRID 256
#ifdef	GRID
    if (gflag) {
      //fprintf(stderr, "draw grid %d\n", GRID);
      for (y = GRID; y < iht; y += GRID)
        for (x = 0; x < iwid; x++)
          idat[y * iwid + x] ^= 128;
      for (x = GRID; x < iwid; x += GRID)
        for (y = 0; y < iht; y++)
          idat[y * iwid + x] ^= 128;
    }
#endif
if(verbose) // usually supress this AWW
fprintf(stderr, "draw ntris %d\n", ntris);
    for (i = 0; i < ntris; i++) {
      fprintf(stderr, "dtri %d %d %d\n", tri[i][0], tri[i][1], tri[i][2]);
      dtri(vert[tri[i][0]], vert[tri[i][1]], vert[tri[i][2]]);
    }
if(verbose) fprintf(stderr, "draw nquads %d\n", nquads);
    for (i = 0; i < nquads; i++) {
      fprintf(stderr, "dquad %d %d %d %d\n",
quad[i][0], quad[i][1], quad[i][2], quad[i][3]);
dquad(vert[quad[i][0]], vert[quad[i][1]], vert[quad[i][2]], vert[quad[i][3]]);
    }
    ndraw++;
if(verbose) fprintf(stderr, "ndraw %d\n", ndraw);
  }                             // end main loop
  // default stdout is pgm to allow... "a.out < x.map | cjpeg > x.jpg"
  if (nwrite == 0 && ndraw > 0) {
    w_ticks -= getticks();
    printf("P5\n%d %d\n255\n", owid, oht);
    fwrite(obase, 1, owid * oht, stdout);
    w_ticks += getticks();
  }
  t_ticks += getticks();
  if (verbose) {
    fprintf(stderr, "donec <%d>  %ld npix   %d ndraw  %d nwrite\n", c, npix, ndraw, nwrite);
    fprintf(stderr, "t_ticks %llu\n", t_ticks);
    fprintf(stderr, "r_ticks %llu\n", r_ticks);
    fprintf(stderr, "w_ticks %llu\n", w_ticks);
    fprintf(stderr, "hl_ticks %llu\n", hl_ticks);
    fprintf(stderr, "hr_ticks %llu\n", hr_ticks);
    fprintf(stderr, "tri_ticks %llu\n", tri_ticks);
    fprintf(stderr, "aff_ticks %llu\n", aff_ticks);
  }
	exit(0);
}

#define MAX 1000                // XXX Jan 2016 was 100 but 10000 failed
#define MINVAL 0.0001

void affine(int inpts, float *v, float ethresh, int leastpts) {
  float aug[MAX][MAX];          // augmented co-efficient matrix
  float solution[MAX];          // simultaneous equation soln
  int i, j, k, neqn, rowlen, temp, minus, maxei, npts;
  float temporary, r, ad0, ad1, det;
  float dx, dy, e, maxe, err, rms;

  float xa[MAX], ya[MAX];
  float xb[MAX], yb[MAX];
  float x00, y00;
  float x10, y10;
  float x01, y01;
  float x11, y11;
  int reject[MAX], rindex[MAX], nreject;

  aff_ticks -= getticks();
  neqn = 3;
  rowlen = 5;

  for (i = 0; i < inpts; i++)
    reject[i] = 0;
  nreject = 0;
 repeat:
  fprintf(stderr, "repeat inpts %d \n", inpts);  // XXX Jan 2016
  minus = 0;
  for (i = 0; i < neqn; i++)
    for (j = 0; j < rowlen; j++)
      aug[i][j] = 0;
  for (npts = i = 0; i < inpts; i++) {
    fprintf(stderr, "i %d: %g %g  %g %g  %d\n", i, v[4 * i + 0], v[4 * i + 1], v[4 * i + 2], v[4 * i + 3], reject[i]);
    if (reject[i])
      continue;                 // skip this rejected point
    xa[npts] = v[4 * i + 0];
    ya[npts] = v[4 * i + 1];
    xb[npts] = v[4 * i + 2];
    yb[npts] = v[4 * i + 3];
    rindex[npts] = i;
    npts++;
  }
  fprintf(stderr, "npts %d\n", npts); // XXX Jan 2016

  for (i = 0; i < npts; i++)
    fprintf(stderr, "orig %d: %g %g  %g %g\n", i, xa[i], ya[i], xb[i], yb[i]);

  //repeat:
  if (neqn != 3 || rowlen != 5) {
    fprintf(stderr, "bad neqn %d rowlen %d\n", neqn, rowlen);
    exit(1);
  }
  for (i = 0; i < npts; i++) {
    aug[0][3] += xa[i] * xb[i];
    aug[1][3] += ya[i] * xb[i];
    aug[2][3] += xb[i];
    aug[0][4] += xa[i] * yb[i];
    aug[1][4] += ya[i] * yb[i];
    aug[2][4] += yb[i];
    aug[0][0] += xa[i] * xa[i];
    aug[0][1] += xa[i] * ya[i];
    aug[0][2] += xa[i];
    aug[1][0] += ya[i] * xa[i];
    aug[1][1] += ya[i] * ya[i];
    aug[1][2] += ya[i];
    aug[2][0] += xa[i];
    aug[2][1] += ya[i];
    aug[2][2] += 1.0;
  }

  /*
*/
  fprintf(stderr, "aug %d %d\n", neqn, rowlen);
	  for(j = 0; j < rowlen; j++)
		  fprintf(stderr, " %g", aug[0][j]);
	  fprintf(stderr, "\n");
	  for(j = 0; j < rowlen; j++)
		  fprintf(stderr, " %g", aug[1][j]);
	  fprintf(stderr, "\n");
	  for(j = 0; j < rowlen; j++)
		  fprintf(stderr, " %g", aug[2][j]);
	  fprintf(stderr, "\n");
/*
  */

  // put augmented matrix into diagonal form
  for (j = 0; j < neqn; j++) {
    temp = j;

    // find MAX coefficient of Xj in last (neqn-j) equations
//    for (i = j + 1; i < neqn; i++) {
    for (i = j; i < neqn; i++) {
fprintf(stderr, "cmp i j t  %d %d %d  %g %g\n", i, j, temp, aug[i][j], aug[temp][j]);
      if (aug[i][j] > aug[temp][j]) {
        temp = i;
fprintf(stderr, "ne %d  j %d  temp %d  aug %g\n", neqn, j, i, aug[temp][j]);
	}
}

    if (fabs(aug[temp][j]) < MINVAL) {
      fprintf(stderr, "\n Coefficients too small !!!\n");
      //exit(1);
    }
    // swap row with MAX coefficient of Xj
    if (temp != j) {
      minus++;
      for (k = 0; k < rowlen; k++) {
        temporary = aug[j][k];
        aug[j][k] = aug[temp][k];
        aug[temp][k] = temporary;
      }
    }
    // row operations to form required diagonal matrix
    for (i = 0; i < neqn; i++)
      if (i != j) {
        r = aug[i][j];
        for (k = 0; k < rowlen; k++)
          aug[i][k] -= (aug[j][k] / aug[j][j]) * r;
      }
  }

  for (i = 0; i < neqn; i++)
    solution[i] = aug[i][neqn] / aug[i][i];

  mf[0][0] = aug[0][3] / aug[0][0];
  mf[0][1] = aug[1][3] / aug[1][1];
  mf[0][2] = aug[2][3] / aug[2][2];
  mf[1][0] = aug[0][4] / aug[0][0];
  mf[1][1] = aug[1][4] / aug[1][1];
  mf[1][2] = aug[2][4] / aug[2][2];
  ad0 = aug[0][0] * aug[1][1] - aug[0][1] * aug[1][0];
  ad1 = aug[0][3] * aug[1][4] - aug[0][4] * aug[1][3];
  x00 = 0 * mf[0][0] + 0 * mf[0][1] + mf[0][2];
  y00 = 0 * mf[1][0] + 0 * mf[1][1] + mf[1][2];
  x10 = 1 * mf[0][0] + 0 * mf[0][1] + mf[0][2];
  y10 = 1 * mf[1][0] + 0 * mf[1][1] + mf[1][2];
  x01 = 0 * mf[0][0] + 1 * mf[0][1] + mf[0][2];
  y01 = 0 * mf[1][0] + 1 * mf[1][1] + mf[1][2];
  x11 = 1 * mf[0][0] + 1 * mf[0][1] + mf[0][2];
  y11 = 1 * mf[1][0] + 1 * mf[1][1] + mf[1][2];
  affine_inverse(&mi[0][0], &mf[0][0]);
  err = maxe = 0;
  for (maxei = i = 0; i < npts; i++) {
    x00 = xa[i] * mf[0][0] + ya[i] * mf[0][1] + mf[0][2];
    y00 = xa[i] * mf[1][0] + ya[i] * mf[1][1] + mf[1][2];
    dx = xb[i] - x00;
    dy = yb[i] - y00;
    e = dx * dx + dy * dy;
    fprintf(stderr, "%d: %g %g  %g %g    %g %g\n", i, xa[i], ya[i], x00, y00, e, sqrt(e));
    err += e;
    if (e > maxe) {
      maxe = e;
      maxei = i;
    }
  }
  rms = sqrt(err / npts);
  fprintf(stderr, "maxei %d: %g %g npts %d rms %g\n", maxei, maxe, sqrt(maxe), npts, rms);
#define	REJECT
#ifdef	REJECT
  if (rms > ethresh && npts > leastpts) {
    fprintf(stderr, "reject %d %d %d: %g %g  %g %g\n",
            nreject, maxei, rindex[maxei], xa[maxei], ya[maxei], xb[maxei], yb[maxei]);
    reject[rindex[maxei]] = 1;
    nreject++;
    goto repeat;
  }
#endif                          // REJECT
  aff_ticks += getticks();
  fprintf(stderr, "\txtile %g %g %g\n", mf[0][0], mf[0][1], mf[0][2]);
  fprintf(stderr, "\tytile %g %g %g\n", mf[1][0], mf[1][1], mf[1][2]);
  fprintf(stderr, "\tnewa %g\n", atan((mf[0][1] - mf[1][0]) / (mf[0][0] + mf[1][1])) * 180 / M_PI);
  fprintf(stderr, "\txout %g %g %g\n", mi[0][0], mi[0][1], mi[0][2]);
  fprintf(stderr, "\tyout %g %g %g\n", mi[1][0], mi[1][1], mi[1][2]);
  fprintf(stderr, "\tolda %g\n", atan((mi[0][1] - mi[1][0]) / (mi[0][0] + mi[1][1])) * 180 / M_PI);
  fprintf(stderr, "rms %g  npts %d\n", sqrt(err / npts), npts);
  printf("%s AF  %g %g %g  %g %g %g\n", fname, mi[0][0], mi[0][1], mi[0][2], mi[1][0], mi[1][1], mi[1][2]);
  printf("%s AI  %g %g %g  %g %g %g\n", fname, mf[0][0], mf[0][1], mf[0][2], mf[1][0], mf[1][1], mf[1][2]);
}

void affine_inverse(float *mi, float *mf) {
  float det = mf[0] * mf[3 + 1] - mf[1] * mf[3 + 0];
  if(verbose) fprintf(stderr, "det %g -> sc %g\n", det, sqrt(1 / det));
  mi[0] = mf[3 + 1] / det;
  mi[1] = -mf[1] / det;
  mi[2] = -mf[2] * mi[0] - mf[3 + 2] * mi[1];
  mi[3] = -mf[3] / det;
  mi[3 + 1] = mf[0] / det;
  mi[3 + 2] = -mf[2] * mi[3] - mf[3 + 2] * mi[3 + 1];
}
