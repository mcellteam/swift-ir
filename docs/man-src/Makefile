ALL: BUILD MAN HTML

BUILD:; mkdir -p ../build

MAN: ../build/mir.1 ../build/iscale.1 ../build/iavg.1 \
	../build/remod.1 ../build/swim.1
HTML: ../build/mir.1.html ../build/iscale.1.html ../build/iavg.1.html \
	../build/remod.1.html ../build/swim.1.html

../build/%.1: %.1.txt
	a2x --doctype manpage --format manpage --no-xmllint \
		--destination-dir=../build $<

../build/%.1.html: %.1.txt
	a2x --doctype manpage --format xhtml --no-xmllint \
		--destination-dir=../build $<

