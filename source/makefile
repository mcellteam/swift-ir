all: swim iavg iscale mir remod sxox json_parser.jar run_swift.jar swift_gui.jar sha1sum.txt

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

sxox: sxox.c makefile
	gcc -Wno-implicit -O3 -o sxox sxox.c -lm

# "Normal" rule for run_swift.jar
#run_swift.jar: run_swift.java makefile
#	javac -nowarn -source 1.6 run_swift.java
#	jar -cfe run_swift.jar run_swift *.class

# "Fixed Date" rule for run_swift.jar that produces a consistent jar file the same for each compilation
run_swift.jar: run_swift.java makefile
	rm -f *.class
	mkdir -p META-INF
	cp -f run_swift.MF META-INF/MANIFEST.MF
	javac -nowarn -source 1.6 run_swift.java
	touch -t 201901181818 *.class
	touch -t 201901181818 META-INF/MANIFEST.MF
	zip -X run_swift.jar META-INF/MANIFEST.MF *.class

# "Fixed Date" rule for swift_gui.jar that produces a consistent jar file the same for each compilation
swift_gui.jar: swift_gui.java ZoomPanLib.java run_swift.java json_parser.java makefile
	rm -f *.class
	mkdir -p META-INF
	cp -f swift_gui.MF META-INF/MANIFEST.MF
	javac -nowarn -source 1.6 swift_gui.java
	touch -t 201901181818 *.class
	touch -t 201901181818 META-INF/MANIFEST.MF
	zip -X swift_gui.jar META-INF/MANIFEST.MF *.class

json_parser.jar: json_parser.java makefile
	javac -nowarn -source 1.6 json_parser.java
	jar -cfe json_parser.jar json_parser *.class

sha1sum.txt: swim iavg iscale mir remod run_swift.jar swift_gui.jar
	sha1sum swim > sha1sum.txt
	sha1sum iavg >> sha1sum.txt
	sha1sum iscale >> sha1sum.txt
	sha1sum mir >> sha1sum.txt
	sha1sum remod >> sha1sum.txt
	sha1sum run_swift.jar >> sha1sum.txt
	sha1sum swift_gui.jar >> sha1sum.txt

clean:
	rm -f swim iavg iscale mir remod sxox
	rm -f *.jar
	rm -f *.class
	rm -f *.o
	rm -f a.out
	rm -f *~

