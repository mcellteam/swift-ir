import sys
import os
import argparse
import cv2

import json

import alignem
from alignem import IntField, BoolField, FloatField, CallbackButton, MainWindow

import pyswift_tui

main_win = None

def write_json_project ( project_file_name="alignem_out.json",
                         fb=None, project_path="",
                         destination_path="",
                         max_image_file_size = 100000000,
                         current_plot_code = "",
                         current_scale = 1 ):

  print ( "write_json_project called" )

  # Update the data layer(s) from the current fields before writing!
  print ( "WARNING: current fields may not be taken into account yet." )
  #store_fields_into_current_layer()

  alignment_layer_list = alignem.alignment_layer_list
  alignment_layer_index = alignem.alignment_layer_index

  control_panel_data = main_win.control_panel.copy_self_to_data()

  if len(project_file_name) > 0:
    # Actually write the file
    # gui_fields.proj_label.set_text ( "Project File: " + str(project_file_name) )

    j = {}
    j['version'] = 0.2
    j['method'] = "SWiFT-IR"
    j['user_settings'] = { "max_image_file_size": 100000000 }
    j['data'] = {}
    jd = j['data']
    jd['source_path'] = ""
    jd['destination_path'] = "test"
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
    jd['current_scale'] = 1
    jd['current_layer'] = 2
    jd['scales'] = {}
    jds = jd['scales']
    for scale in [ 1 ]:
      align_layer_list_for_scale = alignem.alignment_layer_list # This should be indexed by scale
      jds[str(scale)] = {}
      jdsn = jds[str(scale)]
      if align_layer_list_for_scale != None:
        if len(align_layer_list_for_scale) > 0:
          jdsn['alignment_stack'] = []
          for a in align_layer_list_for_scale:
            jdsns = {}
            jdsns['skip'] = str(control_panel_data[0][2][3]).lower()
            jdsns['images'] = {}
            for im in a.image_list:
              jdsns['images'][im.role] = {}
              jdsnsr = jdsns['images'][im.role]
              rel_file_name = ""
              if type(im.image_file_name) != type(None):
                rel_file_name = os.path.relpath(im.image_file_name,start=project_path)
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
              'affine_matrix': [ [1.0, 0.0, 0,0], [0.0, 1.0, 0.0] ],
              'cumulative_afm': [ [1.0, 0.0, 0,0], [0.0, 1.0, 0.0] ],
              'snr': 12.345
            }
            jdsn['alignment_stack'].append ( jdsns )

    jde = json.JSONEncoder ( indent=2, separators=(",",": "), sort_keys=True )
    proj_json = jde.encode ( j )

    f = None
    if fb is None:
      # This is the default to write to a file
      alignem.print_debug ( 50, "Saving destination path = " + str(destination_path) )
      f = open ( project_file_name, 'w' )
    else:
      # Since a file buffer (fb) was provided, write to it rather than a file
      alignem.print_debug ( 50, "Writing to string" )
      f = fb
    f.write ( proj_json )

    """
    rel_dest_path = ""
    if len(destination_path) > 0:
      rel_dest_path = os.path.relpath(destination_path,start=project_path)

    f = None
    if fb is None:
      # This is the default to write to a file
      alignem.print_debug ( 50, "Saving destination path = " + str(destination_path) )
      f = open ( project_file_name, 'w' )
    else:
      # Since a file buffer (fb) was provided, write to it rather than a file
      alignem.print_debug ( 50, "Writing to string" )
      f = fb

    f.write ( '{\n' )
    f.write ( '  "version": 0.2,\n' )
    f.write ( '  "method": "SWiFT-IR",\n' )

    f.write ( '  "user_settings": {\n' )
    f.write ( '    "max_image_file_size": ' + str(max_image_file_size) + '\n' )
    f.write ( '  },\n' )

    if len(current_plot_code.strip()) > 0:
      alignem.print_debug ( 1, "Saving custom plot code" )
      code_p = pickle.dumps ( current_plot_code, protocol=0 )
      code_e = base64.b64encode ( code_p )
      sl = 40
      code_l = [ code_e[sl*s:(sl*s)+sl] for s in range(1+(len(code_e)/sl)) ]
      f.write ( '  "plot_code": [\n' )
      for s in code_l:
        f.write ( '    "' + s + '",\n' )
      f.write ( '    ""\n' )
      f.write ( '  ],\n' )

    f.write ( '  "data": {\n' )
    f.write ( '    "source_path": "",\n' )
    f.write ( '    "destination_path": "' + str(rel_dest_path).replace('\\','/') + '",\n' )
    f.write ( '    "pairwise_alignment": true,\n' )
    f.write ( '    "defaults": {\n' )
    f.write ( '      "align_to_next_pars": {\n' )
    f.write ( '        "window_size": 1024,\n' )
    f.write ( '        "addx": 800,\n' )
    f.write ( '        "addy": 800,\n' )
    f.write ( '        "bias_x_per_image": 0.0,\n' )
    f.write ( '        "bias_y_per_image": 0.0,\n' )
    f.write ( '        "output_level": 0\n' )
    f.write ( '      }\n' )
    f.write ( '    },\n' )
    f.write ( '    "current_scale": ' + str(current_scale) + ',\n' )
    f.write ( '    "current_layer": ' + str(alignment_layer_index) + ',\n' )

    f.write ( '    "scales": {\n' )

    last_scale_key = 1
    #if len(scales_dict.keys()) > 0:
    #  last_scale_key = sorted(scales_dict.keys())[-1]

    for scale_key in sorted([1]):

      align_layer_list_for_scale = alignem.alignment_layer_list # scales_dict[scale_key]

      f.write ( '      "' + str(scale_key) + '": {\n' )
      if align_layer_list_for_scale != None:
        if len(align_layer_list_for_scale) > 0:
          f.write ( '        "alignment_stack": [\n' )
          for a in align_layer_list_for_scale:
            f.write ( '          {\n' )
            f.write ( '            "skip": ' + str(control_panel_data[0][2][3]).lower() + ',\n' )
            if a != align_layer_list_for_scale[-1]:
              # Not sure what to leave out for last image ... keep all for now
              pass
            f.write ( '            "images": {\n' )
            for im in a.image_list:
              if im.image_file_name != None:
                if len(im.image_file_name) > 0:
                  f.write ( '              "' + im.role + '": {\n' )
                  alignem.print_debug ( 90, "Try to get relpath for " + str(im.image_file_name) + " starting at " + str(project_path) )
                  rel_file_name = ""
                  if type(im.image_file_name) != type(None):
                    rel_file_name = os.path.relpath(im.image_file_name,start=project_path)
                  f.write ( '                "filename": "' + rel_file_name.replace('\\','/') + '",\n' )
                  f.write ( '                "metadata": {\n' )
                  f.write ( '                  "match_points": [],\n' )
                  f.write ( '                  "annotations": []\n' )
                  f.write ( '                }\n' )
                  if im != a.image_list[-1]:
                    f.write ( '              },\n' )
                  else:
                    f.write ( '              }\n' )

            f.write ( '            },\n' )
            f.write ( '            "align_to_ref_method": {\n' )
            f.write ( '              "selected_method": "' + str("Auto Swim Align") + '",\n' )
            f.write ( '              "method_options": ["Auto Swim Align", "Match Point Align"],\n' )
            f.write ( '              "method_data": {\n' )
            f.write ( '                "alignment_options": ["Init Affine", "Refine Affine", "Apply Affine"],\n' )
            f.write ( '                "alignment_option": "Init Affine",\n' )
            f.write ( '                "window_size": 256,\n' )
            f.write ( '                "addx": 256,\n' )
            f.write ( '                "addy": 256,\n' )
            f.write ( '                "bias_x_per_image": 0.0,\n' )
            f.write ( '                "bias_y_per_image": 0.0,\n' )
            f.write ( '                "bias_scale_x_per_image": 0.0,\n' )
            f.write ( '                "bias_scale_y_per_image": 0.0,\n' )
            f.write ( '                "bias_skew_x_per_image": 0.0,\n' )
            f.write ( '                "bias_rot_per_image": 0.0,\n' )
            f.write ( '                "output_level": 0\n' )
            f.write ( '              },\n' )
            f.write ( '              "method_results": {\n' )
            #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
            #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

            '''
            if type(a.results_dict) != type(None):
              if 'affine' in a.results_dict:
                smat = str(a.results_dict['affine'])
                smat = smat.replace ( 'nan', 'NaN' )
                f.write ( '                "affine_matrix": ' + smat + ',\n' )
              if 'cumulative_afm' in a.results_dict:
                smat = str(a.results_dict['cumulative_afm'])
                smat = smat.replace ( 'nan', 'NaN' )
                f.write ( '                "cumulative_afm": ' + smat + ',\n' )
              if 'snr' in a.results_dict:
                f.write ( '                "snr": ' + fstring(a.results_dict['snr']) + '\n' )
            '''
            f.write ( '              }\n' )
            f.write ( '            }\n' )
            if a != align_layer_list_for_scale[-1]:
              f.write ( '          },\n' )
            else:
              f.write ( '          }\n' )
          f.write ( '        ]\n' )
          if scale_key != last_scale_key:
            f.write ( '      },\n' )
          else:
            f.write ( '      }\n' )

      f.write ( '    }\n' ) # "scales": {

      f.write ( '  }\n' ) # "data": {

      f.write ( '}\n' ) # End of entire dictionary
    """

class StringBufferFile:
  def __init__ ( self ):
    self.fs = ""
  def write ( self, s ):
    self.fs = self.fs + s

def align_all():
    alignem.print_debug ( 30, "Aligning All with SWiFT-IR ..." )

    code_mode = 'python'

    ### All of this code is just trying to find the right menu item for the Use C Version check box:
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

    # Print out what might be done to produce the JSON for this project
    for index in range(len(alignem.alignment_layer_list)):
      print ( "Aligning layer " + str(index) )
      al = alignem.alignment_layer_list[index]
      for im in al.image_list:
        if im.image_file_name != None:
          print ( "   " + im.role + ":  " + im.image_file_name )

    # Generate the JSON on the fly
    fb = StringBufferFile()
    write_json_project ( "alignem_out.json", fb=fb )
    if len(fb.fs.strip()) > 0:
      d = None
      try:
        d = json.loads ( fb.fs )
        print ( "Running pyswift_tui.run_json_project" )
        pyswift_tui.run_json_project ( d, 'init_affine', 0, 1, 0, code_mode )
      except:
        alignem.print_debug ( 1, "Error when running" )
        alignem.print_debug ( 1, "JSON:" )
        alignem.print_debug ( 1, str(d) )


    # Use a dummy project for now just to verify that the pyswift_tui interface works
    #fp = open("pyswift_gui_gtk.json",'r')
    #d = json.load(fp)
    #print ( "Running pyswift_tui.run_json_project" )
    #pyswift_tui.run_json_project ( d, 'init_affine', 0, 1, 0, code_mode )



def align_forward():
    alignem.print_debug ( 30, "Aligning Forward with SWiFT-IR ..." )
    alignem.print_debug ( 70, "Control Model = " + str(control_model) )

def notyet():
    alignem.print_debug ( 0, "Function not implemented yet. Skip = " + str(skip.value) )

skip = BoolField("Skip",False)

control_model = [
  # Panes
  [ # Begin first pane of rows
    [ "Project File:", CallbackButton('Write JSON', write_json_project) ],
    [ "Destination:", write_json_project ],
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

    #main_win.define_roles ( ['ref','src','align'] )
    main_win.define_roles ( ['ref','base','align'] )

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
    main_win.load_images_in_role ( 'base', src_image_stack )
    main_win.load_images_in_role ( 'align', aln_image_stack )

    alignem.run_app(main_win)

