#!/usr/bin/env python3

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

import os
import argparse
import interface
import asyncio


'''globals'''
main_win = None

# LOGGER
#     logging.DEBUG: 'black',
#     logging.INFO: 'blue',
#     logging.WARNING: 'orange',
#     logging.ERROR: 'red',
#     logging.CRITICAL: 'purple',

if __name__ == "__main__":
    global_parallel_mode = True
    global_use_file_io = False
    width = 1580
    # height = 640
    height = 800

    # objc[46147]: +[__NSCFConstantString initialize] may have been in progress in another thread when fork() was called. We cannot safely call it or ignore it in the fork() child process. Crashing instead. Set a breakpoint on objc_initializeAfterForkError to debug.
    os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

    # print(f'Loading {__name__}')
    print("Running " + __file__ + ".__main__()")
    options = argparse.ArgumentParser()
    options.add_argument("-d", "--debug", type=int, required=False, default=10,help="Print more information with larger DEBUG (0 to 100)")
    options.add_argument("-p", "--parallel", type=int, required=False, default=1, help="Run in parallel")
    options.add_argument("-l", "--preload", type=int, required=False, default=3,help="Preload +/-, total to preload = 2n-1")
    options.add_argument("-c", "--use_c_version", type=int, required=False, default=1,help="Run the C versions of SWiFT tools")
    options.add_argument("-f", "--use_file_io", type=int, required=False, default=0,help="Use files to gather output from tasks")
    args = options.parse_args()
    interface.DEBUG_LEVEL = int(args.debug)
    print("run.py | cli args:", args)

    if args.parallel != None: global_parallel_mode = args.parallel != 0
    if args.use_c_version != None: interface.use_c_version = args.use_c_version != 0
    if args.use_file_io != None: global_use_file_io = args.use_file_io != 0
    if args.preload != None: interface.preloading_range = int(args.preload)

    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
    source_list = ["run.py","alignem_data_model.py","interface.py","swift_project.py","pyswift_tui.py",
                   "swiftir.py","align_swiftir.py","source_tracker.py","task_queue.py","task_queue2.py",
                   "task_wrapper.py","single_scale_job.py","multi_scale_job.py","project_runner.py",
                   "single_alignment_job.py","single_crop_job.py","stylesheet.qss","make_zarr.py","glanceem_ng.py",
                   "glanceem_utils.py","align_recipe_1.py"
                   ]

    print("run.py | Launching AlignEM-SWiFT with window size %dx%d pixels" % (width, height))
    main_win = interface.MainWindow(title="GlanceEM_SWiFT") # no more control_model
    main_win.resize(width, height)
    main_win.define_roles(['ref', 'base', 'aligned'])
    interface.run_app(main_win)



