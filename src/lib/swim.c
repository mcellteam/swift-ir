/*
 * swim.c — FFT-based image cross-correlation for serial-section alignment
 *
 * Computes translational offsets between pairs of microscopy images using
 * spectral (whitened) cross-correlation.  Supports optional affine transforms
 * (rotation, scale, shear) on the "pattern" patch and iterative refinement.
 *
 * Pipeline per image pair:
 *   1. Extract target patch from image 0 (centered at tarx,tary)
 *   2. Extract pattern patch from image 1 (centered at patx,paty) with
 *      optional affine warp via bilinear interpolation
 *   3. Apply Tukey/cosine window (apodization) to target; expand pattern
 *      to FFT size and scale both to [0,255]
 *   4. Forward FFT both patches (1-D r2c over the flattened 2-D array)
 *   5. Multiply spectra (conjugate of target * pattern) with spectral
 *      whitening: magnitude^wht_expon  (default -0.65; -1 = phase corr.)
 *   6. Inverse FFT → correlation surface
 *   7. Quadrant-flip to place zero-lag at center
 *   8. Locate best (darkest) match; compute sub-pixel offset via weighted
 *      cumulative distributions; update pattern position for next iteration
 *
 * Build:
 *   make -f makefile.linux
 *   (or: gcc -O3 -m64 -msse3 swim.c -ltiff -ljpeg -lpng -lfftw3f -lwebp -lm)
 *
 * Usage:
 *   ./swim <FFTsize> [flags] <img0> <x0> <y0> <img1> [<x1> <y1>] [affine...]
 *   ./swim <FFTsize> < batch_file.txt   (one command per line)
 */

// gcc -o swim -O3 -m64 -msse3 swim.c -ltiff -ljpeg -lpng -lfftw3f -lwebp -lm
// ./swim 800 -k keep.JPG -i 1 R34CA1-B_S12.112.pgm 2048 2048 R34CA1-B_S12.113.pgm 2000 2100  1
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
#include <math.h>
#include <sys/time.h>
#include "swimio.h"

#define	MSIZE 65536	// maximum FFT size (flattened 2-D)

/* --- Global FFT dimensions, set from command-line argument --- */
int SIZEX = 512, SIZEY = 480;
int fftw_mode = FFTW_ESTIMATE;	// FFTW_ESTIMATE (fast plan) or FFTW_MEASURE (optimal plan)

/* --- CPU cycle counter for internal profiling --- */
typedef	unsigned long long ticks;		// the cycle counter is 64 bits
static	__inline__ ticks getticks(void) {	// read CPU cycle counter via rdtsc
	unsigned a, d;
	a = 0;
	d = 0;
#ifndef ARM64
	asm volatile("rdtsc" : "=a" (a), "=d" (d));
#endif
	return ((ticks)a) | (((ticks)d) << 32);
}

/* Profiling tick accumulators for each pipeline stage */
ticks tstart, targs, tread0, tread1, total_ticks, tinit, tprep0, tprep1;
ticks tpost, tfft0, tfft1, tfft2, tmult;

/* Wall-clock timing */
struct timeval tv;
int starts, startu;
float elapsed_sec;
int loopquit, threshquit;

/* Per-iteration offset magnitude tracking, indexed by niter value */
#define	MAXITER	1000
float m0niter[MAXITER];       // sum of offset magnitudes for each niter setting
int m0nitercnt[MAXITER];      // count of samples for each niter setting

/* Best-match tracking across iterations and whitening sweeps */
float besta, bestz = 0, bestw, worst;  // best angle, z-score, whitening, worst z
float curra, currz, currw;             // current iteration angle, z, whitening
int bestx, besty, newbest, nbests = 0; // best match pixel coords, counters
float sumbestx = 0, sumbesty = 0, sum2bestx = 0, sum2besty = 0, sdvx, sdvy;
float fbestx, fbesty, uncert;          // sub-pixel best position + uncertainty
float snrthr = 0, xthr = 1000000, ythr = 1000000; // thresholds for affine reset
int areset = 0; // affine reset on failure of above

/* Verbosity and whitening controls */
int quiet = 1;         // 1 = suppress debug output
int whiten = 1;        // 0 = no whitening, 1 = apply wht_expon
double wht_expon = -0.65; // whitening exponent: 0=none, -1=phase, -0.5=fast sqrt

/* Statistics for target, pattern, and windowed patches */
float targavg, targvar, targsd; // target average, variance, standard deviation
float patavg, patvar, patsd;    // pattern average, variance, standard deviation
float winavg, winvar, winsd;    // windowed average, variance, standard deviation

/* Affine transform matrices: 2x2 "shape" part (rotation, scale, shear) */
float afm[4]; // current affine matrix [a00, a01, a10, a11]
float ofm[4]; // previous affine matrix (for change detection / FFT caching)

/*
 * mk_fpat — Extract a pattern patch from image with affine transform
 *
 * Reads pixels from 'im' centered at (xc,yc) into a PW×PH float buffer.
 * The affine transform is defined by the directional vectors:
 *   x-step: (xdx, xdy)  — how to move in source image per output x pixel
 *   y-step: (ydx, ydy)  — how to move in source image per output y pixel
 * This enables rotation, scaling, and shear via bilinear interpolation.
 *
 * Out-of-bounds pixels are marked with sentinel -1048576.0 (exact in float),
 * then replaced with the patch mean in a second pass.
 *
 * Computes patavg, patvar, patsd from valid pixels.
 *
 * @param im   Source image
 * @param xc   Center x in source coordinates
 * @param yc   Center y in source coordinates
 * @param xdx  Source dx per output x-step (cos(angle)*scale for rotation)
 * @param ydx  Source dy per output x-step (sin(angle)*scale for rotation)
 * @param xdy  Source dx per output y-step (-sin(angle)*scale for rotation)
 * @param ydy  Source dy per output y-step (cos(angle)*scale for rotation)
 * @param lut  Optional 256-entry lookup table (e.g. for inversion), or NULL
 * @param fpp  Output float buffer, size nx*ny
 * @param nx   Patch width
 * @param ny   Patch height
 */
void mk_fpat(struct image *im, double xc, double yc, double xdx, double ydx, double xdy, double ydy, int *lut, float *fpp, int nx, int ny) {
	int x, y, ix, iy, v0, v1, v2, v3, n = nx*ny;
	uchar *pp;
	float f0, f1, f2, f3, psum = 0, psum2 = 0, *ifpp = fpp;
if(!quiet)
fprintf(stderr, "im %p  del %d xy %g %g  %g %g  %g %g  lut %p  flt %p %d %d\n",
im, im->ydelta, xc, yc, xdx, ydx, xdy, ydy, lut, fpp, nx, ny);
if(!quiet)
fprintf(stderr, "AFFINE afm %g %g %g %g\n", afm[0], afm[1], afm[2], afm[3]);
	/* Convert center coords to upper-left origin by subtracting half-extents
	 * along both affine axes */
	f0 = (nx-1) * xdx/2;
	f1 = (nx-1) * xdy/2;
	f2 = (ny-1) * ydx/2;
	f3 = (ny-1) * ydy/2;
	xc -= f0;	// cvt from ctr coords to NW==UL origin
	yc -= f1;
	xc -= f2;
	yc -= f3;
	n = 0;	// count valid (in-bounds) pixels instead of assuming nx*ny
	for(y = 0; y < ny; y++) {
		for(x = 0; x < nx; x++, xc += xdx, yc += xdy) {
			float frx, fry, fv = 0;
			/* Truncate to integer for bilinear base pixel */
			ix = xc;
			iy = yc;
			/* Bounds check: need (ix,iy) and (ix+1,iy+1) in image */
			if(ix < 0 || iy < 0 || ix >= im->wid || iy >= im->ht || ix+1 >= im->wid || iy+1 >= im->ht) {
				*fpp++ = -1048576.0; // sentinel for OOB (exact float value)
				continue;
			}
			/* Read 2x2 neighborhood for bilinear interpolation */
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
			/* Fractional parts for bilinear weighting */
			frx = xc - ix;
			fry = yc - iy;
			fv = (1-fry)*((1-frx)*v0+frx*v1)
				+ fry*((1-frx)*v2+frx*v3);
			*fpp++ = fv;	// output to contiguous presized rect
			psum += fv;	// running sum for mean
			psum2 += fv*fv; // running sum-of-squares for variance
			n++;
		}
		/* Advance source position: undo accumulated x-steps, add one y-step */
		xc += ydx - nx * xdx;
		yc += ydy - nx * xdy;
	}
	/* Compute patch statistics from valid pixels */
	if(n > 0) {
		patavg = psum / n;
		patvar = n > 1 ? (psum2 - psum*psum/n) / (n-1) : 0;
		patsd = sqrt(patvar);
	} else {
		patavg = 0;
		patvar = 0;
		patsd = 0;
	}
	/* Second pass: replace OOB sentinels with patch mean */
	if(n != nx*ny) {
		for(y = 0; y < ny; y++) for(x = 0; x < nx; x++, ifpp++) {
			if(*ifpp == -1048576.0)
				*ifpp = patavg;
		}
	}
}

/*
 * mk_ftarg — Extract a target patch from image (axis-aligned, no transform)
 *
 * Copies an nx×ny rectangle from 'im' starting at corner (xc,yc) into
 * float buffer 'fpp'.  Out-of-bounds rows/columns are filled with the
 * computed mean of the valid region.
 *
 * Computes targavg, targvar, targsd from valid pixels.
 *
 * @param im   Source image
 * @param xc   Left-edge x coordinate (upper-left corner of patch)
 * @param yc   Top-edge y coordinate
 * @param fpp  Output float buffer, size nx*ny
 * @param nx   Patch width
 * @param ny   Patch height
 */
void mk_ftarg(struct image *im, int xc, int yc, float *fpp, int nx, int ny) {
	int x, y, ix, iy, v0, v1, v2, v3, n = nx*ny;
	uchar *pp;
	float fv = 0, psum = 0, psum2 = 0;
if(!quiet)
fprintf(stderr, "im %p  %d x %d del %d cornerxy %d %d flt %p %d %d\n",
im, im->wid, im->ht, im->ydelta, xc, yc, fpp, nx, ny);
	n = 0; // replace nx*ny by count to handle off edge cases
if(!quiet)
fprintf(stderr, "**** xc %d  yc %d\n", xc, yc);
	/* First pass: copy pixels, accumulate statistics */
	for(y = 0; y < ny; y++, yc++, fpp += nx) {
		if(yc < 0 || yc >= im->ht)
			continue;  // skip rows outside image vertically
		pp = &im->pp[yc*im->ydelta + xc];
		for(x = 0; x < nx; x++, xc++) {
#define	CLIPLEFT 0 // Davi's camera left edge 20 ... XXX cond check for blk cols
			if(xc < CLIPLEFT || xc >= im->wid) // skip columns outside image
{
fpp[x] = 0; // XXX AWW
				continue;
}
			fv = pp[x];
			fpp[x] = fv;
			psum += fv;	// running sum for mean
			psum2 += fv*fv; // running sum-of-squares for variance
			n++;
		}
		xc -= nx;  // reset xc for next row
	}
	/* Compute target patch statistics */
	if(n > 0) {
		targavg = psum / n;
		targvar = n > 1 ? (psum2 - psum*psum/n) / (n-1) : 0;
		targsd = sqrt(targvar);
	} else {
		targavg = 0;
		targvar = 0;
		targsd = 0;
	}
	/* Second pass: fill OOB regions with patch mean */
	fpp -= ny*nx;  // rewind pointer to start of buffer
	yc -= ny;
	fv = targavg;
if(!quiet)
fprintf(stderr, "restart yc %d fpp %p  fv %g\n", yc, fpp, fv);
	for(y = 0; y < ny; y++, yc++, fpp += nx) {
		if(yc < 0 || yc >= im->ht) {
			/* Fill entire out-of-bounds row with mean */
			for(x = 0; x < nx; x++)
				fpp[x] = fv;
		} else { // fill left/right OOB columns with mean
			for(x = 0; fpp[x] == 0 && x < nx; x++)
				fpp[x] = fv;
			for(x = nx-1; fpp[x] == 0 && x > 0; x--)
				fpp[x] = fv;
		}
	}
if(!quiet)
fprintf(stderr, "ftarg stats  av %g  va %g  sd %g  n %d\n", targavg, targvar, targsd, n);
}

/*
 * scalepat — Normalize a float array to [0, 255]
 *
 * Linearly maps (min → 0, max → 255).  If all values are equal (fmax == fmin),
 * zeroes the entire buffer to avoid division by zero.
 *
 * @param pat  Float buffer to normalize in-place
 * @param nx   Width
 * @param ny   Height
 */
void scalepat(float *pat, int nx, int ny) {
	float *fp, fmin = 1e20, fmax = -1e20;
	int x, y, xmax, ymax, xmin, ymin;
	/* Find min and max values */
	for(y = 0, fp = pat; y < ny; y++, fp += nx)
		for(x = 0; x < nx; x++) {
			if(fp[x] > fmax) {
				fmax = fp[x];
				xmax = x;
				ymax = y;
			} else if(fp[x] < fmin) {
				fmin = fp[x];
				xmin = x;
				ymin = y;
			}
		}
	/* Normalize to [0,255] or zero-fill if constant */
	if(fmax == fmin) {
		for(y = 0, fp = pat; y < ny; y++, fp += nx)
			for(x = 0; x < nx; x++)
				fp[x] = 0;
	} else {
		for(y = 0, fp = pat; y < ny; y++, fp += nx)
			for(x = 0; x < nx; x++)
				fp[x] = 255*(fp[x] - fmin)/(fmax - fmin);
	}
}

/*
 * qflip — Quadrant-flip the correlation surface
 *
 * Rearranges the output of the inverse FFT so that zero-lag (DC) is at the
 * center of the array instead of the corners.  This is equivalent to
 * fftshift in MATLAB.  The two steps are:
 *   1. Swap left and right halves of each row
 *   2. Swap top and bottom halves of each column
 * A final fixup pass corrects for the 1-D FFT layout (data is stored as
 * a single contiguous 1-D transform of the flattened 2-D array).
 *
 * @param pat  Float buffer (EW × EH) to flip in-place
 * @param nx   Width (EW)
 * @param ny   Height (EH)
 */
void qflip(float *pat, int nx, int ny) {
	float *fp, *fp2, t;
	int x, y;
	/* Step 1: swap left/right halves of each row */
	for(y = 0, fp = pat; y < ny; y++, fp += nx)
		for(x = 0; x < nx/2; x++) {
			t = fp[x];
			fp[x] = fp[x+(nx+1)/2];
			fp[x+(nx+1)/2] = t;
		}
	/* Step 2: swap top/bottom halves */
	for(y = 0, fp = pat; y < ny/2; y++, fp += nx) {
		fp2 = fp + (ny+1)/2 * nx;
		for(x = 0; x < nx; x++) {
			t = fp[x];
			fp[x] = fp2[x];
			fp2[x] = t;
		}
	}
	/* Step 3: fixup for 1-D FFT layout — shift right half of each row
	 * up by one row to compensate for the way 1-D FFT wraps 2-D data */
	for(y = ny-1; y > 0; y--) {
		fp = pat + y*nx;
		for(x = 0; x < nx/2; x++)
			fp[x] = fp[x-nx];
	}
}

/*
 * cpfout — Copy float array to an image struct (for PNG/PGM output)
 *
 * Truncates float values to unsigned char and writes them into the
 * image pixel buffer at offset (xo, yo).  Used to save debug images
 * (pattern, target, correlation surface).
 *
 * @param pat  Source float buffer
 * @param nx   Width of float buffer
 * @param ny   Height of float buffer
 * @param im   Destination image struct
 * @param xo   X offset in destination
 * @param yo   Y offset in destination
 */
void cpfout(float *pat, int nx, int ny, struct image *im, int xo, int yo) {
	int x, y;
	unsigned char *cp = im->pp;
	cp += yo*im->ydelta + xo;
	for(y = 0; y < ny; y++, pat += nx, cp += im->ydelta)
		for(x = 0; x < nx; x++)
			cp[x] = pat[x];
}

/*
 * expand — Copy a smaller patch into a larger buffer, padding with 'pad'
 *
 * Copies the ix×iy input into the upper-left corner of the ox×oy output,
 * and fills the remaining pixels with 'pad' (typically the windowed mean).
 * This zero/mean-pads the pattern up to the FFT size before transform.
 *
 * @param ip   Input float buffer (ix × iy)
 * @param ix   Input width
 * @param iy   Input height
 * @param op   Output float buffer (ox × oy)
 * @param ox   Output width (FFT size X)
 * @param oy   Output height (FFT size Y)
 * @param pad  Fill value for the padding region
 */
void expand(float *ip, int ix, int iy, float *op, int ox, int oy, float pad) {
	int x, y;
	for(y = 0; y < iy; y++, ip += ix, op += ox) {
		/* Copy input row */
		for(x = 0; x < ix; x++)
			op[x] = ip[x];
		/* Pad remaining columns */
		for( ; x < ox; x++)
			op[x] = pad;
	}
	/* Pad remaining rows entirely */
	for( ; y < oy; y++, op += ox)
		for(x = 0; x < ox; x++)
			op[x] = pad;
}

/*
 * mk_winf — Build a 2-D Tukey (tapered cosine) apodization window
 *
 * Creates a separable window that is 1.0 in the central 80% and
 * cosine-tapers to 0 over the outer 20% of each axis.  This reduces
 * spectral leakage from sharp patch boundaries in the FFT.
 *
 * The window function per axis is:
 *   |d| <= 0.8:  w = 1.0
 *   |d| >  0.8:  w = 0.5 + 0.5 * cos(5π(|d| - 0.8))
 * where d = normalized distance from center (-1 to +1).
 *
 * @param winf  Output float buffer (nx × ny)
 * @param nx    Window width
 * @param ny    Window height
 */
void mk_winf(float *winf, int nx, int ny) {
	int x, y;
	float dx, dy, r, rad;
	rad = nx/2;
	if(ny < nx)
		rad = ny/2;
	rad *= 1.05; // extend slightly so edges aren't truly 0
	rad /= M_PI/2;
if(!quiet)
fprintf(stderr, "mk_winf %d %d rad %g\n", nx, ny, rad);
	for(y = 0; y < ny; y++, winf += nx) {
		/* Vertical taper: normalized distance from center */
		dy = fabs(y - ny/2.)/(ny/2);
		if(dy > .8)
			dy = .5 + cos(5*M_PI*(dy-.8))/2;  // cosine taper
		else
			dy = 1;  // flat region
		for(x = 0; x < nx; x++) {
			/* Horizontal taper: same formula */
			dx = fabs(x - nx/2.)/(nx/2);
			if(dx > .8)
				dx = .5 + cos(5*M_PI*(dx-.8))/2;
			else
				dx = 1;
			winf[x] = dy*dx;  // separable product
		}
	}
}

/*
 * use_winf — Apply apodization window and subtract weighted mean
 *
 * Multiplies each pixel by the window weight, subtracts the weighted mean
 * (to center data around zero), then stores the result.  This prepares
 * the target patch for correlation: apodized + zero-mean.
 *
 * Computes winavg, winvar, winsd for the windowed data.
 *
 * @param winf  Apodization window (nx × ny)
 * @param pat   Patch to window in-place (nx × ny)
 * @param nx    Width
 * @param ny    Height
 */
void use_winf(float *winf, float *pat, int nx, int ny) {
	int x, y, n = nx * ny;
	float *pp, *wp, en = 0, fsum = 0, fv, wsum = 0, wsum2 = 0;
	/* First pass: compute weighted sum and effective N */
	for(y = 0, pp = pat, wp = winf; y < ny; y++, pp += nx, wp += nx)
		for(x = 0; x < nx; x++) {
			fsum += pp[x] * wp[x];  // weighted pixel sum
			en += wp[x];             // effective N (sum of weights)
		}
	fsum /= en;  // weighted mean
	/* Second pass: subtract mean, apply window, accumulate windowed stats */
	for(y = 0, pp = pat, wp = winf; y < ny; y++, pp += nx, wp += nx)
		for(x = 0; x < nx; x++) {
			fv = (pp[x] - fsum) * wp[x];  // mean-subtract then taper
			wsum += fv;
			wsum2 += fv*fv;
			pp[x] = fv;
		}
	winavg = wsum / n;
	winvar = (wsum2 - wsum*wsum/n) / (n-1);
	winsd = sqrt(winvar);
if(!quiet)
fprintf(stderr, "win stats  av %g  va %g  sd %g  n %d\n", winavg, winvar, winsd, n);
}

/* --- Correlation surface statistics (set by stats()) --- */
float stat_avg, stat_var, stat_sd, stat_min, stat_max, stat_maxz, stat_minz;
int stat_n, stat_minx, stat_miny, stat_maxx, stat_maxy;

/* --- Persistent state across batch calls --- */
int fixedpattern;       // >0 if the fixed-pattern peak should be suppressed
int PW, PH;             // pattern patch dimensions (= SIZEX, SIZEY)
float *fpat;            // pattern patch float buffer
float *winf;		// apodization window buffer (Apr 2012)
float *epat;            // expanded pattern (padded to FFT size)
float *targ;            // target patch float buffer
int EW, EH;             // expanded/FFT dimensions (= SIZEX, SIZEY)
int RW, RH;             // result dimensions (= SIZEX, SIZEY)
struct image *im0, *im1, *io, *eo, *ro;  // source images + output image structs
char *fname0 = "target.pgm";   // target image filename
char lastf0[1000];              // cached target filename (avoid re-reading)
char *fname1 = "pattern.pgm";  // pattern image filename
char lastf1[1000];              // cached pattern filename
int ndone;		// number of sets processed — triggers first-time init
char oname[100];
int revlut[256];        // reverse LUT: revlut[i] = 255 - i
float tarx, tary, patx, paty, startpatx, startpaty;  // current positions
float oldtarx = -10000, oldtary = -10000;             // previous positions (for caching)
float oldpatx = -10000, oldpaty = -10000, oldpata = -10000;
int ntargft, npatft, ncalls;  // FFT and call counters
int nread0, nread1;           // image read counters

/* Scratch arrays for find_xyoff: horizontal/vertical projections and CDF */
float fha[MSIZE];      // horizontal projection (weighted)
float fhca[MSIZE];     // horizontal cumulative distribution
float fva[MSIZE];      // vertical projection (weighted)
float fvca[MSIZE];     // vertical cumulative distribution

/*
 * stats — Compute statistics of the correlation surface and track best match
 *
 * Scans the correlation surface to find min/max, compute mean, variance,
 * and z-scores.  The minimum (darkest point) represents the best match
 * because the correlation is negated (dark = high correlation).
 *
 * If fixedpattern is set, suppresses the expected peak location (from the
 * previous known offset) to find the next-best match — useful when the
 * same pattern appears at a known position due to repeat imaging.
 *
 * Updates global best-match variables (bestz, bestx, besty) if this
 * iteration's z-score exceeds the previous best.
 *
 * @param ifp  Correlation surface buffer (nx × ny)
 * @param nx   Width
 * @param ny   Height
 */
void stats(float *ifp, int nx, int ny) {
	double sum = 0, sum2 = 0, zscore;
	int x, y, stat_n = nx * ny;
	int nfixed = 0;
	float *fp;
again:
	fp = ifp; // reset to start of buffer
	sum = 0;
	sum2 = 0;
	stat_min = 1e20;
	stat_max = -1e20;
	/* Find min, max, mean, variance over entire surface */
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
	stat_maxz = stat_max - stat_avg;
	stat_minz = stat_min - stat_avg;
	/* Suppress fixed-pattern peak: replace the known peak location with mean,
	 * then re-scan to find the true best match */
	if(fixedpattern && nfixed == 0) {
		int dx, dy, x, y;;
		float *mp = ifp + nx*ny/2 + nx/2 + 0;
		dx = ((int)(patx-tarx+nx/2+.5)) - nx/2;
		dy = ((int)(paty-tary+ny/2+.5)) - ny/2;
fprintf(stderr, "supress fixed peak dxy %d %d\n", dx, dy);
		mp += dy*nx + dx;
		#define	D 1
		for(y = -D; y <= D; y++) for(x = -D; x <= D; x++)
			*(mp + y*nx + x) = stat_avg;
		if(nfixed++ == 0)
			goto again;  // re-compute stats after suppression
	}
	/* Z-score of the minimum (best match): how many SDs below mean */
	zscore = -stat_minz/stat_sd;
	newbest = 0;
	/* Update best-match if this is the best z-score so far */
	if(zscore > bestz) {
if(!quiet)
fprintf(stderr, "newbest %g vs %g a %g w %g xy %d %d\n",
zscore, bestz, curra, wht_expon, stat_minx, stat_miny);
		besta = curra;
		bestz = zscore;
		worst = stat_maxz/stat_sd;
		bestw = wht_expon;
		bestx = stat_minx;
		besty = stat_miny;
		newbest = 1;
		/* Accumulate for running mean/variance of best positions */
		sumbestx += bestx;
		sumbesty += besty;
		sum2bestx += bestx*bestx;
		sum2besty += besty*besty;
		nbests++;
	} else {
		float zdiff = bestz-zscore;
if(!quiet || zdiff > 1.5)
fprintf(stderr, "%s %g %g GOTWORSE by %g:  %g vs %g a %g xy %d %d\n",
fname0, tarx, tary, zdiff, zscore, bestz, curra, stat_minx, stat_miny);
	}
}

/*
 * find_xyoff — Estimate sub-pixel match offset from the correlation image
 *
 * Analyzes the correlation surface (as a grayscale image) to determine the
 * sub-pixel location of the best match.  The algorithm:
 *
 *   1. Compute image statistics (mean, SD)
 *   2. For each pixel darker than mean (potential match), compute a weight
 *      w = exp(z_score / 10) where z_score = (mean - pixel) / SD
 *   3. Accumulate horizontal and vertical weighted projections
 *   4. Build cumulative distribution functions (CDFs) for both axes
 *   5. Find the median (50th percentile) of each CDF → integer match
 *   6. Interpolate between neighboring CDF values → sub-pixel fraction
 *   7. Find 2nd and 98th percentile spread → uncertainty estimate
 *
 * Sets globals: fbestx, fbesty (sub-pixel position), uncert (uncertainty)
 *
 * @param ip   Correlation surface as unsigned char (from cpfout)
 * @param wid  Width
 * @param ht   Height
 * @return     Uncertainty metric (sqrt of sum-of-squares of x/y spreads)
 */
float find_xyoff(unsigned char *ip, int wid, int ht) {
	int i, n = 0, v, x, y;
	int xmin, xmax, ymin, ymax, minv = 256, maxv = -1, matchx = 0, matchy = 0;
	int firstx, lastx, firsty, lasty, x10, x90 = 0, y10, y90 = 0, ux, uy;
	unsigned char *cp;
	float f, *fh, *fv, *fhc, *fvc, frh, frv;
	double av, sd, sum=0, sumsq=0, var, halfeh, halfev, h10, h90, v10, v90;
	float sdt[256], bestsd, worstsd;
	firstx = firsty = -1;
	lastx = lasty = 1000000;
	n = ht * wid;
	/* Use pre-allocated static arrays (fha, fhca, fva, fvca) instead of
	 * malloc to avoid per-call allocation overhead */
	fh = fha;
	fhc = fhca;
	fv = fva;
	fvc = fvca;
	/* Zero the projection arrays */
	for(x = 0; x < wid; x++)
		fh[x] = 0;
	for(y = 0; y < ht; y++)
		fv[y] = 0;
	/* First pass: basic image statistics (mean, SD, min, max) */
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
	av = sum/n;
	var = (sumsq - sum*sum/n) / (n-1);
	sd = sqrt(var);
	worstsd = (maxv-av)/sd;  // z-score of brightest pixel
	bestsd = (av-minv)/sd;   // z-score of darkest pixel (best match)

	/* Second pass: build weighted projections for dark (matching) pixels
	 * Only pixels with z-score > bestsd/2 contribute */
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
			v = (av - v);  // flip: dark becomes positive
			if(v > 0) {
				f = v/sd;   // z-score
#define	ETHR (bestsd/2)
if(f < ETHR) continue;  // threshold: only significant matches
			f = exp(f/10.); // soft weight via exponential
				if(f > 0) {
					fh[x] += f;   // accumulate horizontal projection
					fv[y] += f;   // accumulate vertical projection
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

/* Build cumulative distribution functions from projections */
for(x = 0; x < wid; x++)  {
	fhc[x] += fh[x];
	if(x > 0) {
		fhc[x] += fhc[x-1];  // running sum = CDF
		halfeh = fhc[x];     // total will be final value
	}
	}
	for(y = 0; y < ht; y++) {
		fvc[y] += fv[y];
		if(y > 0) {
			fvc[y] += fvc[y-1];
			halfev = fvc[y];
		}
	}
	/* If no significant match signal, return huge uncertainty */
	if(halfeh < 1 || halfev < 1)
		return(1000000);
	/* Percentile thresholds for the CDF */
	h10 = .02*halfeh;   // 2nd percentile horizontal
	h90 = .98*halfeh;   // 98th percentile horizontal
	v10 = .02*halfev;   // 2nd percentile vertical
	v90 = .98*halfev;   // 98th percentile vertical
	halfeh /= 2;        // 50th percentile (median) thresholds
	halfev /= 2;
if(!quiet)
fprintf(stderr, "half %g %g\n", halfeh, halfev);
	/* Find integer positions where CDF crosses median and percentiles */
	x10 = y10 = 0;
	for(x = 0; x < wid; x++) {
		if(fhc[x] < halfeh)
			matchx = x;     // last x before median crossing
		if(fhc[x] < h10)
			x10 = x;        // 2nd percentile boundary
		if(fhc[x] < h90)
			x90 = x;        // 98th percentile boundary
	}
	for(y = 0; y < ht; y++) {
		if(fvc[y] < halfev)
			matchy = y;
		if(fvc[y] < v10)
	 		y10 = y;
		if(fvc[y] < v90)
	 		y90 = y;
	}
if(!quiet) {
fprintf(stderr, "matchxy %d %d\n", matchx, matchy);
fprintf(stderr, "  h (%g - %g) / (%g - %g)\n", halfeh, fhc[matchx], fhc[matchx+1], fhc[matchx]);
fprintf(stderr, "  v (%g - %g) / (%g - %g)\n", halfev, fvc[matchy], fvc[matchy+1], fvc[matchy]);
fprintf(stderr, "   at 1   %g %g\n", fhc[matchx+1], fvc[matchy+1]);
}
	/* Clamp to valid interpolation range [1, size-2] to avoid OOB access */
	if(matchx < 1) matchx = 1;
	if(matchx >= wid-1) matchx = wid-2;
	if(matchy < 1) matchy = 1;
	if(matchy >= ht-1) matchy = ht-2;
	/* Sub-pixel interpolation using CDF neighbors (linear interpolation
	 * of where the median falls between the two bracketing CDF values) */
	frh = (fhc[matchx+1] - fhc[matchx-1]) != 0 ?
		(halfeh - fhc[matchx]) / (fhc[matchx+1] - fhc[matchx-1]) : 0;
	frv = (fvc[matchy+1] - fvc[matchy-1]) != 0 ?
		(halfev - fvc[matchy]) / (fvc[matchy+1] - fvc[matchy-1]) : 0;
matchx++;
matchy++;	// bump by one to align with actual peak position
frh -= 0.5;
frv -= 0.5;	// account for 0-lag position being at SIZE/2
if(!quiet)
fprintf(stderr, "frac %g %g\n", frh, frv);
	/* Final sub-pixel match position */
	fbestx = matchx+frh;
	fbesty = matchy+frv;
	/* Uncertainty = distance between 2nd and 98th percentile bounds */
	ux = x90 - x10;
	uy = y90 - y10;
if(!quiet) {
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

/*
 * color2byte — Convert 3-channel RGB image to single-channel grayscale
 *
 * Uses perceptual weighting: gray = (4*G + 2*R + B) / 7.0
 * Converts in-place (output overwrites input) and reallocs to save memory.
 *
 * @param im  Image to convert (bpp changes from 3 to 1)
 */
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

/*
 * short2byte — Convert 16-bit image to 8-bit by linear scaling
 *
 * Finds min/max of 16-bit data, then linearly maps to [0, 255].
 * Converts in-place and reallocs to save memory.
 *
 * @param im  Image to convert (bpp changes from 2 to 1)
 */
void short2byte(struct image *im) {
	int i, n, min = 1000000, max = 0, v, sum = 0;
	unsigned short *sp = (unsigned short *)im->pp;
	unsigned char *cp = im->pp;
	float m;
	n = im->wid*im->ht;
	/* First pass: find min, max, sum */
	for(i = 0; i < n; i++) {
		v = sp[i];
		sum += v;
		if(v > max)
			max = v;
		else if(v < min)
			min = v;
	}
	m = 255./(max - min);  // scale factor
fprintf(stderr, "short2byte  %d %g %d  %g\n", min, sum/(float)n, max, m);
	/* Second pass: apply linear mapping */
	for(i = 0; i < n; i++)
		cp[i] = m*(sp[i] - min);
	im->pp = realloc(im->pp, n);
	im->bpp = 1;
}

/*
 * eval_expr — Simple recursive-descent arithmetic expression evaluator
 *
 * Parses and evaluates arithmetic expressions from strings, supporting:
 *   - Numbers (integer and floating point, with optional exponent)
 *   - Operators: +, -, *, /, ^ (power)
 *   - Parentheses for grouping
 *   - Unary minus
 *   - Standard operator precedence
 *
 * Used to parse coordinate and affine values from command-line arguments,
 * allowing expressions like "1216.0" or simple arithmetic.
 *
 * @param s  Null-terminated string containing the expression
 * @return   Evaluated result as double
 */
#define	STSIZE	15
static int pstack[STSIZE];     // operator stack
static double vstack[STSIZE];  // value stack
static int sp, prec[256];      // stack pointer and operator precedence table

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

/* Reduce back to matching '(' — evaluate all pending ops within parens */
void reducepar() {
	while(pstack[sp-2] != '(')
		doop(pstack[sp-2]);
	sp--;					/* account for the ( slot */
	vstack[sp-1] = vstack[sp];		/* move the value down one */
}

double eval_expr(char *s) {
	char *p = s;
	int i, unary = 1;
	/* Initialize precedence table on first call */
	if(prec['+'] == 0) {
		prec['='] = 1;
		prec['+'] = prec['-'] = 2;
		prec['*'] = prec['/'] = 3;
		prec['^'] = 4;
	}
	sp = 0;
	pstack[sp++] = '(';	/* preinsert ( as sentinel */
	for( ; ; ) {
		char c = *p++;
		if(isdigit(c) || c == '.') {
			pstack[sp] = '#';	/* mark as number */
			if(c != '.') {
				vstack[sp] = c - '0';	/* initial digit */
				while(isdigit(*p)) {
					vstack[sp] *= 10;
					vstack[sp] += *p - '0';
					p++;
				}
			} else {
				vstack[sp] = 0.;
				p--;
			}
			/* Parse fractional part */
			if(*p == '.') {
				double fr = 1.;
				p++;
				while(isdigit(*p)) {
					fr *= .1;
					vstack[sp] += fr * (*p - '0');
					p++;
				}
			}
			/* Parse exponent (e.g. 1.5e-3) */
			if(*p == 'e' || *p == 'E') {
				int esign = 1, expo = 0;
fprintf(stderr, "EXP\n");
				p++;
				if(*p == '-' || *p == '+') {
					if(*p == '-')
						esign = -1;
					p++;
				}
				while(isdigit(*p))
					expo = expo*10 + *p++ - '0';
fprintf(stderr, "%d %d\n", esign, expo);
				vstack[sp] *= pow(10., (float)(esign*expo));
			}
			/* Apply unary minus if present */
			if(unary < 1)
				vstack[sp] = -vstack[sp];
			sp++;
			unary = 1;
		} else if(c == '(')
			pstack[sp++] = '(';
		else if(c == ')' || (c == 0 && sp > 1))
			reducepar();
		else if(prec[c] == 2 && pstack[sp-1] == '(') {
			if(c == '-')
				unary = -unary;
		} else if(prec[c] == 2 && prec[pstack[sp-1]]) {
			if(c == '-')
				unary = -unary;
		} else if(prec[c]) {	/* it's an operator */
			if(sp > 3)		/* evaluate higher-precedence stacked ops */
				if(prec[pstack[sp-2]] >= prec[c])
					doop(pstack[sp-2]);
			pstack[sp++] = c;	/* push new operator */
			c = *p;
			if(c == '-') {
				unary = -unary;
				p++;
			}
			if(c == '+')
				p++;
		}
		if(c == 0) {
			if(sp != 1)
				fprintf(stderr, "Error - sp was %d\n", sp);
			return(vstack[0]);
		}
	}
}

/*
 * fastPow — Fast approximate power function using IEEE 754 bit manipulation
 *
 * Exploits the logarithmic structure of IEEE 754 double-precision floats:
 * the exponent bits encode log2(value), so linear operations on the
 * exponent field approximate pow(a, b).  Accuracy is ~5-10% but vastly
 * faster than libm pow().  Used in the spectral whitening loop where
 * exact values are not critical.
 *
 * @param a  Base (must be positive)
 * @param b  Exponent
 * @return   Approximate a^b
 */
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

/* Forward and inverse 2×3 affine matrices (rotation+scale+translation) */
float mf[2][3] = {1, 0, 0, 0, 1, 0};	// forward affine
float mi[2][3] = {1, 0, 0, 0, 1, 0};	// inverse affine

/*
 * affine_inverse — Compute the inverse of a 2×3 affine matrix
 *
 * Given forward matrix [a b tx; c d ty], computes the inverse using
 * the determinant: det = a*d - b*c.  The inverse maps transformed
 * coordinates back to original coordinates.
 *
 * @param mi  Output 2×3 inverse matrix (flat array of 6 floats)
 * @param mf  Input 2×3 forward matrix (flat array of 6 floats)
 */
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

/* Optional output image filenames (set by -k, -b, -t flags) */
char *keepimg, *bestimg, *targimg;

/* FFTW buffers and plans */
fftwf_complex *fft_result0, *fft_result1, *fft_comb;  // frequency-domain buffers
fftwf_plan forward_plan0, backward_plan;                // FFTW plan handles
int Nforw, Nrev;                                        // forward/reverse FFT counters
float *ifft_comb;                                       // inverse FFT output (correlation surface)

/*
 * oldmain — Core correlation engine for one image pair
 *
 * Processes one set of command-line arguments to correlate a target region
 * in image 0 with a pattern region in image 1.  Supports multiple iterations
 * (-i flag) that refine the pattern position based on correlation results.
 *
 * This function is called once per command line in batch mode, or once for
 * direct command-line invocation.  The name "oldmain" is a historical
 * artifact from when this was the original main().
 *
 * Key flags parsed:
 *   -i N       Number of refinement iterations
 *   -w E       Whitening exponent (default -0.65; -1 = phase correlation)
 *   -k file    Save pattern patch image
 *   -b file    Save best correlation surface image
 *   -t file    Save target patch image
 *   -f[N]      Enable fixed-pattern suppression (N times)
 *   -r         Reverse (invert) target image
 *   -v         Verbose output
 *   -A         Disable apodization
 *   -V/-H      Suppress vertical/horizontal offset components
 *   -T s,x[,y] SNR and offset thresholds for affine reset
 *   -d dir     Change working directory
 *   -x/-y val  Add offset to coordinates
 *   -m val     Coordinate multiplier
 *
 * @param argc  Argument count (as if from command line)
 * @param argv  Argument vector
 * @return      0 on success, -1 on failure
 */
int oldmain(int argc, char *argv[]) {
	float *fp, a, addx = 0, addy = 0, MUL = 1.0;
	float rota = 0, mag = 1, ntarx, ntary, npatx, npaty, deltx, delty;
	float rng_up, rng_dn, rng_lft, rng_rt;
	double fdx, fdy;
	double tdx, tdy;
	int i, ia, x, y, size;
	int niter = 1, reverse = 0, no_vert = 0, no_hor = 0, apodize = 1;
	char *cp;
	float m0, m1;
targs -= getticks();
	ncalls++;
	fixedpattern = 0;  // reset between batch calls
	patx = -1000000;
	paty = -1000000;
	tarx = -1000000;
	tary = -1000000;

	/* --- Parse flags --- */
	while(argc > 1 && *argv[1] == '-') {
		char flag = argv[1][1];
		if(flag == 'd' && argc > 2) {       // -d dir: change directory
			if(chdir(argv[2]))
				fprintf(stderr, "FAILED: chdir %s\n", argv[2]);
			argc--;
			argv++;
		} else if(flag == 'x' && argc > 2) { // -x val: x offset
			addx = MUL*eval_expr(argv[2]);
			argc--;
			argv++;
		} else if(flag == 'y' && argc > 2) { // -y val: y offset
			addy = MUL*eval_expr(argv[2]);
			argc--;
			argv++;
		} else if(flag == 'm' && argc > 2) { // -m val: multiplier
			MUL = eval_expr(argv[2]);
			argc--;
			argv++;
		} else if(flag == 'i' && argc > 2) { // -i N: iteration count
			niter = atoi(argv[2]);
			if(niter >= MAXITER) niter = MAXITER - 1;  // clamp to valid range
			argc--;
			argv++;
		} else if(flag == 'w' && argc > 2) { // -w E: whitening exponent
			wht_expon = eval_expr(argv[2]);
			whiten = 1;
			if(wht_expon == 0.0)
				whiten = 0;
			argc--;
			argv++;
		} else if(flag == 'T' && argc > 2) { // -T s,x[,y]: thresholds
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
		} else if(flag == 'f')               // -f[N]: fixed-pattern suppression
			fixedpattern++;
		else if(flag == 'v')
			quiet = 0;                   // -v: verbose
		else if(flag == 'A')
			apodize = 0;                 // -A: disable apodization
		else if(flag == 'V')
			no_vert = 1;                 // -V: suppress vertical offset
		else if(flag == 'H')
			no_hor = 1;                  // -H: suppress horizontal offset
		else if(flag == 'r')
			reverse = 1;                 // -r: invert target image
 		else if(flag == 'k' && argc > 2) { // -k file: save pattern patch
 			keepimg = argv[2];
			argc--;
			argv++;
		} else if(flag == 'b' && argc > 2) { // -b file: save correlation surface
 			bestimg = argv[2];
			argc--;
			argv++;
		} else if(flag == 't' && argc > 2) { // -t file: save target patch
 			targimg = argv[2];
			argc--;
			argv++;
		}
		argc--;
		argv++;
	}

	/* --- Parse positional arguments: filenames and coordinates --- */
	afm[0] = 1;  // initialize affine to identity
	afm[1] = 0;
	afm[2] = 0;
	afm[3] = 1;
	fname0 = argv[1];  // target image filename
	if(argc == 3) {
		/* Simple mode: just two filenames, use image center */
		fname1 = argv[2];
	} else {
		/* Full mode: filename x y filename [x y] [affine...] */
		tarx = eval_expr(argv[2]);
		tary = eval_expr(argv[3]);
		fname1 = argv[4];
		patx = tarx;  // default pattern position = target position
		paty = tary;
		if(argc > 5)
			patx = eval_expr(argv[5]);
		if(argc > 6)
			paty = eval_expr(argv[6]);
		if(argc == 8 || argc == 9) {
			/* argc 8: rotation angle only; argc 9: rotation + magnitude */
			rota = eval_expr(argv[7]);
			a = rota*M_PI/180;
			afm[0] = cos(a);
			afm[1] = sin(a);
			afm[2] = -sin(a);
			afm[3] = cos(a);
			if(argc == 9) {
				mag = eval_expr(argv[8]);
				afm[0] *= mag;
				afm[1] *= mag;
				afm[2] *= mag;
				afm[3] *= mag;
rota = 1024;  // magic value to signal explicit affine mode
			}
		} else if(argc == 11) {
			/* Explicit 2×2 affine matrix as 4 values */
			rota = 1024;
			afm[0] = eval_expr(argv[7]);
			afm[1] = eval_expr(argv[8]);
			afm[2] = eval_expr(argv[9]);
			afm[3] = eval_expr(argv[10]);
		} else if(argc == 12) {
			/* Full 2×3 affine: compute pattern position from forward/inverse */
			rota = 1024;
			mf[0][0] = eval_expr(argv[5]);
			mf[0][1] = eval_expr(argv[6]);
			mf[0][2] = eval_expr(argv[7]);
			mf[1][0] = eval_expr(argv[8]);
			mf[1][1] = eval_expr(argv[9]);
			mf[1][2] = eval_expr(argv[10]);
fprintf(stderr, "MF  %g %g %g  %g %g %g\n",
mf[0][0], mf[0][1], mf[0][2], mf[1][0], mf[1][1], mf[1][2]);
			affine_inverse(&mi[0][0], &mf[0][0]);
fprintf(stderr, "MI  %g %g %g  %g %g %g\n",
mi[0][0], mi[0][1], mi[0][2], mi[1][0], mi[1][1], mi[1][2]);
			if(argv[11][0] == '-') {
				/* Use inverse transform */
				patx = tarx*mi[0][0] + tary*mi[0][1] + mi[0][2];
				paty = tarx*mi[1][0] + tary*mi[1][1] + mi[1][2];
				afm[0] = mi[0][0];
				afm[1] = mi[0][1];
				afm[2] = mi[1][0];
				afm[3] = mi[1][1];
			} else {
				/* Use forward transform */
				patx = tarx*mf[0][0] + tary*mf[0][1] + mf[0][2];
				paty = tarx*mf[1][0] + tary*mf[1][1] + mf[1][2];
				afm[0] = mf[0][0];
				afm[1] = mf[0][1];
				afm[2] = mf[1][0];
				afm[3] = mf[1][1];
			}
		} else if(argc != 7 && argc != 5)
			fprintf(stderr, "******** bad argc %d\n", argc);
	}

targs += getticks();

	/* --- Read target image (image 0) --- cached if same filename --- */
	if(/*fname0[0] != '-' ||*/ strcmp(fname0, lastf0)) {
tread0 -= getticks();
		strncpy(lastf0, fname0, sizeof(lastf0)-1);
		lastf0[sizeof(lastf0)-1] = '\0';
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
			short2byte(im0);  // convert 16-bit to 8-bit
		if(im0->bpp == 3)
			color2byte(im0);  // convert RGB to grayscale
		if(reverse) {
			unsigned char *p = im0->pp;
			int i;
			for(i = 0; i < im0->wid * im0->ht; i++)
				p[i] = 255 - p[i];  // invert target
		}
		oldtarx = -10000;  // force re-computation of target FFT
		oldtary = -10000;
		nread0++;
tread0 += getticks();
	}
	if(im0 == NULL)
		return(-1);  // quietly handle repeat open failures

	/* --- Read pattern image (image 1) --- cached if same filename --- */
	if(/*fname1[0] != '-' ||*/ strcmp(fname1, lastf1)) {
tread1 -= getticks();
		strncpy(lastf1, fname1, sizeof(lastf1)-1);
		lastf1[sizeof(lastf1)-1] = '\0';
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
		oldpatx = -10000;  // force re-computation of pattern FFT
		oldpaty = -10000;
		nread1++;
tread1 += getticks();
	}
	if(im1 == NULL)
		return(-1);

	/* Default center positions if not specified */
	if(tarx <= -1000000)
		tarx = im0->wid/2;
	if(tary <= -1000000)
		tary = im0->ht/2;
	if(patx <= -1000000)
		patx = im1->wid/2;
	if(paty <= -1000000)
		paty = im1->ht/2;
	/* Apply coordinate multiplier and offsets */
	tarx *= MUL;
	tary *= MUL;
	patx *= MUL;
	paty *= MUL;
	tarx += addx;
	tary += addy;
	patx += addx*afm[0] + addy*afm[1];  // transform offset through affine
	paty += addx*afm[2] + addy*afm[3];
	tarx = (int)(tarx + .5); // round target coords to integer (avoids interpolation)
	tary = (int)(tary + .5);
	startpatx = patx;  // save initial pattern position for drift detection
	startpaty = paty;
	if(!quiet)
		fprintf(stderr, "args  %s %g %g  %s %g %g  MUL %g SIZ %dx%d\n",
			fname0, tarx, tary, fname1, patx, paty,MUL,SIZEX,SIZEY);
#ifdef	VERB
	fprintf(stderr, "SWIM %dx%d %s %g %g %s %g %g  %g %g %g %g\n",
		SIZEX, SIZEY, fname0, tarx, tary, fname1,
		patx, paty, afm[0], afm[1], afm[2], afm[3]);
#endif // VERB
	PW = SIZEX;   // pattern width
	PH = SIZEY;   // pattern height
	EW = SIZEX;   // expanded (FFT) width
	EH = SIZEY;   // expanded (FFT) height
	size = EW*EH;
	RW = EW;
	RH = EH;

	/* --- First-time initialization: allocate FFTW buffers and plans --- */
	if(ndone++ == 0) {
tinit -= getticks();
		io = newimage(PW, PH, 1); // output image for pattern area
		ro = newimage(RW, RH, 1); // output image for correlation result
		eo = newimage(EW, EH, 1); // output image for expanded pattern
		for(i = 0; i < 256; i++)
			revlut[i] = 255-i;  // build reverse lookup table
		/* Allocate FFTW complex buffers for forward/inverse transforms */
		fft_result0 = (fftwf_complex*)
			fftwf_malloc(sizeof(fftw_complex) * (size/2+1));
		fft_result1 = (fftwf_complex*)
			fftwf_malloc(sizeof(fftw_complex) * (size/2+1));
		fft_comb = (fftwf_complex*)
			fftwf_malloc(sizeof(fftw_complex) * (size/2+1));
		ifft_comb = fftwf_malloc(sizeof(fftw_complex) * (size/2+1));
		/* Create FFTW plans (r2c = real-to-complex, c2r = complex-to-real)
		 * Uses 1-D FFT over the entire flattened 2-D array for speed */
		forward_plan0 = fftwf_plan_dft_r2c_1d(
			size, targ, fft_result0, fftw_mode);
		backward_plan = fftwf_plan_dft_c2r_1d(
			size, fft_comb, ifft_comb, fftw_mode);
		mk_winf(winf, PW, PH);  // build apodization window
tinit += getticks();
		if(fftw_mode == FFTW_MEASURE) {
			gettimeofday(&tv, NULL);
			elapsed_sec = (tv.tv_sec-starts) +
				(tv.tv_usec - startu)/1000000.;
			fprintf(stderr, "FFTW_MEASURE %12llu ticks  %g sec\n",
				tinit, elapsed_sec);
		}
	}

	/* --- Prepare target patch: extract, window, normalize --- */
	if(!quiet)
		fprintf(stderr, "make targ at %g %g EWH %d %d\n",
			tarx, tary, EW, EH);
	if(oldtarx != tarx || oldtary != tary) {
tprep0 -= getticks();
		mk_ftarg(im0, tarx-EW/2, tary-EH/2, targ, EW, EH);
		if(apodize)
			use_winf(winf, targ, EW, EH);  // apply Tukey window
		scalepat(targ, EW, EH);  // normalize to [0,255]
		/* Reset best-match tracking for new target */
		bestz = 0;
		nbests = 0;
		sumbestx = 0;
		sumbesty = 0;
		sum2bestx = 0;
		sum2besty = 0;
		if(keepimg || !quiet)
			cpfout(targ, EW, EH, eo, 0, 0);
		tprep0 += getticks();
		if(targimg || !quiet)
			write_img(targimg, eo);  // save target patch image
	}
	/* Reset best-match tracking for this correlation run */
	bestz = 0;
	nbests = 0;
	sumbestx = 0;
	sumbesty = 0;
	sum2bestx = 0;
	sum2besty = 0;

	/* ========================= ITERATION LOOP ========================= */
loop:
	if(!quiet)
		fprintf(stderr, "LOOP patxy %g %g  bestz %g %d\n",
			patx, paty, bestz, nbests);
	bestz = 0; // reinit per iteration
	nbests = 0;
	sumbestx = 0;
	sumbesty = 0;
	sum2bestx = 0;
	sum2besty = 0;
	ia = 0;
	curra = 0;
	currw = wht_expon;
	a = (rota+curra)*M_PI/180;
	fdx = cos(a);
	fdy = sin(a);
	m0 = sqrt(fdx*fdx + fdy*fdy);

	/* --- Prepare pattern patch: extract with optional affine, expand, normalize --- */
	if(1 || oldpatx != patx || oldpaty != paty || oldpata != a) {
tprep1 -= getticks();
		if(a >= -.001 && a <= 0.001)
			/* No rotation: use faster axis-aligned extraction */
			mk_ftarg(im1, patx-PW/2, paty-PH/2, fpat, PW,  PH);
		else if(rota == 1024)
			/* Explicit affine matrix mode */
			mk_fpat(im1, patx, paty, afm[0], afm[1], afm[2], afm[3],
				NULL, fpat, PW, PH);
		else
			/* Rotation-only mode */
			mk_fpat(im1, patx, paty, fdx, fdy, -fdy, fdx, NULL,
				fpat, PW, PH);
		fp = fpat;
		/* Expand pattern to FFT size, pad with windowed mean */
		expand(fpat, PW, PH, epat, EW, EH, winavg);
		if(!quiet)
			fprintf(stderr, "expanded\n");
		scalepat(epat, EW, EH);    // normalize expanded pattern to [0,255]
		cpfout(epat, EW, EH, eo, 0, 0);
		scalepat(fpat, PW, PH);    // normalize original pattern for output
		if(!quiet)
			fprintf(stderr, "scaled\n");
		cpfout(fpat, PW, PH, io, 0, 0);
tprep1 += getticks();
	}

	/* --- Forward FFT of target (cached if position unchanged) --- */
	if(oldtarx != tarx || oldtary != tary) {
if(!quiet) fprintf(stderr, "need first FFT %g %g  %p\n", tarx, tary, targ);
tfft0 -= getticks();
		fftwf_execute_dft_r2c(forward_plan0, targ, fft_result0);
		oldtarx = tarx; oldtary = tary; ntargft++;
tfft0 += getticks();
		Nforw++;
	}

	/* --- Forward FFT of pattern (cached if position/affine unchanged) --- */
	fdx = patx - oldpatx;
	fdy = paty - oldpaty;
	m0 = sqrt(fdx*fdx + fdy*fdy);
	if(oldpatx != patx || oldpaty != paty || oldpata != a ||
	afm[0] != ofm[0] || afm[1] != ofm[1] || afm[2] != ofm[2] ||
	afm[3] != ofm[3]) {
if(!quiet)
fprintf(stderr, "need second FFT %g %g\n", patx, paty);
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

	/* --- Spectral multiplication with whitening --- */
	/* Cross-correlation in frequency domain:
	 *   C = conj(FFT0) * FFT1
	 * with spectral whitening:
	 *   C *= |C|^wht_expon
	 * The result is negated so the best match appears as a dark minimum */
tmult -= getticks();
	for(i = 0; i < size/2+1; i++) {
		double re, im, conj, s;
		conj = -fft_result0[i][1]; // conjugate target spectrum
		/* Complex multiply: conj(target) × pattern */
		re = fft_result0[i][0] * fft_result1[i][0];
		re -= conj * fft_result1[i][1];
		im = fft_result0[i][0] * fft_result1[i][1];
		im += fft_result1[i][0] * conj;
		/* Apply spectral whitening: scale by |magnitude|^exponent */
		if(whiten) {
			s = sqrt(re*re + im*im);
			if(s > 1e-5) {
				s = fastPow(s, wht_expon);  // approximate power function
				re *= s;
				im *= s;
			}
		}
		fft_comb[i][0] = -re; // negate so correlation peak is dark
		fft_comb[i][1] = im;
	}
tmult += getticks();

	/* --- Inverse FFT → correlation surface --- */
	if(!quiet)
		fprintf(stderr, "ready for backward_plan\n");
tfft2 -= getticks();
	fftwf_execute_dft_c2r(backward_plan, fft_comb, ifft_comb);
tfft2 += getticks();
	Nrev++;

	/* --- Post-processing: flip, stats, find match --- */
tpost -= getticks();
	qflip(ifft_comb, EW, EH);       // quadrant-flip to center zero-lag
	stats(ifft_comb, EW, EH);        // find best match, compute z-scores
	scalepat(ifft_comb, EW, EH);     // normalize for visualization
	cpfout(ifft_comb, EW, EH, eo, 0, 0);  // copy to output image

	if(newbest) {
		if(bestimg || !quiet)
			write_img(bestimg, eo);  // save best correlation surface
		if(keepimg)
			write_img(keepimg, io);  // save pattern patch
		/* Estimate sub-pixel offset from the correlation surface image */
		uncert = find_xyoff(eo->pp, eo->wid, eo->ht);
		if(!quiet)
			fprintf(stderr, "uncert %f\n", uncert);
	}
tpost += getticks();
	if(!quiet)
		fprintf(stderr, "loop all done\n");

	/* --- Compute safe matching range (overlap region) --- */
	rng_lft = tarx < patx ? tarx : patx;
	rng_up = tary < paty ? tary : paty;
	rng_rt = im0->wid - tarx < im1->wid - patx ? im0->wid - tarx : im1->wid - patx;
	rng_dn = im0->ht - tary < im1->ht - paty ? im0->ht - tary : im1->ht - paty;
	deltx = (rng_rt - rng_lft)/2;
	delty = (rng_dn - rng_up)/2;
	if(!quiet)
	fprintf(stderr, "up/down %g %g  lft/rt %g %g  del %g %g \n",
	rng_up, rng_dn, rng_lft, rng_rt, deltx, delty);
	ntarx = tarx + deltx;
	ntary = tary + delty;
	npatx = patx + deltx;
	npaty = paty + delty;
	if(!quiet)
	fprintf(stderr, "%g: %s %g %g %s %g %g delt %g %g\n", bestz,
		fname0, ntarx, ntary, fname1, npatx, npaty, deltx, delty);

	/* --- Update pattern position: move by measured offset --- */
	fdx = fbestx-SIZEX/2.;   // offset from center = displacement
	fdy = fbesty-SIZEY/2.;
	m0 = sqrt(fdx*fdx + fdy*fdy);
	m0niter[niter] += m0;       // accumulate offset magnitude statistics
	m0nitercnt[niter]++;
	/* Transform offset through affine matrix */
	tdx = afm[0]*fdx + afm[1]*fdy;
	tdy = afm[2]*fdx + afm[3]*fdy;
	if(no_hor)
		tdx = 0;  // suppress horizontal component if -H flag
	if(no_vert)
		tdy = 0;  // suppress vertical component if -V flag
	if(!quiet)
		fprintf(stderr, "MOVE by %g-%g=%g  %g-%g=%g   %g\n",
	fbestx, SIZEX/2., fdx, fbesty, SIZEY/2., fdy, m0);
	if(!quiet)
		fprintf(stderr, "TXY %g %g = %g\n", tdx, tdy, sqrt(tdx*tdx + tdy*tdy));
	if(!quiet)
		fprintf(stderr, "OLD %g %g", patx, paty);
	patx = patx - tdx;  // update pattern position (subtract because corr is negated)
	paty = paty - tdy;
	if(!quiet)
		fprintf(stderr, "   NEW patx paty %g %g\n", patx, paty);

	/* --- Iterate if more iterations requested --- */
	if(--niter > 0)
		goto loop;

	if(!quiet) {
		fprintf(stderr, "tarx %g tary %g\n", tarx, tary);
		fprintf(stderr, "patx %g paty %g\n", patx, paty);
		fprintf(stderr, "bstx %g bsty %g\n", fbestx, fbesty);
	}
	if(!quiet && rota == 1024) {
		fprintf(stderr, "keep %g: %s %d %d %s %g %g  %g %g %g %g\n",
			bestz, fname0, (int)tarx, (int)tary, fname1, patx, paty,
			afm[0], afm[1], afm[2], afm[3]);
	} else if(!quiet) {
		fprintf(stderr, "keep %g: %s %d %d %s %g %g  %g\n",
			bestz, fname0, (int)tarx, (int)tary, fname1, patx, paty,
			rota+besta);
	}

	/* --- Compute total drift from initial pattern position --- */
	fdx = patx - startpatx;
	fdy = paty - startpaty;
	m0 = sqrt(fdx*fdx + fdy*fdy);

	/* --- Output result: atomic write to stdout --- */
{
#define OBS 10000
	char outbuf[OBS];
	static char *flags[] = { "", " dx", " dy", " dxy", " dreset" };
	int flag = 0, nw;
	/* Flag large offsets (> 1/4 of FFT size) */
	if(sqrt(fdx*fdx) > SIZEX/4)
		flag |= 1;
	if(sqrt(fdy*fdy) > SIZEY/4)
		flag |= 2;
	/* Check SNR and offset thresholds for affine reset */
	if(snrthr > bestz)
		areset = 1;
	if(sqrt(fdx*fdx) > xthr)
		areset += 2;
	if(sqrt(fdy*fdy) > ythr)
	areset += 4;
	if(areset) {
		flag = 4;  // dreset flag
		patx = startpatx;  // revert to initial position
		paty = startpaty;
		areset = 0;
	}
	/* Format and write result line atomically via write() to avoid
	 * interleaved output from concurrent processes */
	snprintf(outbuf, OBS, "%g: %s %g %g %s %g %g  %g %g %g %g (%g %g %g%s)\n",
		bestz, fname0, tarx, tary, fname1, patx, paty,
		afm[0], afm[1], afm[2], afm[3], fdx, fdy, m0, flags[flag]);
	nw = write(1, outbuf, strlen(outbuf));
}
	return(0);
}

/* --- Batch mode argument parsing --- */
int nargc;
#define MAXARGS 100
char *nargv[MAXARGS];
#define	LLEN 2000
char line[LLEN];

/*
 * mkargs — Split a text line into an argv-style array
 *
 * Tokenizes the input string by whitespace (space, tab, newline),
 * replacing delimiters with NUL bytes and storing pointers to each
 * token.  Used to parse batch-mode input lines into argc/argv format.
 *
 * @param oargv  Output pointer array (must be at least MAXARGS entries)
 * @param s      Input string (modified in-place: delimiters → NUL)
 * @return       Number of tokens found
 */
int mkargs(char *oargv[], char *s) {
	int i, n = 0;
	char *p = s;
	while(*p) {
		if(n >= MAXARGS - 1) {
			fprintf(stderr, "mkargs: too many arguments (max %d)\n", MAXARGS);
			break;
		}
		oargv[n++] = p;
		while(*p && *p != '\n' && *p != ' ' &&  *p != '\t')
			p++;
		while(*p == ' ' || *p == '\t' || *p == '\n')
			*p++ = 0;
	}
	oargv[n] = NULL;
	return(n);
}

/*
 * main — Entry point: parse FFT size, then dispatch to single or batch mode
 *
 * Usage:
 *   swim <WxH>                   — batch mode, reads command lines from stdin
 *   swim <WxH> [flags] args...   — single-pair mode
 *
 * The first argument specifies the FFT size, either as a single number
 * (square) or WxH (rectangular).  Valid range: 4 to MSIZE.
 *
 * In batch mode, each line of stdin is parsed into argc/argv and passed
 * to oldmain().  Lines starting with '#', empty lines, or blank lines
 * are skipped.
 *
 * Allocates the four main float buffers (epat, targ, winf, fpat) sized
 * to SIZEX × SIZEY.
 */
int main(int argc, char *argv[]) {
	int i;
	char *p;
	gettimeofday(&tv, NULL);
	starts = tv.tv_sec;
	startu = tv.tv_usec;
	tstart = getticks();
	/* Require FFT size as first argument */
	if(argc < 2 || !isdigit(argv[1][0])) {
		fprintf(stderr, "%s requires FFT size\n", argv[0]);
		return(-1);
	}
	/* Parse FFT size: "1664" or "1664x1664" */
	p = argv[1];
	SIZEX = atoi(p);
	while(isdigit(*p))
		p++;
	SIZEY = SIZEX;  // default to square
	if(*p == 'x') {
		p++;
		SIZEY = atoi(p);  // rectangular: WxH
	}
	/* Validate size range and consume the size argument */
	if(SIZEY >= 4 && SIZEY <= MSIZE) {
		argv++;
		argc--;
	} else {
		SIZEX = 128;  // fallback default
		SIZEY = 128;
	}
	/* Allocate working buffers */
	epat = (float *)malloc(SIZEX*SIZEY*sizeof(float));  // expanded pattern
	targ = (float *)malloc(SIZEX*SIZEY*sizeof(float));  // target patch
	winf = (float *)malloc(SIZEX*SIZEY*sizeof(float));  // apodization window
	fpat = (float *)malloc(SIZEX*SIZEY*sizeof(float));  // raw pattern patch
	if(argc > 2) {
		/* Single-pair mode: process command-line arguments directly */
		oldmain(argc, argv);
	} else while(fgets(line, LLEN, stdin)) {
		/* Batch mode: read command lines from stdin */
		if(line[0] == 0 || line[0] == '#' || line[0] == '\n') {
			continue;  // skip comments, empty lines
		}
		targs -= getticks();
		nargc = mkargs(nargv, line);
		targs += getticks();
		oldmain(nargc, nargv);
	}
	/* Final timing summary (only in VERB mode) */
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
	return(0);
}
