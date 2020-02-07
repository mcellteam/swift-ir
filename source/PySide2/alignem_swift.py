import sys
import os
import argparse
import cv2

import alignem
from alignem import IntField, BoolField, FloatField, CallbackButton, MainWindow

main_win = None

def align_all():
    alignem.print_debug ( 30, "Aligning All with SWiFT-IR ..." )

def align_forward():
    alignem.print_debug ( 30, "Aligning Forward with SWiFT-IR ..." )
    alignem.print_debug ( 70, "Control Model = " + str(control_model) )

def notyet():
    alignem.print_debug ( 0, "Function not implemented yet. Skip = " + str(skip.value) )

skip = BoolField("Skip",False)

control_model = [
  # Panes
  [ # Begin first pane of rows
    [ "Project File:" ],
    [ "Destination:" ],
    [ CallbackButton("Jump To:",notyet), IntField(None,1,1), 6*" ", skip, CallbackButton("Clear All Skips",notyet), CallbackButton("Auto Swim Align",notyet) ],
    [ FloatField("X:",1.1), 6*" ", FloatField("Y:",2.2), 6*" ", FloatField("Z:",3.3) ],
    [ FloatField("a:",1010), "   ", FloatField("b:",1011), "   ", FloatField("c:",1100), "   ",
      FloatField("d:",1101), "   ", FloatField("e:",1110), "   ", FloatField("f:",1111), "   " ],
    [ CallbackButton('Align All SWiFT', align_all), 6*" ", CallbackButton('Align Forward SWiFT',align_forward), 60*" ", IntField("# Forward",1) ]
  ] # End first pane
]


if __name__ == "__main__":
    global main_win

    alignem.debug_level = 20

    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False)
    args = options.parse_args()
    if args.debug != None:
      alignem.debug_level = args.debug

    main_win = alignem.MainWindow ( control_model=control_model, title="Align SWiFT-IR" )

    alignem.print_debug ( 30, "================= Defining Roles =================" )
    main_win.define_roles ( ['ref','src','align'] )

    alignem.print_debug ( 30, "================= Importing Images =================" )
    ref_image_stack = [ None,
                        "vj_097_shift_rot_skew_crop_1k1k_1.jpg",
                        "vj_097_shift_rot_skew_crop_1k1k_2.jpg",
                        "vj_097_shift_rot_skew_crop_1k1k_3.jpg",
                        "vj_097_shift_rot_skew_crop_1k1k_4.jpg",
                        "vj_097_shift_rot_skew_crop_1k1k_5.jpg",
                        "vj_097_shift_rot_skew_crop_1k1k_6.jpg" ]

    src_image_stack = [ "vj_097_shift_rot_skew_crop_1k1k_1.jpg",
                        "vj_097_shift_rot_skew_crop_1k1k_2.jpg",
                        "vj_097_shift_rot_skew_crop_1k1k_3.jpg",
                        "vj_097_shift_rot_skew_crop_1k1k_4.jpg",
                        "vj_097_shift_rot_skew_crop_1k1k_5.jpg",
                        "vj_097_shift_rot_skew_crop_1k1k_6.jpg",
                        "vj_097_shift_rot_skew_crop_1k1k_7.jpg" ]

    aln_image_stack = [ "aligned/vj_097_shift_rot_skew_crop_1k1k_1a.jpg",
                        "aligned/vj_097_shift_rot_skew_crop_1k1k_2a.jpg",
                        "aligned/vj_097_shift_rot_skew_crop_1k1k_3a.jpg",
                        "aligned/vj_097_shift_rot_skew_crop_1k1k_4a.jpg",
                        "aligned/vj_097_shift_rot_skew_crop_1k1k_5a.jpg",
                        "aligned/vj_097_shift_rot_skew_crop_1k1k_6a.jpg",
                        "aligned/vj_097_shift_rot_skew_crop_1k1k_7a.jpg" ]

    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    main_win.load_images_in_role ( 'ref', ref_image_stack )
    main_win.load_images_in_role ( 'src', src_image_stack )
    main_win.load_images_in_role ( 'align', aln_image_stack )

    alignem.run_app(main_win)

