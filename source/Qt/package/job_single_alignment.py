#!/usr/bin/env python3

# This program is just a stub to call pyswift_tui.run_json_project
# This function could be done in the main of pyswift_tui.py itself,
# but since that file is being simultaneously changed for other
# reasons, it makes sense to have a separate runner stub. At some
# point this functionality could be added back or refactored other ways.

import os
import sys
import json
from run_json_project import run_json_project

# from pyswift_tui import run_json_project  # <- previous import before refactoring

if __name__ == '__main__':

    if len(sys.argv) != 8:
        print ( "Error: " + sys.argv[0] + " requires 7 arguments (only got " + str(len(sys.argv)) + ")" )
        pass
    else:
        this_file = sys.argv[0]
        project = sys.argv[1]
        align_option = sys.argv[2]
        use_scale = int(sys.argv[3].strip())
        code_mode = sys.argv[4]
        start_layer = int(sys.argv[5].strip())
        num_layers = int(sys.argv[6].strip())
        use_file_io = (int(sys.argv[7].strip()) != 0)
        print("single_alignment_job | %s, %s, %s, %s, %s, %s" % (project, align_option, use_scale, code_mode, start_layer, num_layers))
        with open(project, 'r') as f:
            text = f.read()

        project_dict = json.loads(text)
        updated_model, need_to_write_json = run_json_project(
                project=project_dict,
                alignment_option=align_option,
                use_scale=use_scale,
                swiftir_code_mode=code_mode,
                start_layer=start_layer,
                num_layers=num_layers)

        # Send the updated data model and need_to_write_json back to the project runner via stdout
        jde = json.JSONEncoder(indent=1, separators=(",", ": "), sort_keys=True)
        run_output_json = jde.encode({'data_model': updated_model, 'need_to_write_json': need_to_write_json})

        # FILE I/O ONLY
        if use_file_io:
            path_out = os.path.join(project_dict['data']['destination_path'], "scale_%d" % use_scale, "single_alignment_out_%d.json" % start_layer)
            fout = open(path_out, 'w')
            fout.write(run_output_json)
            fout.close()
        else:
            print("---JSON-DELIMITER---")
            print(run_output_json)
            print("---JSON-DELIMITER---")

        sys.stdout.close()
        sys.stderr.close()
