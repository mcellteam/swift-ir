#!/bin/sh

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

$SCRIPT_DIR/bin_darwin/swim $1 -k fpat000.pgm -t newtarg.pgm -b best.pgm ${@:2}
