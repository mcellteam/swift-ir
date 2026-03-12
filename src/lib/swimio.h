/*
 * swimio.h — Multi-format image I/O library
 *
 * Provides read/write support for: TIFF (via libtiff), PNG (via libpng),
 * JPEG (via libjpeg), WebP (via libwebp), PGM/PPM (Netpbm P5/P6),
 * and raw binary image data.
 *
 * All images are represented as a simple struct image with a flat pixel
 * buffer (pp), dimensions (wid x ht), row stride (ydelta), bytes per
 * pixel (bpp: 1=gray, 2=16-bit gray, 3=RGB), and an optional single
 * transparency value (trans, -1 means none).
 *
 * Format detection in read_img() uses file extension for raw/dat/tif,
 * then falls back to magic-byte sniffing: 0x52='R' (RIFF/WebP),
 * 0x89 (PNG), 0xFF (JPEG), 'I' (little-endian TIFF), else PGM/PPM.
 */

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <strings.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <jpeglib.h>
#include <tiffio.h>
#include <png.h>
#include <unistd.h>
#include <webp/types.h>
#include <webp/encode.h>
#include <webp/decode.h>

#define uchar unsigned char
#define ushort unsigned short
#define uint16 unsigned short

/* Global I/O counters for diagnostics */
int Nswim_reads, Nswim_writes, Nswim_nullwrites;

/*
 * struct image — simple raster image container
 *   pp:     pixel data buffer (row-major, contiguous)
 *   wid:    image width in pixels
 *   ht:     image height in pixels
 *   ydelta: row stride in pixels (usually == wid)
 *   bpp:    bytes per pixel (1=gray8, 2=gray16, 3=RGB24)
 *   trans:  transparency index (-1 = none, >= 0 = transparent value)
 */
struct image {
	unsigned char *pp;
	int wid, ht, ydelta, bpp, trans;
};

/*
 * newimage — allocate a new image with given dimensions and depth.
 * Allocates (ht+1) rows to provide a one-row guard against off-by-one
 * access at the bottom edge. Returns NULL on allocation failure.
 */
struct image *newimage(int wid, int ht, int bpp) {
	struct image *ip = (struct image *)malloc(sizeof(struct image));
	ip->wid = wid;
	ip->ht = ht;
	ip->bpp = bpp;
	ip->ydelta = wid;
	ip->trans = -1;
	ip->pp = (unsigned char *)malloc((ht+1)*(long)wid*bpp);
	if(!ip->pp) {
		fprintf(stderr, "image malloc failed %d %d %d\n", ht, wid, bpp);
		free(ip);
		return(NULL);
	}
	return(ip);
}

/*
 * ltiff_reader — read a TIFF file using libtiff (strip-based).
 * Supports 8-bit and 16-bit images, 1 or 3 samples per pixel.
 * Returns pixel data via *bp, dimensions via *widp/*htp, depth via *bpp.
 * Returns 0 on success, -1 on failure.
 */
int tiffout = 0;
int ltiff_reader(char *fname, int *widp, int *htp, int *bpp, uchar **bp) {
	TIFF *timg;
	uint16 bps, spp, phot;
	unsigned char *buff;
	int i, wid, ht, stsize, stmax, strips, bytesperpixel;
	unsigned long qread, got;
	unsigned long buffsz, count;
	char pgmhdr[100];

	TIFFSetWarningHandler(NULL); /* suppress libtiff warnings */
	if((timg = TIFFOpen(fname, "r")) == NULL) {
		fprintf(stderr, "Could not open input: %s\n", fname);
		return(-1);
	}

	/* Validate bits per sample: only 8 or 16 supported */
	if(TIFFGetField(timg, TIFFTAG_BITSPERSAMPLE, &bps) == 0 ||
		(bps != 8 && bps != 16)) {
		fprintf(stderr, "bad bps %d\n", bps);
		goto end;
	}
	bytesperpixel = bps/8;

	/* Validate samples per pixel: only 1 (gray) or 3 (RGB) */
	if(TIFFGetField(timg, TIFFTAG_SAMPLESPERPIXEL, &spp) == 0 || (spp != 1 && spp != 3)) {
		fprintf(stderr, "bad spp %d - assume 1\n", spp);
		spp = 1;
	}

	if(TIFFGetField(timg, TIFFTAG_IMAGEWIDTH, &wid) == 0) {
		fprintf(stderr, "No wid\n");
		goto end;
	}

	if(TIFFGetField(timg, TIFFTAG_IMAGELENGTH, &ht) == 0) {
		fprintf(stderr, "No ht\n");
		goto end;
	}

	/* Allocate buffer for all strips; TIFFStripSize already accounts
	 * for bytes-per-sample, so no extra multiply needed */
	stsize = TIFFStripSize(timg);
	stmax = TIFFNumberOfStrips(timg);
	qread = 0;

	buffsz = stsize*(unsigned long)TIFFNumberOfStrips(timg);
	if((buff = (unsigned char *)malloc(buffsz)) == NULL) {
		fprintf(stderr, "malloc err (bytes = %ld)\n", buffsz);
		goto end;
	}

	/* Read all strips sequentially into the buffer */
	for(strips = 0; strips < stmax; strips++) {
		if((got = TIFFReadEncodedStrip(timg, strips,
		    buff + qread, stsize)) == -1) {
			fprintf(stderr, "error strip %d\n", strips);
			free(buff);
			goto end;
		}
		qread += got;
	}

	/* Return results to caller */
	*widp = wid;
	*htp = ht;
	*bp = buff;
	*bpp = bytesperpixel*spp; /* total bytes per pixel (e.g. 2*3=6 for 16-bit RGB) */
	tiffout = 1;
end:	TIFFClose(timg);
	return(0);
}

/*
 * read_img — universal image reader.
 *
 * Format detection strategy:
 *   1. File extension: .raw/.dat -> raw binary, .tif/.tiff -> libtiff
 *   2. Magic byte sniffing (first byte of file):
 *      0x52 'R' -> RIFF container (WebP)
 *      0x89     -> PNG signature
 *      0xFF     -> JPEG SOI marker
 *      'I'      -> little-endian TIFF (inline parser, not libtiff)
 *      else     -> PGM (P5) or PPM (P6) Netpbm format
 *
 * Returns a malloc'd struct image, or NULL on failure.
 * Caller is responsible for freeing ip->pp and ip.
 */
struct image *read_img(char *fname) {
	FILE *fp;
	char tmptxt[256];
	struct image *ip;
	int bpp = 1, wid, ht, range, c, nr;
	unsigned char *idata;
	char *cp, *ep = NULL; /* ep tracks the last '.' for extension detection */
	Nswim_reads++;

	/* Find the file extension (last dot in filename) */
	for(cp = fname; *cp; cp++)
		if(*cp == '.')
			ep = cp;
	if(!ep) {
		fprintf(stderr, "No extension in filename: %s\n", fname);
		return(NULL);
	}

	/* --- Raw binary format (hardcoded 2560x2160 for Davi temca2 camera) --- */
	if(strstr(ep, ".raw") || strstr(ep, ".RAW")
	    || strstr(ep, ".dat") || strstr(ep, ".DAT")) {
		int fd;
#define RWID	2560	/* Davi temca2 camera width */
#define RHT	2160	/* Davi temca2 camera height */
#define RBPP	1	/* 8-bit grayscale */
#define	RHDR	0	/* no header bytes to skip */
fprintf(stderr, "Davi temca2 raw\n");
		ip = (struct image *)malloc(sizeof(struct image));
		ip->wid = RWID;
		ip->ht = RHT;
		ip->bpp = RBPP;
		ip->ydelta = RWID;
		ip->trans = -1;
		ip->pp = (unsigned char *)malloc(ip->wid*ip->ht);
		fd = open(fname, 0);
fprintf(stderr, "raw fd %d\n", fd);
		if(RHDR)
			nr = read(fd, ip->pp, RHDR);
		nr = read(fd, ip->pp, ip->wid*ip->ht*ip->bpp);
		close(fd);
		return(ip);
	}

	/* --- TIFF format via libtiff (matches .tif and .tiff) --- */
	if(strstr(ep, ".tif") || strstr(ep, ".TIF")) {
		if(ltiff_reader(fname, &wid, &ht, &bpp, &idata) < 0)
			return(NULL);
		ip = (struct image *)malloc(sizeof(struct image));
		ip->wid = wid;
		ip->ht = ht;
		ip->bpp = bpp;
		ip->ydelta = wid;
		ip->trans = -1;
		ip->pp = idata;
		return(ip);
	}

	/* For remaining formats, open the file and sniff the first byte */
	if(!(fp = fopen(fname, "rb"))) {
		return(NULL);
	}
	c = fgetc(fp);
	ungetc(c, fp);

	/* --- WebP format (RIFF container, first byte 'R' = 0x52) --- */
	if(c == 0122) {
#define	WEBPSIZ 100000000 /* 100MB temp buffer for WebP decoding */
		int nr, wid, ht;;
		unsigned char *imp, *tp = (unsigned char *)malloc(WEBPSIZ);
		ip = (struct image *)malloc(sizeof(struct image));
		nr = fread(tp, 1, WEBPSIZ, fp);
fprintf(stderr, "webp nr %d\n", nr);
		imp = WebPDecodeRGB(tp, nr, &wid, &ht);
fprintf(stderr, "webp wh %d %d  %p\n", wid, ht, imp);
		free(tp);
		if(!imp) {
			fprintf(stderr, "WebPDecodeRGB failed\n");
			free(ip);
			fclose(fp);
			return(NULL);
		}
		ip->pp = imp;
		ip->wid = wid;
		ip->ht = ht;
		ip->ydelta = wid;
		ip->bpp = 3; /* WebP always decoded as RGB */
	} else

	/* --- PNG format (signature byte 0x89) --- */
	if(c == 0211) {
		int i, o, nr = 0, x, y, number_of_passes, rowbytes;
		png_bytep *row_ptr;
		uchar png_hdr[8];
		png_structp png_ptr;
		png_infop info_ptr;
		unsigned char *idata, color_type, bit_depth;

		/* Validate PNG signature (8 bytes) */
		nr += fread(png_hdr, 1, 8, fp);
		if(png_sig_cmp(png_hdr, 0, 8)) {
			fclose(fp);
			return(NULL);
		}

		/* Set up libpng read structures */
		png_ptr = png_create_read_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
		png_set_sig_bytes(png_ptr, 8); /* tell libpng we already read the sig */
		info_ptr = png_create_info_struct(png_ptr);
		png_init_io(png_ptr, fp);
		png_read_info(png_ptr, info_ptr);

		ip = (struct image *)malloc(sizeof(struct image));
		ip->wid = png_get_image_width(png_ptr, info_ptr);
		ip->ydelta = ip->wid;
		ip->ht = png_get_image_height(png_ptr, info_ptr);
		color_type = png_get_color_type(png_ptr, info_ptr);
		bit_depth = png_get_bit_depth(png_ptr, info_ptr);
fprintf(stderr, "PNG color_type %d  bit_depth %d\n", color_type, bit_depth);
fprintf(stderr, "PNG_COLOR_TYPE_PALETTE %d\n", PNG_COLOR_TYPE_PALETTE);
fprintf(stderr, "PNG_COLOR_TYPE_GRAY %d\n", PNG_COLOR_TYPE_GRAY);
fprintf(stderr, "PNG_COLOR_TYPE_GRAY_ALPHA %d\n", PNG_COLOR_TYPE_GRAY_ALPHA);
fprintf(stderr, "PNG_COLOR_TYPE_RGB %d\n", PNG_COLOR_TYPE_RGB);
fprintf(stderr, "PNG_COLOR_TYPE_RGB_ALPHA %d\n", PNG_COLOR_TYPE_RGB_ALPHA);

		/* Determine output bpp: 8-bit gray -> 1, everything else -> 3 (RGB) */
		if(color_type == 0 && bit_depth == 8)
			ip->bpp = 1;
		else
			ip->bpp = 3;

		number_of_passes = png_set_interlace_handling(png_ptr);
		png_read_update_info(png_ptr, info_ptr);

		/* Allocate row pointers and output buffer */
		row_ptr = (png_bytep *)malloc(sizeof(png_bytep)*ip->ht);
		if(bit_depth == 16)
			rowbytes = ip->wid*8;  /* 16-bit RGBA = 8 bytes/pixel */
		else
			rowbytes = ip->wid*4;  /* 8-bit RGBA = 4 bytes/pixel */
		idata = malloc(ip->ht*ip->wid*ip->bpp);

		if(color_type == 0) {
			/* Grayscale: read directly into output buffer */
			int rowlen = ip->wid*ip->bpp;
			for(y = 0; y < ip->ht; y++)
				row_ptr[y] = (png_byte *)&idata[y*rowlen];
			png_read_image(png_ptr, row_ptr);
		} else {
			/* Color: read into temp rows, extract RGB, skip alpha if RGBA */
			int rowlen = ip->wid*ip->bpp;
			uchar *in, *out;
			for(y = 0; y < ip->ht; y++)
				row_ptr[y] = (png_byte *)malloc(rowbytes);
			png_read_image(png_ptr, row_ptr);
			for(y=0; y < ip->ht; y++) {
				in = row_ptr[y];
				out = &idata[y*rowlen];
				for(x = 0; x < ip->wid; x++) {
					*out++ = *in++; /* R */
					*out++ = *in++; /* G */
					*out++ = *in++; /* B */
					if(color_type == PNG_COLOR_TYPE_RGB_ALPHA)
						in++; /* skip alpha channel */
				}
			}
			for(y = 0; y < ip->ht; y++)
				free(row_ptr[y]);
		}
		free(row_ptr);
		png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
		ip->pp = idata;
		ip->trans = -1;

	/* --- JPEG format (SOI marker 0xFF) --- */
	} else if(c == 0377) {
		int i = 0, l = 0, row_stride;
		struct jpeg_decompress_struct cinfo;
		struct jpeg_error_mgr jerr;
		JSAMPARRAY row_buffer;

		cinfo.err = jpeg_std_error(&jerr);
		jpeg_create_decompress(&cinfo);
		jpeg_stdio_src(&cinfo, fp);
		jpeg_read_header(&cinfo, TRUE);
		jpeg_calc_output_dimensions(&cinfo);
		row_stride = cinfo.output_width * cinfo.output_components;
		wid = cinfo.output_width;
		ht = cinfo.output_height;
		bpp = cinfo.output_components; /* 1=gray, 3=RGB */

		if((ip = newimage(wid, ht, bpp))) {
			row_buffer = (*cinfo.mem->alloc_sarray)((j_common_ptr)
				&cinfo, JPOOL_IMAGE, row_stride, 1);
			jpeg_start_decompress(&cinfo);
			/* Read scanlines one at a time into our image buffer */
			for(i = 0; cinfo.output_scanline < cinfo.output_height; i++) {
				jpeg_read_scanlines(&cinfo, row_buffer, 1);
				memcpy(ip->pp + i*row_stride, row_buffer[0],
					row_stride);
			}
			jpeg_finish_decompress(&cinfo);
			jpeg_destroy_decompress(&cinfo);
		} else {
			jpeg_destroy_decompress(&cinfo);
			fclose(fp);
			return(NULL);
		}

	/* --- Little-endian TIFF (inline parser, 'I' = 0x49) ---
	 * Simple inline TIFF parser for basic single-strip grayscale images.
	 * For more complex TIFFs, the libtiff path above (via extension) is preferred. */
	} else if(c == 'I') {
		int i, o, nr = 0;
		ushort tiff_hdr[4], ntags, *tags;
		unsigned char *idata = NULL;

		nr += fread(tiff_hdr, 1, 8, fp);
		if(tiff_hdr[0] != 0x4949) { /* verify "II" byte order mark */
			fprintf(stderr, "only II for now\n");
			fclose(fp);
			return(NULL);
		}

		/* Get offset to IFD (Image File Directory) */
		o = *(int *)(&tiff_hdr[2]);
		if(o > 8) {
			/* Data between header and IFD — might contain image data */
			idata = (unsigned char *)malloc(o-8);
			nr += fread(idata, 1, o-8, fp);
		}

		/* Read IFD: tag count + tag entries (12 bytes each, 6 shorts) */
		nr += fread(&ntags, 1, 2, fp);
		tags = (unsigned short *)malloc(12*ntags);
		nr += fread(tags, 1, 12*ntags, fp);

		/* Parse essential tags: width (0x100), height (0x101), strip offset (0x111) */
		for(i = 0; i < ntags; i++) {
			if(tags[6*i] == 0x100)
				wid = tags[6*i+4];
			else if(tags[6*i] == 0x101)
				ht = tags[6*i+4];
			else if(tags[6*i] == 0x111)
				o = (tags[6*i+3] << 16) + tags[6*i+4];
		}

		if(nr <= o) {
			/* Image data comes after current read position */
			free(idata);
			idata = (unsigned char *)malloc(wid*ht);
			if(nr < o)
				nr += fread(idata, 1, o-nr, fp); /* skip to strip offset */
			nr += fread(idata, 1,  wid*ht, fp);
		} else if(o > 8 && idata) {
			/* Image data was already read as part of pre-IFD data */
			bcopy(idata+o-8, idata, wid*ht);
		}
		free(tags);
		ip = (struct image *)malloc(sizeof(struct image));
		ip->wid = wid;
		ip->ht = ht;
		ip->bpp = bpp;
		ip->ydelta = wid;
		ip->trans = -1;
		ip->pp = idata;

	/* --- PGM/PPM Netpbm format (P5 = grayscale, P6 = RGB) --- */
	} else {
		int ignore = fscanf(fp, "%[^\n] ", tmptxt);
		if(strcmp(tmptxt, "P5")) {
			if(strcmp(tmptxt, "P6")) {
				fprintf(stderr, "Not P5 or P6\n");
				return(NULL);
			}
			bpp = 3; /* P6 = RGB */
		}
		/* Skip comment lines (e.g. from XV) starting with '#' */
		while((c = fgetc(fp)) == '#') {
			int t;
			while((t = fgetc(fp)) != '\n')
				;
		}
		ungetc(c, fp);

		/* Read dimensions and max value */
		ignore = fscanf (fp, "%d%d", &wid, &ht);
		ignore = fscanf(fp, "%d", &range);
		if(range == 65535)
			bpp = 2; /* 16-bit grayscale */
		c = fgetc(fp); /* consume the single whitespace after range */
		if(range != 255 && range != 65535) {
			fprintf(stderr, "bad PPM range %d\n", range);
			fclose(fp);
			return(NULL);
		}
		ip = newimage(wid, ht, bpp);
		if(!ip)
			return(NULL);
		/* Read raw pixel data */
		ignore = fread(ip->pp, 1, (long)ht*wid*bpp, fp);
	}
	fclose(fp);

	/* Debug: optionally overlay a grid on the image */
#ifdef	INGRID
{
int x, y;
fprintf(stderr, "do grid.....\n");
for(y = 0; y < ht; y += INGRID) for(x = 0; x < wid; x++) ip->pp[y*wid+x] = 255;
for(y = 0; y < ht; y++) for(x = 0; x < wid; x += INGRID) ip->pp[y*wid+x] = 255;
}
#endif
	return(ip);
}

/* TIFF header/IFD templates (legacy, used by old raw TIFF writer — now replaced by libtiff) */
ushort tiff_hdr[] = { 0x4949, 42, 0x0, 0x0 };
ushort tiff_mfd[] = { 7,
0x100, 3, 1, 0, 0, 0, /* width */
0x101, 3, 1, 0, 0, 0, /* height */
0x102, 3, 1, 0, 8, 0, /* bits per sample */
0x106, 3, 1, 0, 1, 0, /* photometric: 0=white-is-zero, 1=black-is-zero, 2=RGB */
0x111, 4, 1, 0, 0, 0, /* strip offsets */
0x115, 4, 1, 0, 1, 0, /* samples per pixel */
0x117, 4, 1, 0, 0, 0, /* strip byte count */
};

unsigned char palette[256][3]; /* grayscale palette (used by PNG writer) */

/*
 * write_img — universal image writer.
 *
 * Format is selected by substring match in filename:
 *   "png"/"PNG" -> PNG via libpng
 *   "tif"/"TIF" -> TIFF via libtiff
 *   "jpg"/"jpeg" -> JPEG via libjpeg (quality 90)
 *   "raw"       -> raw binary with optional append/seek support
 *   else        -> PGM (P5) or PPM (P6) Netpbm format
 *
 * For raw output, the extension can encode append mode:
 *   "file.raw+"      -> append to existing file
 *   "file.raw+NNN"   -> seek to byte offset NNN then write
 *   "file.-raw"      -> strip the extension, write headerless
 *
 * Returns 0 on success, -1 on failure.
 */
int write_img(char *fname, struct image *ip) {
	char hdr[100], *ext;
	int fd = -1, nw, rowbytes, color_type = 2; /* default PNG color: RGB */
	long qw, tqw = 0, want;

	/* NULL filename -> write to a default debug file */
if(!fname) { fname = "nullwrite.pgm"; Nswim_nullwrites++; }
	Nswim_writes++;

	/* --- PNG output --- */
	if(strstr(fname, "png") || strstr(fname, "PNG")) {
		int i;
		unsigned int transparent[256];
		png_structp png_ptr;
		png_infop info_ptr;
		png_bytep *row_ptr;
		png_color_16 gray_trans;
		png_color_8 sig_bit;
		FILE *fp = fopen(fname, "wb");
		if(!fp) {
			fprintf(stderr, "can't open %s for PNG write\n", fname);
			return(-1);
		}
		png_ptr = png_create_write_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
		info_ptr = png_create_info_struct(png_ptr);
		png_init_io(png_ptr, fp);

		if(ip->bpp == 1)
			color_type = PNG_COLOR_TYPE_GRAY;

		png_set_IHDR(png_ptr, info_ptr, ip->wid, ip->ht,
			8, color_type, PNG_INTERLACE_NONE,
			PNG_COMPRESSION_TYPE_BASE, PNG_FILTER_TYPE_BASE);

		/* Set up identity grayscale palette (not currently used) */
		for(i = 0; i < 256; i++)
			transparent[i] = 255;
		for(i = 0; i < 256; i++) {
			palette[i][0] = i;
			palette[i][1] = i;
			palette[i][2] = i;
		}

		/* Set single-value transparency if specified */
		if(ip->trans >= 0) {
			gray_trans.gray = ip->trans;
			png_set_tRNS(png_ptr, info_ptr, NULL, 0, &gray_trans);
		}
		png_write_info(png_ptr, info_ptr);

		/* Set up row pointers into our contiguous pixel buffer */
		row_ptr = (png_bytep *)malloc(sizeof(png_bytep)*ip->ht);
		if(1) {
			int y, rowlen = ip->wid*ip->bpp;
			for(y = 0; y < ip->ht; y++)
				row_ptr[y] = (png_byte *)&ip->pp[y*rowlen];
			png_write_image(png_ptr, row_ptr);
		}
		free(row_ptr);
		png_write_end(png_ptr, NULL);
		png_destroy_write_struct(&png_ptr, &info_ptr);
		fclose(fp);

	/* --- TIFF output via libtiff --- */
	} else if(strstr(fname, "tif") || strstr(fname, "TIF")) {
		TIFF *tif;
		int y;

		TIFFSetWarningHandler(NULL);
		if((tif = TIFFOpen(fname, "w")) == NULL) {
			fprintf(stderr, "Could not open output: %s\n", fname);
			return(-1);
		}

		/* Set required TIFF tags */
		TIFFSetField(tif, TIFFTAG_IMAGEWIDTH, ip->wid);
		TIFFSetField(tif, TIFFTAG_IMAGELENGTH, ip->ht);
		TIFFSetField(tif, TIFFTAG_BITSPERSAMPLE, 8);
		TIFFSetField(tif, TIFFTAG_SAMPLESPERPIXEL, ip->bpp);
		TIFFSetField(tif, TIFFTAG_PLANARCONFIG, PLANARCONFIG_CONTIG);

		if(ip->bpp == 3)
			TIFFSetField(tif, TIFFTAG_PHOTOMETRIC, PHOTOMETRIC_RGB);
		else
			TIFFSetField(tif, TIFFTAG_PHOTOMETRIC, PHOTOMETRIC_MINISBLACK);

		TIFFSetField(tif, TIFFTAG_ROWSPERSTRIP, 1);
		TIFFSetField(tif, TIFFTAG_COMPRESSION, COMPRESSION_NONE);

		/* Write one scanline at a time */
		for(y = 0; y < ip->ht; y++) {
			if(TIFFWriteScanline(tif, ip->pp + y*ip->wid*ip->bpp, y, 0) < 0) {
				fprintf(stderr, "Error writing TIFF scanline %d\n", y);
				TIFFClose(tif);
				return(-1);
			}
		}

		TIFFClose(tif);

	/* --- JPEG output via libjpeg (quality 90) --- */
	} else if(strstr(fname, "jpg") || strstr(fname, "JPG") || strstr(fname, "jpeg") || strstr(fname, "JPEG")) {
		int quality = 90;
		struct jpeg_compress_struct cinfo;
		struct jpeg_error_mgr jerr;
		FILE *outfile;
		JSAMPROW row_pointer[1];
		int row_stride;

		cinfo.err = jpeg_std_error(&jerr);
		jpeg_create_compress(&cinfo);
		if((outfile = fopen(fname, "wb")) == NULL) {
			fprintf(stderr, "can't open %s\n", fname);
			return(-1);
		}
		jpeg_stdio_dest(&cinfo, outfile);
		cinfo.image_width = ip->wid;
		cinfo.image_height = ip->ht;
		cinfo.input_components = ip->bpp;
		cinfo.in_color_space = JCS_GRAYSCALE;
		if(ip->bpp == 3)
			cinfo.in_color_space = JCS_RGB;
		jpeg_set_defaults(&cinfo);
		jpeg_set_quality(&cinfo, quality, TRUE);
		jpeg_start_compress(&cinfo, TRUE);
		row_stride = ip->wid * ip->bpp;
		/* Write scanlines one at a time */
		while(cinfo.next_scanline < cinfo.image_height) {
			unsigned char *image_buffer = ip->pp;
			row_pointer[0] =
				&image_buffer[cinfo.next_scanline * row_stride];
			(void) jpeg_write_scanlines(&cinfo, row_pointer, 1);
		}
		jpeg_finish_compress(&cinfo);
		fclose(outfile);
		jpeg_destroy_compress(&cinfo);

	/* --- Raw binary output with optional append/seek ---
	 * Supports special extension syntax:
	 *   "file.-raw"     -> strip extension, write headerless binary
	 *   "file.raw+"     -> append to end of existing file
	 *   "file.raw+NNN"  -> seek to byte offset NNN, then write */
	} else if((ext = strstr(fname, "raw"))) {
fprintf(stderr, "+++++ write raw %s  ext %s  %d %d  %d\n",
fname, ext-1, ip->wid, ip->ht, ip->bpp);
		/* Handle "-raw" convention: strip the extension from filename */
		if(*(ext-1) == '-') {
fprintf(stderr, "truncate fname %s\n", fname);
if(*(ext-2) == '.')
*(ext-2) = 0; /* clobber the dot to remove extension */
else fprintf(stderr, "NO EXTENSION DOT???\n");
		}
		/* Find '+' for append/seek mode */
		while(*ext && *ext != '+')
			ext++;
		if(*ext == '+') {
			off_t spos;
			fd = open(fname, O_RDWR);
			spos = lseek(fd, (off_t)0, SEEK_END);
fprintf(stderr, "fd %d reopening %s at end %ld\n", fd, fname, spos);
		}
        	if(fd < 0) {
                	fd = open(fname, O_CREAT|O_RDWR, 0666);
fprintf(stderr, "created new %s %d\n", fname, fd);
		}
		/* Seek to specific offset if specified after '+' */
		if(*ext == '+') {
			off_t seekpos = atoi(ext+1);
			if(seekpos > 0) {
				seekpos = lseek(fd, (off_t)seekpos, 0);
fprintf(stderr, "new seekpos %ld\n", seekpos);
			}
		}
		goto raw_pgm; /* share the write loop with PGM path */

	/* --- PGM/PPM Netpbm output (default fallback) --- */
	} else {
		fd = creat(fname, 0666);
		if(fd < 0) {
			fprintf(stderr, "pgm_creat err %s\n", fname);
			return(-1);
		}
		/* Write Netpbm header: P6 for RGB, P5 for grayscale */
		if(ip->bpp == 3)
			sprintf(hdr, "P6\n%d %d\n255\n", ip->wid, ip->ht);
		else if(ip->bpp == 2)
			sprintf(hdr, "P5\n%d %d\n65535\n", ip->wid, ip->ht);
		else
			sprintf(hdr, "P5\n%d %d\n255\n", ip->wid, ip->ht);
		nw = write(fd, hdr, strlen(hdr));

		/* Write pixel data in a loop to handle partial writes */
raw_pgm:
		want = ip->ht*(unsigned long)ip->wid*ip->bpp;
		while(tqw < want) {
			qw = write(fd, ip->pp+tqw, want-tqw);
			if(qw <= 0) {
				fprintf(stderr, "write_img %d exit tqw %ld/%ld\n",
					fd, qw, want);
				return(-1);
			}
			tqw += qw;
		}
fprintf(stderr, "close %d\n", fd);
		close(fd);
	}
	return(0);
}
