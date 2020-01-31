import sys
import os
import argparse
import cv2

import alignem

def align_forward():
    print ( "Aligning Forward with SWiFT-IR ..." )

control_model = [
  # Panes
  [ # Begin first pane
    # Rows
    [ # Begin first row
      # Items
      "File Name: junk.txt",  # A string by itself is just a label
      "Layer: 5"  # A string by itself is just a label
    ], # End first row
    [ # Begin second row
      # Items
      "X:",  1.1,
      "      ",
      "Y: ", 2.2,
      "      ",
      "Z: ", 3.3
    ], # End second row
    [ # Begin third row
      # Items
      "a: ", 1010,
      "      ",
      "b: ", 1011,
      "      ",
      "c: ", 1100,
      "      ",
      "d: ", 1101,
      "      ",
      "e: ", 1110,
      "      ",
      "f: ", 1111
    ], # End third row
    [ # Begin fourth row
      # Items
      ['Align All'],
      "      ",
      alignem.CallbackButton('Align Forward SWiFT', align_forward),
      "      ",
      "# Forward", 1
    ] # End fourth row
  ] # End first pane
]


if __name__ == "__main__":
    # global app  # global isn't needed here ... because the "if" doesn't create a new scope (unlike many other languages)

    options = argparse.ArgumentParser()
    options.add_argument("-f", "--file", type=str, required=False)
    args = options.parse_args()
    fname = args.file

    main_win = alignem.MainWindow(control_model=control_model)
    alignem.run_app(main_win)

