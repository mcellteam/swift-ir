// gcc -o swim -O3 -m64 -msse3 swim.c -ltiff -ljpeg -lpng -lfftw3f -lm
// ./swim 800 -k keep.JPG -i 1 R34CA1-B_S12.112.pgm 2048 2048 R34CA1-B_S12.113.pgm 2000 2100  1

//	Args:
//
//    WindowSize // may be either a single number for both x and y or a string of the form #x# such as 2048x1024
/*    options:
				-x expr: addx = MUL*eval_expr(expr)
				-y expr: addy = MUL*eval_expr(expr)
				-m expr: MUL = eval_expr(expr)
				-i expr: niter = atoi(expr)
				-w expr: wht_expon = eval_expr(expr);  whiten = 1;  if(wht_expon == 0.0) whiten = 0;
				-A apodize = 0
				-V no_vert = 1
				-H no_hor = 1
				-r reverse = 1
				-k str: keepimg = str
				-t snrthr,xthr,ythr :
							char *p;
							p = argv[2];
							snrthr = atof(p);
							while(*p && *p != ',')
								p++;
							if(*p++ == ',')
								xthr = ythr = atof(p);
							while(*p && *p != ',')
								p++;
							if(*p++ == ',')
								ythr = atof(p);
*/
//    ImageName1
//    ImageName2

//
//#define	VERB
// investigate small reversibility position inaccuracies
// while first starting point stays the same then keep searching - XXX failed??
// new flag to do keep searching vs stop here mode
// do one more loop if saving best.pgm or fpat000.pgm
// resolve which of 4 corners matched
// affine input and internal approximation
// keep recent FT component mags to regen whitening
// ifdef for MKL vs FFTW
// add flag to set MEASURE vs ESTIMATE

#include <fftw3.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/time.h>
#include "swimio.h"

#include "debug.h"

#define	MSIZE 65536	// max size

int SIZEX = 512, SIZEY = 480;
int fftw_mode = FFTW_ESTIMATE;	// modes are FFTW_ESTIMATE or FFTW_MEASURE

typedef	unsigned long long ticks;		// the cycle counter is 64 bits
static	__inline__ ticks getticks(void) {	// read CPU cycle counter
	unsigned a, d;
	asm volatile("rdtsc" : "=a" (a), "=d" (d));
	return ((ticks)a) | (((ticks)d) << 32);
}
ticks tstart, targs, tread0, tread1, total_ticks, tinit, tprep0, tprep1;
ticks tpost, tfft0, tfft1, tfft2, tmult;

struct timeval tv;
int starts, startu;
float elapsed_sec;
int loopquit, threshquit;

#define	MAXITER	1000
float m0niter[MAXITER];
int m0nitercnt[MAXITER];

float besta, bestz = 0, bestw, worst;
float curra, currz, currw;
int bestx, besty, newbest, nbests = 0;
float sumbestx = 0, sumbesty = 0, sum2bestx = 0, sum2besty = 0, sdvx, sdvy;
float fbestx, fbesty, uncert;
float snrthr = 0, xthr = 1000000, ythr = 1000000;
int areset = 0; // affine reset on failure of above

// int quiet = 1;
int debug_level = 0;
int whiten = 1; // 0 is no whitening, 1 enables whitening by wht_expon
double wht_expon = -0.65; // 0 leaves it alone, -1 is phase, -0.5 fast sqrt

float targavg, targvar, targsd; // targ average, variance and standard deviation
float patavg, patvar, patsd; // pat average, variance and standard deviation
float winavg, winvar, winsd; // window average, variance and standard deviation

float afm[4]; // affine "shape" matrix
float ofm[4]; // old affine "shape" matrix
void mk_fpat(struct image *im, double xc, double yc, double xdx, double ydx, double xdy, double ydy, int *lut, float *fpp, int nx, int ny) {
	int x, y, ix, iy, v0, v1, v2, v3, n = nx*ny;
	uchar *pp;
	float f0, f1, f2, f3, psum = 0, psum2 = 0, *ifpp = fpp;
	if(debug_level > 50) {
		fprintf(stderr, "im %p  del %d xy %g %g  %g %g  %g %g  lut %p  flt %p %d %d\n", im, im->ydelta, xc, yc, xdx, ydx, xdy, ydy, lut, fpp, nx, ny);
	}
	if(debug_level > 50) {
		fprintf(stderr, "AFFINE afm %g %g %g %g\n", afm[0], afm[1], afm[2], afm[3]);
	}
	f0 = (nx-1) * xdx/2;
	f1 = (nx-1) * xdy/2;
	f2 = (ny-1) * ydx/2;
	f3 = (ny-1) * ydy/2;
	xc -= f0;	// cvt from ctr coords to NW==UL origin
	yc -= f1;
	xc -= f2;
	yc -= f3;
	n = 0;	// fixed of out of bounds inputs
	for(y = 0; y < ny; y++) {
		for(x = 0; x < nx; x++, xc += xdx, yc += xdy) {
			float frx, fry, fv = 0;
			// bilinear within pixel from surrounding pixels
			ix = xc;
			iy = yc;
			if(ix < 0 || iy < 0 || ix >= im->wid || iy >= im->ht-1) {
				*fpp++ = -1048576.0; // has an exact fp value
				continue;
			}
			v0 = im->pp[iy*im->ydelta+ix];
			v1 = im->pp[iy*im->ydelta+(ix+1)];
			v2 = im->pp[(iy+1)*im->ydelta+ix];
			v3 = im->pp[(iy+1)*im->ydelta+(ix+1)];
			if(lut) {
				v0 = lut[v0];
				v1 = lut[v1];
				v2 = lut[v2];
				v3 = lut[v3];
			}
			frx = xc - ix;
			fry = yc - iy;
			fv = (1-fry)*((1-frx)*v0+frx*v1) + fry*((1-frx)*v2+frx*v3);
			*fpp++ = fv;	// output to contiguous presized rect
			psum += fv;	// to get avg
			psum2 += fv*fv; // to get var
			n++;
			//xc += xdx;	// prep for next output x
			//yc += xdy;
		}
		xc += ydx - nx * xdx;	// remove accumulated x and add 1 y
		yc += ydy - nx * xdy;
	}
	patavg = psum / n;
	patvar = (psum2 - psum*psum/n) / (n-1);
	patsd = sqrt(patvar);
	if(n != nx*ny) {
		for(y = 0; y < ny; y++) for(x = 0; x < nx; x++, ifpp++) {
			if(*ifpp == -1048576.0) {
				*ifpp = patavg;
			}
		}
	}
}

#define	CLIPLEFT 0 // Davi's camera left edge 20 ... XXX cond check for blk cols

void mk_ftarg(struct image *im, int xc, int yc, float *fpp, int nx, int ny) {
	int x, y, ix, iy, v0, v1, v2, v3, n = nx*ny;
	uchar *pp;
	float fv = 0, psum = 0, psum2 = 0;
	if(debug_level > 50) {
		fprintf(stderr, "im %p  %d x %d del %d cornerxy %d %d flt %p %d %d\n", im, im->wid, im->ht, im->ydelta, xc, yc, fpp, nx, ny);
	}
	n = 0; // replace nx*ny by count to handle off edge cases
	if(debug_level > 50) {
		fprintf(stderr, "**** xc %d  yc %d\n", xc, yc);
	}
	for(y = 0; y < ny; y++, yc++, fpp += nx) {
		if(yc < 0 || yc >= im->ht) {
			continue;
		}
		pp = &im->pp[yc*im->ydelta + xc];
		for(x = 0; x < nx; x++, xc++) {
			if(xc < CLIPLEFT || xc >= im->wid) { // XXX move out
				//if(n == 0) fpp[x] = pp[x+nx/2]; else
				//fpp[x] = psum/n; // XXX proper fix later + pretest this all outside the loop
				fpp[x] = 0; // XXX AWW
				continue;
			}
			fv = pp[x];
			fpp[x] = fv;
			psum += fv;	// to get avg
			psum2 += fv*fv; // to get var
			n++;
		}
		xc -= nx;
	}
	targavg = psum / n;
	targvar = (psum2 - psum*psum/n) / (n-1);
	targsd = sqrt(targvar);
	fpp -= ny*nx;
	yc -= ny;
	fv = targavg;
	if(debug_level > 50) {
		fprintf(stderr, "restart yc %d fpp %p  fv %g\n", yc, fpp, fv);
	}
	for(y = 0; y < ny; y++, yc++, fpp += nx) {
		if(yc < 0 || yc >= im->ht) {
			//fprintf(stderr, "fix y %d yc %d to %g\n", y, yc, fv); // XXX AWW apodize edges
			//alternatively fold back and diffuse on opposite edge to preserve this edge
			for(x = 0; x < nx; x++) {
				fpp[x] = fv;
			}
		} else { // XXX should do the same thing for the right side
			for(x = 0; fpp[x] == 0 && x < nx; x++) {
				fpp[x] = fv;
			}
			for(x = nx-1; fpp[x] == 0 && x > 0; x--) {
				fpp[x] = fv;
			}
		}
	}
	if(debug_level > 50) {
		fprintf(stderr, "ftarg stats  av %g  va %g  sd %g  n %d\n", targavg, targvar, targsd, n);
	}
}

void scalepat(float *pat, int nx, int ny) {
	float *fp, fmin = 1e20, fmax = -1e20;
	int x, y;
	for(y = 0, fp = pat; y < ny; y++, fp += nx) {
		for(x = 0; x < nx; x++) {
			if(fp[x] > fmax) fmax = fp[x];
			if(fp[x] < fmin) fmin = fp[x];
		}
	}
	//fprintf(stderr, "scalepat minmax %g %g\n", fmin, fmax);
	for(y = 0, fp = pat; y < ny; y++, fp += nx) {
		for(x = 0; x < nx; x++) {
			fp[x] = 255*(fp[x] - fmin)/(fmax - fmin);
		}
	}
}

void qflip(float *pat, int nx, int ny) {
	float *fp, *fp2, t;
	int x, y;
	//fprintf(stderr, "qflip 0x%lx  %d %d\n", pat, nx, ny);
	for(y = 0, fp = pat; y < ny; y++, fp += nx) { // left and right
		for(x = 0; x < nx/2; x++) {
			t = fp[x];
			fp[x] = fp[x+(nx+1)/2];
			fp[x+(nx+1)/2] = t;
		}
	}
	for(y = 0, fp = pat; y < ny/2; y++, fp += nx) { // top and bottom
		fp2 = fp + (ny+1)/2 * nx;
		for(x = 0; x < nx; x++) {
			t = fp[x];
			fp[x] = fp2[x];
			fp2[x] = t;
		}
	}
/*
	for(y = 0, fp = pat; y < ny-1; y++, fp += nx) // BAD repair for 1D FT
		for(x = nx/2; x < nx; x++)
			fp[x] = fp[x+nx];
*/
	for(y = ny-1; y > 0; y--) { // XXX OK, WANT FASTER FIX due to 1D FFT
		fp = pat + y*nx;
		for(x = 0; x < nx/2; x++) {
			fp[x] = fp[x-nx];
		}
	}
}

void cpfout(float *pat, int nx, int ny, struct image *im, int xo, int yo) {
	int x, y;
	unsigned char *cp = im->pp;
	cp += yo*im->ydelta + xo;
	for(y = 0; y < ny; y++, pat += nx, cp += im->ydelta) {
		for(x = 0; x < nx; x++) {
			cp[x] = pat[x];
		}
	}
}

void expand(float *ip, int ix, int iy, float *op, int ox, int oy, float pad) {
	int x, y;
//fprintf(stderr, "expand %d %d  to %d %d  pad %g\n", ix, iy, ox, oy, pad);
	for(y = 0; y < iy; y++, ip += ix, op += ox) {
//fprintf(stderr, "y %d\n", y);
		for(x = 0; x < ix; x++) {
			op[x] = ip[x];
		}
		for( ; x < ox; x++) {
			op[x] = pad;
		}
	}
	for( ; y < oy; y++, op += ox) {
		for(x = 0; x < ox; x++) {
			op[x] = pad;
		}
	}
//fprintf(stderr, "edone y %d\n", y);
}

void mk_winf(float *winf, int nx, int ny) {
// need unity fraction for Tukey Han
	int x, y;
	float dx, dy, r, rad;
	rad = nx/2;
	if(ny < nx)
		rad = ny/2;
	rad *= 1.05; // fudge so we don't waste true 0 edges.
	rad /= M_PI/2;
	if(debug_level > 50) {
		fprintf(stderr, "mk_winf %d %d rad %g\n", nx, ny, rad);
	}
	for(y = 0; y < ny; y++, winf += nx) {
		dy = fabs(y - ny/2.)/(ny/2);
		if(dy > .8)
			dy = .5 + cos(5*M_PI*(dy-.8))/2;
		else
			dy = 1;
		//fprintf(stderr, "y %d dy %g\n", y, dy);
		for(x = 0; x < nx; x++) {
			dx = fabs(x - nx/2.)/(nx/2);
			if(dx > .8) {
				dx = .5 + cos(5*M_PI*(dx-.8))/2;
			} else {
				dx = 1;
			}
			winf[x] = dy*dx;
			/*
			dy = y - ny/2.;
			dx = x - nx/2.;
			r = sqrt(dx*dx + dy*dy)/rad;
			winf[x] = cos(r); // circular ... radial
			//winf[x] = cos(dx/rad)*cos(dy/rad); // separable
			// annular and mexican hat with negs
			if(winf[x] < 0)
				winf[x] = 0;
			if(x < (nx>>6) || y < (nx>>6) || x > nx-(nx>>6) || y > ny-(ny>>6)) winf[x] = 0;
			else winf[x] = 1; // square crop Apr 2012
			*/
		}
	}
}

void use_winf(float *winf, float *pat, int nx, int ny) {
	int x, y, n = nx * ny;
	float *pp, *wp, en = 0, fsum = 0, fv, wsum = 0, wsum2 = 0;
	for(y = 0, pp = pat, wp = winf; y < ny; y++, pp += nx, wp += nx)
		for(x = 0; x < nx; x++) {
			fsum += pp[x] * wp[x];
			en += wp[x]; // effective n is weighted n
		}
//fprintf(stderr, "fsum %g   %g\n", fsum, fsum/en);
	fsum /= en;
	for(y = 0, pp = pat, wp = winf; y < ny; y++, pp += nx, wp += nx)
		for(x = 0; x < nx; x++) {
			fv = (pp[x] - fsum) * wp[x];
			wsum += fv;
			wsum2 += fv*fv;
			pp[x] = fv;
		}
	winavg = wsum / n;
	winvar = (wsum2 - wsum*wsum/n) / (n-1);
	winsd = sqrt(winvar);
	if(debug_level > 50) {
		fprintf(stderr, "win stats  av %g  va %g  sd %g  n %d\n", winavg, winvar, winsd, n);
	}
}

float stat_avg, stat_var, stat_sd, stat_min, stat_max, stat_maxz, stat_minz;
int stat_n, stat_minx, stat_miny, stat_maxx, stat_maxy;
int PW, PH;
float *fpat;
float *winf;	// Apr 2012 --- XXX make separate target if EW!=PW...
float *epat;
float *targ;
int EW, EH;
int RW, RH;
struct image *im0, *im1, *io, *eo, *ro;
char *fname0 = "target.pgm";
char lastf0[1000];
char *fname1 = "pattern.pgm";
char lastf1[1000];
int ndone;		// number of sets processed - trigger for first init
char oname[100];
int revlut[256];
float tarx, tary, patx, paty, startpatx, startpaty;
float oldtarx = -10000, oldtary = -10000;
float oldpatx = -10000, oldpaty = -10000, oldpata = -10000;
int ntargft, npatft, ncalls;
int nread0, nread1;

float fha[MSIZE];
float fhca[MSIZE];
float fva[MSIZE];
float fvca[MSIZE];
void stats(float *fp, int nx, int ny) {
	double sum = 0, sum2 = 0, zscore;
	int x, y, stat_n = nx * ny;
	stat_min = 1e20;
	stat_max = -1e20;
	for(y = 0; y < ny; y++) {
		for(x = 0; x < nx; x++) {
			float v = fp[x];
			sum += v;
			sum2 += v*v;
			if(v > stat_max) {
				stat_max = v;
				stat_maxx = x;
				stat_maxy = y;
			}
			if(v < stat_min) {
				stat_min = v;
				stat_minx = x;
				stat_miny = y;
			}
		}
		fp += nx;
	}
	stat_avg = sum/stat_n;
	stat_var = (sum2 - sum*sum/stat_n)/(stat_n-1);
	stat_sd = sqrt(stat_var);
//fprintf(stderr, "call stats  av %g  va %g  sd %g  n %d\n", stat_avg, stat_var, stat_sd, stat_n);
	stat_maxz = stat_max - stat_avg;
	stat_minz = stat_min - stat_avg;
//fprintf(stderr, "max %g at %d %d\n", stat_max, stat_maxx, stat_maxy);
//fprintf(stderr, "min %g at %d %d  *****\n", stat_min, stat_minx, stat_miny);
//fprintf(stderr, "minmaxz %g %g  %g %g  at %d %d\n",
//stat_minz, stat_maxz, stat_minz/stat_sd, stat_maxz/stat_sd, stat_minx, stat_miny);
	zscore = -stat_minz/stat_sd;
	newbest = 0;
//fprintf(stderr, "compare %g > %g\n", zscore, bestz);
	if(zscore > bestz) {
		if(debug_level > 50) {
			fprintf(stderr, "newbest %g vs %g a %g w %g xy %d %d\n",
														zscore, bestz, curra, wht_expon, stat_minx, stat_miny);
		}
		besta = curra;
		bestz = zscore;
		worst = stat_maxz/stat_sd;
		bestw = wht_expon;
		bestx = stat_minx;
		besty = stat_miny;
		newbest = 1;
		sumbestx += bestx;
		sumbesty += besty;
		sum2bestx += bestx*bestx;
		sum2besty += besty*besty;
		nbests++;
	} else {
		float zdiff = bestz-zscore;
		if ( (debug_level > 50) || (zdiff > 1.5) ) {
			fprintf(stderr, "%s %g %g GOTWORSE by %g:  %g vs %g a %g xy %d %d\n",
											fname0, tarx, tary, zdiff, zscore, bestz, curra, stat_minx, stat_miny);
		}
	}
	//fprintf(stderr, "ret from stats\n");
}

#define	ETHR (bestsd/2)

float find_xyoff(unsigned char *ip, int wid, int ht) {
	int i, n = 0, v, x, y;
	int xmin, xmax, ymin, ymax, minv = 256, maxv = -1, matchx, matchy;
	int firstx, lastx, firsty, lasty, x10, x90, y10, y90, ux, uy;
	unsigned char *cp;
	float f, *fh, *fv, *fhc, *fvc, frh, frv;
	double av, sd, sum=0, sumsq=0, var, halfeh, halfev, h10, h90, v10, v90;
	float sdt[256], bestsd, worstsd;
	firstx = firsty = -1;
	lastx = lasty = 1000000;
	n = ht * wid;
	if(debug_level > 50) {
		fprintf(stderr, "xy %d %d\n", wid, ht);
	}
	fh = fha;
	fhc = fhca;
	fv = fva;
	fvc = fvca;
	for(x = 0; x < wid; x++)
		fh[x] = 0;
	for(y = 0; y < ht; y++)
		fv[y] = 0;
	for(y = 0, cp = ip; y < ht; y++) {
		for(x = 0; x < wid; x++) {
			v = *cp++;
			if(v > maxv) {
				maxv = v;
				xmax = x;
				ymax = y;
			}
			if(v < minv) {
				minv = v;
				xmin = x;
				ymin = y;
			}
			fh[x] += v;
			fv[y] += v;
			sum += v;
			sumsq += v*v;
		}
	}
	fprintf(stderr, "sumsq %g\n", sumsq);
	//if(hiprot[0] != 1234.) { fprintf(stderr, "****** B\n"); exit(1); }
	av = sum/n;
	var = (sumsq - sum*sum/n) / (n-1);
	sd = sqrt(var);
	fprintf(stderr, "avg %g  var %g  sd %g\n", sum/n, var, sd);
	fprintf(stderr, "max %d at %d %d ... %g\n", maxv, xmax, ymax, (maxv-av)/sd);
	fprintf(stderr, "min %d at %d %d ... %g\n", minv, xmin, ymin, (av-minv)/sd);
	worstsd = (maxv-av)/sd;
	bestsd = (av-minv)/sd;
	/*
	for(x = 0; x < wid; x++)
		fprintf(stderr, "%d %g\n", x, -(fh[x]/wid - av));
	printf("\n");
	for(y = 0; y < ht; y++)
		fprintf(stderr, "%d %g\n", y, -(fv[y]/ht - av));
	*/
	for(x = 0; x < wid; x++) {
		fh[x] = 0;
		fhc[x] = 0;
	}
	for(y = 0; y < ht; y++) {
		fv[y] = 0;
		fvc[y] = 0;
	}
	for(y = 0, cp = ip; y < ht; y++) {
		for(x = 0; x < wid; x++) {
			v = *cp++;
			v = (av - v);
			if(v > 0) {
				f = v/sd;
				if(f < ETHR) continue;
				//fprintf(stderr, "f %g ETHR %g\n", f, ETHR);
				//fprintf(stderr, "xy %d %d: f %g -> ", x, y, f);
				f = exp(f/10.); // use Q errf instead XXX
				//fprintf(stderr, "exp %g\n", f); // no div by 10 gave too many nan overflows
				if(f > 0) {
					fh[x] += f;
					fv[y] += f;
					if(firstx < 0)
						firstx = x;
					if(firsty < 0)
						firsty = y;
					lastx = x;
					lasty = y;
				}
			}
		}
	}
//if(hiprot[0] != 1234.) { fprintf(stderr, "****** C\n"); exit(1); }
//printf("\n");
for(x = 0; x < wid; x++)  {
	fhc[x] += fh[x];
	if(x > 0) {
		fhc[x] += fhc[x-1];
		halfeh = fhc[x];
	}
	//printf("%d %g\n", x, fh[x]);
//fprintf(stderr, "x %d: %g\n", x, fh[x]);
	}
	//printf("\n");
	for(y = 0; y < ht; y++) {
		fvc[y] += fv[y];
		if(y > 0) {
			fvc[y] += fvc[y-1];
			halfev = fvc[y];
		}
		//printf("%d %g\n", y, fv[y]);
//fprintf(stderr, "y %d: %g\n", y, fv[y]);
	}
//for(y = 0; y < ht; y++) fprintf(stderr, "i %d: %g %g\n", y, fhc[y], fvc[y]);
	if(halfeh < 1 || halfev < 1)
		return(1000000); // return huge uncertainty
	h10 = .02*halfeh;
	h90 = .98*halfeh;
	v10 = .02*halfev;
	v90 = .98*halfev;
	halfeh /= 2;
	halfev /= 2;
//if(hiprot[0] != 1234.) { fprintf(stderr, "****** D\n"); exit(1); }
if(debug_level > 50)
fprintf(stderr, "half %g %g\n", halfeh, halfev);
	//printf("\n");
	x10 = y10 = 0;
	for(x = 0; x < wid; x++) {
		if(fhc[x] < halfeh)
			matchx = x;
		if(fhc[x] < h10)
			x10 = x;
		if(fhc[x] < h90)
			x90 = x;
		//printf("%d %g\n", x, fhc[x]);
//fprintf(stderr, "x %d: %g\n", x, fhc[x]);
	}
	//printf("\n");
	for(y = 0; y < ht; y++) {
		if(fvc[y] < halfev)
			matchy = y;
		if(fvc[y] < v10)
	 		y10 = y;
		if(fvc[y] < v90)
	 		y90 = y;
		//printf("%d %g\n", y, fvc[y]);
//fprintf(stderr, "y %d: %g\n", y, fvc[y]);
	}
if(debug_level > 50) {
fprintf(stderr, "matchxy %d %d\n", matchx, matchy);
fprintf(stderr, "  h (%g - %g) / (%g - %g)\n", halfeh, fhc[matchx], fhc[matchx+1], fhc[matchx]);
fprintf(stderr, "  v (%g - %g) / (%g - %g)\n", halfev, fvc[matchy], fvc[matchy+1], fvc[matchy]);
fprintf(stderr, "   at 1   %g %g\n", fhc[matchx+1], fvc[matchy+1]);
}
// XXX lots to check here
	frh = (halfeh - fhc[matchx]) / (fhc[matchx+1] - fhc[matchx-1]);
	frv = (halfev - fvc[matchy]) / (fvc[matchy+1] - fvc[matchy-1]);
matchx++;
matchy++;	// XXX Apr 25, 2012 - bump by one to hit actual peak!!! XXX
frh -= 0.5;
frv -= 0.5;	// account for 0 pos being at SIZE/2 - off by one/half XXX
if(debug_level > 50)
fprintf(stderr, "frac %g %g\n", frh, frv);
//fprintf(stderr, "final %g %g\n", matchx+frh, matchy+frv); ////////////////
//fprintf(stderr, "hthresh %g %g %g\n", h10, halfeh, h90);
//fprintf(stderr, "vthresh %g %g %g\n", v10, halfev, v90);
//fprintf(stderr, "hlimits %d %d %d\n", x10, matchx, x90);
//fprintf(stderr, "vlimits %d %d %d\n", y10, matchy, y90);
	//free(fh);
	//free(fv);
	//free(fhc);
	//free(fvc);
	fbestx = matchx+frh;
	fbesty = matchy+frv;
	ux = x90 - x10;
	uy = y90 - y10;
if(debug_level > 50) {
fprintf(stderr, "matchx %d matchy %d\n", matchx, matchy);
fprintf(stderr, "frh %g frv %g\n", frh, frv);
fprintf(stderr, "fbestx %g fbesty %g\n", fbestx, fbesty);
fprintf(stderr, "firstlast %d %d  %d %d", firstx, lastx, firsty, lasty);
fprintf(stderr, " xy90 %d %d  %d %d", x90, x10, y90, y10);
fprintf(stderr, " ux %d uy %d\n", ux, uy);
}
	uncert = sqrt(ux*ux + uy*uy);
	return(uncert);
}

void color2byte(struct image *im) {
	int i, n, R, G, B;
	unsigned char *ip = im->pp;
	unsigned char *op = im->pp;
	n = im->wid*im->ht;
	for(i = 0; i < n; i++) {
		R = *ip++;
		G = *ip++;
		B = *ip++;
		*op++ = (4*G + 2*R + B)/7.0;
	}
	im->pp = realloc(im->pp, n);
	im->bpp = 1;
}

void short2byte(struct image *im) {
	int i, n, min = 1000000, max = 0, v, sum = 0;
	unsigned short *sp = (unsigned short *)im->pp;
	unsigned char *cp = im->pp;
	float m;
	n = im->wid*im->ht;
	for(i = 0; i < n; i++) {
		v = sp[i];
		sum += v;
		if(v > max)
			max = v;
		else if(v < min)
			min = v;
	}
	m = 255./(max - min);
fprintf(stderr, "short2byte  %d %g %d  %g\n", min, sum/(float)n, max, m);
	for(i = 0; i < n; i++)
		cp[i] = m*(sp[i] - min);
	im->pp = realloc(im->pp, n);
	im->bpp = 1;
}

#define	STSIZE	15
static int pstack[STSIZE];
static double vstack[STSIZE];
static int sp, prec[256];

void doop(int op) {
	switch(op) {				/* do the indicated operation */
	case	'+':
		vstack[sp-3] = vstack[sp-3] + vstack[sp-1];
		break;
	case	'-':
		vstack[sp-3] = vstack[sp-3] - vstack[sp-1];
		break;
	case	'*':
		vstack[sp-3] = vstack[sp-3] * vstack[sp-1];
		break;
	case	'/':
		vstack[sp-3] = vstack[sp-3] / vstack[sp-1];
		break;
	case	'^':
		vstack[sp-3] = pow(vstack[sp-3], vstack[sp-1]);
		break;
	}
	sp -= 2;				/* used 3 slots to make 1 */
}

void reducepar() {
	while(pstack[sp-2] != '(')
		doop(pstack[sp-2]);
	sp--;					/* account for the ( slot */
	vstack[sp-1] = vstack[sp];		/* move the value down one */
}

double eval_expr(char *s) {
	/* This is where we should handle scientific notation */
	char *p = s;
	int i, unary = 1;
	if(prec['+'] == 0) {
		prec['='] = 1;	/* set up prec values */
		prec['+'] = prec['-'] = 2;
		prec['*'] = prec['/'] = 3;
		prec['^'] = 4;
	}
	sp = 0;
	pstack[sp++] = '(';	/* preinsert ( as sentinel */
//fprintf(stderr, "enter eval %s\n", p);
	for( ; ; ) {
		char c = *p++;
//for(i = 0; i < sp; i++) fprintf(stderr, "i %d %c\n", i, pstack[i]);
//fprintf(stderr, "c %d <%c>\n", c, c);
		if(isdigit(c) || c == '.') {
			pstack[sp] = '#';	/* stack its type */
			if(c != '.') {
				vstack[sp] = c - '0';	/* and value */
				while(isdigit(*p)) {
					vstack[sp] *= 10;
					vstack[sp] += *p - '0';
					p++;
				}
			} else {
				vstack[sp] = 0.;
				p--;
			}
			if(*p == '.') {
				double fr = 1.;
				p++;
				while(isdigit(*p)) {
					fr *= .1;
//fprintf(stderr, "fr %g <%c> %g\n", fr, *p, vstack[sp]);
					vstack[sp] += fr * (*p - '0');
					p++;
				}
			}
//fprintf(stderr, "testunary# %d %g\n", unary, vstack[sp]);
			if(unary < 1)
				vstack[sp] = -vstack[sp];
//fprintf(stderr, "final # %g\n", vstack[sp]);
			sp++;
			unary = 1;
		} else if(c == '(')
			pstack[sp++] = '(';	/* stack type - no value */
		else if(c == ')' || (c == 0 && sp > 1))
			reducepar();		/* reduce back to a '(' */
		else if(prec[c] == 2 && pstack[sp-1] == '(') {
			if(c == '-')
				unary = -unary;
		} else if(prec[c] == 2 && prec[pstack[sp-1]]) {
			if(c == '-')
				unary = -unary;
		} else if(prec[c]) {	/* its an OP */
//fprintf(stderr, "on OP stack %c\n", pstack[sp-1]);
			if(sp > 3)		/* do a high prec stacked op */
				if(prec[pstack[sp-2]] >= prec[c])
					doop(pstack[sp-2]);
			pstack[sp++] = c;	/* stack the new op */
			c = *p;
			if(c == '-') {
				unary = -unary;
//fprintf(stderr, "reset unary %d\n", unary);
				p++;
			}
			if(c == '+')
				p++;
		}
		if(c == 0) {
//			if(sp == 1) {		/* this should be TRUE! */
//fprintf(stderr, "eval_expr <%s> %g\n", s, vstack[0]);
//				return(vstack[0]);
//			} else
//				printf("Error - sp was %d\n", sp);
			if(sp != 1)
				fprintf(stderr, "Error - sp was %d\n", sp);
			return(vstack[0]);
		}
	}
}

static __inline__
double fastPow(double a, double b) {
	union {
		double d;
		int x[2];
	} u = { a };
	u.x[1] = (int)(b * (u.x[1] - 1072632447) + 1072632447);
	u.x[0] = 0;
	return u.d;
}

// #define	MUL 1
//float MUL  = 1.0;

float mf[2][3] = {1, 0, 0, 0, 1, 0};	// forward affine
float mi[2][3] = {1, 0, 0, 0, 1, 0};	// inverse affine

void affine_inverse(float *mi, float *mf) {
	float det = mf[0]*mf[3+1] - mf[1]*mf[3+0];
	fprintf(stderr, "det %g -> sc %g\n", det, sqrt(1/det));
	mi[0] = mf[3+1]/det;
	mi[1] = -mf[1]/det;
	mi[2] = -mf[2]*mi[0] - mf[3+2]*mi[1];
	mi[3] = -mf[3]/det;
	mi[3+1] = mf[0]/det;
	mi[3+2] = -mf[2]*mi[3] - mf[3+2]*mi[3+1];
}

char *keepimg;

fftwf_complex *fft_result0, *fft_result1, *fft_comb;
fftwf_plan forward_plan0, backward_plan;

int Nforw, Nrev;
float *ifft_comb;

int oldmain(int argc, char *argv[]) {
	float *fp, a, addx = 0, addy = 0, MUL = 1.0;
	float rota = 0, ntarx, ntary, npatx, npaty, deltx, delty;
	float rng_up, rng_dn, rng_lft, rng_rt;
	double fdx, fdy;
	double tdx, tdy;
	int i, ia, x, y, size;
	int niter = 1, reverse = 0, no_vert = 0, no_hor = 0, apodize = 1;
	char *cp;
	float m0, m1;


  // Search for the debug option to turn it on before anything else
  // Note that this should have been completed in main itself, but
  // because of the mkargs function (maps stdin to args), the options
  // wouldn't have been in argv for main. So it's checked here again.
  for (i=0; i<argc; i++) {
    if (strcmp(argv[i],"-$")==0) {
      if (i<(argc-1)) {
        debug_level = atoi(argv[i+1]);
      }
    }
  }


	if (debug_level > 50) print_args ( "oldmain:", argc, argv );

	targs -= getticks();
	ncalls++;
	patx = -1000000;
	paty = -1000000;
	tarx = -1000000;
	tary = -1000000;
	while(*argv[1] == '-') {
		if (debug_level > 50) print_args ( "oldmain top of while:", argc, argv );
		if(argv[1][1] == '$') { // -$
			debug_level = atoi(argv[2]);
			argc--;
			argv++;
		}
		if(argv[1][1] == 'x') { // -x
			addx = MUL*eval_expr(argv[2]);
			argc--;
			argv++;
		}
		if(argv[1][1] == 'y') { // -y
			addy = MUL*eval_expr(argv[2]);
			argc--;
			argv++;
		}
		if(argv[1][1] == 'm') { // -m
			MUL = eval_expr(argv[2]);
			argc--;
			argv++;
		}
		if(argv[1][1] == 'i') { // -i
			niter = atoi(argv[2]);
			if (niter >= MAXITER) {
			  fprintf(stderr, "WARNING  niter=%d >= MAXITER=%d  limiting niter to MAXITER-1\n", niter, MAXITER);
			  niter = MAXITER - 1;
			}
			argc--;
			argv++;
		}
		if(argv[1][1] == 'w') { // -w
			wht_expon = eval_expr(argv[2]);
			whiten = 1;
			if(wht_expon == 0.0)
				whiten = 0;
			argc--;
			argv++;
		}
		if(argv[1][1] == 't') { // -t Thresholds for affine reset
			char *p;
			p = argv[2];
			snrthr = atof(p);
			while(*p && *p != ',')
				p++;
			if(*p++ == ',')
				xthr = ythr = atof(p);
			while(*p && *p != ',')
				p++;
			if(*p++ == ',')
				ythr = atof(p);
			argc--;
			argv++;
		}
		if(argv[1][1] == 'A') // -A
			apodize = 0;
		if(argv[1][1] == 'V') // -V
			no_vert = 1;
		if(argv[1][1] == 'H') // -H
			no_hor = 1;
		if(argv[1][1] == 'r') // -r
			reverse = 1;
		if(argv[1][1] == 'k') { // -k
 			keepimg = argv[2];
			argc--;
			argv++;
		}
		argc--;
		argv++;
	}
	afm[0] = 1;
	afm[1] = 0;
	afm[2] = 0;
	afm[3] = 1;

	if (debug_level > 50) print_args ( "main after parsing options:", argc, argv );

	fname0 = argv[1];
	if(argc == 3) {
	  if (debug_level > 50) printf ( "3 non-option arguments (including 0)\n" );
		fname1 = argv[2];
	} else {
		if (debug_level > 50) printf ( "not 3 non-option arguments (including 0)\n" );
		tarx = eval_expr(argv[2]);
		tary = eval_expr(argv[3]);
		fname1 = argv[4];
		patx = tarx;
		paty = tary;
		if(argc > 5)
			if (debug_level > 50) printf ( "more than 5 non-option arguments (including 0)\n" );
			patx = eval_expr(argv[5]);
		if(argc > 6)
			if (debug_level > 50) printf ( "more than 6 non-option arguments (including 0)\n" );
			paty = eval_expr(argv[6]);
		if(argc == 8) {
			if (debug_level > 50) printf ( "exactly 8 non-option arguments (including 0)\n" );
			rota = eval_expr(argv[7]);
			a = rota*M_PI/180;
			afm[0] = cos(a);
			afm[1] = sin(a);
			afm[2] = -sin(a);
			afm[3] = cos(a);
		} else if(argc == 11) {
			if (debug_level > 50) printf ( "exactly 11 non-option arguments (including 0)\n" );
			rota = 1024; // XXX magic to use explicit afm
			afm[0] = eval_expr(argv[7]);
			afm[1] = eval_expr(argv[8]);
			afm[2] = eval_expr(argv[9]);
			afm[3] = eval_expr(argv[10]);
		} else if(argc == 12) { // affine predict
			if (debug_level > 50) printf ( "exactly 12 non-option arguments (including 0)\n" );
			rota = 1024; // XXX magic to use explicit afm
			mf[0][0] = eval_expr(argv[5]);
			mf[0][1] = eval_expr(argv[6]);
			mf[0][2] = eval_expr(argv[7]);
			mf[1][0] = eval_expr(argv[8]);
			mf[1][1] = eval_expr(argv[9]);
			mf[1][2] = eval_expr(argv[10]);
			fprintf(stderr, "MF  %g %g %g  %g %g %g\n", mf[0][0], mf[0][1], mf[0][2], mf[1][0], mf[1][1], mf[1][2]);
			affine_inverse(&mi[0][0], &mf[0][0]);
			fprintf(stderr, "MI  %g %g %g  %g %g %g\n", mi[0][0], mi[0][1], mi[0][2], mi[1][0], mi[1][1], mi[1][2]);
			if(argv[11][0] == '-') {
				if (debug_level > 50) printf ( "argv[11][0] == -\n" );
				patx = tarx*mi[0][0] + tary*mi[0][1] + mi[0][2];
				paty = tarx*mi[1][0] + tary*mi[1][1] + mi[1][2];
				afm[0] = mi[0][0];
				afm[1] = mi[0][1];
				afm[2] = mi[1][0];
				afm[3] = mi[1][1];
			} else {
				if (debug_level > 50) printf ( "argv[11][0] =/= -\n" );
				patx = tarx*mf[0][0] + tary*mf[0][1] + mf[0][2];
				paty = tarx*mf[1][0] + tary*mf[1][1] + mf[1][2];
				afm[0] = mf[0][0];
				afm[1] = mf[0][1];
				afm[2] = mf[1][0];
				afm[3] = mf[1][1];
			}
		} else if(argc != 7 && argc != 5) {
			if (debug_level > 50) printf ( "argc =/= 7 or 5" );
			fprintf(stderr, "******** bad argc %d\n", argc);
		}
	}

	targs += getticks();
	if(/*fname0[0] != '-' ||*/ strcmp(fname0, lastf0)) {  // XXX recheck
		tread0 -= getticks();
		strcpy(lastf0, fname0);
		if(im0 && im0->pp) {
			free(im0->pp);
			free(im0);
		}
		im0 = read_img(fname0);
		if(im0 == NULL) {
			tread0 += getticks();
			fprintf(stderr, "Can't read_img %s\n", fname0);
			return(-1);
		}
		if(im0->bpp == 2)
			short2byte(im0);
		if(im0->bpp == 3)
			color2byte(im0);
		if(reverse) {
			unsigned char *p = im0->pp;
			unsigned short *s = (unsigned short *)im0->pp;
			int i;
			if(im0->bpp == 1)
				for(i = 0; i < im0->wid * im0->ht; i++)
					p[i] = 255 - p[i];
			else if(im0->bpp == 2)
				for(i = 0; i < im0->wid * im0->ht; i++)
					s[i] = 65536 - s[i];
		}
		oldtarx = -10000;
		oldtary = -10000;
		nread0++;
		tread0 += getticks();
	}
	if(im0 == NULL) // quietly handle repeat open failures
		return(-1);
	if(/*fname1[0] != '-' ||*/ strcmp(fname1, lastf1)) {  // XXX recheck
		tread1 -= getticks();
		strcpy(lastf1, fname1);
		if(im1 && im1->pp) {
			free(im1->pp);
			free(im1);
		}
		im1 = read_img(fname1);
		if(im1 == NULL) {
			tread1 += getticks();
			fprintf(stderr, "Can't read_img %s\n", fname1);
			return(-1);
		}
		if(im1->bpp == 2)
			short2byte(im1);
		if(im1->bpp == 3)
			color2byte(im1);
		oldpatx = -10000;
		oldpaty = -10000;
		nread1++;
		tread1 += getticks();
	}
	if(im1 == NULL)	// quietly handle repeat open failures
		return(-1);
	if(tarx <= -1000000)
		tarx = im0->wid/2;
	if(tary <= -1000000)
		tary = im0->ht/2;
	if(patx <= -1000000)
		patx = im1->wid/2;
	if(paty <= -1000000)
		paty = im1->ht/2;
	tarx *= MUL;
	tary *= MUL;
	patx *= MUL;
	paty *= MUL;
	tarx += addx;
	tary += addy;
	patx += addx*afm[0] + addy*afm[1];
	paty += addx*afm[2] + addy*afm[3];
	tarx = (int)(tarx + .5); /// XXX int to avoid mk_targ interpolation
	tary = (int)(tary + .5);
	startpatx = patx;
	startpaty = paty;
	if(debug_level > 50)
		fprintf(stderr, "args  %s %g %g  %s %g %g  MUL %g SIZ %dx%d\n",
			fname0, tarx, tary, fname1, patx, paty,MUL,SIZEX,SIZEY);
#ifdef	VERB
	fprintf(stderr, "SWIM %dx%d %s %g %g %s %g %g  %g %g %g %g\n",
		SIZEX, SIZEY, fname0, tarx, tary, fname1,
		patx, paty, afm[0], afm[1], afm[2], afm[3]);
#endif // VERB
	PW = SIZEX;
	PH = SIZEY;
	EW = SIZEX;
	EH = SIZEY;
	size = EW*EH;
	RW = EW;
	RH = EH;
	if(ndone++ == 0) {
		tinit -= getticks();
		io = newimage(PW, PH, 1); // for the original pattern area
		ro = newimage(RW, RH, 1); // the result corr over the roi
		eo = newimage(EW, EH, 1); // expanded pattern for correlation
		for(i = 0; i < 256; i++)
			revlut[i] = 255-i;
		fft_result0 = (fftwf_complex*) fftwf_malloc(sizeof(fftw_complex) * (size/2+1));
		fft_result1 = (fftwf_complex*) fftwf_malloc(sizeof(fftw_complex) * (size/2+1));
		fft_comb    = (fftwf_complex*) fftwf_malloc(sizeof(fftw_complex) * (size/2+1));
		ifft_comb   = fftwf_malloc(sizeof(fftw_complex) * (size/2+1));
		forward_plan0 = fftwf_plan_dft_r2c_1d(size, targ, fft_result0, fftw_mode);
		backward_plan = fftwf_plan_dft_c2r_1d(size, fft_comb, ifft_comb, fftw_mode);
		mk_winf(winf, PW, PH);
		tinit += getticks();
		if(fftw_mode == FFTW_MEASURE) {
			gettimeofday(&tv, NULL);
			elapsed_sec = (tv.tv_sec-starts) + (tv.tv_usec - startu)/1000000.;
			fprintf(stderr, "FFTW_MEASURE %12llu ticks  %g sec\n", tinit, elapsed_sec);
		}
	}
	if(debug_level > 50)
		fprintf(stderr, "make targ at %g %g EWH %d %d\n", tarx, tary, EW, EH);
	if(oldtarx != tarx || oldtary != tary) {
		tprep0 -= getticks();
		mk_ftarg(im0, tarx-EW/2, tary-EH/2, targ, EW, EH);
		if(apodize)
			use_winf(winf, targ, EW, EH);
		scalepat(targ, EW, EH);	// Apr 2012 - apply once to targ
		bestz = 0; // by themselves these failed for multiple runs
		nbests = 0;
		sumbestx = 0;
		sumbesty = 0;
		sum2bestx = 0;
		sum2besty = 0;
		if(keepimg || (debug_level > 50))
			cpfout(targ, EW, EH, eo, 0, 0);
		tprep0 += getticks();
		if(keepimg || (debug_level > 50))
			write_img("newtarg.JPG", eo);
	}
	bestz = 0;
	nbests = 0;
	sumbestx = 0;
	sumbesty = 0;
	sum2bestx = 0;
	sum2besty = 0;
loop:
	if(debug_level > 50)
		fprintf(stderr, "LOOP patxy %g %g  bestz %g %d\n",
			patx, paty, bestz, nbests);
	bestz = 0; // reinit to fix mpl image bug XXX
	nbests = 0;
	sumbestx = 0;
	sumbesty = 0;
	sum2bestx = 0;
	sum2besty = 0;
	ia = 0;
	fprintf(stderr, "LOOP ia %d  wht_expon %g\n", ia, wht_expon);
	curra = 0;
	currw = wht_expon;
	a = (rota+curra)*M_PI/180;
	fdx = cos(a);
	fdy = sin(a);
	m0 = sqrt(fdx*fdx + fdy*fdy);
	fprintf(stderr, "ia %d a %g  %g %g  %g\n", ia, a, fdx, fdy, m0);
	if(1 || oldpatx != patx || oldpaty != paty || oldpata != a) { // XXX
		tprep1 -= getticks();
		if(a >= -.001 && a <= 0.001)
			mk_ftarg(im1, patx-PW/2, paty-PH/2, fpat, PW,  PH);
		else if(rota == 1024)
			mk_fpat(im1, patx, paty, afm[0], afm[1], afm[2], afm[3],
				NULL, fpat, PW, PH);
		else
			mk_fpat(im1, patx, paty, fdx, fdy, -fdy, fdx, NULL,
				fpat, PW, PH);
		fp = fpat; // XXX is this ever used???
		expand(fpat, PW, PH, epat, EW, EH, winavg);
		if(debug_level > 50)
			fprintf(stderr, "expanded\n");
		scalepat(epat, EW, EH);
		cpfout(epat, EW, EH, eo, 0, 0);
		scalepat(fpat, PW, PH);
		if(debug_level > 50)
			fprintf(stderr, "scaled\n");
		cpfout(fpat, PW, PH, io, 0, 0);
		tprep1 += getticks();
	}
	if(oldtarx != tarx || oldtary != tary) {
		if(debug_level > 50) fprintf(stderr, "need first FFT %g %g  %p\n", tarx, tary, targ);
		tfft0 -= getticks();
		fftwf_execute_dft_r2c(forward_plan0, targ, fft_result0);
		oldtarx = tarx; oldtary = tary; ntargft++;
		tfft0 += getticks();
		Nforw++;
		fprintf(stderr, "did first FFT\n");
	}
	fdx = patx - oldpatx;
	fdy = paty - oldpaty;
	m0 = sqrt(fdx*fdx + fdy*fdy);
	if(oldpatx != patx || oldpaty != paty || oldpata != a || afm[0] != ofm[0] || afm[1] != ofm[1] || afm[2] != ofm[2] || afm[3] != ofm[3]) {
		if(debug_level > 50) fprintf(stderr, "need second FFT %g %g\n", patx, paty);
		tfft1 -= getticks();
		fftwf_execute_dft_r2c(forward_plan0, epat, fft_result1);
		oldpatx = patx; oldpaty = paty; oldpata = a; npatft++;
		ofm[0] = afm[0];
		ofm[1] = afm[1];
		ofm[2] = afm[2];
		ofm[3] = afm[3];
		tfft1 += getticks();
		Nforw++;
	}
	tmult -= getticks();
	for(i = 0; i < size/2+1; i++) { // convolution multiply loop
		double re, im, conj, s;
		conj = -fft_result0[i][1]; // conjugate to correlate
		re = fft_result0[i][0] * fft_result1[i][0];
		re -= conj * fft_result1[i][1];
		im = fft_result0[i][0] * fft_result1[i][1];
		im += fft_result1[i][0] * conj;
		if(whiten) {
			s = sqrt(re*re + im*im);
#define	pow(a, b) fastPow(a, b)
			if(s > 1e-5) {
				s = pow(s, wht_expon);
				re *= s;
				im *= s;
			}
		}
		fft_comb[i][0] = -re; // reversed to dark corr
		fft_comb[i][1] = im;
	}
	tmult += getticks();
	if(debug_level > 50)
		fprintf(stderr, "ready for backward_plan\n");
	tfft2 -= getticks();
	fftwf_execute_dft_c2r(backward_plan, fft_comb, ifft_comb);
	tfft2 += getticks();
	Nrev++;
	tpost -= getticks();
	scalepat(ifft_comb, EW, EH);
	qflip(ifft_comb, EW, EH);
	stats(ifft_comb, EW, EH); // easier to understand in gray levs
	cpfout(ifft_comb, EW, EH, eo, 0, 0);
	if(newbest) {
		if(keepimg || (debug_level > 50)) {
			sprintf(oname, "best.JPG");
			write_img(oname, eo);
		}
		if(keepimg)
			write_img(keepimg, io); /// XXX should regen after move
		uncert = find_xyoff(eo->pp, eo->wid, eo->ht);
		if(debug_level > 50)
			fprintf(stderr, "uncert %f\n", uncert);
	}
	tpost += getticks();
	if(debug_level > 50)
		fprintf(stderr, "loop all done\n");
	rng_lft = tarx < patx ? tarx : patx;
	rng_up = tary < paty ? tary : paty;
	rng_rt = im0->wid - tarx < im1->wid - patx ? im0->wid - tarx : im1->wid - patx;
	rng_dn = im0->ht - tary < im1->ht - paty ? im0->ht - tary : im1->ht - paty;
	deltx = (rng_rt - rng_lft)/2;
	delty = (rng_dn - rng_up)/2;
	if(debug_level > 50)
	fprintf(stderr, "up/down %g %g  lft/rt %g %g  del %g %g \n",
	rng_up, rng_dn, rng_lft, rng_rt, deltx, delty);
	ntarx = tarx + deltx;
	ntary = tary + delty;
	npatx = patx + deltx;
	npaty = paty + delty;
	if(debug_level > 50)
	fprintf(stderr, "%g: %s %g %g %s %g %g delt %g %g\n", bestz,
	fname0, ntarx, ntary, fname1, npatx, npaty, deltx, delty);
	fdx = fbestx-SIZEX/2.;
	fdy = fbesty-SIZEY/2.;
	m0 = sqrt(fdx*fdx + fdy*fdy);
	m0niter[niter] += m0;
	m0nitercnt[niter]++;
	tdx = afm[0]*fdx + afm[1]*fdy;
	tdy = afm[2]*fdx + afm[3]*fdy;
	if(no_hor)
		tdx = 0;
	if(no_vert)
		tdy = 0;
	if(debug_level > 50)
		fprintf(stderr, "MOVE by %g-%g=%g  %g-%g=%g   %g\n",
	fbestx, SIZEX/2., fdx, fbesty, SIZEY/2., fdy, m0);
	if(debug_level > 50)
		fprintf(stderr, "TXY %g %g = %g\n", tdx, tdy, sqrt(tdx*tdx + tdy*tdy));
	if(debug_level > 50)
		fprintf(stderr, "OLD %g %g", patx, paty);
	patx = patx - tdx;
	paty = paty - tdy;
	if(debug_level > 50)
		fprintf(stderr, "   NEW patx paty %g %g\n", patx, paty);
	if(--niter > 0)
		goto loop;
	if(debug_level > 50) {
		fprintf(stderr, "tarx %g tary %g\n", tarx, tary);
		fprintf(stderr, "patx %g paty %g\n", patx, paty);
		fprintf(stderr, "bstx %g bsty %g\n", fbestx, fbesty);
	}
	fprintf(stderr, "keep %g: %s %d %d %s %g %g  %g\n", bestz, fname0,
		(int)tarx, (int)tary, fname1, patx, paty, rota+besta);
	fdx = patx - startpatx;
	fdy = paty - startpaty;
	m0 = sqrt(fdx*fdx + fdy*fdy);
	{
		char outbuf[10000];
		static char *flags[] = { "", " dx", " dy", " dxy", " dreset" };
		int flag = 0, nw;
		if(sqrt(fdx*fdx) > SIZEX/4) {
			flag |= 1;
		}
		if(sqrt(fdy*fdy) > SIZEY/4) {
			flag |= 2;
		}
		if(snrthr > bestz) {
			areset = 1;
		}
		if(sqrt(fdx*fdx) > xthr) {
			areset += 2;
		}
		if(sqrt(fdy*fdy) > ythr) {
			areset += 4;
		}
		if(areset) {
			flag = 4;
			patx = startpatx;
			paty = startpaty;
			areset = 0; //// XXX do this somewhere else
		}
		sprintf(outbuf, "%g: %s %g %g %s %g %g  %g (%g %g %g%s)\n", bestz, fname0, tarx, tary, fname1, patx, paty, rota+besta, fdx, fdy, m0, flags[flag]);
		nw = write(1, outbuf, strlen(outbuf));
	}
	return(0);
}

int nargc;
#define MAXARGS 100
char *nargv[MAXARGS];
#define	LLEN 2000
char line[LLEN];

int mkargs(char *oargv[], char *s) {
	int i, n = 0;
	char *p = s;

	while(*p) {
		oargv[n++] = p;
		while(*p && *p != '\n' && *p != ' ' &&  *p != '\t')
			p++;
		while(*p == ' ' || *p == '\t' || *p == '\n')
			*p++ = 0;
	}
	oargv[n] = NULL;
	return(n);
}

int main(int argc, char *argv[]) {
	int i;
	char *p;

	if ( (argc<=1) || (strcmp(argv[1],"--help")==0) ) {
		printf ( "\n" );
		printf ( "\n" );
		printf ( "Usage:\n" );
		printf ( "\n" );
		//          ----------- argv[0] -------argv[1]--
		printf ( "  swim WindowSize [Options] ImageName1 ImageName2\n" ); // Exactly 2 arguments after name and options
		printf ( "  swim WindowSize [Options] ImageName1 tarx tary ImageName2\n" ); // Exactly 4 arguments after name and options
		printf ( "  swim WindowSize [Options] ImageName1 tarx tary ImageName2 patx\n" ); // Exactly 5 arguments after name and options
		printf ( "  swim WindowSize [Options] ImageName1 tarx tary ImageName2 patx paty\n" ); // Exactly 6 arguments after name and options
		printf ( "  swim WindowSize [Options] ImageName1 tarx tary ImageName2 patx paty rota\n" ); // Exactly 7 arguments after name and options
		printf ( "  swim WindowSize [Options] ImageName1 tarx tary ImageName2 patx paty afm0 afm1 afm2 afm3\n" ); // Exactly 10 arguments after name and options
		printf ( "  swim WindowSize [Options] ImageName1 tarx tary ImageName2 mf00 mf01 mf02 mf10 mf11 mf12 -\n" ); // Exactly 11 arguments after name and options
		printf ( "  swim WindowSize [Options] ImageName1 tarx tary ImageName2 mf00 mf01 mf02 mf10 mf11 mf12 ??\n" ); // Exactly 12 arguments after name and options
		//          ----------- argv[0] -------argv[1]----2----3-------4-------5----6----7----8----9----10
		printf ( "\n" );
		printf ( " Where:\n" );
		printf ( "\n" );
		printf ( "  WindowSize: either # (x and y) or #x# (x by y, such as \"2048x1024\")\n" );
		printf ( "  Options:\n" );
		printf ( "    -x expr: addx = MUL*eval_expr(expr)\n" );
		printf ( "    -y expr: addy = MUL*eval_expr(expr)\n" );
		printf ( "    -m expr: MUL = eval_expr(expr)\n" );
		printf ( "    -i expr: niter = atoi(expr)\n" );
		printf ( "    -w expr: wht_expon = eval_expr(expr);  whiten = 1;  if(wht_expon == 0.0) whiten = 0;\n" );
		printf ( "    -A apodize = 0\n" );
		printf ( "    -V no_vert = 1\n" );
		printf ( "    -H no_hor = 1\n" );
		printf ( "    -r reverse = 1\n" );
		printf ( "    -k str: keepimg = str\n" );
		printf ( "    -t snrthr,xthr,ythr: set thresholds\n" );
		printf ( "    -$ debug_level\n" );
		exit(0);
	}

  // Search for the debug option to turn it on before anything else
  // Of course, this doesn't work properly here because stdin hasn't
  // been mapped to the arguments yet via the crazy mkargs function.
  for (i=0; i<argc; i++) {
    if (strcmp(argv[i],"-$")==0) {
      if (i<(argc-1)) {
        debug_level = atoi(argv[i+1]);
      }
    }
  }

	if (debug_level > 50) print_args ( "main:", argc, argv );

	gettimeofday(&tv, NULL);
	starts = tv.tv_sec;
	startu = tv.tv_usec;
	tstart = getticks();
	p = argv[1];
	if(argc < 2 || !isdigit(argv[1][0])) {
		fprintf(stderr, "%s requires FFT size\n", argv[0]);
		return(-1);
	}
	SIZEX = atoi(p);
	while(isdigit(*p)) {
		p++;
	}
	SIZEY = SIZEX;
	if(*p == 'x') {
		p++;
		SIZEY = atoi(p);
	}
	if(SIZEY >= 4 && SIZEY <= MSIZE) {
		argv++;
		argc--;
	} else {
		SIZEX = 128;
		SIZEY = 128;
	}

	if (debug_level > 50) print_args ( "main after sizing:", argc, argv );
	if (debug_level > 50) printf ( "    SIZEX=%d, sizeY=%d\n", SIZEX, SIZEY );

	epat = (float *)malloc(SIZEX*SIZEY*sizeof(float));
	targ = (float *)malloc(SIZEX*SIZEY*sizeof(float));
	winf = (float *)malloc(SIZEX*SIZEY*sizeof(float));
	fpat = (float *)malloc(SIZEX*SIZEY*sizeof(float));
	if(argc > 2) {
		oldmain(argc, argv); // oldmain is historical vestage!
		if (debug_level > 50) print_args ( "main after oldmain(argc,argv):", nargc, nargv );
	} else while(fgets(line, LLEN, stdin)) {
		if(line[0] == 0 || line[0] == '#' || line[0] == '\n') {
			//fprintf(stderr, "%s", line);
			continue;
		}
		//fprintf(stderr, "line -> <%s>\n", line);
		targs -= getticks();
		nargc = mkargs(nargv, line);
		targs += getticks();
		oldmain(nargc, nargv);
		if (debug_level > 50) print_args ( "main after oldmain(nargc,nargv):", nargc, nargv );
	}

	if (debug_level > 50) print_args ( "main after oldmain:", argc, argv );

	total_ticks = getticks() - tstart;
	gettimeofday(&tv, NULL);
#ifdef	VERB
	elapsed_sec = (tv.tv_sec-starts) + (tv.tv_usec - startu)/1000000.;
	fprintf(stderr, "elapsed_sec %g\n", elapsed_sec);
	fprintf(stderr, "tickrate %g\n", total_ticks/elapsed_sec);
	fprintf(stderr, "targs %12llu\n", targs);
	fprintf(stderr, "tinit %12llu\n", tinit);
	fprintf(stderr, "tread %12llu = %12llu + %12llu\n",
		tread0+tread1, tread0, tread1);
	fprintf(stderr, "tprep %12llu = %12llu + %12llu\n",
		tprep0+tprep1, tprep0, tprep1);
	fprintf(stderr, "tffts %12llu = %12llu + %12llu + %12llu\n",
		tfft0+tfft1+tfft2, tfft0, tfft1, tfft2);
	fprintf(stderr, "tmult %12llu\n", tmult);
	fprintf(stderr, "tpost %12llu\n", tpost);
	fprintf(stderr, "total %12llu\n", total_ticks);
	fprintf(stderr, "nread %d %d\n", nread0, nread1);
	fprintf(stderr, "nft %d %d ncalls %d\n", ntargft, npatft, ncalls);
	fprintf(stderr, "ticks/pixel %g\n",
		total_ticks/((double)ncalls*SIZEX*SIZEY));
	fprintf(stderr, "pixels %g\n", ncalls*(double)SIZEX*SIZEY);
	fprintf(stderr, "pixels/sec %g\n",
		ncalls*(double)SIZEX*SIZEY/elapsed_sec);
	fprintf(stderr, "\tpixels/sec %5.0f %dx%d = %d\n",
		Nrev*ncalls*(double)SIZEX*SIZEY/elapsed_sec, EW, EH, EW*EH);
	fprintf(stderr, "Nforw %d  Nrev %d  EW %d EH %d  %d\n",
		Nforw, Nrev, EW, EH, EW*EH);
#endif // VERB
	if (debug_level > 50) print_args ( "main before exit:", argc, argv );
	return(0);
}