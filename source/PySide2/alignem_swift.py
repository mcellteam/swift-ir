import sys, traceback
import os
import argparse
import cv2
import copy

import json

import shutil

import alignem
from alignem import IntField, BoolField, FloatField, CallbackButton, MainWindow

from PySide2.QtWidgets import QInputDialog

import pyswift_tui
import align_swiftir

main_win = None

project_data = None

swift_roles = ['ref','base','aligned']

def print_exception():
    exi = sys.exc_info()
    print ( "  Exception type = " + str(exi[0]) )
    print ( "  Exception value = " + str(exi[1]) )
    print ( "  Exception trace = " + str(exi[2]) )
    print ( "  Exception traceback:" )
    traceback.print_tb(exi[2])


def generate_scales ():
    print ( "generate_scales inside alignem_swift called" )

    image_scales_to_run = [ alignem.get_scale_val(s) for s in sorted(alignem.project_data['data']['scales'].keys()) ]

    alignem.print_debug ( 40, "Create images at all scales: " + str ( image_scales_to_run ) )

    if (alignem.project_data['data']['destination_path'] == None) or (len(alignem.project_data['data']['destination_path']) <= 0):

      alignem.show_warning ( "Note", "Scales can not be generated without a destination (use File/Set Destination)" )

    else:

      for scale in image_scales_to_run:

        alignem.print_debug ( 70, "Creating images for scale " + str(scale) )

        scale_key = str(scale)
        if not 'scale_' in scale_key:
          scale_key = 'scale_' + scale_key

        subdir_path = os.path.join(alignem.project_data['data']['destination_path'],scale_key)
        scale_1_path = os.path.join(alignem.project_data['data']['destination_path'],'scale_1')

        alignem.print_debug ( 70, "Creating a subdirectory named " + subdir_path )
        try:
          os.mkdir ( subdir_path )
        except:
          # This catches directories that already exist
          pass
        src_path = os.path.join(subdir_path,'img_src')
        alignem.print_debug ( 70, "Creating source subsubdirectory named " + src_path )
        try:
          os.mkdir ( src_path )
        except:
          # This catches directories that already exist
          pass
        aligned_path = os.path.join(subdir_path,'img_aligned')
        alignem.print_debug ( 70, "Creating aligned subsubdirectory named " + aligned_path )
        try:
          os.mkdir ( aligned_path )
        except:
          # This catches directories that already exist
          pass

        for layer in alignem.project_data['data']['scales'][scale_key]['alignment_stack']:
          # Remove previously aligned images from panel ??

          # Copy (or link) the source images to the expected scale_key"/img_src" directory
          for role in layer['images'].keys():

            base_file_name = layer['images'][role]['filename']
            if base_file_name != None:
              if len(base_file_name) > 0:
                abs_file_name = os.path.abspath(base_file_name)
                bare_file_name = os.path.split(abs_file_name)[1]
                destination_path = os.path.abspath ( alignem.project_data['data']['destination_path'] )
                outfile_name = os.path.join(destination_path, scale_key, 'img_src', bare_file_name)
                if scale == 1:
                  try:
                    alignem.print_debug ( 101, "UnLinking " + outfile_name )
                    os.unlink ( outfile_name )
                  except:
                    alignem.print_debug ( 101, "Error UnLinking " + outfile_name )
                  try:
                    alignem.print_debug ( 70, "Linking from " + abs_file_name + " to " + outfile_name )
                    os.symlink ( abs_file_name, outfile_name )
                  except:
                    alignem.print_debug ( 1, "Error Linking from " + abs_file_name + " to " + outfile_name )
                    print_exception()
                else:
                  try:
                    # Do the scaling
                    alignem.print_debug ( 70, "Copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale) )

                    if os.path.split ( os.path.split ( os.path.split ( abs_file_name )[0] )[0] )[1].startswith('scale_'):
                      # Convert the source from whatever scale is currently processed to scale_1
                      p,f = os.path.split(abs_file_name)
                      p,r = os.path.split(p)
                      p,s = os.path.split(p)
                      abs_file_name = os.path.join ( p, 'scale_1', r, f )

                    img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage(abs_file_name), fac=scale )
                    align_swiftir.swiftir.saveImage ( img, outfile_name )
                    # Change the base image for this scale to the new file
                    layer['images'][role]['filename'] = outfile_name
                  except:
                    alignem.print_debug ( 1, "Error copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale) )
                    print_exception()


def align_all():
    alignem.print_debug ( 30, "Aligning All with SWiFT-IR ..." )

    code_mode = 'python'

    ### All of this code is just trying to find the right menu item for the Use C Version check box:
    ###   It would be better if such options were created in the menu bar by this subclass of alignem.
    menubar = alignem.main_window.menu
    menubar_items = [ menubar.children()[x].title() for x in range(len(menubar.children())) if 'title' in dir(menubar.children()[x]) ]
    submenus = [ menubar.children()[x] for x in range(len(menubar.children())) if 'title' in dir(menubar.children()[x]) ]
    print ( "Menubar contains: " + str(menubar_items) )
    setmenu_index = -1
    for m in menubar_items:
      if "Set" in m:
        setmenu_index = menubar_items.index(m)
    print ( "Set menu is item " + str(setmenu_index) )
    if setmenu_index >= 0:
      set_menu = submenus[setmenu_index]
      set_menu_actions = set_menu.actions()
      use_c_version = None
      for action in set_menu_actions:
        if "Use C Version" in action.text():
          use_c_version = action
          break
      if use_c_version != None:
        if use_c_version.isChecked():
          code_mode = "c"

    # Check that there is a place to put the aligned images
    if (alignem.project_data['data']['destination_path'] == None) or len(alignem.project_data['data']['destination_path']) <= 0:

      alignem.print_debug ( 1, "Error: Cannot align without destination set (use File/Set Destination)" )
      alignem.show_warning ( "Note", "Projects can not be aligned without a destination (use File/Set Destination)" )

    else:

      alignem.print_debug ( 10, "Aligning with output in " + alignem.project_data['data']['destination_path'] )
      scale_to_run_text = alignem.project_data['data']['current_scale']
      alignem.print_debug ( 10, "Aligning scale " + str(scale_to_run_text) )

      # Create the expected directory structure for pyswift_tui.py
      source_dir = os.path.join ( alignem.project_data['data']['destination_path'], scale_to_run_text, "img_src" )
      alignem.makedirs_exist_ok ( source_dir, exist_ok=True )
      target_dir = os.path.join ( alignem.project_data['data']['destination_path'], scale_to_run_text, "img_aligned" )
      alignem.makedirs_exist_ok ( target_dir, exist_ok=True )

      # Create links or copy files in the expected directory structure
      # os.symlink(src, dst, target_is_directory=False, *, dir_fd=None)
      stack_at_this_scale = alignem.project_data['data']['scales'][scale_to_run_text]['alignment_stack']
      for layer in stack_at_this_scale:
        image_name = None
        if 'base' in layer['images'].keys():
          image = layer['images']['base']
          try:
            image_name = os.path.basename(image['filename'])
            destination_image_name = os.path.join(source_dir,image_name)
            shutil.copyfile(image.image_file_name, destination_image_name)
          except:
            pass

      # Copy the data model for this project to add local fields
      dm = copy.deepcopy ( alignem.project_data )
      # Add fields needed for SWiFT:
      stack_at_this_scale = dm['data']['scales'][scale_to_run_text]['alignment_stack']
      for layer in stack_at_this_scale:
        layer['align_to_ref_method']['method_data']['bias_x_per_image'] = 0.0
        layer['align_to_ref_method']['method_data']['bias_y_per_image'] = 0.0
        layer['align_to_ref_method']['selected_method'] = 'Auto Swim Align'

      # Run the project via pyswift_tui
      #                              dm,   align_opt,  scale_done,      use_scale,                        scale_tbd, swiftir_code_mode
      pyswift_tui.run_json_project ( dm, 'init_affine',    0,   alignem.get_scale_val(scale_to_run_text),      0,        code_mode )

      # Load the alignment stack after the alignment has completed
      aln_image_stack = []
      stack_at_this_scale = alignem.project_data['data']['scales'][scale_to_run_text]['alignment_stack']

      for layer in stack_at_this_scale:

        image_name = None
        if 'base' in layer['images'].keys():
          image_name = layer['images']['base']['filename']

        # Convert from the base name to the standard aligned name:
        aligned_name = None
        if image_name != None:
          # The first scale is handled differently now, but it might be better to unify if possible
          if scale_to_run_text == "scale_1":
            aligned_name = os.path.join ( os.path.abspath(alignem.project_data['data']['destination_path']), scale_to_run_text, 'img_aligned', os.path.split(image_name)[-1] )
          else:
            name_parts = os.path.split(image_name)
            if len(name_parts) >= 2:
              aligned_name = os.path.join ( os.path.split(name_parts[0])[0], os.path.join('img_aligned', name_parts[1]) )
        aln_image_stack.append ( aligned_name )
        alignem.print_debug ( 30, "Adding aligned image " + aligned_name )
        layer['images']['aligned'] = {}
        layer['images']['aligned']['filename'] = aligned_name
      try:
        main_win.load_images_in_role ( 'aligned', aln_image_stack )
      except:
        alignem.print_debug ( 1, "Error from main_win.load_images_in_role." )
        print_exception()
        pass


def align_forward():
    alignem.print_debug ( 30, "Aligning Forward with SWiFT-IR ..." )
    alignem.print_debug ( 70, "Control Model = " + str(control_model) )

def remove_aligned():
    alignem.print_debug ( 30, "Removing aligned images ..." )

    delete_list = []

    for layer in alignem.project_data['data']['scales'][alignem.current_scale]['alignment_stack']:
      if 'aligned' in layer['images'].keys():
        delete_list.append ( layer['images']['aligned']['filename'] )
        layer['images'].pop('aligned')

    alignem.image_library.remove_all_images()

    for fname in delete_list:
      if fname != None:
        if os.path.exists(fname):
          os.remove(fname)
          alignem.image_library.remove_image_reference ( fname )

    main_win.update_panels()


def method_debug():
    print ( "In Method debug for " + str(__name__) )
    __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

def notyet():
    alignem.print_debug ( 0, "Function not implemented yet. Skip = " + str(skip.value) )


gen_scales_cb = CallbackButton('GenScales', generate_scales)
align_all_cb  = CallbackButton('Align All SWiFT', align_all)
align_fwd_cb  = CallbackButton('Align Forward SWiFT', align_all)
num_fwd       = IntField("#",1,1)
rem_algn_cb   = CallbackButton('Remove Aligned', remove_aligned)
skip          = BoolField("Skip",False)
debug_cb      = CallbackButton('SWIFT Debug', method_debug)

control_model = [
  # Panes
  [ # Begin first pane of rows
    [ gen_scales_cb, align_all_cb, align_fwd_cb, num_fwd, rem_algn_cb, "         ", skip, debug_cb ]
  ] # End first pane
]


if __name__ == "__main__":

    alignem.debug_level = 20

    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False, help="Print more information with larger DEBUG (0 to 100)")
    options.add_argument("-t", "--test", type=int, required=False, help="Run test case: TEST")
    args = options.parse_args()

    test_option = 0
    if args.debug != None:
      alignem.debug_level = args.debug
    try:
      if args.debug != None:
        alignem.debug_level = int(args.debug)
    except:
        pass
    try:
      if args.test != None:
        test_option = int(args.test)
    except:
        pass

    main_win = alignem.MainWindow ( control_model=control_model, title="Align SWiFT-IR" )
    #main_win.register_project_open ( open_json_project )
    #main_win.register_project_save ( save_json_project )
    #main_win.register_gen_scales ( generate_scales )

    alignem.print_debug ( 30, "================= Defining Roles =================" )

    main_win.define_roles ( swift_roles )

    if test_option in [ 1, 2 ]:
        # Import test images

        alignem.print_debug ( 30, "================= Importing Images =================" )

        ref_image_stack = [ None,
                            "vj_097_shift_rot_skew_crop_1k1k_1.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_2.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_3.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_4.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_5.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_6.jpg" ]
        try:
          main_win.load_images_in_role ( 'ref', ref_image_stack )
        except:
          pass

        src_image_stack = [ "vj_097_shift_rot_skew_crop_1k1k_1.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_2.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_3.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_4.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_5.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_6.jpg",
                            "vj_097_shift_rot_skew_crop_1k1k_7.jpg" ]
        try:
          main_win.load_images_in_role ( 'base', src_image_stack )
        except:
          pass

        if test_option == 2:
            aln_image_stack = [ os.path.join("output","scale_1","img_aligned","vj_097_shift_rot_skew_crop_1k1k_1.jpg"),
                                os.path.join("output","scale_1","img_aligned","vj_097_shift_rot_skew_crop_1k1k_2.jpg"),
                                os.path.join("output","scale_1","img_aligned","vj_097_shift_rot_skew_crop_1k1k_3.jpg"),
                                os.path.join("output","scale_1","img_aligned","vj_097_shift_rot_skew_crop_1k1k_4.jpg"),
                                os.path.join("output","scale_1","img_aligned","vj_097_shift_rot_skew_crop_1k1k_5.jpg"),
                                os.path.join("output","scale_1","img_aligned","vj_097_shift_rot_skew_crop_1k1k_6.jpg"),
                                os.path.join("output","scale_1","img_aligned","vj_097_shift_rot_skew_crop_1k1k_7.jpg") ]
            try:
              main_win.load_images_in_role ( 'aligned', aln_image_stack )
            except:
              pass


    alignem.run_app(main_win)

