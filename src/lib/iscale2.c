/* =========================================================================
 * iscale2 — Image downscaler (block-average)
 *
 * Reads one or more images and produces 1/N scaled versions by averaging
 * NxN pixel blocks.  Supports grayscale (bpp=1) and RGB (bpp=3).
 *
 * Usage:
 *   iscale2 [+N] [-C] [-v] [of=FILE] [p=DIR] image1 [image2 ...]
 *
 * Options (parsed via goto-loop, not getopt):
 *   +N       Scale factor (default 8). Output is 1/N of input dimensions.
 *   -C       Contrast adjustment factor (integer).
 *   -v       Variance mode: output per-block mean absolute deviation.
 *   of=FILE  Explicit output filename (used for all input images).
 *   p=DIR    Output directory prefix; basename derived from input path.
 *
 * Output naming (when of= and p= are not given):
 *   dir/S<N><basename>   normal mode
 *   dir/V<N><basename>   variance mode
 * ========================================================================= */

// gcc -O3 -o iscale iscale.c -ljpeg -ltiff -lpng
// gcc -o iscale -O3 -m64 -msse3 iscale.c -ltiff -lfftw3f
// icc -o iscale -O3 -ip -xSSE4.2 -no-prec-div -unroll-agressive -m64 -Wl,-z-ffast-math iscale.c -ltiff -lfftw3f
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <jpeglib.h>
#include <tiffio.h>

#define uchar unsigned char
#define ushort unsigned short

#include "swimio.h"

struct image *im0, *im1;

char outpath[32767] = "\0";
char outfile[32767] = "\0";

int contr, variance;
int main(int argc, char *argv[]) {
  int path_prefix_index = -1;
  int iscale = 8, x, y, i, j, v, fd;
  long int no;

  /* --- Argument parsing (goto-based loop) --- */
  argv++;
  argc--;
 again:
  if (argc <= 0) goto done_args; /* FIX(iscale2-C1#1): guard against no arguments */
  //if(isdigit(*argv[0]))
  if (*argv[0] == '+') {
    /* +N: set scale factor */
    iscale = atoi(argv[0] + 1);
    argv++;
    argc--;
    goto again;
  } else if (*argv[0] == '-') {
    /* -v: variance mode; -N: contrast factor */
    if (argv[0][1] == 'v')
      variance++;
    else
      contr = atoi(argv[0] + 1);
    argv++;
    argc--;
    goto again;
  } else if (strncmp (argv[0],"of=", 3) == 0) {
    /* of=FILE: explicit output filename */
    strncpy ( outfile, &argv[0][3], sizeof(outfile) - 1 ); /* FIX(iscale2-C1#4): bounded copy */
    outfile[sizeof(outfile) - 1] = '\0';
//    fprintf (stderr, "Output filename = %s\n", outfile );
    argv++;
    argc--;
    goto again;
  } else if (strncmp (argv[0],"p=", 2) == 0) {
    /* p=DIR: output directory prefix */
    strncpy ( outpath, &argv[0][2], sizeof(outpath) - 1 ); /* FIX(iscale2-C1#5): bounded copy */
    outpath[sizeof(outpath) - 1] = '\0';
//    fprintf (stderr, "Output path = %s\n", outpath );
    argv++;
    argc--;
    goto again;
  }

  /* --- Main processing loop: one iteration per input image --- */
//  fprintf(stderr, "iscale %d  contr %d var %d\n", iscale, contr, variance);
 done_args:
  while (argc > 0) {
    int owid, oht, R, G, B, av = 0;
    unsigned char *ip;
    char outname[32767];

    /* -- Load input image -- */
//    fprintf(stderr, "reading image %s\n", argv[0]);
    im0 = read_img(argv[0]);
    if (!im0) { /* FIX(iscale2-C1#2): NULL check on read_img */
      fprintf(stderr, "iscale2: cannot read image %s\n", argv[0]);
      argv++; argc--;
      continue;
    }

    /* -- Allocate output image (1/N dimensions) -- */
    owid = im0->wid / iscale;
    oht = im0->ht / iscale;
    im1 = newimage(owid, oht, im0->bpp);
    if (!im1) { /* FIX(iscale2-C1#3,C2#1): NULL check on newimage; free im0 */
      fprintf(stderr, "iscale2: cannot allocate output image\n");
      free(im0->pp); free(im0);
      argv++; argc--;
      continue;
    }

    /* -- Contrast mode: compute whole-image average for recentering -- */
    if (contr) {
      ip = im0->pp;
      for (av = y = 0; y < im0->ht; y++)
        for (x = 0; x < im0->wid; x++)
          av += *ip++;
      av /= im0->ht * im0->wid;
    }

    /* -- Downscale: average NxN blocks into output pixels -- */
//    fprintf(stderr, "sc %d   contr %d   av %d   cav %d\n", iscale, contr, av, contr * av);
    for (no = y = 0; y + iscale <= im0->ht; y += iscale) {
      ip = im0->pp + (long)y *im0->wid * im0->bpp;

      /* Grayscale path (bpp == 1) */
      if (im0->bpp == 1)
        for (x = 0; x + iscale <= im0->wid; x += iscale) {
          /* Sum NxN block */
          v = 0;
          for (j = 0; j < iscale; j++)
            for (i = 0; i < iscale; i++)
              v += ip[j * im0->wid + x + i];

          if (contr) {
            /* Contrast adjustment: rescale around midpoint 128 */
            v *= contr;
            v -= contr * av * iscale * iscale;
            v += 128 * iscale * iscale;
            v = v / (iscale * iscale);
            if (v < 0)
              v = 0;
            else if (v > 255)
              v = 255;
          } else
            /* Normal average */
            v = v / (iscale * iscale);

          if (variance) {
            /* Variance mode: mean absolute deviation from block average */
            int d, s = v;
            v = 0;
            for (j = 0; j < iscale; j++)
              for (i = 0; i < iscale; i++) {
                d = s - ip[j * im0->wid + x + i];
                if (d < 0)
                  d = -d;
                v += d;
              }
            v /= variance;
            if (v > 255)
              v = 255;
          }
          im1->pp[no++] = v;

      /* RGB path (bpp == 3) */
      } else if (im0->bpp == 3)
        for (x = 0; x + iscale <= im0->wid; x += iscale) {
          /* Sum NxN block per channel */
          R = G = B = 0;
          for (j = 0; j < iscale; j++)
            for (i = 0; i < iscale; i++) {
              R += ip[3 * (j * im0->wid + x + i) + 0];
              G += ip[3 * (j * im0->wid + x + i) + 1];
              B += ip[3 * (j * im0->wid + x + i) + 2];
            }
          /* Average each channel */
          R = R / (iscale * iscale);
          G = G / (iscale * iscale);
          B = B / (iscale * iscale);
          im1->pp[no++] = R;
          im1->pp[no++] = G;
          im1->pp[no++] = B;
      } else
        /* Unsupported bpp — skip row */
//        fprintf(stderr, "not gray or RGB\n");
        continue;
    }

    /* -- Build output filename -- */
    if (strlen(outfile) > 0) {
      /* "of=" was given: use explicit filename */
      snprintf(outname, sizeof(outname), "%s", outfile); /* FIX(iscale2-C1#6): bounded */
//      fprintf (stderr, "Outname = %s\n", outname );
    }
    else if (strlen(outpath) > 0) {
      /* "p=" was given: combine outpath + input basename */
//      fprintf(stderr, "outpath: parsing argv[0]  %s\n",argv[0]);
      char *pre, *post, *lasts = NULL;
      pre = argv[0];
      for (post = pre; *post; post++) {
        if (*post == '/')
          lasts = post;
      }
      if (lasts) {
        *lasts++ = 0;
        post = lasts;
      }
      else {
        post = pre;
      }
//      fprintf(stderr, "outpath: parsing argv[0]: %s  ->  got: %s\n",pre,post);
//      fprintf (stderr, "Outpath = %s\n", outpath );
//      sprintf(outname, "%s/S%d%s", outpath, iscale, post);
      snprintf(outname, sizeof(outname), "%s/%s", outpath, post); /* FIX(iscale2-C1#6) */
//      fprintf (stderr, "Outname = %s\n", outname );
    }
    else {
      /* Default: dir/S<N><basename> or dir/V<N><basename> */
      char *pre, *post, *lasts = NULL;
      pre = argv[0];
      for (post = pre; *post; post++) {
        if (*post == '/')
          lasts = post;
      }
      if (lasts) {
        *lasts++ = 0;
        post = lasts;
      }
      if (!variance) {
        if (*post)
          snprintf(outname, sizeof(outname), "%s/S%d%s", pre, iscale, post); /* FIX(iscale2-C1#6) */
        else
          snprintf(outname, sizeof(outname), "S%d%s", iscale, argv[0]); /* FIX(iscale2-C1#6) */
      } else {
        if (*post)
          snprintf(outname, sizeof(outname), "%s/V%d%s", pre, iscale, post); /* FIX(iscale2-C1#6) */
        else
          snprintf(outname, sizeof(outname), "V%d%s", iscale, argv[0]); /* FIX(iscale2-C1#6) */
      }
    }

    /* -- Write output and clean up -- */
    if (write_img(outname, im1) != 0) /* FIX(iscale2-C3#1): check write return */
      fprintf(stderr, "iscale2: error writing %s\n", outname);
    argv++;
    argc--;
    free(im0->pp);
    free(im0);
    free(im1->pp);
    free(im1);
  }
  return (0);
}
