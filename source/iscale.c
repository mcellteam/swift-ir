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

int contr, variance;
int main(int argc, char *argv[]) {
  int path_prefix_index = -1;
  int iscale = 8, x, y, i, j, v, fd;
  long int no;
  argv++;
  argc--;
 again:
  //if(isdigit(*argv[0]))
  if (*argv[0] == '+') {
    iscale = atoi(argv[0] + 1);
    argv++;
    argc--;
    goto again;
  } else if (*argv[0] == '-') {
    if (argv[0][1] == 'v')
      variance++;
    else
      contr = atoi(argv[0] + 1);
    argv++;
    argc--;
    goto again;
  } else if (strncmp (argv[0],"p=", 2) == 0) {
    strcpy ( outpath, &argv[0][2] );
    printf ( "Output path = %s\n", outpath );
    argv++;
    argc--;
    goto again;
  }
  fprintf(stderr, "iscale %d  contr %d var %d\n", iscale, contr, variance);
  while (argc > 0) {
    int owid, oht, R, G, B, av = 0;
    unsigned char *ip;
    char outname[32767];
    im0 = read_img(argv[0]);
    owid = im0->wid / iscale;
    oht = im0->ht / iscale;
    im1 = newimage(owid, oht, im0->bpp);
    if (contr) {
      ip = im0->pp;
      for (av = y = 0; y < im0->ht; y++)
        for (x = 0; x < im0->wid; x++)
          av += *ip++;
      av /= im0->ht * im0->wid;
    }
    fprintf(stderr, "sc %d   contr %d   av %d   cav %d\n", iscale, contr, av, contr * av);
    for (no = y = 0; y + iscale <= im0->ht; y += iscale) {
      ip = im0->pp + (long)y *im0->wid * im0->bpp;
      if (im0->bpp == 1)
        for (x = 0; x + iscale <= im0->wid; x += iscale) {
          v = 0;
          for (j = 0; j < iscale; j++)
            for (i = 0; i < iscale; i++)
              v += ip[j * im0->wid + x + i];
          if (contr) {
            v *= contr;
            v -= contr * av * iscale * iscale;
            v += 128 * iscale * iscale;
            v = v / (iscale * iscale);
            if (v < 0)
              v = 0;
            else if (v > 255)
              v = 255;
          } else
            v = v / (iscale * iscale);
          if (variance) {
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
      } else if (im0->bpp == 3)
        for (x = 0; x + iscale <= im0->wid; x += iscale) {
          R = G = B = 0;
          for (j = 0; j < iscale; j++)
            for (i = 0; i < iscale; i++) {
              R += ip[3 * (j * im0->wid + x + i) + 0];
              G += ip[3 * (j * im0->wid + x + i) + 1];
              B += ip[3 * (j * im0->wid + x + i) + 2];
            }
          R = R / (iscale * iscale);
          G = G / (iscale * iscale);
          B = B / (iscale * iscale);
          im1->pp[no++] = R;
          im1->pp[no++] = G;
          im1->pp[no++] = B;
      } else
        fprintf(stderr, "not gray or RGB\n");
    }
    if (strlen(outpath) > 0) {
      // Use the "p=" path
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
      printf ( "Outpath = %s\n", outpath );
      sprintf(outname, "%s/S%d%s", outpath, iscale, post);
      printf ( "Outname = %s\n", outname );
    } else {
      // Use the existing logic unchanged
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
          sprintf(outname, "%s/S%d%s", pre, iscale, post);
        else
          sprintf(outname, "S%d%s", iscale, argv[0]);
      } else {
        if (*post)
          sprintf(outname, "%s/V%d%s", pre, iscale, post);
        else
          sprintf(outname, "V%d%s", iscale, argv[0]);
      }
    }


    write_img(outname, im1);
    argv++;
    argc--;
    free(im0->pp);
    free(im0);
    free(im1->pp);
    free(im1);
  }
  return (0);
}
