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
from recipe_maker import run_recipe


logger = logging.getLogger(__name__)

if __name__ == '__main__':

    f_self = sys.argv[0]
    f_temp = sys.argv[1]
    scale_val = int(sys.argv[2])
    zpos = int(sys.argv[3])
    use_file_io = bool(int(sys.argv[4]))
    dev_mode = bool(sys.argv[5])
    with open(f_temp, 'r') as f:
        project = json.load(f)
    updated_model, need_to_write_json = run_recipe(
        project=project,
        scale_val=scale_val,
        zpos=zpos,
        dev_mode=dev_mode
    )
    # Send the updated datamodel previewmodel and need_to_write_json back to the datamodel runner via stdout
    jde = json.JSONEncoder(indent=1, separators=(",", ": "), sort_keys=True)
    run_output_json = jde.encode({'data_model': updated_model, 'need_to_write_json': need_to_write_json})

    if use_file_io:
        of = os.path.join(project['data']['destination_path'], 'single_alignment_out_%d.json' % zpos)
        if scale_val > 0:
            of = os.path.join(project['data']['destination_path'], "scale_%d" % scale_val,
                                    "single_alignment_out_%d.json" % zpos)
        with open(of, 'w') as f:
            f.write(run_output_json)
    else:
        print("---JSON-DELIMITER---")
        print(run_output_json)
        print("---JSON-DELIMITER---")

    sys.stdout.close()
    sys.stderr.close()
