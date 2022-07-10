echo "Running tests"
echo "  First Swim"
sh swim_first.sh 2> swim_first_stderr.txt 1> swim_first_stdout.txt
echo "  Second Swim"
sh swim_second.sh 2> swim_second_stderr.txt 1> swim_second_stdout.txt
echo "  First Mir"
sh mir_first.sh 2> mir_first_stderr.txt 1> mir_first_stdout.txt
echo "  Third Swim"
sh swim_third.sh 2> swim_third_stderr.txt 1> swim_third_stdout.txt
echo "  Second Mir"
sh mir_second.sh 2> mir_second_stderr.txt 1> mir_second_stdout.txt
echo "  Fourth Swim"
sh swim_fourth.sh 2> swim_fourth_stderr.txt 1> swim_fourth_stdout.txt
echo "  Third Mir"
sh mir_third.sh 2> mir_third_stderr.txt 1> mir_third_stdout.txt
echo "Done tests"

