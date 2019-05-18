all: swim mir makefile
	@echo "Copying swim"
	cp ../source/swim swim
	@echo "Copying mir"
	cp ../source/mir mir

tests:
	@echo "Copying swim"
	cp ../source/swim swim
	@echo "Copying mir"
	cp ../source/mir mir
	sh run_swim_mir.sh

clean:
	rm -f best.JPG
	rm -f keep.JPG
	rm -f mir_first_out.JPG
	rm -f mir_second_out.JPG
	rm -f mir_third_out.jpg
	rm -f newtarg.JPG

cleanall:
	rm -f best.JPG
	rm -f keep.JPG
	rm -f mir_first_out.JPG
	rm -f mir_second_out.JPG
	rm -f mir_third_out.jpg
	rm -f newtarg.JPG
	rm -f mir_first_stderr.txt
	rm -f mir_first_stdout.txt
	rm -f mir_second_stderr.txt
	rm -f mir_second_stdout.txt
	rm -f mir_third_stderr.txt
	rm -f mir_third_stdout.txt
	rm -f swim_first_stderr.txt
	rm -f swim_first_stdout.txt
	rm -f swim_fourth_stderr.txt
	rm -f swim_fourth_stdout.txt
	rm -f swim_second_stderr.txt
	rm -f swim_second_stdout.txt
	rm -f swim_third_stderr.txt
	rm -f swim_third_stdout.txt

