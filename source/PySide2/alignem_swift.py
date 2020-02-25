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

'''
def build_current_data_model ( destination_path=None, project_file_name=None ):

    reference_path = ""
    if destination_path != None:
      reference_path = destination_path
    if project_file_name != None:
      reference_path = os.path.split(os.path.abspath(project_file_name))[0]

    alignment_layer_list = alignem.scale_dict[alignem.current_scale]
    alignment_layer_index = alignem.alignment_layer_index

    control_panel_data = main_win.control_panel.copy_self_to_data()

    j = {}
    j['version'] = 0.2
    j['method'] = "SWiFT-IR"
    j['user_settings'] = { "max_image_file_size": 100000000 }
    j['data'] = {}
    jd = j['data']
    jd['panel_roles'] = alignem.global_panel_roles
    jd['source_path'] = ""
    jd['destination_path'] = alignem.project_data['data']['destination_path']
    jd['pairwise_alignment'] = True
    jd['defaults'] = {}
    jdd = jd['defaults']
    jdd['align_to_next_pars'] = {}
    jdda = jdd['align_to_next_pars']
    jdda['window_size'] = 1024
    jdda['addx'] = 800
    jdda['addy'] = 800
    jdda['bias_x_per_image'] = 0.0
    jdda['bias_y_per_image'] = 0.0
    jdda['output_level'] = 0
    jd['current_scale'] = alignem.current_scale
    jd['current_layer'] = alignem.alignment_layer_index

    print ( "\n\n\n" + (100*"%") )
    print ( "alignem.current_scale = " + str(alignem.current_scale) )
    print ( "alignem.alignment_layer_index = " + str(alignem.alignment_layer_index) )
    print ( "\n\n\n" + (100*"%") )


    jd['scales'] = {}
    jds = jd['scales']
    print ( "Saving scales for: " + str(alignem.image_scales_to_run) )
    for scale in [ str(s) for s in alignem.image_scales_to_run ]:
      align_layer_list_for_scale = alignem.scale_list[alignem.scale_index] # This should be indexed by scale but there's only one at this time
      jds[str(scale)] = {}
      jdsn = jds[str(scale)]
      if align_layer_list_for_scale != None:
        if len(align_layer_list_for_scale) > 0:
          jdsn['alignment_stack'] = []
          for a in align_layer_list_for_scale:
            jdsns = {}
            jdsns['skip'] = control_panel_data[0][0][3][0]
            jdsns['images'] = {}
            for im in a.image_list:
              jdsns['images'][im.role] = {}
              jdsnsr = jdsns['images'][im.role]
              rel_file_name = ""
              if type(im.image_file_name) != type(None):
                rel_file_name = os.path.relpath(im.image_file_name,start=reference_path)
              jdsnsr['filename'] = rel_file_name
              jdsnsr['metadata'] = {}
              jdsnsrm = jdsnsr['metadata']
              jdsnsrm['match_points'] = []
              jdsnsrm['annotations'] = []
            jdsns['align_to_ref_method'] = {}
            jdsnsa = jdsns['align_to_ref_method']
            jdsnsa['selected_method'] = "Auto Swim Align"
            jdsnsa['method_options'] = ["Auto Swim Align", "Match Point Align"]
            jdsnsa['method_data'] = {}
            jdsnsam = jdsnsa['method_data']
            jdsnsam['alignment_options'] = ["Init Affine", "Refine Affine", "Apply Affine"]
            jdsnsam['alignment_option'] = "Init Affine"
            jdsnsam['window_size'] = 256
            jdsnsam['addx'] = 256
            jdsnsam['addy'] = 256
            jdsnsam['bias_x_per_image'] = 0.0
            jdsnsam['bias_y_per_image'] = 0.0
            jdsnsam['bias_scale_x_per_image'] = 0.0
            jdsnsam['bias_scale_y_per_image'] = 0.0
            jdsnsam['bias_skew_x_per_image'] = 0.0
            jdsnsam['bias_rot_per_image'] = 0.0
            jdsnsam['output_level'] = 0
            jdsnsa['method_results'] = {
              'affine_matrix': [ [1.0, 0.0, 0.0], [0.0, 1.0, 0.0] ],
              'cumulative_afm': [ [1.0, 0.0, 0.0], [0.0, 1.0, 0.0] ],
              'snr': 12.345
            }
            jdsn['alignment_stack'].append ( jdsns )

    return ( j )


def open_json_project ( project_file_name ):
    global project_data
    print ( "SWiFT opening project " + str(project_file_name) )

    f = open ( project_file_name, 'r' )
    text = f.read()
    f.close()

    main_win.remove_all_layers(None)
    main_win.remove_all_panels(None)

    # Read the JSON file from the text
    project_data = json.loads ( text )

    all_roles = None
    if 'panel_roles' in project_data['data'].keys():
        all_roles = project_data['data']['panel_roles']
        print ( "Using panel roles from JSON: " + str(all_roles) )
    else:
        # Find all of the image roles in the file
        set_of_roles = set()
        empty_roles = None
        for scale_key in sorted(project_data['data']['scales'].keys()):
            print ( "Finding roles in scale " + str(scale_key) )
            for layer in project_data['data']['scales'][scale_key]['alignment_stack']:
                # Add images to this layer by role
                for role_key in layer['images'].keys():
                    set_of_roles.add ( role_key )
        all_roles = [ k for k in set_of_roles ]

    # Define all of the roles found as panels
    main_win.define_roles ( all_roles )

    # Add the images to the scales
    alignem.image_scales_to_run = sorted(project_data['data']['scales'].keys())
    main_win.define_scales ( alignem.image_scales_to_run )

    alignem.project_data['data']['destination_path'] = project_data['data']['destination_path']

    for scale_key in alignem.image_scales_to_run:
        print ( "Importing images for scale " + str(scale_key) )
        for layer in project_data['data']['scales'][scale_key]['alignment_stack']:
            print ( "  Importing images for a layer" )
            added_roles = set()
            for role_key in layer['images'].keys():
                if len(layer['images'][role_key]['filename']) > 0:
                    added_roles.add ( role_key )
                    print ( "      Adding image " + str(layer['images'][role_key]['filename']) + " to role " + role_key )
                    main_win.add_image_to_role ( layer['images'][role_key]['filename'], role_key )
            # Any roles that didn't have images at this layer need to be given an "empty" in this layer
            empty_roles = set(all_roles) - added_roles
            print ( "    Empty Roles for layer: " + str(empty_roles) )
            for empty_role in empty_roles:
                print ( "      Adding empty to role " + empty_role )
                main_win.add_empty_to_role ( empty_role )


def save_json_project ( project_file_name ):
    global project_data
    print ( "SWiFT saving project to " + str(project_file_name) )
    if project_file_name != None:
        if len(project_file_name) > 0:
            # Write out the project
            f = open ( project_file_name, 'w' )
            jde = json.JSONEncoder ( indent=2, separators=(",",": "), sort_keys=True )
            proj_json = jde.encode ( build_current_data_model ( destination_path=alignem.project_data['data']['destination_path'], project_file_name=project_file_name ) )
            f.write ( proj_json )
            f.close()
'''

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

        # alignem.print_debug ( 1, "WARNING: Only Scale 1 is supported in alignem_swift at this time!" )

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
                    alignem.print_debug ( 70, "Linking from " + abs_file_name + " to " + outfile_name )
                    os.symlink ( abs_file_name, outfile_name )
                  except:
                    alignem.print_debug ( 1, "Error!!" )
                    pass
                else:
                  try:
                    # Do the scaling
                    alignem.print_debug ( 70, "Copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale) )
                    img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage(abs_file_name), fac=scale )
                    align_swiftir.swiftir.saveImage ( img, outfile_name )
                    # Change the base image for this scale to the new file
                    layer['images'][role]['filename'] = outfile_name
                  except:
                    alignem.print_debug ( 1, "Error copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(scale) )
                    exi = sys.exc_info()
                    print ( "  Exception type = " + str(exi[0]) )
                    print ( "  Exception value = " + str(exi[1]) )
                    print ( "  Exception trace = " + str(exi[2]) )
                    print ( "  Exception traceback:" )
                    traceback.print_tb(exi[2])
                    pass

                # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


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

      # Print out what might be done to produce the JSON for this project
      #for index in range(len(alignem.scale_list[alignem.scale_index])):
      #  print ( "Aligning layer " + str(index) )
      #  al = alignem.scale_list[alignem.scale_index][index]
      #  for im in al.image_list:
      #    if im.image_file_name != None:
      #      print ( "   " + im.role + ":  " + im.image_file_name )

      # Build a data model for this project
      #### dm = build_current_data_model ( destination_path=alignem.project_data['data']['destination_path'], project_file_name=None )
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


      '''
      # Load the alignment stack after the alignment
      aln_image_stack = []
      for layer in alignem.scale_dict[alignem.current_scale]:
        image_name = None
        for image in layer.image_list:
          if image.role == 'base':
            image_name = image.image_file_name
      '''
      aln_image_stack = []

      # Load the alignment stack after the alignment
      stack_at_this_scale = alignem.project_data['data']['scales'][scale_to_run_text]['alignment_stack']
      for layer in stack_at_this_scale:

        image_name = None
        if 'base' in layer['images'].keys():
          image_name = layer['images']['base']['filename']

        # Convert from the base name to the standard aligned name:
        aligned_name = None
        if image_name != None:
          if not image_name.startswith(os.path.sep):
            # This is relative to the destination, so make it absolute?
            aligned_name = os.path.join ( os.path.join ( os.path.join(alignem.project_data['data']['destination_path'], scale_to_run_text), 'img_aligned'), image_name )
          else:
            #
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

    '''
    for layer in alignem.scale_list[alignem.scale_index]:
      for image in layer.image_list:
        if image.role == 'aligned':
          delete_list.append ( image.image_file_name )
          image.unload()
          image.pixmap = None
          image.image_file_name = None
    '''

    alignem.image_library.remove_all_images()

    for fname in delete_list:
      if fname != None:
        if os.path.exists(fname):
          os.remove(fname)
          alignem.image_library.remove_image_reference ( fname )

    '''
    alignem.image_library.remove_all_images()
    '''
    main_win.update_panels()


def method_debug():
    print ( "In Method debug for " + str(__name__) )
    __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

def notyet():
    alignem.print_debug ( 0, "Function not implemented yet. Skip = " + str(skip.value) )


skip = BoolField("Skip",False)

control_model = [
  # Panes
  [ # Begin first pane of rows
    [ CallbackButton('GenScales', generate_scales), CallbackButton('Align All SWiFT', align_all), CallbackButton('Align Forward SWiFT', align_all), IntField("#",1,1), CallbackButton('Remove Aligned', remove_aligned), "         ", skip, CallbackButton('SWIFT Debug', method_debug) ]
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

    main_win.define_roles ( ['ref','base','aligned'] )

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

