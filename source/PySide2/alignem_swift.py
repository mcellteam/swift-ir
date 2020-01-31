import sys
import os
import argparse
import cv2

import alignem
from alignem import IntField, BoolField, FloatField, CallbackButton, MainWindow

def align_all():
    print ( "Aligning All with SWiFT-IR ..." )

def align_forward():
    print ( "Aligning Forward with SWiFT-IR ..." )
    print ( "Control Model = " + str(control_model) )

def notyet():
    print ( "Function not implemented yet." )

skip = BoolField("Skip",False)

control_model = [
  # Panes
  [ # Begin first pane of rows
    [ "Project File:" ],
    [ "Destination:" ],
    [ CallbackButton("Jump To:",notyet), IntField(None,1), 6*" ", skip, CallbackButton("Clear All Skips",notyet), CallbackButton("Auto Swim Align",notyet) ],
    [ FloatField("X:",1.1), 6*" ", FloatField("Y:",2.2), 6*" ", FloatField("Z:",3.3) ],
    [ FloatField("a:",1010), "   ", FloatField("b:",1011), "   ", FloatField("c:",1100), "   ",
      FloatField("d:",1101), "   ", FloatField("e:",1110), "   ", FloatField("f:",1111), "   " ],
    [ CallbackButton('Align All SWiFT', align_all), 6*" ", CallbackButton('Align Forward SWiFT',align_forward), 60*" ", IntField("# Forward",1) ]
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

