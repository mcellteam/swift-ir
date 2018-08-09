all: swim iavg iscale mir remod

swim: swim.c swimio.h debug.h makefile
	gcc -Wno-implicit -o swim -O3 -m64 -msse3 swim.c -ltiff -ljpeg -lpng -lfftw3f -lm

iavg: iavg.c swimio.h debug.h makefile
	gcc -Wno-implicit -O -o iavg iavg.c -ljpeg -ltiff -lpng

iscale: iscale.c swimio.h debug.h makefile
	gcc -Wno-implicit -O3 -o iscale iscale.c -ljpeg -ltiff -lpng

mir: mir.c swimio.h debug.h makefile
	gcc -Wno-implicit -O3 -o mir mir.c -ljpeg -ltiff -lpng -lm

remod: remod.c swimio.h debug.h makefile
	gcc -Wno-implicit -O3 -o remod remod.c -lfftw3f -ltiff -ljpeg -lpng -lm

sha1sum.txt: swim
	sha1sum swim > sha1sum.txt
	sha1sum swim >> sha1sum.txt

clean:
	rm -f swim iavg iscale mir remod
	rm -f *.jar
	rm -f *.class
	rm -f *.o
	rm -f swim
	rm -f a.out
	rm -f *~

