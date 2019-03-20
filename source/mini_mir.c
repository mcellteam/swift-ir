// MIR: Multiple Image Rendering

// gcc -O3 -o mir mir.c -ljpeg -ltiff -lpng -lm
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

#include "debug.h"


// void affine_wrapped (int inpts, float **v, float ethresh, int leastpts);


struct image *inimg, *outimg, outtile;

typedef unsigned long long ticks; // the cycle counter is 64 bits
static __inline__ ticks getticks(void) {  // read CPU cycle counter
  unsigned a, d;
  asm volatile ("rdtsc":"=a" (a), "=d"(d));
  return ((ticks) a) | (((ticks) d) << 32);
}

ticks t_ticks, hl_ticks, hr_ticks, tri_ticks, aff_ticks, r_ticks, w_ticks;

#define	VL	4                   // vector len 6 can be x0,y0, x1, y1, bright, cont XXX 6 fail
#define	NVERTS 60000
int gflag;                      // overlay grid - ignore input image if flaged twice
int sflag;                      // show solid triangles
int oflag;                      // outline triangles
int iflag = 0;                  // interpolation level nearest=0, linear=1, cubic=2
int bflag = 0;                  // save overlap image for later intensity correction calculation
int trival;
float vert[NVERTS][VL];
int nverts;
int oxmin = 1000000, oxmax, oymin = 1000000, oymax;
#define	NTRI	20000
int tri[NTRI][3];
int ntris;
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

void dtri(float *v0, float *v1, float *v2) {
  float *tp, x0, y0, x1, y1;
  float tx0, tx1, ty0, ty1;
  float afargs[3][4];
  double f0, f1, dx0, dx1, dx2, dy0, dy1, dy2;
  int i;
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
  affine(3, &afargs[0][0], ethresh, leastpts);
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

#define	STRLENS 1024
char prefix[STRLENS];
char fname[STRLENS];
char fullname[STRLENS];
char outname[STRLENS];
char line[STRLENS];
int ndraw, nwrite;

int prompt = 0;

void main(int argc, char *argv[]) {
  FILE *fp;
  int c, i, j, x, y, *trp, pushed, sv;
  int box_xmin, box_ymin, box_xmax, box_ymax;
  float *vp, det, fx, fy;
  t_ticks -= getticks();

  fprintf ( stderr, "Calling affine from main\n" );
  affine(4, NULL, 3.0, 4);
}

#define MAX 1000                // XXX Jan 2016 was 100 but 10000 failed
#define MINVAL 0.0001

/*
void affine_wrapped (int inpts, float *v[], float ethresh, int leastpts) {

  fprintf ( stderr, "Inside affine wrapped\n" );

  affine (inpts, v, ethresh, leastpts);

}
*/

void affine(int inpts, float *v, float ethresh, int leastpts) {

  fprintf ( stderr, "Inside affine\n" );
  fflush ( stderr );

//  fprintf ( stderr, "Called affine with ( %d, %f, %f, %d )\n", inpts, v[0], ethresh, leastpts );

//  float aug[MAX][MAX];          // augmented co-efficient matrix
}

void affine_inverse(float *mi, float *mf) {
  float det = mf[0] * mf[3 + 1] - mf[1] * mf[3 + 0];
  fprintf(stderr, "det %g -> sc %g\n", det, sqrt(1 / det));
  mi[0] = mf[3 + 1] / det;
  mi[1] = -mf[1] / det;
  mi[2] = -mf[2] * mi[0] - mf[3 + 2] * mi[1];
  mi[3] = -mf[3] / det;
  mi[3 + 1] = mf[0] / det;
  mi[3 + 2] = -mf[2] * mi[3] - mf[3 + 2] * mi[3 + 1];
}
