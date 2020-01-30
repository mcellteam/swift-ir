import sys
import os
import argparse
import cv2

import alignem


if __name__ == "__main__":
    # global app  # global isn't needed here ... because the "if" doesn't create a new scope (unlike many other languages)

    options = argparse.ArgumentParser()
    options.add_argument("-f", "--file", type=str, required=False)
    args = options.parse_args()
    fname = args.file

    alignem.run_app(fname)

