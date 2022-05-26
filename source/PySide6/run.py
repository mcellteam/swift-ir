"""
GlanceEM-SWiFT - A software tool for image alignment that is under active development.

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to [http://unlicense.org]
"""
import os, sys, argparse
# from glanceem_utils import update_skips_callback, update_linking_callback, crop_mode_callback, mouse_down_callback, mouse_move_callback
import alignem

'''global variables'''
main_win = None

if __name__ == "__main__":
    print("Running " + __file__ + ".__main__()")
    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False, default=10,help="Print more information with larger DEBUG (0 to 100)")
    options.add_argument("-p", "--parallel", type=int, required=False, default=1, help="Run in parallel")
    options.add_argument("-l", "--preload", type=int, required=False, default=3,help="Preload +/-, total to preload = 2n-1")
    options.add_argument("-c", "--use_c_version", type=int, required=False, default=1,help="Run the C versions of SWiFT tools")
    options.add_argument("-f", "--use_file_io", type=int, required=False, default=0,help="Use files to gather output from tasks")
    args = options.parse_args()
    alignem.DEBUG_LEVEL = int(args.debug)
    print("alignem_swift.py | cli args:", args)
    size_x = 1600
    size_y = 700
    global_source_rev = ""
    global_source_hash = ""
    global_parallel_mode = True #was False
    global_use_file_io = False

    if args.parallel != None: global_parallel_mode = args.parallel != 0
    if args.use_c_version != None: alignem.use_c_version = args.use_c_version != 0
    if args.use_file_io != None: global_use_file_io = args.use_file_io != 0
    if args.preload != None:
        alignem.preloading_range = int(args.preload)
        if alignem.preloading_range < 1:
            alignem.preloading_range = 1

    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
    source_list = ["alignem_swift.py","alignem_data_model.py","alignem.py","swift_project.py","pyswift_tui.py",
                   "swiftir.py","align_swiftir.py","source_tracker.py","task_queue.py","task_queue2.py",
                   "task_wrapper.py","single_scale_job.py","multi_scale_job.py","project_runner.py",
                   "single_alignment_job.py","single_crop_job.py","stylesheet.qss","make_zarr.py","glanceem_ng.py",
                   "glanceem_utils.py","align_recipe_1.py"
                   ]

    # print("alignem_swift.py | Source tag: %s" % str(global_source_tag))
    # print("alignem_swift.py | Source hash: %s" % str(global_source_hash))
    print('alignem_swift.py | Initializing MainWindow')

    main_win = alignem.MainWindow(title="GlanceEM_SWiFT") # no more control_model
    # main_win.register_mouse_move_callback(mouse_move_callback)
    # main_win.register_mouse_down_callback(mouse_down_callback)
    # alignem.crop_mode_callback = crop_mode_callback
    # alignem.update_linking_callback = update_linking_callback
    # alignem.update_skips_callback = update_skips_callback
    print("alignem_swift.py | Resizing main window to %dx%d pixels" % (size_x, size_y))
    main_win.resize(size_x, size_y)
    main_win.define_roles(['ref', 'base', 'aligned'])
    alignem.run_app(main_win)
