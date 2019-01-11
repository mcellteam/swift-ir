all: swim iavg iscale mir remod run_swift.jar sha1sum.txt

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

run_swift.jar: run_swift.java makefile
	javac -nowarn -source 1.6 run_swift.java
	jar -cfe run_swift.jar run_swift *.class

sha1sum.txt: swim iavg iscale mir remod run_swift.jar
	sha1sum swim > sha1sum.txt
	sha1sum iavg >> sha1sum.txt
	sha1sum iscale >> sha1sum.txt
	sha1sum mir >> sha1sum.txt
	sha1sum remod >> sha1sum.txt
	sha1sum run_swift.jar >> sha1sum.txt

clean:
	rm -f swim iavg iscale mir remod
	rm -f *.jar
	rm -f *.class
	rm -f *.o
	rm -f a.out
	rm -f *~

