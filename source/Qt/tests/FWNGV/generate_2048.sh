rm -f test01.jpg
rm -f test02.jpg
rm -f test03.jpg
rm -f test04.jpg
rm -f test05.jpg
rm -f test06.jpg
rm -f test07.jpg
rm -f test08.jpg
rm -f test09.jpg
rm -f test10.jpg
rm -f test11.jpg
rm -f test12.jpg
rm -f test13.jpg
rm -f test14.jpg
rm -f test15.jpg
rm -f test16.jpg
rm -f test17.jpg
rm -f test18.jpg
rm -f test19.jpg
rm -f test20.jpg
convert -distort SRT '1  0' -transform FWNGV.1.jpg -crop 2046x2046+1024+1024 -transform test01.jpg
convert -distort SRT '1  3' -transform FWNGV.1.jpg -crop 2046x2046+850+1024  -transform test02.jpg
convert -distort SRT '1 -1' -transform FWNGV.1.jpg -crop 2046x2046+950+900   -transform test03.jpg
convert -distort SRT '1 -5' -transform FWNGV.1.jpg -crop 2046x2046+1050+800  -transform test04.jpg
convert -distort SRT '1 -2' -transform FWNGV.1.jpg -crop 2046x2046+1070+700  -transform test05.jpg
convert -distort SRT '1  3' -transform FWNGV.1.jpg -crop 2046x2046+1040+900  -transform test06.jpg
convert -distort SRT '1  6' -transform FWNGV.1.jpg -crop 2046x2046+1030+1010 -transform test07.jpg
convert -distort SRT '1  2' -transform FWNGV.1.jpg -crop 2046x2046+1060+1030 -transform test08.jpg
convert -distort SRT '1 -1' -transform FWNGV.1.jpg -crop 2046x2046+1050+1040 -transform test09.jpg
convert -distort SRT '1  3' -transform FWNGV.1.jpg -crop 2046x2046+1045+1045 -transform test10.jpg
convert -distort SRT '1  1' -transform FWNGV.1.jpg -crop 2046x2046+1024+1020 -transform test11.jpg
convert -distort SRT '1  2' -transform FWNGV.1.jpg -crop 2046x2046+950+1030  -transform test12.jpg
convert -distort SRT '1 -2' -transform FWNGV.1.jpg -crop 2046x2046+900+1045  -transform test13.jpg
convert -distort SRT '1 -6' -transform FWNGV.1.jpg -crop 2046x2046+1010+1025 -transform test14.jpg
convert -distort SRT '1 -3' -transform FWNGV.1.jpg -crop 2046x2046+1033+1047 -transform test15.jpg
convert -distort SRT '1  2' -transform FWNGV.1.jpg -crop 2046x2046+1052+1055 -transform test16.jpg
convert -distort SRT '1  1' -transform FWNGV.1.jpg -crop 2046x2046+1060+1070 -transform test17.jpg
convert -distort SRT '1  8' -transform FWNGV.1.jpg -crop 2046x2046+1070+1051 -transform test18.jpg
convert -distort SRT '1  4' -transform FWNGV.1.jpg -crop 2046x2046+1038+1038 -transform test19.jpg
convert -distort SRT '1  1' -transform FWNGV.1.jpg -crop 2046x2046+1045+1045 -transform test20.jpg

