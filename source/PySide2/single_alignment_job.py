#!/usr/bin/env python3

# This program is just a stub to call pyswift_tui.run_json_project
# This function could be done in the main of pyswift_tui.py itself,
# but since that file is being simultaneously changed for other
# reasons, it makes sense to have a separate runner stub. At some
# point this functionality could be added back or refactored other ways.

import sys
import json
import pyswift_tui

if __name__ == '__main__':

  if len(sys.argv) != 7:
    # print ( "Error: " + sys.argv[0] + " requires 7 arguments (only got " + str(len(sys.argv)) + ")" )
    pass
  else:
    this_file = sys.argv[0]
    project_name = sys.argv[1]
    alignment_option = sys.argv[2]
    use_scale = int(sys.argv[3].strip())
    swiftir_code_mode = sys.argv[4]
    start_layer = int(sys.argv[5].strip())
    num_layers = int(sys.argv[6].strip())

    '''
    print ( "Inside single_alignment_job with: " +
                                         str(project_name) + ', ' +
                                         str(alignment_option) + ', ' +
                                         str(use_scale) + ', ' +
                                         str(swiftir_code_mode) + ', ' +
                                         str(start_layer) + ', ' +
                                         str(num_layers) )
    '''

    # Read the project from the JSON file
    f = open ( project_name, 'r' )
    text = f.read()
    f.close()
    project_dict = json.loads ( text )

    #print ( "project_dict.keys() = " + str(project_dict.keys()) )
    #print ( str(project_dict['data']['scales']['scale_%d'%use_scale]['alignment_stack'][0]['images']['ref']['filename']) )

    # print ( "\n\n\nBefore running JSON DATA MODEL\n\n" )

    updated_model, need_to_write_json = pyswift_tui.run_json_project (
                                         project = project_dict,
                                         alignment_option = alignment_option,
                                         use_scale = use_scale,
                                         swiftir_code_mode = swiftir_code_mode,
                                         start_layer = start_layer,
                                         num_layers = num_layers )

    # print ( "\n\nAfter running JSON DATA MODEL")

    # Send the updated data model and need_to_write_json back to the project runner via stdout
    jde = json.JSONEncoder ( indent=1, separators=(",",": "), sort_keys=True )
    run_output_json = jde.encode ( { 'data_model': updated_model, 'need_to_write_json': need_to_write_json } )

    print ( run_output_json )
    # print ( "\n\n\n JSON DATA MODEL:\n" + str(proj_json) + "\n\n" )
    flush()
