import sys, traceback
import os
import argparse
import cv2
import copy

import json

import shutil

import alignem
from alignem import IntField, BoolField, FloatField, CallbackButton, MainWindow

from PySide2.QtWidgets import QInputDialog, QDialog, QPushButton, QProgressBar
from PySide2.QtCore import QThread, Signal, QObject

import pyswift_tui
import align_swiftir

import time


main_win = None

## project_data = None  # Use from alignem

swift_roles = ['ref','base','aligned']

def print_exception():
    exi = sys.exc_info()
    print ( "  Exception type = " + str(exi[0]) )
    print ( "  Exception value = " + str(exi[1]) )
    print ( "  Exception trace = " + str(exi[2]) )
    print ( "  Exception traceback:" )
    traceback.print_tb(exi[2])

def get_best_path ( file_path ):
    return os.path.abspath(os.path.normpath(file_path))

def link_stack_orig():
    print ( "Linking stack" )

    ref_image_stack = []
    for layer_index in range(len(alignem.project_data['data']['scales'][alignem.current_scale]['alignment_stack'])):
      if layer_index == 0:
        main_win.add_empty_to_role ( 'ref' )
      else:
        # layer = alignem.project_data['data']['scales'][alignem.current_scale]['alignment_stack'][layer_index]
        prev_layer = alignem.project_data['data']['scales'][alignem.current_scale]['alignment_stack'][layer_index-1]
        fn = ""
        if 'base' in prev_layer['images'].keys():
          fn = prev_layer['images']['base']['filename']
        main_win.add_image_to_role ( fn, 'ref' )

    print ( "Loading images: " + str(ref_image_stack) )
    #main_win.load_images_in_role ( 'ref', ref_image_stack )

    main_win.update_panels()

    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


def link_stack():
    print ( "Linking stack" )

    skip_list = []
    for layer_index in range(len(alignem.project_data['data']['scales'][alignem.current_scale]['alignment_stack'])):
      if alignem.project_data['data']['scales'][alignem.current_scale]['alignment_stack'][layer_index]['skip']==True:
        skip_list.append(layer_index)

    print('\nSkip List = \n' + str(skip_list) + '\n')

    for layer_index in range(len(alignem.project_data['data']['scales'][alignem.current_scale]['alignment_stack'])):
      base_layer = alignem.project_data['data']['scales'][alignem.current_scale]['alignment_stack'][layer_index]

      if layer_index == 0:
        # No ref for layer 0
        if 'ref' not in base_layer['images'].keys():
          base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
        base_layer['images']['ref']['filename'] = ''
      elif layer_index in skip_list:
        # No ref for skipped layer
        if 'ref' not in base_layer['images'].keys():
          base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
        base_layer['images']['ref']['filename'] = ''
      else:
        # Find nearest previous non-skipped layer
        j = layer_index-1
        while (j in skip_list) and (j>=0):
          j -= 1

        # Use the nearest previous non-skipped layer as ref for this layer
        if (j not in skip_list) and (j>=0):
          ref_layer = alignem.project_data['data']['scales'][alignem.current_scale]['alignment_stack'][j]
          ref_fn = ''
          if 'base' in ref_layer['images'].keys():
            ref_fn = ref_layer['images']['base']['filename']
          if 'ref' not in base_layer['images'].keys():
            base_layer['images']['ref'] = copy.deepcopy(alignem.new_image_template)
          base_layer['images']['ref']['filename'] = ref_fn

    main_win.update_panels()

    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


def generate_scales ():
    print ( "generate_scales inside alignem_swift called" )
    main_win.status.showMessage("Generating Scales ...")

    image_scales_to_run = [ alignem.get_scale_val(s) for s in sorted(alignem.project_data['data']['scales'].keys()) ]

    alignem.print_debug ( 40, "Create images at all scales: " + str ( image_scales_to_run ) )

    if (alignem.project_data['data']['destination_path'] == None) or (len(alignem.project_data['data']['destination_path']) <= 0):

      alignem.show_warning ( "Note", "Scales can not be generated without a destination (use File/Set Destination)" )

    else:

      for scale in sorted(image_scales_to_run):

        alignem.print_debug ( 70, "Creating images for scale " + str(scale) )
        main_win.status.showMessage("Generating Scale " + str(scale) + " ...")

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

            # Only copy files for roles "ref" and "base"

            if role in ['ref', 'base']:

              base_file_name = layer['images'][role]['filename']
              if base_file_name != None:
                if len(base_file_name) > 0:
                  abs_file_name = os.path.abspath(base_file_name)
                  bare_file_name = os.path.split(abs_file_name)[1]
                  destination_path = os.path.abspath ( alignem.project_data['data']['destination_path'] )
                  outfile_name = os.path.join(destination_path, scale_key, 'img_src', bare_file_name)
                  if scale == 1:
                    if get_best_path(abs_file_name) != get_best_path(outfile_name):
                      # The paths are different so make the link
                      try:
                        alignem.print_debug ( 70, "UnLinking " + outfile_name )
                        os.unlink ( outfile_name )
                      except:
                        alignem.print_debug ( 70, "Error UnLinking " + outfile_name )
                      try:
                        alignem.print_debug ( 70, "Linking from " + abs_file_name + " to " + outfile_name )
                        os.symlink ( abs_file_name, outfile_name )
                      except:
                        alignem.print_debug ( 5, "Unable to link from " + abs_file_name + " to " + outfile_name )
                        alignem.print_debug ( 5, "Copying file instead" )
                        # Not all operating systems allow linking for all users (Windows 10, for example, requires admin rights)
                        try:
                          shutil.copy ( abs_file_name, outfile_name )
                        except:
                          alignem.print_debug ( 1, "Unable to link or copy from " + abs_file_name + " to " + outfile_name )
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

                  # Update the Data Model with the new absolute file name. This replaces the originally opened file names
                  alignem.print_debug ( 40, "Original File Name: " + str(layer['images'][role]['filename']) )
                  layer['images'][role]['filename'] = outfile_name
                  alignem.print_debug ( 40, "Updated  File Name: " + str(layer['images'][role]['filename']) )
    # main_win.status.showMessage("Done Generating Scales ...")


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
    if (alignem.project_data['data']['destination_path'] == None) or (len(alignem.project_data['data']['destination_path']) <= 0):

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
      updated_model, need_to_write_json = pyswift_tui.run_json_project ( dm, 'init_affine',    0,   alignem.get_scale_val(scale_to_run_text),      0,        code_mode )
      if need_to_write_json:
          alignem.project_data = updated_model
      else:
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
      refresh_all()

def align_forward():
    alignem.print_debug ( 30, "Aligning Forward with SWiFT-IR ..." )
    alignem.print_debug ( 70, "Control Model = " + str(control_model) )
    alignem.print_debug ( 1, "Currently aligning all..." )
    align_all()

def jump_to_layer():
    requested_layer = jump_to_val.get_value()
    alignem.print_debug ( 3, "Jump to layer " + str(requested_layer) )
    num_layers = len(alignem.project_data['data']['scales'][alignem.current_scale]['alignment_stack'])
    if requested_layer >= num_layers: # Limit to largest
        requested_layer = num_layers - 1
    if requested_layer < 0: # Consider negative values as indexes from the end
        requested_layer = num_layers + requested_layer
    if requested_layer < 0: # If the end index was greater than the length, just show 0
        requested_layer = 0
    alignem.project_data['data']['current_layer'] = requested_layer
    main_win.image_panel.update_multi_self()

def center_all():
    main_win.center_all_images()


def refresh_all ():
    main_win.refresh_all_images ()


def remove_aligned():
    alignem.print_debug ( 30, "Removing aligned images ..." )

    delete_list = []

    for layer in alignem.project_data['data']['scales'][alignem.current_scale]['alignment_stack']:
      if 'aligned' in layer['images'].keys():
        delete_list.append ( layer['images']['aligned']['filename'] )
        layer['images'].pop('aligned')

    #alignem.image_library.remove_all_images()

    for fname in delete_list:
      if fname != None:
        if os.path.exists(fname):
          os.remove(fname)
          alignem.image_library.remove_image_reference ( fname )

    main_win.update_panels()
    refresh_all ()


def method_debug():
    print ( "In Method debug for " + str(__name__) )
    __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

def notyet():
    alignem.print_debug ( 0, "Function not implemented yet. Skip = " + str(skip.value) )

def data_changed_callback ( prev_layer, next_layer ):
    alignem.print_debug ( 30, "Layer changed from " + str(prev_layer) + " to " + str(next_layer) )
    if alignem.project_data != None:
      alignem.print_debug ( 30, "Swapping data" )
      scale_key = alignem.project_data['data']['current_scale']
      layer_num = alignem.project_data['data']['current_layer']
      stack = alignem.project_data['data']['scales'][scale_key]['alignment_stack']
      if layer_num in range(len(stack)):
        layer = stack[layer_num]

        # Limit to legal values
        if prev_layer < 0:
          prev_layer = 0
        if next_layer >= len(stack):
          next_layer = len(stack)-1

        if prev_layer == next_layer:
          # Just copy the data into this layer
          stack[prev_layer]['skip'] = skip.get_value()
        else:
          # Save the value into the previous layer and set the value from the next layer
          stack[prev_layer]['skip'] = skip.get_value()
          skip.set_value(stack[next_layer]['skip'])


def mouse_down_callback ( role, screen_coords, image_coords, button ):
    global match_pt_mode
    if match_pt_mode.get_value():
        alignem.print_debug ( 20, "Adding a match point for role \"" + str(role) + "\" at " + str(screen_coords) + " == " + str(image_coords) )
        scale_key = alignem.project_data['data']['current_scale']
        layer_num = alignem.project_data['data']['current_layer']
        stack = alignem.project_data['data']['scales'][scale_key]['alignment_stack']
        layer = stack[layer_num]

        if not 'metadata' in layer['images'][role]:
            layer['images'][role]['match_points'] = {}

        metadata = layer['images'][role]['metadata']

        if not 'match_points' in metadata:
            metadata['match_points'] = []
        match_point_data = [ c for c in image_coords ]
        metadata['match_points'].append ( match_point_data )

        if not 'annotations' in metadata:
            metadata['annotations'] = []
        '''
        # Use default colors when commented, so there are no colors in the JSON
        if not 'colors' in metadata:
            metadata['colors'] = [ [ 255, 0, 0 ], [ 0, 255, 0 ], [ 0, 0, 255 ], [ 255, 255, 0 ], [ 255, 0, 255 ], [ 0, 255, 255 ] ]
        '''

        match_point_data = [ m for m in match_point_data ]

        color_index = len(metadata['annotations'])
        match_point_data.append ( color_index )

        metadata['annotations'].append ( "circle(%f,%f,10,%d)" % tuple(match_point_data) )
        for ann in metadata['annotations']:
          alignem.print_debug ( 20, "   Annotation: " + str(ann) )
        return ( True )  # Lets the framework know that the click has been handled
    else:
        # print ( "Do Normal Processing" )
        return ( False ) # Lets the framework know that the click has not been handled

def mouse_move_callback ( role, screen_coords, image_coords, button ):
    global match_pt_mode
    if match_pt_mode.get_value():
        return ( True )  # Lets the framework know that the move has been handled
    else:
        return ( False ) # Lets the framework know that the move has not been handled

def clear_match_points():
    global match_pt_mode
    if not match_pt_mode.get_value():
        alignem.print_debug ( 1, "\nMust be in \"Match\" mode to delete all match points." )
    else:
        alignem.print_debug ( 20, "Deleting all match points for this layer" )
        scale_key = alignem.project_data['data']['current_scale']
        layer_num = alignem.project_data['data']['current_layer']
        stack = alignem.project_data['data']['scales'][scale_key]['alignment_stack']
        layer = stack[layer_num]

        for role in layer['images'].keys():
            if 'metadata' in layer['images'][role]:
                layer['images'][role]['metadata']['match_points'] = []
                layer['images'][role]['metadata']['annotations'] = []
        main_win.update_panels()


class RunProgressDialog(QDialog):
    """
    Simple dialog that consists of a Progress Bar and a Button.
    Clicking on the button results in the start of a timer and
    updates the progress bar.
    """
    def __init__(self):
        super().__init__()
        print ( "RunProgressDialog constructor called" )
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Progress Bar')
        self.progress = QProgressBar(self)
        self.progress.setGeometry(0, 0, 300, 25)
        self.progress.setMaximum(100)
        #self.button = QPushButton('Start', self)
        #self.button.move(0, 30)
        self.setModal(True)
        self.show()
        self.onButtonClick()

        #self.button.clicked.connect(self.onButtonClick)

    def onButtonClick(self):
        self.calc = RunnableThread()
        self.calc.countChanged.connect(self.onCountChanged)
        self.calc.start()

    def onCountChanged(self, value):
        self.progress.setValue(value)

COUNT_LIMIT = 100
class RunnableThread(QThread):
    """
    Runs a counter thread.
    """
    countChanged = Signal(int)

    def run(self):
        count = 0
        while count < COUNT_LIMIT:
            count +=1
            time.sleep(0.05)
            self.countChanged.emit(count)

window = None
def run_progress():
    global window
    print ( "Run started" )
    window = RunProgressDialog()


link_stack_cb = CallbackButton('Link Stack', link_stack)
gen_scales_cb = CallbackButton('Gen Scales', generate_scales)
align_all_cb  = CallbackButton('Align All', align_all)
center_cb     = CallbackButton('Center', center_all)
align_fwd_cb  = CallbackButton('Align Forward', align_forward)
num_fwd       = IntField("#",1,1)
jump_to_cb    = CallbackButton('Jump To:', jump_to_layer)
jump_to_val   = IntField("#",1,1)
rem_algn_cb   = CallbackButton('Remove Aligned', remove_aligned)
skip          = BoolField("Skip",False)
match_pt_mode = BoolField("Match",False)
clear_match   = CallbackButton("Clear Match", clear_match_points)
progress_cb   = CallbackButton('Run', run_progress)
debug_cb      = CallbackButton('Debug', method_debug)

control_model = [
  # Panes
  [ # Begin first pane of rows
    [
      link_stack_cb,
      " ", gen_scales_cb,
      " ", align_all_cb,
      " ", align_fwd_cb, num_fwd,
      " ", jump_to_cb, jump_to_val,
      " ", center_cb,
      "  ", rem_algn_cb,
      "    ", skip,
      "  ", match_pt_mode,
      " ", clear_match,
      "    "
    ],
    [
      "This row is for temporary debugging controls:      ",
      debug_cb,
      " ", progress_cb
    ]
  ] # End first pane
]


if __name__ == "__main__":

    alignem.debug_level = 20

    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False, help="Print more information with larger DEBUG (0 to 100)")
    args = options.parse_args()

    if args.debug != None:
      alignem.debug_level = args.debug
    try:
      if args.debug != None:
        alignem.debug_level = int(args.debug)
    except:
        pass

    main_win = alignem.MainWindow ( control_model=control_model, title="Align SWiFT-IR" )
    main_win.register_data_change_callback ( data_changed_callback )
    main_win.register_mouse_move_callback ( mouse_move_callback )
    main_win.register_mouse_down_callback ( mouse_down_callback )

    main_win.resize(1200,600)

    #main_win.register_project_open ( open_json_project )
    #main_win.register_project_save ( save_json_project )
    #main_win.register_gen_scales ( generate_scales )

    alignem.print_debug ( 30, "================= Defining Roles =================" )

    main_win.define_roles ( swift_roles )

    alignem.run_app(main_win)

