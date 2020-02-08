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
  #store_fields_into_current_layer()

  alignment_layer_list = alignem.alignment_layer_list
  alignment_layer_index = alignem.alignment_layer_index

  if len(project_file_name) > 0:
    # Actually write the file
    # gui_fields.proj_label.set_text ( "Project File: " + str(project_file_name) )
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
            f.write ( '            "skip": ' + str(a.skip).lower() + ',\n' )
            if a != align_layer_list_for_scale[-1]:
              # Not sure what to leave out for last image ... keep all for now
              pass
            f.write ( '            "images": {\n' )

            img_keys = sorted(a.image_dict.keys(), reverse=True)
            for k in img_keys:
              im = a.image_dict[k]
              #alignem.print_debug ( 90, "    " + str(k) + " alignment points: " + str(im.get_marker_points()) )
              f.write ( '              "' + k + '": {\n' )  # "base": {
              # rel_file_name = os.path.relpath(a.base_image_name,start=project_path)
              alignem.print_debug ( 90, "Try to get relpath for " + str(im.file_name) + " starting at " + str(project_path) )
              rel_file_name = ""
              if type(im.file_name) != type(None):
                rel_file_name = os.path.relpath(im.file_name,start=project_path)
              f.write ( '                "filename": "' + rel_file_name.replace('\\','/') + '",\n' )
              f.write ( '                "metadata": {\n' )
              f.write ( '                  "match_points": ' + str(im.get_marker_points()) + ',\n' )
              if len(im.graphics_items) <= 0:
                f.write ( '                  "annotations": []\n' )
              else:
                f.write ( '                  "annotations": [\n' )
                # Filter out the markers which are handled in other code
                non_marker_list = [ gi for gi in im.graphics_items if not gi.marker ]
                # Filter out any temporary annotations
                non_marker_list = [ gi for gi in non_marker_list if not gi.temp ]
                # Only output the non-markers being careful not to add a trailing comma
                for gi_index in range(len(non_marker_list)):
                  gi = non_marker_list[gi_index]
                  f.write ( "                    " + gi.to_json_string().replace('\\','/') )
                  if gi_index < (len(non_marker_list)-1):
                    f.write ( ',\n' )
                  else:
                    f.write ( '\n' )
                f.write ( '                  ]\n' )
              f.write ( '                }\n' )
              if k != img_keys[-1]:
                f.write ( '              },\n' )
              else:
                f.write ( '              }\n' )
            f.write ( '            },\n' )
            f.write ( '            "align_to_ref_method": {\n' )
            f.write ( '              "selected_method": "' + str(a.align_method_text) + '",\n' )
            f.write ( '              "method_options": ["Auto Swim Align", "Match Point Align"],\n' )
            f.write ( '              "method_data": {\n' )
            f.write ( '                "alignment_options": [' + ', '.join ( ['"'+o+'"' for o in alignment_opts] ) + '],\n' )
            f.write ( '                "alignment_option": "' + str(a.init_refine_apply) + '",\n' )
            f.write ( '                "window_size": ' + str(a.trans_ww) + ',\n' )
            f.write ( '                "addx": ' + str(a.trans_addx) + ',\n' )
            f.write ( '                "addy": ' + str(a.trans_addy) + ',\n' )
            f.write ( '                "bias_x_per_image": ' + fstring(a.bias_dx) + ',\n' )
            f.write ( '                "bias_y_per_image": ' + fstring(a.bias_dy) + ',\n' )
            f.write ( '                "bias_scale_x_per_image": ' + fstring(a.bias_scale_x) + ',\n' )
            f.write ( '                "bias_scale_y_per_image": ' + fstring(a.bias_scale_y) + ',\n' )
            f.write ( '                "bias_skew_x_per_image": ' + fstring(a.bias_skew_x) + ',\n' )
            f.write ( '                "bias_rot_per_image": ' + fstring(a.bias_rotation) + ',\n' )
            f.write ( '                "output_level": 0\n' )
            f.write ( '              },\n' )
            f.write ( '              "method_results": {\n' )
            #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

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


def align_all():
    alignem.print_debug ( 30, "Aligning All with SWiFT-IR ..." )

    for index in range(len(alignem.alignment_layer_list)):
      print ( "Aligning layer " + str(index) )
      al = alignem.alignment_layer_list[index]
      for im in al.image_list:
        if im.image_file_name != None:
          print ( "   " + im.role + ":  " + im.image_file_name )

    fp = open("pyswift_gui_gtk.json",'r')
    d = json.load(fp)
    print ( "Running pyswift_tui.run_json_project" )
    pyswift_tui.run_json_project ( d, 'init_affine', 0, 1, 0, 'python' )



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

