#!/usr/bin/env python3
'''
This program is just a stub to call pyswift_tui.run_json_project
This function could be done in the main of pyswift_tui.py itself,
but since that file is being simultaneously changed for other
reasons, it makes sense to have a separate runner stub. At some
point this functionality could be added back or refactored other ways.
'''
import os
import sys
import json
import logging
from recipe_maker import run_json_project

logger = logging.getLogger(__name__)

if __name__ == '__main__':

    if len(sys.argv) != 8:
        logger.critical ( "Error: " + sys.argv[0] + " requires 7 arguments (got " + str(len(sys.argv)) + ")" )
        pass
    else:
        this_file = sys.argv[0]
        project_name = sys.argv[1]
        alignment_option = sys.argv[2]
        use_scale = int(sys.argv[3].strip())
        swiftir_code_mode = sys.argv[4]
        start_layer = int(sys.argv[5].strip())
        num_layers = int(sys.argv[6].strip())
        use_file_io = (int(sys.argv[7].strip()) != 0)
        with open(project_name, 'r') as f:
            project_dict = json.load(f)
        updated_model, need_to_write_json = run_json_project(
                project=project_dict,
                alignment_option=alignment_option,
                use_scale=use_scale,
                start_layer=start_layer,
                num_layers=num_layers)
        # Send the updated datamodel previewmodel and need_to_write_json back to the datamodel runner via stdout
        jde = json.JSONEncoder(indent=1, separators=(",", ": "), sort_keys=True)
        run_output_json = jde.encode({'data_model': updated_model, 'need_to_write_json': need_to_write_json})

        if use_file_io:
            of = os.path.join(project_dict['data']['destination_path'], 'single_alignment_out_%d.json' % start_layer)
            if use_scale > 0:
                of = os.path.join(project_dict['data']['destination_path'], "scale_%d" % use_scale,
                                        "single_alignment_out_%d.json" % start_layer)
            with open(of, 'w') as f:
                f.write(run_output_json)
        else:
            print("---JSON-DELIMITER---")
            print(run_output_json)
            print("---JSON-DELIMITER---")

        sys.stdout.close()
        sys.stderr.close()
