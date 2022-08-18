all: test_libs swim iavg iscale mir remod remod_old sxox json_parser.jar ImageAlign.jar run_swift.jar swift_gui.jar swim_lab.jar sha1sum.txt

test_libs: test_libs.c swimio.h debug.h makefile
	gcc -Wno-implicit -o test_libs -O3 -m64 -msse3 test_libs.c -ltiff -ljpeg -lpng -lfftw3f -lm

swim: swim.c swimio.h debug.h makefile
	gcc -Wno-implicit -o swim -O3 -m64 -msse3 swim.c -ltiff -ljpeg -lpng -lfftw3f -lm

iavg: iavg.c swimio.h debug.h makefile
	gcc -Wno-implicit -O -o iavg iavg.c -ljpeg -ltiff -lpng

iscale: iscale.c swimio.h debug.h makefile
	gcc -Wno-implicit -O3 -o iscale iscale.c -ljpeg -ltiff -lpng

# Detect OS to set an explicit stack size for Windows
ifeq ($(OS),Windows_NT)  # 2000, XP, Vista, 7, 10 according to stackoverflow.com/questions/714100/os-detecting-makefile
OSOPTS := -O3 -Wl,--stack,0x1000000
else
OSOPTS := -O3
endif

mir: mir.c swimio.h debug.h makefile
	gcc -Wno-implicit $(OSOPTS) -o mir mir.c -ljpeg -ltiff -lpng -lm


# These failed in Windows:

#mir: mir.c swimio.h debug.h makefile
#	gcc -Wno-implicit -O3 -Wl,--stack,0x100000 -o mir mir.c -ljpeg -ltiff -lpng -lm

#mir: mir.c swimio.h debug.h makefile
#	gcc -Wno-implicit -O3 -Wl,--stack,0x200000 -o mir mir.c -ljpeg -ltiff -lpng -lm


# All of these worked in Windows:

#mir: mir.c swimio.h debug.h makefile
#	gcc -Wno-implicit -O3 -Wl,--stack,0x400000 -o mir mir.c -ljpeg -ltiff -lpng -lm

#mir: mir.c swimio.h debug.h makefile
#	gcc -Wno-implicit -O3 -Wl,--stack,0x800000 -o mir mir.c -ljpeg -ltiff -lpng -lm

#mir: mir.c swimio.h debug.h makefile
#	gcc -Wno-implicit -O3 -Wl,--stack,16777216 -o mir mir.c -ljpeg -ltiff -lpng -lm

#mir: mir.c swimio.h debug.h makefile
#	gcc -Wno-implicit -O3 -Wl,--stack,0x1000000 -o mir mir.c -ljpeg -ltiff -lpng -lm

#mir: mir.c swimio.h debug.h makefile
#	gcc -Wno-implicit -O3 -Wl,--stack,0x10000000 -o mir mir.c -ljpeg -ltiff -lpng -lm

#mir: mir.c swimio.h debug.h makefile
#	gcc -Wno-implicit -ggdb -Og -fstack-check -fstack-protector-all -fstack-protector-strong -fconserve-stack  -c -o mir.o mir.c
#	gcc -Wno-implicit -ggdb -Og -fstack-check -fstack-protector-all -fstack-protector-strong -fconserve-stack --stack,0x100000000 -o mir mir.o -ljpeg -ltiff -lpng -lm



remod: remod.c swimio.h debug.h makefile
	gcc -Wno-implicit -O3 -o remod remod.c -lfftw3f -ltiff -ljpeg -lpng -lm

remod_old: remod_old.c swimio.h debug.h makefile
	gcc -Wno-implicit -O3 -o remod_old remod_old.c -lfftw3f -ltiff -ljpeg -lpng -lm

sxox: sxox.c makefile
	gcc -Wno-implicit -O3 -o sxox sxox.c -lm

# "Normal" rule for run_swift.jar
run_swift.jar: run_swift.java revision.java makefile
	javac -nowarn -source 1.6 -target 1.6 run_swift.java
	jar -cfe run_swift.jar run_swift *.class

# "Fixed Date" rule for run_swift.jar that produces a consistent jar file the same for each compilation
#run_swift.jar: run_swift.java makefile
#	rm -f *.class
#	mkdir -p META-INF
#	cp -f run_swift.MF META-INF/MANIFEST.MF
#	javac -nowarn -source 1.6 run_swift.java
#	touch -t 201901181818 *.class
#	touch -t 201901181818 META-INF/MANIFEST.MF
#	zip -X run_swift.jar META-INF/MANIFEST.MF *.class

# "Normal" rule for swim_lab.jar
swim_lab.jar: swim_lab.java ZoomPanLib.java run_swift.java json_parser.java revision.java makefile
	rm -f *.class
	javac -nowarn -source 1.6 -target 1.6 swim_lab.java
	jar -cfe swim_lab.jar swim_lab *.class

# "Normal" rule for swift_gui.jar
swift_gui.jar: swift_gui.java ZoomPanLib.java run_swift.java json_parser.java revision.java makefile
	rm -f *.class
	javac -nowarn -source 1.6 -target 1.6 swift_gui.java
	jar -cfe swift_gui.jar swift_gui *.class

# "Normal" rule for ImageAlign.jar
ImageAlign.jar: ImageAlign.java ZoomPanLib.java run_swift.java json_parser.java revision.java makefile
	rm -f *.class
	javac -nowarn -source 1.6 -target 1.6 ImageAlign.java
	jar -cfe ImageAlign.jar ImageAlign *.class

# "Fixed Date" rule for swift_gui.jar that produces a consistent jar file the same for each compilation
#swift_gui.jar: swift_gui.java ZoomPanLib.java run_swift.java json_parser.java makefile
#	rm -f *.class
#	mkdir -p META-INF
#	cp -f swift_gui.MF META-INF/MANIFEST.MF
#	javac -nowarn -source 1.6 swift_gui.java
#	touch -t 201901181818 *.class
#	touch -t 201901181818 META-INF/MANIFEST.MF
#	zip -X swift_gui.jar META-INF/MANIFEST.MF *.class

json_parser.jar: json_parser.java makefile
	javac -nowarn -source 1.6 -target 1.6 json_parser.java
	jar -cfe json_parser.jar json_parser *.class

swift_lin.jar: swift_gui.jar makefile swim iavg iscale mir remod
	javac -nowarn -source 1.6 run_swift.java
	javac -nowarn -source 1.6 swift_gui.java
	jar -cfe swift_lin.jar swift_gui *.class swim iavg iscale mir remod

swift_win.jar: swift_gui.jar makefile swim.exe iavg.exe iscale.exe mir.exe remod.exe
	javac -nowarn -source 1.6 run_swift.java
	javac -nowarn -source 1.6 swift_gui.java
	jar -cfe swift_win.jar swift_gui *.class swim.exe iavg.exe iscale.exe mir.exe remod.exe cygfftw3f-3.dll cygjbig-2.dll cygjpeg-8.dll cyglzma-5.dll cygpng12.dll cygpng16-16.dll cygtiff-6.dll cygwin1.dll cygz.dll

bundle: swift_gui.jar run_swift.jar
	git bundle create ../swift_windows_bundle.dat master windows

sha1sum.txt: swim iavg iscale mir remod run_swift.jar swift_gui.jar
	sha1sum swim > sha1sum.txt
	sha1sum iavg >> sha1sum.txt
	sha1sum iscale >> sha1sum.txt
	sha1sum mir >> sha1sum.txt
	sha1sum remod >> sha1sum.txt
	sha1sum run_swift.jar >> sha1sum.txt
	sha1sum swift_gui.jar >> sha1sum.txt
#sha1sum pyswift_gui.py >> sha1sum.txt
#sha1sum app_window.py >> sha1sum.txt

rev:
	git log --pretty=format:"public class revision { static String githash=\"%H on %ad\"; }" HEAD^..HEAD > revision.java

clean:
	rm -f swim iavg iscale mir remod sxox test_libs
	rm -f *.jar
	rm -f *.class
	rm -f *.o
	rm -f a.out
	rm -f *~

