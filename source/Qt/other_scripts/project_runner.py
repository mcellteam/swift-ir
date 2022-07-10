#!/usr/bin/env python2.7
# print(f'project_runner.py | Loading {__name__}')
import sys
import os
import time
import json
import copy
import psutil
import inspect


# try: import package.alignem_utils as em
# except: import alignem_utils as em
#
# try: import package.task_queue_mp as task_queue
# except: import task_queue_mp as task_queue
#
# try: import package.config as cfg
# except: import config as cfg
#
# try: from package.run_json_project import run_json_project
# except: from run_json_project import run_json_project
#
# # try: from package.run_json_project import run_json_project
from run_json_project import run_json_project
from utils.image import BoundingRect, SetStackCafm
from utils.alignem_utils import save_bias_analysis
import task_queue_mp as task_queue
from config import CODE_MODE, USE_FILE_IO


# pyswift_tui -- calls by project_runner:
# Remaining:
# , BoundingRect, SetStackCafm,
# Done:
# save_bias_analysis run_json_project


# This is monotonic (0 to 100) with the amount of output:
debug_level = 30  # A larger value prints more stuff
print_switch = 0

# Using the Python version does not work because the Python 3 code can't
# even be parsed by Python2. It could be dynamically compiled, or use the
# alternate syntax, but that's more work than it's worth for now.
if sys.version_info >= (3, 0):
    # print ( "Python 3: Supports arbitrary arguments via print")
    # def print_debug ( level, *ds ):
    #  # print_debug ( 1, "This is really important!!" )
    #  # print_debug ( 99, "This isn't very important." )
    #  global debug_level
    #  if level <= debug_level:
    #    print ( *ds )
    pass
else:
    # print ("Python 2: Use default parameters for limited support of arbitrary arguments via print")
    pass


# For now, always use the limited argument version
def print_debug(level, p1=None, p2=None, p3=None, p4=None, p5=None):
    # print_debug ( 1, "This is really important!!" )
    # print_debug ( 99, "This isn't very important." )
    global debug_level
    if level <= debug_level:
        if p1 == None:
            print("")
        elif p2 == None:
            print(str(p1))
        elif p3 == None:
            print(str(p1) + str(p2))
        elif p4 == None:
            print(str(p1) + str(p2) + str(p3))
        elif p5 == None:
            print(str(p1) + str(p2) + str(p3) + str(p4))
        else:
            print(str(p1) + str(p2) + str(p3) + str(p4) + str(p5))


def print_debug_enter(level):
    if level <= debug_level:
        call_stack = inspect.stack()
        # print ( "Call Stack: " + str([stack_item.function for stack_item in call_stack][1:]) )




class project_runner:
    ''' Run an alignment project by splitting it up by scales and/or layers '''

    # The project_runner starts with a Full Data Model (FDM)
    # The project_runner may run in either serial or parallel mode
    # When running in serial mode, the project_runner calls run_json_project directly
    # When running in parallel mode:
    #   The project_runner writes the FDM to a temporary file to be read by the worker tasks
    #   The project_runner breaks up the alignment layers into specific jobs and starts a worker (pyswift_tui) for each job
    #   Each worker will see the temporary data model file and get command line parameters about which part(s) it must complete
    #   The project_runner will collect the alignment data from each pyswift_tui run and integrate it into the "master" data model
    #  def __init__ ( self, project=None, alignment_option='init_affine', use_scale=0, swiftir_code_mode='python', start_layer=0, num_layers=-1, run_parallel=False, use_file_io=True ):
    def __init__(self, project=None, use_scale=0, swiftir_code_mode='c', start_layer=0, num_layers=-1,use_file_io=True):
    # def __init__(self, project, current_scale):
        # if use_scale <= 0:
        #     # print ( "Error: project_runner must be given an explicit scale")
        #     return
        self.project = copy.deepcopy(project)
        # self.alignment_option = 'init_affine'
        self.use_scale = use_scale
        self.swiftir_code_mode = CODE_MODE
        self.use_file_not_pipe = USE_FILE_IO
        self.start_layer = 0
        self.num_layers = -1
        self.generate_images = True
        self.run_parallel = True
        self.task_queue = None
        self.updated_model = None
        self.need_to_write_json = None
        self.t0 = 0

        print('project_runner | INITIALIZATION')
        print('project_runner | self.use_scale = ', self.use_scale)
        print('project_runner | self.swiftir_code_mode = ', self.swiftir_code_mode)
        print('project_runner | self.start_layer = ', self.start_layer)
        print('project_runner | self.num_layers = ', self.num_layers)
        print('project_runner | self.generate_images = ', self.generate_images)
        print('project_runner | self.run_parallel = ', self.run_parallel)
        print('project_runner | self.task_queue = ', self.task_queue)
        print('project_runner | self.updated_model = ', self.updated_model)
        print('project_runner | self.need_to_write_json = ', self.need_to_write_json)
        print('project_runner | self.use_file_not_pipe = ', self.use_file_not_pipe)
        print('project_runner | self.t0 = ', self.t0)


    def get_updated_data_model(self):
        # print ( "Returning the updated data model" )
        #    return self.updated_model
        return self.project

    # Class Method to Align the Stack
    #  def start ( self ):
    def do_alignment(self, alignment_option='init_affine', generate_images=True):
        print("\nproject_runner.do_alignment(alignment_option=%s,generate_images=%s):" % (alignment_option,generate_images))

        self.alignment_option = alignment_option
        self.generate_images = generate_images
        print('project_runner.do_alignment | alignment_option = ', alignment_option)
        # scale_key = "scale_%d" % self.use_scale
        scale_key = em.getCurScale()
        alstack = self.project['data']['scales'][scale_key]['alignment_stack']

        if self.run_parallel:

            # Run the project as a series of jobs

            # Write the entire project as a single JSON file with a unique stable name for this run

            # f = tempfile.NamedTemporaryFile (prefix="temp_proj_", suffix=".json", dir=self.project['data']['destination_path'], delete=False)
            # run_project_name = f.name
            # f.close()
            # print ("Temp file is: " + str (f.name))
            print("project_runner.do_alignment | Coppy project file to 'project_runner_job_file.json'")
            run_project_name = os.path.join(self.project['data']['destination_path'], "project_runner_job_file.json")
            f = open(run_project_name, 'w')
            jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
            proj_json = jde.encode(self.project)
            f.write(proj_json)
            f.close()

            # self.task_queue = task_queue.TaskQueue() #0704
            self.task_queue = task_queue.TaskQueue(n_tasks=len(alstack))
            cpus = psutil.cpu_count(logical=False)
            if cpus > 48:
                cpus = 48
            print("Starting Project Runner Task Queue with %d CPUs (TaskQueue.start)" % (cpus))
            self.task_queue.start(cpus)

            my_path = os.path.split(os.path.realpath(__file__))[0]
            # align_job = os.path.join(my_path, 'source/Qt/package/single_alignment_job.py')
            align_job = os.path.join(my_path, 'single_alignment_job.py')
            print('project_runner.do_alignment | do_alignment | align_job=',align_job)
            # (tag) (do_align) project_runner | do_alignment | align_job= /Users/joelyancey/glanceem_swift/swift-ir/source/Qt/package/single_alignment_job.py

            # for layer in tqdm(alstack):
            for layer in alstack:
                lnum = alstack.index(layer)
                skip = False
                if 'skip' in layer:
                    skip = layer['skip']
                if False and skip:

                    print_debug(-1, "\n" + (20 * 'Skip') + '\n   Skipping layer ' + str(lnum) + '\n' + (
                                20 * 'Skip') + "\n")

                else:

                    if print_switch: print_debug(1, "Starting a task for layer " + str(lnum))
                    '''
                    self.task_queue.add_task ( cmd=sys.executable,
                                               args=[ align_job,                     # Python program to run (single_alignment_job)
                                                      str(run_project_name),         # Project file name
                                                      str(self.alignment_option),    # Init, Refine, or Apply
                                                      str(self.use_scale),           # Scale to use or 0
                                                      str(self.swiftir_code_mode),   # Python or C mode
                                                      str(lnum),                     # First layer number to run from Project file
                                                      str(1),                        # Number of layers to run
                                                      str(self.use_file_not_pipe)    # Flag (0 or 1) for pipe/file I/O. 0=Pipe, 1=File
                                                      ],
                                               wd='.' )
                                               # wd=self.project['data']['destination_path'] )
                    '''

                    # Use task_queue_mp
                    task_args = [sys.executable,
                                 align_job,  # Python program to run (single_alignment_job)
                                 str(run_project_name),  # Project file name
                                 str(self.alignment_option),  # Init, Refine, or Apply
                                 str(self.use_scale),  # Scale to use or 0
                                 str(self.swiftir_code_mode),  # Python or C mode
                                 str(lnum),  # First layer number to run from Project file
                                 str(1),  # Number of layers to run
                                 str(self.use_file_not_pipe)  # Flag (0 or 1) for pipe/file I/O. 0=Pipe, 1=File
                                 ]
                    print_debug(50, "project_runner.do_alignment | Starting task_queue_mp with args:")
                    for p in task_args:
                        print_debug(50, "  " + str(p))

                    self.task_queue.add_task(task_args)

            # self.task_queue.work_q.join()

            self.t0 = time.time()
            if print_switch: print_debug(-1, 'project_runner.do_alignment | Waiting for Alignment Tasks to Complete...')
            self.task_queue.collect_results()
            dt = time.time() - self.t0
            #  print_debug ( -1, 'Alignment Tasks Completed in %.2f seconds' % (dt) )

            # Check status of all tasks and report final tally
            # print ("Tasks completed with these arguments")
            n_tasks = len(self.task_queue.task_dict.keys())
            n_success = 0
            n_queued = 0
            n_failed = 0
            for k in self.task_queue.task_dict.keys():
                task_item = self.task_queue.task_dict[k]
                status = task_item['status']
                if status == 'completed':
                    n_success += 1
                elif status == 'queued':
                    n_queued += 1
                elif status == 'task_error':
                    main_window.hud.post('\nTask Error:')
                    main_window.hud.post('   CMD:    %s' % (str(task_item['cmd'])))
                    main_window.hud.post('   ARGS:   %s' % (str(task_item['args'])))
                    main_window.hud.post('   STDERR: %s\n' % (str(task_item['stderr'])))
                    n_failed += 1
                #        print_debug ( -1, 'Task STDOUT: \n%s\n' % (task_item['stdout']))
                #        print_debug ( -1, 'Task STDERR: \n%s\n' % (task_item['stderr']))
                # print ( '  ' + str(self.task_queue.task_dict[k]['args']) + " " + str(self.task_queue.task_dict[k]['status']) )
                #        if self.task_queue.task_dict[k]['status'] == 'task_error':
                #          print_debug ( -1, '  ' + str(self.task_queue.task_dict[k]['cmd']) + " " + str(self.task_queue.task_dict[k]['args']) )
                pass
            if print_switch:
                main_window.hud.post('%d Alignment Tasks Completed in %.2f seconds' % (n_tasks, dt))
                main_window.hud.post('  Num Successful:   %d' % (n_success))
                main_window.hud.post('  Num Still Queued: %d' % (n_queued))
                main_window.hud.post('  Num Failed:       %d' % (n_failed))

            # Sort the tasks by layers rather than by process IDs
            task_dict_by_start_layer = {}
            for k in self.task_queue.task_dict.keys():
                t = self.task_queue.task_dict[k]
                task_dict_by_start_layer[int(t['args'][5])] = t

            # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })

            tasks_by_start_layer = []
            for k in sorted(task_dict_by_start_layer.keys()):
                tasks_by_start_layer.append(task_dict_by_start_layer[k])

            # print ("Tasks sorted by layer numbers")
            for l in tasks_by_start_layer:
                # print ( '  ' + str(l['args']) + '  ' + str(l['status']) )
                pass

            # Integrate the output from each task into a new combined data model

            self.updated_model = copy.deepcopy(self.project)

            cur_scale_new_key = self.updated_model['data']['current_scale']
            if self.use_scale > 0:
                cur_scale_new_key = 'scale_' + str(self.use_scale)

            for tnum in range(len(tasks_by_start_layer)):

                if self.use_file_not_pipe:
                    # if print_switch: print('\n\n' + (80 * '#') + '\nUsing File I/O\n' + (80 * '#') + '\n\n')
                    # Get the updated data model from the file written by single_alignment_job
                    # Start by getting the location of the project's output files:
                    output_dir = os.path.join(os.path.split(run_project_name)[0], scale_key)
                    # Get the name of the file for this task number
                    # NOTE / TODO : This uses the TASK NUMBER and NOT the LAYER NUMBER ... THEY MAY BE DIFFERENT!!
                    output_file = "single_alignment_out_" + str(tnum) + ".json"
                    with open(os.path.join(output_dir, output_file), 'r') as job_output_file:  # Use file to refer to the file object
                        dm_text = job_output_file.read()
                    # job_output_file = open(os.path.join(output_dir, output_file), 'r')
                    # dm_text = job_output_file.read()
                    # job_output_file.close()
                    # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })

                else:
                    print_debug(50, '\n' + (80 * '#') + '\nUsing Pipe I/O\n' + (80 * '#') + '\n')
                    # Get the updated data model from stdout for the task
                    parts = tasks_by_start_layer[tnum]['stdout'].split('---JSON-DELIMITER---')
                    dm_text = None
                    for p in parts:
                        ps = p.strip()
                        if ps.startswith('{') and ps.endswith('}'):
                            dm_text = p

                if dm_text != None:
                    results_dict = json.loads(dm_text)
                    fdm_new = results_dict['data_model']

                    # Get the same scale from both the old and new data models
                    cur_scale_new = fdm_new['data']['scales'][cur_scale_new_key]
                    cur_scale_old = self.updated_model['data']['scales'][cur_scale_new_key]

                    al_stack_old = cur_scale_old['alignment_stack']
                    al_stack_new = cur_scale_new['alignment_stack']

                    lnum = int(tasks_by_start_layer[tnum]['args'][5])  # Note that this may differ from tnum!!

                    al_stack_old[lnum] = al_stack_new[lnum]

                    if tasks_by_start_layer[tnum]['status'] == 'task_error':
                        ref_fn = al_stack_old[lnum]['images']['ref']['filename']
                        base_fn = al_stack_old[lnum]['images']['base']['filename']
                        if print_switch:
                            main_window.hud.post('Alignment Task Error at: ' + str(tasks_by_start_layer[tnum]['cmd']) + " " + str(tasks_by_start_layer[tnum]['args']))
                            main_window.hud.post('Automatically Skipping Layer %d' % (lnum))
                            main_window.hud.post('ref image: %s   base image: %s' % (ref_fn, base_fn))
                        al_stack_old[lnum]['skip'] = True
                    print("results_dict['need_to_write_json'] = ", results_dict['need_to_write_json'])
                    self.need_to_write_json = results_dict['need_to_write_json']  # It's not clear how this should be used (many to one)

            '''
            # Propagate the AFMs to generate and appropriate CFM at each layer
            null_biases = self.updated_model['data']['scales'][cur_scale_new_key]['null_cafm_trends']
            SetStackCafm ( self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'], null_biases=null_biases )

            destination_path = self.project['data']['destination_path']
            bias_data_path = os.path.join(destination_path,cur_scale_new_key,'bias_data')
            em.save_bias_analysis(self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'], bias_data_path)

            use_bounding_rect = self.updated_model['data']['scales'][cur_scale_new_key]['use_bounding_rect']
            if use_bounding_rect:
              rect = BoundingRect( self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'] )
            '''

            # Reset task_queue
            self.task_queue.stop()
            del self.task_queue
            self.task_queue = None

            self.project = self.updated_model

            if self.generate_images:
                self.generate_aligned_images()

            #0615 fix bug where bias_data is only saved if/when images are generated
            #0619 this is probably causing the problems
            cur_scale = self.project['data']['current_scale']
            bias_data_path = os.path.join(self.project['data']['destination_path'], self.project['data']['current_scale'], 'bias_data')
            em.save_bias_analysis(self.project['data']['scales'][cur_scale]['alignment_stack'], bias_data_path) # <-- call to save bias data


        #   Run Project in Serial Mode:
        #   Note: does not generate aligned images here
        else:

            # Run the project directly as one serial model
            # print ( "Running the project as one serial model")

            # **** run_json_project call ****
            self.updated_model, self.need_to_write_json = run_json_project(
                project=self.project,
                alignment_option=self.alignment_option,
                use_scale=self.use_scale,
                swiftir_code_mode=self.swiftir_code_mode,
                start_layer=self.start_layer,
                num_layers=self.num_layers)
            self.project = self.updated_model



        # print("\nAlignment Complete\n")
    #
    # # Class Method to Generate the Aligned Images
    # def generate_aligned_images(self):
    #     print("\nproject_runner.generate_aligned_images was called by " + inspect.stack()[1].function)
    #
    #
    #     cur_scale = self.project['data']['current_scale']
    #
    #     # Propagate the AFMs to generate and appropriate CFM at each layer
    #     null_biases = self.project['data']['scales'][cur_scale]['null_cafm_trends']
    #     # SetStackCafm ( self.project['data']['scales'][cur_scale]['alignment_stack'], null_biases )
    #     SetStackCafm(self.project['data']['scales'][cur_scale], null_biases=null_biases)
    #
    #     destination_path = self.project['data']['destination_path']
    #     bias_data_path = os.path.join(destination_path, cur_scale, 'bias_data')
    #     em.save_bias_analysis(self.project['data']['scales'][cur_scale]['alignment_stack'], bias_data_path) # <-- call to save bias data
    #
    #     use_bounding_rect = self.project['data']['scales'][cur_scale]['use_bounding_rect']
    #     print('project_runner.do_alignment | type(use_bounding_rect) = ', type(use_bounding_rect))
    #     print('project_runner.do_alignment | use_bounding_rect = ', use_bounding_rect)
    #
    #     if use_bounding_rect:
    #         rect = BoundingRect(self.project['data']['scales'][cur_scale]['alignment_stack'])
    #
    #     with open(os.path.join(bias_data_path,'bounding_rect.dat'), 'w') as file:  # Use file to refer to the file object
    #         if use_bounding_rect:
    #             file.write("%d %d %d %d\n" % (rect[0],rect[1],rect[2],rect[3]) )
    #         else:
    #             file.write("None\n")
    #
    #
    #     # Finally generate the images with a parallel run of image_apply_affine.py
    #
    #     self.task_queue = task_queue.TaskQueue(n_tasks=em.getNumImportedImages())
    #     cpus = psutil.cpu_count(logical=False)
    #     if cpus > 48:
    #         cpus = 48
    #     print("Starting Project Runner Task Queue with %d CPUs" % (cpus))
    #     self.task_queue.start(cpus)
    #
    #     my_path = os.path.split(os.path.realpath(__file__))[0]
    #     # apply_affine_job = os.path.join(my_path, 'source/Qt/package/image_apply_affine.py')
    #     apply_affine_job = os.path.join(my_path, 'image_apply_affine.py')
    #     print("project_runnner.generate_aligned_images | class=project_runner | apply_affine_job=",apply_affine_job)
    #     scale_key = "scale_%d" % self.use_scale
    #     alstack = self.project['data']['scales'][scale_key]['alignment_stack']
    #
    #     if self.num_layers == -1:
    #         end_layer = len(alstack)
    #     else:
    #         end_layer = self.start_layer + self.num_layers
    #
    #     # Previous code at top of main loop:
    #     #      for tnum in range(len(tasks_by_start_layer)):
    #     #        tdata = tasks_by_start_layer[tnum]
    #     #        layer_index = int(tdata['args'][5])  # Note the hard-coded index of 5 here is not the best way to go!!
    #     #        layer = self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'][layer_index]
    #
    #     #  Loop over the stack:
    #     for layer in alstack[self.start_layer:end_layer + 1]:
    #
    #         base_name = layer['images']['base']['filename']
    #         ref_name = layer['images']['ref']['filename']
    #
    #         al_path, fn = os.path.split(base_name)
    #         al_name = os.path.join(os.path.split(al_path)[0], 'img_aligned', fn)
    #
    #         layer['images']['aligned'] = {}
    #         layer['images']['aligned']['filename'] = al_name
    #
    #         cafm = layer['align_to_ref_method']['method_results']['cumulative_afm']
    #
    #         # print_debug ( -1, 'Run processes for: python image_apply_affine.py [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name' )
    #
    #         if use_bounding_rect:
    #             args = [sys.executable,
    #                     apply_affine_job,
    #                     '-gray',
    #                     '-rect',
    #                     str(rect[0]),
    #                     str(rect[1]),
    #                     str(rect[2]),
    #                     str(rect[3]),
    #                     '-afm',
    #                     str(cafm[0][0]),
    #                     str(cafm[0][1]),
    #                     str(cafm[0][2]),
    #                     str(cafm[1][0]),
    #                     str(cafm[1][1]),
    #                     str(cafm[1][2]),
    #                     base_name,
    #                     al_name
    #                     ]
    #         else:
    #             args = [sys.executable,
    #                     apply_affine_job,
    #                     '-gray',
    #                     '-afm',
    #                     str(cafm[0][0]),
    #                     str(cafm[0][1]),
    #                     str(cafm[0][2]),
    #                     str(cafm[1][0]),
    #                     str(cafm[1][1]),
    #                     str(cafm[1][2]),
    #                     base_name,
    #                     al_name
    #                     ]
    #
    #         '''
    #         self.task_queue.add_task ( cmd=sys.executable,
    #                                    args=args,
    #                                    wd='.' )
    #                                    # wd=self.project['data']['destination_path'] )
    #         '''
    #
    #         self.task_queue.add_task(args)
    #
    #     # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
    #
    #     print_debug(-1, 'Waiting for ImageApplyAffine Tasks to Complete...')
    #     t1 = time.time()
    #     self.task_queue.collect_results()
    #     t3 = time.time()
    #     dt = t3 - t1
    #     print_debug(-1, 'ImageApplyAffine Tasks Completed in %.2f seconds' % (dt))
    #
    #     if self.t0 != 0:
    #         tt = t3 - self.t0
    #         print_debug(-1, 'Total Alignment Time: %.2f seconds' % (tt))
    #
    #     self.task_queue.stop()
    #
    #     del self.task_queue
    #     self.task_queue = None
    #
    #     print('\nGenerating Aligned Images Complete\n')
    #
    #






    #
    # def do_alignment(self, alignment_option='init_affine', generate_images=True):
    #     print(
    #         "\nproject_runner.do_alignment(alignment_option=%s,generate_images=%s):" % (alignment_option, generate_images))
    #
    #     self.alignment_option = alignment_option
    #     self.generate_images = generate_images
    #
    #     # print ( "Starting Alignment Jobs" )
    #
    #     # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
    #
    #     scale_key = "scale_%d" % self.use_scale
    #     alstack = self.project['data']['scales'][scale_key]['alignment_stack']
    #
    #     if self.run_parallel:
    #
    #         # Run the project as a series of jobs
    #
    #         # Write the entire project as a single JSON file with a unique stable name for this run
    #
    #         # f = tempfile.NamedTemporaryFile (prefix="temp_proj_", suffix=".json", dir=self.project['data']['destination_path'], delete=False)
    #         # run_project_name = f.name
    #         # f.close()
    #         # print ("Temp file is: " + str (f.name))
    #         run_project_name = os.path.join(self.project['data']['destination_path'],
    #                                         "../../../../project_runner_job_file.json")
    #         f = open(run_project_name, 'w')
    #         jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
    #         proj_json = jde.encode(self.project)
    #         f.write(proj_json)
    #         f.close()
    #
    #         # Prepare the task queue
    #
    #         #      task_queue.debug_level = alignem.debug_level
    #         #      task_wrapper.debug_level = alignem.debug_level
    #         #      self.task_queue = task_queue.TaskQueue(sys.executable)
    #         #      cpus = psutil.cpu_count(logical=False)
    #         #      print("Starting Project Runner Task Queue with %d CPUs" % (cpus))
    #         #      self.task_queue.start (cpus)
    #         #      self.task_queue.notify = False
    #         #      self.task_queue.passthrough_stdout = False
    #         #      self.task_queue.passthrough_stderr = False
    #
    #         # self.task_queue = task_queue.TaskQueue()
    #         self.task_queue = task_queue.TaskQueue(n_tasks=20) #TEMP #0707
    #         cpus = psutil.cpu_count(logical=False)
    #         if cpus > 48:
    #             cpus = 48
    #         print("Starting Project Runner Task Queue with %d CPUs (TaskQueue.start)" % (cpus))
    #         self.task_queue.start(cpus)
    #
    #         my_path = os.path.split(os.path.realpath(__file__))[0]
    #         # align_job = os.path.join(my_path, 'source/Qt/package/single_alignment_job.py')
    #         align_job = os.path.join(my_path, 'single_alignment_job.py')
    #         print('(tag) (do_align) project_runner | do_alignment | align_job=', align_job)
    #         # (tag) (do_align) project_runner | do_alignment | align_job= /Users/joelyancey/glanceem_swift/swift-ir/source/Qt/package/single_alignment_job.py
    #
    #         # for layer in tqdm(alstack):
    #         for layer in alstack:
    #             lnum = alstack.index(layer)
    #             skip = False
    #             if 'skip' in layer:
    #                 skip = layer['skip']
    #             if False and skip:
    #
    #                 print_debug(-1, "\n\n" + (20 * 'Skip') + '\n   Skipping layer ' + str(lnum) + '\n' + (
    #                         20 * 'Skip') + "\n\n")
    #
    #             else:
    #
    #                 if print_switch: print_debug(1, "Starting a task for layer " + str(lnum))
    #                 '''
    #                 self.task_queue.add_task ( cmd=sys.executable,
    #                                            args=[ align_job,                     # Python program to run (single_alignment_job)
    #                                                   str(run_project_name),         # Project file name
    #                                                   str(self.alignment_option),    # Init, Refine, or Apply
    #                                                   str(self.use_scale),           # Scale to use or 0
    #                                                   str(self.swiftir_code_mode),   # Python or C mode
    #                                                   str(lnum),                     # First layer number to run from Project file
    #                                                   str(1),                        # Number of layers to run
    #                                                   str(self.use_file_not_pipe)    # Flag (0 or 1) for pipe/file I/O. 0=Pipe, 1=File
    #                                                   ],
    #                                            wd='.' )
    #                                            # wd=self.project['data']['destination_path'] )
    #                 '''
    #
    #                 # Use task_queue_mp
    #                 task_args = [sys.executable,
    #                              align_job,  # Python program to run (single_alignment_job)
    #                              str(run_project_name),  # Project file name
    #                              str(self.alignment_option),  # Init, Refine, or Apply
    #                              str(self.use_scale),  # Scale to use or 0
    #                              str(self.swiftir_code_mode),  # Python or C mode
    #                              str(lnum),  # First layer number to run from Project file
    #                              str(1),  # Number of layers to run
    #                              str(self.use_file_not_pipe)  # Flag (0 or 1) for pipe/file I/O. 0=Pipe, 1=File
    #                              ]
    #                 if print_switch: print_debug(50, "project_runner.do_alignment | Starting task_queue_mp with args:")
    #                 for p in task_args:
    #                     print_debug(50, "  " + str(p))
    #
    #                 self.task_queue.add_task(task_args)
    #
    #         # self.task_queue.work_q.join()
    #
    #         self.t0 = time.time()
    #         if print_switch: print_debug(-1, 'project_runner.do_alignment | Waiting for Alignment Tasks to Complete...')
    #         self.task_queue.collect_results()
    #         dt = time.time() - self.t0
    #         #  print_debug ( -1, 'Alignment Tasks Completed in %.2f seconds' % (dt) )
    #
    #         # Check status of all tasks and report final tally
    #         # print ("Tasks completed with these arguments")
    #         n_tasks = len(self.task_queue.task_dict.keys())
    #         n_success = 0
    #         n_queued = 0
    #         n_failed = 0
    #         for k in self.task_queue.task_dict.keys():
    #             task_item = self.task_queue.task_dict[k]
    #             status = task_item['status']
    #             if status == 'completed':
    #                 n_success += 1
    #             elif status == 'queued':
    #                 n_queued += 1
    #             elif status == 'task_error':
    #                 print_debug(-1, '\nTask Error:')
    #                 print_debug(-1, '   CMD:    %s' % (str(task_item['cmd'])))
    #                 print_debug(-1, '   ARGS:   %s' % (str(task_item['args'])))
    #                 print_debug(-1, '   STDERR: %s\n' % (str(task_item['stderr'])))
    #                 n_failed += 1
    #             #        print_debug ( -1, 'Task STDOUT: \n%s\n' % (task_item['stdout']))
    #             #        print_debug ( -1, 'Task STDERR: \n%s\n' % (task_item['stderr']))
    #             # print ( '  ' + str(self.task_queue.task_dict[k]['args']) + " " + str(self.task_queue.task_dict[k]['status']) )
    #             #        if self.task_queue.task_dict[k]['status'] == 'task_error':
    #             #          print_debug ( -1, '  ' + str(self.task_queue.task_dict[k]['cmd']) + " " + str(self.task_queue.task_dict[k]['args']) )
    #             pass
    #         if print_switch:
    #             print_debug(-1, '%d Alignment Tasks Completed in %.2f seconds' % (n_tasks, dt))
    #             print_debug(-1, '    Num Successful:   %d' % (n_success))
    #             print_debug(-1, '    Num Still Queued: %d' % (n_queued))
    #             print_debug(-1, '    Num Failed:       %d' % (n_failed))
    #
    #         # Sort the tasks by layers rather than by process IDs
    #         task_dict_by_start_layer = {}
    #         for k in self.task_queue.task_dict.keys():
    #             t = self.task_queue.task_dict[k]
    #             task_dict_by_start_layer[int(t['args'][5])] = t
    #
    #         # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
    #
    #         tasks_by_start_layer = []
    #         for k in sorted(task_dict_by_start_layer.keys()):
    #             tasks_by_start_layer.append(task_dict_by_start_layer[k])
    #
    #         # print ("Tasks sorted by layer numbers")
    #         for l in tasks_by_start_layer:
    #             # print ( '  ' + str(l['args']) + '  ' + str(l['status']) )
    #             pass
    #
    #         # Integrate the output from each task into a new combined data model
    #
    #         self.updated_model = copy.deepcopy(self.project)
    #
    #         cur_scale_new_key = self.updated_model['data']['current_scale']
    #         if self.use_scale > 0:
    #             cur_scale_new_key = 'scale_' + str(self.use_scale)
    #
    #         for tnum in range(len(tasks_by_start_layer)):
    #
    #             if self.use_file_not_pipe:
    #                 if print_switch: print('\n\n' + (80 * '#') + '\nUsing File I/O\n' + (80 * '#') + '\n\n')
    #                 # Get the updated data model from the file written by single_alignment_job
    #                 # Start by getting the location of the project's output files:
    #                 output_dir = os.path.join(os.path.split(run_project_name)[0], scale_key)
    #                 # Get the name of the file for this task number
    #                 # NOTE / TODO : This uses the TASK NUMBER and NOT the LAYER NUMBER ... THEY MAY BE DIFFERENT!!
    #                 output_file = "single_alignment_out_" + str(tnum) + ".json"
    #                 with open(os.path.join(output_dir, output_file),
    #                           'r') as job_output_file:  # Use file to refer to the file object
    #                     dm_text = job_output_file.read()
    #                 # job_output_file = open(os.path.join(output_dir, output_file), 'r')
    #                 # dm_text = job_output_file.read()
    #                 # job_output_file.close()
    #                 # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
    #
    #             else:
    #                 print_debug(50, '\n\n' + (80 * '#') + '\nUsing Pipe I/O\n' + (80 * '#') + '\n\n')
    #                 # Get the updated data model from stdout for the task
    #                 parts = tasks_by_start_layer[tnum]['stdout'].split('---JSON-DELIMITER---')
    #                 dm_text = None
    #                 for p in parts:
    #                     ps = p.strip()
    #                     if ps.startswith('{') and ps.endswith('}'):
    #                         dm_text = p
    #
    #             if dm_text != None:
    #                 results_dict = json.loads(dm_text)
    #                 fdm_new = results_dict['data_model']
    #
    #                 # Get the same scale from both the old and new data models
    #                 cur_scale_new = fdm_new['data']['scales'][cur_scale_new_key]
    #                 cur_scale_old = self.updated_model['data']['scales'][cur_scale_new_key]
    #
    #                 al_stack_old = cur_scale_old['alignment_stack']
    #                 al_stack_new = cur_scale_new['alignment_stack']
    #
    #                 lnum = int(tasks_by_start_layer[tnum]['args'][5])  # Note that this may differ from tnum!!
    #
    #                 al_stack_old[lnum] = al_stack_new[lnum]
    #
    #                 if tasks_by_start_layer[tnum]['status'] == 'task_error':
    #                     ref_fn = al_stack_old[lnum]['images']['ref']['filename']
    #                     base_fn = al_stack_old[lnum]['images']['base']['filename']
    #                     if print_switch:
    #                         print_debug(-1, 'Alignment Task Error at: ' + str(tasks_by_start_layer[tnum]['cmd']) + " " + str(
    #                                 tasks_by_start_layer[tnum]['args']))
    #                         print_debug(-1, 'Automatically Skipping Layer %d' % (lnum))
    #                         print_debug(-1, 'ref image: %s   base image: %s' % (ref_fn, base_fn))
    #                     al_stack_old[lnum]['skip'] = True
    #
    #                 self.need_to_write_json = results_dict[
    #                     'need_to_write_json']  # It's not clear how this should be used (many to one)
    #
    #         '''
    #         # Propagate the AFMs to generate and appropriate CFM at each layer
    #         null_biases = self.updated_model['data']['scales'][cur_scale_new_key]['null_cafm_trends']
    #         SetStackCafm ( self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'], null_biases=null_biases )
    #
    #         destination_path = self.project['data']['destination_path']
    #         bias_data_path = os.path.join(destination_path,cur_scale_new_key,'bias_data')
    #         save_bias_analysis(self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'], bias_data_path)
    #
    #         use_bounding_rect = self.updated_model['data']['scales'][cur_scale_new_key]['use_bounding_rect']
    #         if use_bounding_rect:
    #           rect = BoundingRect( self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'] )
    #         '''
    #
    #         # Reset task_queue
    #         self.task_queue.stop()
    #         del self.task_queue
    #         self.task_queue = None
    #
    #         self.project = self.updated_model
    #
    #         if self.generate_images:
    #             self.generate_aligned_images()
    #
    #         # 0615 fix bug where bias_data is only saved if/when images are generated
    #         # 0619 this is probably causing the problems
    #         cur_scale = self.project['data']['current_scale']
    #         bias_data_path = os.path.join(self.project['data']['destination_path'], self.project['data']['current_scale'],
    #                                       'bias_data')
    #         save_bias_analysis(self.project['data']['scales'][cur_scale]['alignment_stack'],
    #                                        bias_data_path)  # <-- call to save bias data
    #
    #
    #     #   Run Project in Serial Mode:
    #     #   Note: does not generate aligned images here
    #     else:
    #
    #         # Run the project directly as one serial model
    #         # print ( "Running the project as one serial model")
    #
    #         self.updated_model, self.need_to_write_json = run_json_project(
    #                 project=self.project,
    #                 alignment_option=self.alignment_option,
    #                 use_scale=self.use_scale,
    #                 swiftir_code_mode=self.swiftir_code_mode,
    #                 start_layer=self.start_layer,
    #                 num_layers=self.num_layers)
    #         self.project = self.updated_model
    #
    #     # print("\nAlignment Complete\n")
    #
    #     # Class Method to Generate the Aligned Images


    def generate_aligned_images(self):
        '''Called one time without arguments by 'project_runner.do_alignment' '''

        print("\nproject_runner.generate_aligned_images was called by " + inspect.stack()[1].function)

        cur_scale = self.project['data']['current_scale']

        # Propagate the AFMs to generate and appropriate CFM at each layer
        null_biases = self.project['data']['scales'][cur_scale]['null_cafm_trends']
        # SetStackCafm ( self.project['data']['scales'][cur_scale]['alignment_stack'], null_biases )
        SetStackCafm(self.project['data']['scales'][cur_scale], null_biases=null_biases)

        destination_path = self.project['data']['destination_path']
        bias_data_path = os.path.join(destination_path, cur_scale, 'bias_data')
        save_bias_analysis(self.project['data']['scales'][cur_scale]['alignment_stack'],
                                       bias_data_path)  # <-- call to save bias data

        use_bounding_rect = self.project['data']['scales'][cur_scale]['use_bounding_rect']

        if use_bounding_rect:
            rect = BoundingRect(self.project['data']['scales'][cur_scale]['alignment_stack'])

        with open(os.path.join(bias_data_path, 'bounding_rect.dat'), 'w') as file:  # Use file to refer to the file object
            if use_bounding_rect:
                file.write("%d %d %d %d\n" % (rect[0], rect[1], rect[2], rect[3]))
            else:
                file.write("None\n")

        # Finally generate the images with a parallel run of image_apply_affine.py

        self.task_queue = task_queue.TaskQueue()
        cpus = psutil.cpu_count(logical=False)
        if cpus > 48:
            cpus = 48
        print("Starting Project Runner Task Queue with %d CPUs" % (cpus))
        self.task_queue.start(cpus)

        my_path = os.path.split(os.path.realpath(__file__))[0]
        # apply_affine_job = os.path.join(my_path, 'source/Qt/package/image_apply_affine.py')
        apply_affine_job = os.path.join(my_path, 'image_apply_affine.py')
        print("(tag) project_runnner | class=project_runner | apply_affine_job=", apply_affine_job)
        scale_key = "scale_%d" % self.use_scale
        alstack = self.project['data']['scales'][scale_key]['alignment_stack']

        if self.num_layers == -1:
            end_layer = len(alstack)
        else:
            end_layer = self.start_layer + self.num_layers

        # Previous code at top of main loop:
        #      for tnum in range(len(tasks_by_start_layer)):
        #        tdata = tasks_by_start_layer[tnum]
        #        layer_index = int(tdata['args'][5])  # Note the hard-coded index of 5 here is not the best way to go!!
        #        layer = self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'][layer_index]

        #  Loop over the stack:
        for layer in alstack[self.start_layer:end_layer + 1]:

            base_name = layer['images']['base']['filename']
            ref_name = layer['images']['ref']['filename']

            al_path, fn = os.path.split(base_name)
            al_name = os.path.join(os.path.split(al_path)[0], 'img_aligned', fn)

            layer['images']['aligned'] = {}
            layer['images']['aligned']['filename'] = al_name

            cafm = layer['align_to_ref_method']['method_results']['cumulative_afm']

            # print_debug ( -1, 'Run processes for: python image_apply_affine.py [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name' )

            if use_bounding_rect:
                args = [sys.executable,
                        apply_affine_job,
                        '-gray',
                        '-rect',
                        str(rect[0]),
                        str(rect[1]),
                        str(rect[2]),
                        str(rect[3]),
                        '-afm',
                        str(cafm[0][0]),
                        str(cafm[0][1]),
                        str(cafm[0][2]),
                        str(cafm[1][0]),
                        str(cafm[1][1]),
                        str(cafm[1][2]),
                        base_name,
                        al_name
                        ]
            else:
                args = [sys.executable,
                        apply_affine_job,
                        '-gray',
                        '-afm',
                        str(cafm[0][0]),
                        str(cafm[0][1]),
                        str(cafm[0][2]),
                        str(cafm[1][0]),
                        str(cafm[1][1]),
                        str(cafm[1][2]),
                        base_name,
                        al_name
                        ]

            '''
            self.task_queue.add_task ( cmd=sys.executable,
                                       args=args,
                                       wd='.' )
                                       # wd=self.project['data']['destination_path'] )
            '''

            self.task_queue.add_task(args)

        # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })

        print_debug(-1, 'Waiting for ImageApplyAffine Tasks to Complete...')
        t1 = time.time()
        self.task_queue.collect_results()
        t3 = time.time()
        dt = t3 - t1
        print_debug(-1, 'ImageApplyAffine Tasks Completed in %.2f seconds' % (dt))

        if self.t0 != 0:
            tt = t3 - self.t0
            print_debug(-1, 'Total Alignment Time: %.2f seconds' % (tt))

        self.task_queue.stop()

        del self.task_queue
        self.task_queue = None

        print('\nGenerating Aligned Images Complete\n')


    def get_updated_data_model(self):
        # print ( "Returning the updated data model" )
        #    return self.updated_model
        return self.project


'''
if (__name__ == '__main__'):
  # print ("Align Task Manager run as main ... not sure what this should do.")
  from argparse import ArgumentParser
  import time
  my_q = task_queue.TaskQueue (sys.executable)
  cpus = 3
  my_q.start(cpus)
  my_q.notify = True
  begin = time.time ()
  wd = '.'
  my_q.add_task (cmd='cp foo.txt foo_1.txt', wd=wd)
  my_q.add_task (cmd='cp foo.txt foo_2.txt', wd=wd)
  my_q.add_task (cmd='cp foo.txt foo_3.txt', wd=wd)
  my_q.add_task (cmd='cp foo.txt foo_4.txt', wd=wd)
  my_q.add_task (cmd='pwd', wd=wd)
  my_q.add_task (cmd='ls', args='.', wd=wd)
  my_q.add_task (cmd='echo', args='Hello World!!!', wd=wd)
  time.sleep (2.)
  pids = list (my_q.task_dict.keys ())
  pids.sort ()
  my_q.work_q.join ()
  if debug_level > 4: sys.stdout.write ('\n\nTook {0:0.2f} seconds.\n\n'.format (time.time () - begin))
'''

'''
  if (len(sys.argv)<3):
    print_command_line_syntax (sys.argv)
    exit(1)
  proj_ifn = sys.argv[-2]
  proj_ofn = sys.argv[-1]
  use_scale = 0
  alignment_option = 'refine_affine'
  scale_tbd = 0
  finest_scale_done = 0
  swiftir_code_mode = 'python'
  start_layer = 0
  num_layers = -1
  run_as_master = False
  run_as_worker = False
  alone = False
  # Scan arguments (excluding program name and last 2 file names)
  i = 1
  while (i < len(sys.argv)-2):
    print ( "Processing option " + sys.argv[i])
    if sys.argv[i] == '-master':
      run_as_master = True
      # No need to increment i because no additional arguments were taken
    elif sys.argv [i] == '-worker':
      run_as_worker = True
      alone = True
      # No need to increment i because no additional arguments were taken
    elif sys.argv[i] == '-scale':
      i += 1  # Increment to get the argument
      use_scale = int(sys.argv[i])
    elif sys.argv[i] == '-code':
      i += 1  # Increment to get the argument
      # align_swiftir.global_swiftir_mode = str(sys.argv[i+1])
      swiftir_code_mode = str(sys.argv[i])
    elif sys.argv [i] == '-alignment_option':
      i += 1  # Increment to get the argument
      alignment_option = sys.argv [i]
    elif sys.argv [i] == '-start':
      i += 1  # Increment to get the argument
      start_layer = int(sys.argv [i])
    elif sys.argv [i] == '-count':
      i += 1  # Increment to get the argument
      num_layers = int (sys.argv [i])
    elif sys.argv [i] == '-debug':
      i += 1  # Increment to get the argument
      debug_level = int (sys.argv [i])
    else:
      print ( "\nImproper argument list: " + str(argv) + "\n")
      print_command_line_syntax ( sys.argv )
      exit(1)
    i += 1  # Increment to get the next option
  #fp = open('/m2scratch/bartol/swift-ir_tests/LM9R5CA1_project.json','r')
  fp = open(proj_ifn,'r')
  d = json.load(fp)
  need_to_write_json = False
  if run_as_worker:
    # This task was called to just process one layer
    print_debug ( 1, "Running as a worker for just one layer with PID=" + str(os.getpid()) )
    # Chop up the JSON project so that the only layer is the one requested
    for scale_key in d['data']['scales'].keys():
      scale = d['data']['scales'][scale_key]
      # Set the entire stack equal to the single layer that needs to be aligned (including both ref and base)
      scale['alignment_stack'] = [ scale['alignment_stack'][start_layer] ]
    # Call run_json_project with the partial data model and the "alone" flag set to True
    d, need_to_write_json = run_json_project ( project=d,
                                               alignment_option=alignment_option,
                                               use_scale=use_scale,
                                               swiftir_code_mode=swiftir_code_mode,
                                               start_layer=start_layer,
                                               num_layers=num_layers,
                                               alone=True)
    # When run as a worker, always return the data model to the master on stdout
    print ("NEED TO RETURN DATA MODEL TO MASTER from PID=" + str(os.getpid()))
  elif run_as_master:
    print_debug ( -1, "Error: The \"run_as_master\" flag should not be used in the current design." )
    exit(99)
  else:
    # This task was called to process the entire stack in serial mode
    print_debug ( 1, "Running in serial mode with PID=" + str(os.getpid()) )
    align_swiftir.debug_level = debug_level
    print_debug ( 20, "Before RJP: " + str( [ d['data']['current_scale'], alignment_option, use_scale, swiftir_code_mode, start_layer, num_layers, alone ] ) )
    d, need_to_write_json = run_json_project ( project=d,
                                               alignment_option=alignment_option,
                                               use_scale=use_scale,
                                               swiftir_code_mode=swiftir_code_mode,
                                               start_layer=start_layer,
                                               num_layers=num_layers,
                                               alone=alone)
    if need_to_write_json:
      # Write out updated json project file
      print_debug(50,"Writing project to file: ", proj_ofn)
      ofp = open(proj_ofn,'w')
      json.dump(d,ofp, sort_keys=True, indent=2, separators=(',', ': '))
'''











#
#
# #!/usr/bin/env python2.7
# # print(f'project_runner.py | Loading {__name__}')
# import logging
# import sys
# import os
# import time
# import json
# import copy
# import inspect
# import psutil
# import inspect
# from tqdm import tqdm
#
# try: import package.task_queue_mp as task_queue
# except: import task_queue_mp as task_queue
#
# try: import package.pyswift_tui as pyswift_tui
# except: import pyswift_tui
#
# try: import package.config as cfg
# except: import config as cfg
#
# try: import package.glanceem_utils as gu
# except: import glanceem_utils as gu
#
# # This is monotonic (0 to 100) with the amount of output:
# debug_level = 0  # A larger value prints more stuff
# # debug_level = 100  # A larger value prints more stuff
#
# # Using the Python version does not work because the Python 3 code can't
# # even be parsed by Python2. It could be dynamically compiled, or use the
# # alternate syntax, but that's more work than it's worth for now.
# if sys.version_info >= (3, 0):
#     # print ( "Python 3: Supports arbitrary arguments via print")
#     # def print_debug ( level, *ds ):
#     #  # print_debug ( 1, "This is really important!!" )
#     #  # print_debug ( 99, "This isn't very important." )
#     #  global debug_level
#     #  if level <= debug_level:
#     #    print ( *ds )
#     pass
# else:
#     # print ("Python 2: Use default parameters for limited support of arbitrary arguments via print")
#     pass
#
#
# # For now, always use the limited argument version
# def print_debug(level, p1=None, p2=None, p3=None, p4=None, p5=None):
#     # print_debug ( 1, "This is really important!!" )
#     # print_debug ( 99, "This isn't very important." )
#     global debug_level
#     if level <= debug_level:
#         if p1 == None:
#             print("")
#         elif p2 == None:
#             print(str(p1))
#         elif p3 == None:
#             print(str(p1) + str(p2))
#         elif p4 == None:
#             print(str(p1) + str(p2) + str(p3))
#         elif p5 == None:
#             print(str(p1) + str(p2) + str(p3) + str(p4))
#         else:
#             print(str(p1) + str(p2) + str(p3) + str(p4) + str(p5))
#
#
# def print_debug_enter(level):
#     if level <= debug_level:
#         call_stack = inspect.stack()
#         # print ( "Call Stack: " + str([stack_item.function for stack_item in call_stack][1:]) )
#
#
#
#
# class project_runner:
#     ''' Run an alignment project by splitting it up by scales and/or layers '''
#
#     # The project_runner starts with a Full Data Model (FDM)
#     # The project_runner may run in either serial or parallel mode
#     # When running in serial mode, the project_runner calls run_json_project directly
#     # When running in parallel mode:
#     #   The project_runner writes the FDM to a temporary file to be read by the worker tasks
#     #   The project_runner breaks up the alignment layers into specific jobs and starts a worker (pyswift_tui) for each job
#     #   Each worker will see the temporary data model file and get command line parameters about which part(s) it must complete
#     #   The project_runner will collect the alignment data from each pyswift_tui run and integrate it into the "master" data model
#     #  def __init__ ( self, project=None, alignment_option='init_affine', use_scale=0, swiftir_code_mode='python', start_layer=0, num_layers=-1, run_parallel=False, use_file_io=True ):
#     def __init__(self, project:dict, current_scale:int):
#
#         self.project = copy.deepcopy(project)
#         self.alignment_option = 'init_affine'
#         self.use_scale = current_scale
#         # self.swiftir_code_mode = 'c'
#         # self.swiftir_code_mode = 'python'
#         # self.swiftir_code_mode = 'c'
#         self.swiftir_code_mode = 'python'
#         self.start_layer = 0
#         self.num_layers = -1
#         self.generate_images = True
#         self.run_parallel = True
#         self.task_queue = None
#         self.updated_model = None
#         self.need_to_write_json = None
#         self.use_file_not_pipe = 0
#         self.t0 = 0
#         print('project_runner (constructor):', self.generate_images)
#         print('project_runner (constructor) | Alignment Option?  ', self.alignment_option)
#         print('project_runner (constructor) | Which Scale?  ', self.use_scale)
#         print('project_runner (constructor) | SWiFT-IR Code Mode?  ', self.swiftir_code_mode)
#         print('project_runner (constructor) | Use File Not Pipe?  ', self.use_file_not_pipe)
#         print('project_runner (constructor) | Run Parallel?  ', self.run_parallel)
#         print('project_runner (constructor) | Generate Images?  ', self.generate_images)
#         print('project_runner (constructor) | type(self.project)?  ', type(self.project))
#         print('project_runner (constructor) | sys.getsizeof(self.project)?  ', sys.getsizeof(self.project))
#
#     # Class Method to Align the Stack
#     #  def start ( self ):
#     def do_alignment(self, alignment_option='init_affine', generate_images=True):
#         print("project_runner.do_alignment(%s,generate_images=%s) >>>>>>>>" % (alignment_option,generate_images))
#         self.alignment_option = alignment_option
#         self.generate_images = generate_images
#         # print ( "Starting Alignment Jobs" )
#         self.scale_key=em.get_scale_key(self.use_scale)
#         print('project_runner.do_alignment | scale_key = ', self.scale_key)
#         alstack = self.project['data']['scales'][self.scale_key]['alignment_stack']
#         self.n_tasks = len(alstack)
#         print('project_runner.do_alignment | len(alstack) = n_tasks = ', self.n_tasks)
#         print('project_runner.do_alignment | # of tasks: ', self.n_tasks)
#
#         if self.run_parallel:
#             # Run the project as a series of jobs
#             # Write the entire project as a single JSON file with a unique stable name for this run
#             # f = tempfile.NamedTemporaryFile (prefix="temp_proj_", suffix=".json", dir=self.project['data']['destination_path'], delete=False)
#             run_project_name = os.path.join(self.project['data']['destination_path'], "project_runner_job_file.json")
#             print('project_runner.do_alignment | Temp file name is', run_project_name)
#             f = open(run_project_name, 'w')
#             jde = json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
#             proj_json = jde.encode(self.project)
#             f.write(proj_json)
#             f.close()
#             main_window.hud.post('Starting up task queue')
#             self.task_queue = task_queue.TaskQueue(n_tasks=self.n_tasks)
#             cpus = min(psutil.cpu_count(logical=False), 48)
#             print("project_runner.do_alignment | Starting Task Queue with %d CPUs (TaskQueue.start)..." % cpus)
#             self.task_queue.start(cpus)
#
#             my_path = os.path.split(os.path.realpath(__file__))[0]
#             # path = os.path.join(my_path, 'source/Qt/package/single_alignment_job.py')
#             path = os.path.join(my_path, 'single_alignment_job.py')
#             print('\nproject_runner.do_alignment | my path = %s' % my_path)
#             print('project_runner.do_alignment | align path = %s\n' % path)
#             try:
#                 os.path.isfile(path)
#             except:
#                 print('EXCEPTION | Invalid Alignment Script Path')
#                 main_window.hud.post('Invalid Alignment Script Path', logging.ERROR)
#
#             print('Adding %d tasks to the queue' % self.n_tasks)
#             for layer in alstack:
#                 '''This step is fast'''
#                 lnum = alstack.index(layer)
#                 skip = False
#
#                 if 'skip' in layer:
#                     skip = layer['skip']
#                 if False and skip:
#
#                     print_debug(-1, "\n\n" + (20 * 'Skip') + '\n   Skipping layer ' + str(lnum) + '\n' + (
#                                 20 * 'Skip') + "\n\n")
#
#                 else:
#                     task_args = [sys.executable,
#                                  path,  # Python program to run (single_alignment_job)
#                                  str(run_project_name),  # Project file name
#                                  str(self.alignment_option),  # Init, Refine, or Apply
#                                  str(self.use_scale),  # Scale to use or 0
#                                  str(self.swiftir_code_mode),  # Python or C mode
#                                  str(lnum),  # First layer number to run from Project file
#                                  str(1),  # Number of layers to run
#                                  str(self.use_file_not_pipe)  # Flag (0 or 1) for pipe/file I/O. 0=Pipe, 1=File
#                                  ]
#                     self.task_queue.add_task(task_args)
#
#                 # if lnum == 0:
#                 #     print('EXAMPLE TASK:')
#                 #     print('    Executable                :', sys.executable)
#                 #     print('    Project File              :', run_project_name)
#                 #     print('    Alignment Type / Scale    : %s / Scale %s' % (self.alignment_option, self.use_scale))
#                 #     print('    Code Mode / Use File IO   : %s / %s' % (self.swiftir_code_mode, bool(self.use_file_not_pipe)))
#
#             # self.task_queue.work_q.join()
#
#             self.t0 = time.time()
#             # print_debug(-1, 'project_runner.do_alignment | Waiting for Alignment Tasks to Complete...')
#
#             # print('project_runner.do_alignment | Collecting results...')
#             self.task_queue.collect_results() # <-- time-consuming step
#             dt = time.time() - self.t0
#             #  print_debug ( -1, 'Alignment Tasks Completed in %.2f seconds' % (dt) )
#
#             # Check status of all tasks and report final tally
#             # print ("Tasks completed with these arguments")
#             n_success = 0
#             n_queued = 0
#             n_failed = 0
#
#             main_window.hud.post('Checking success/failure status of completed tasks')
#
#             # pbar = tqdm(total = self.n_tasks)
#             i = 0
#             for k in self.task_queue.task_dict.keys():
#                 i += 1
#                 # pbar.update()
#                 # self.progress_callback.emit(int((i/n)*100))
#                 # print('k = ',k)
#                 task_item = self.task_queue.task_dict[k]
#                 status = task_item['status']
#                 if status == 'completed':
#                     n_success += 1
#                 elif status == 'queued':
#                     n_queued += 1
#                 elif status == 'task_error':
#                     print_debug(-1, '\nTask Error:')
#                     print_debug(-1, '   CMD:    %s' % (str(task_item['cmd'])))
#                     print_debug(-1, '   ARGS:   %s' % (str(task_item['args'])))
#                     print_debug(-1, '   STDERR: %s\n' % (str(task_item['stderr'])))
#                     n_failed += 1
#                 #        print_debug ( -1, 'Task STDOUT: \n%s\n' % (task_item['stdout']))
#                 #        print_debug ( -1, 'Task STDERR: \n%s\n' % (task_item['stderr']))
#                 # print ( '  ' + str(self.task_queue.task_dict[k]['args']) + " " + str(self.task_queue.task_dict[k]['status']) )
#                 #        if self.task_queue.task_dict[k]['status'] == 'task_error':
#                 #          print_debug ( -1, '  ' + str(self.task_queue.task_dict[k]['cmd']) + " " + str(self.task_queue.task_dict[k]['args']) )
#                 pass
#
#             print_debug(-1, '%d Alignment Tasks Completed in %.2f seconds' % (self.n_tasks, dt))
#             print_debug(-1, '    Num Successful:   %d' % (n_success))
#             print_debug(-1, '    Num Still Queued: %d' % (n_queued))
#             print_debug(-1, '    Num Failed:       %d' % (n_failed))
#
#             main_window.hud.post('%d Alignment Tasks Completed in %.2f seconds' % (self.n_tasks, dt))
#             main_window.hud.post('    Num Successful:   %d' % (n_success))
#             main_window.hud.post('    Num Still Queued: %d' % (n_queued))
#             main_window.hud.post('    Num Failed:       %d' % (n_failed))
#
#             # Sort the tasks by layers rather than by process IDs
#             task_dict_by_start_layer = {}
#             for k in self.task_queue.task_dict.keys():
#                 t = self.task_queue.task_dict[k]
#                 task_dict_by_start_layer[int(t['args'][5])] = t
#
#             # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
#
#             tasks_by_start_layer = []
#             for k in sorted(task_dict_by_start_layer.keys()):
#                 tasks_by_start_layer.append(task_dict_by_start_layer[k])
#
#             # print ("Tasks sorted by layer numbers")
#             for l in tasks_by_start_layer:
#                 # print ( '  ' + str(l['args']) + '  ' + str(l['status']) )
#                 pass
#
#             # Integrate the output from each task into a new combined data model
#
#             self.updated_model = copy.deepcopy(self.project)
#
#             cur_scale_new_key = self.updated_model['data']['current_scale']
#             if self.use_scale > 0:
#                 cur_scale_new_key = 'scale_' + str(self.use_scale)
#
#             # print('len(tasks_by_start_layer) = ',len(tasks_by_start_layer)) # <- equal to number of images
#             # with tqdm(total=len(tasks_by_start_layer)) as pbar:
#
#             if self.use_file_not_pipe:
#                 print('project_runner | self.use_file_not_pipe is True')
#             else:
#                 print('project_runner | self.use_file_not_pipe is False')
#
#             print('\nGetting the results...')
#
#             pbar = tqdm(total = self.n_tasks)
#             i=0
#             for tnum in range(len(tasks_by_start_layer)):
#                 i+=1
#                 pbar.update()
#                 # self.progress_callback.emit(int((i/n)*100))
#                 # print('tnum = ', tnum)
#                 # print("project_runner | tnum = ", tnum)
#
#                 if self.use_file_not_pipe:
#                     # print('\n\n' + (80 * '#') + '\nUsing File I/O\n' + (80 * '#') + '\n\n')
#                     # Get the updated data model from the file written by single_alignment_job
#                     # Start by getting the location of the project's output files:
#                     output_dir = os.path.join(os.path.split(run_project_name)[0], scale_key)
#                     # Get the name of the file for this task number
#                     # NOTE / TODO : This uses the TASK NUMBER and NOT the LAYER NUMBER ... THEY MAY BE DIFFERENT!!
#                     output_file = "single_alignment_out_" + str(tnum) + ".json"
#                     with open(os.path.join(output_dir, output_file), 'r') as job_output_file:  # Use file to refer to the file object
#                         dm_text = job_output_file.read()
#                     # job_output_file = open(os.path.join(output_dir, output_file), 'r')
#                     # dm_text = job_output_file.read()
#                     # job_output_file.close()
#                     # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
#
#                 else:
#                     # print_debug(50, '\n\n' + (80 * '#') + '\nUsing Pipe I/O\n' + (80 * '#') + '\n\n')
#                     # Get the updated data model from stdout for the task
#                     parts = tasks_by_start_layer[tnum]['stdout'].split('---JSON-DELIMITER---')
#                     dm_text = None
#                     for p in parts:
#                         ps = p.strip()
#                         if ps.startswith('{') and ps.endswith('}'):
#                             dm_text = p
#
#                 if dm_text != None:
#                     results_dict = json.loads(dm_text)
#                     fdm_new = results_dict['data_model']
#
#                     # Get the same scale from both the old and new data models
#                     cur_scale_new = fdm_new['data']['scales'][cur_scale_new_key]
#                     cur_scale_old = self.updated_model['data']['scales'][cur_scale_new_key]
#
#                     al_stack_old = cur_scale_old['alignment_stack']
#                     al_stack_new = cur_scale_new['alignment_stack']
#
#                     lnum = int(tasks_by_start_layer[tnum]['args'][5])  # Note that this may differ from tnum!!
#
#                     # print("project_runner | lnum = ", lnum)
#
#
#                     al_stack_old[lnum] = al_stack_new[lnum]
#
#                     if tasks_by_start_layer[tnum]['status'] == 'task_error':
#                         ref_fn = al_stack_old[lnum]['images']['ref']['filename']
#                         base_fn = al_stack_old[lnum]['images']['base']['filename']
#
#                         # print_debug(-1, 'Alignment Task Error at: ' + str(task_by_start_layer[tnum]['cmd']) + " " + str(task_by_start_layer[tnum]['args'])) #bug should be tasks_by_start_layer
#                         print_debug(-1, 'Alignment Task Error at: ' + str(tasks_by_start_layer[tnum]['cmd']) + " " + str(tasks_by_start_layer[tnum]['args']))
#                         print_debug(-1, 'Automatically Skipping Layer %d' % (lnum))
#                         print_debug(-1, 'ref image: %s   base image: %s' % (ref_fn, base_fn))
#                         al_stack_old[lnum]['skip'] = True
#
#                     self.need_to_write_json = results_dict['need_to_write_json']  # It's not clear how this should be used (many to one)
#
#             '''
#             # Propagate the AFMs to generate and appropriate CFM at each layer
#             null_biases = self.updated_model['data']['scales'][cur_scale_new_key]['null_cafm_trends']
#             SetStackCafm ( self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'], null_biases=null_biases )
#
#             destination_path = self.project['data']['destination_path']
#             bias_data_path = os.path.join(destination_path,cur_scale_new_key,'bias_data')
#             em.save_bias_analysis(self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'], bias_data_path)
#
#             use_bounding_rect = self.updated_model['data']['scales'][cur_scale_new_key]['use_bounding_rect']
#             if use_bounding_rect:
#               rect = BoundingRect( self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'] )
#             '''
#
#             print('project_runner.do_alignment | Garbage collecting the TaskQueue')
#             # Reset task_queue
#             self.task_queue.stop()
#             del self.task_queue
#             self.task_queue = None
#
#             self.project = self.updated_model
#
#             if self.generate_images:
#                 self.generate_aligned_images()
#
#             #0615 fix bug where bias_data is only saved if/when images are generated
#             #0619 this is probably causing the problems
#             cur_scale = self.project['data']['current_scale']
#             bias_data_path = os.path.join(self.project['data']['destination_path'], self.project['data']['current_scale'], 'bias_data')
#             main_window.hud.post('Saving Bias Data')
#             em.save_bias_analysis(self.project['data']['scales'][cur_scale]['alignment_stack'], bias_data_path) # <-- call to save bias data
#             main_window.update_alignment_status_indicator()
#
#         #   Run Project in Serial Mode:
#         #   Note: does not generate aligned images here
#         else:
#
#             # Run the project directly as one serial model
#             # print ( "Running the project as one serial model")
#
#             print('project_runner.do_alignment | Calling run_json_project...')
#             self.updated_model, self.need_to_write_json = run_json_project(
#                 project=self.project,
#                 alignment_option=self.alignment_option,
#                 use_scale=self.use_scale,
#                 swiftir_code_mode=self.swiftir_code_mode,
#                 start_layer=self.start_layer,
#                 num_layers=self.num_layers)
#             self.project = self.updated_model
#
#         print("<<<<<<<< project_runner.do_alignment(%s,generate_images=%s)" % (alignment_option,generate_images))
#
#     '''Class Method to Generate the Aligned Images
#        Called by project_runner.do_alignment'''
#     def generate_aligned_images(self):
#         print('project_runner.generate_aligned_images >>>>>>>>')
#         main_window.hud.post('Generating Aligned Images...')
#
#         n = self.num_layers
#
#         cur_scale = self.project['data']['current_scale']
#
#         # Propagate the AFMs to generate and appropriate CFM at each layer
#         null_biases = self.project['data']['scales'][cur_scale]['null_cafm_trends']
#         # SetStackCafm ( self.project['data']['scales'][cur_scale]['alignment_stack'], null_biases )
#         SetStackCafm(self.project['data']['scales'][cur_scale], null_biases=null_biases)
#
#         destination_path = self.project['data']['destination_path']
#         bias_data_path = os.path.join(destination_path, cur_scale, 'bias_data')
#         em.save_bias_analysis(self.project['data']['scales'][cur_scale]['alignment_stack'], bias_data_path) # <-- call to save bias data
#
#         use_bounding_rect = self.project['data']['scales'][cur_scale]['use_bounding_rect']
#
#         if use_bounding_rect:
#             rect = BoundingRect(self.project['data']['scales'][cur_scale]['alignment_stack'])
#
#         with open(os.path.join(bias_data_path,'bounding_rect.dat'), 'w') as file:  # Use file to refer to the file object
#             if use_bounding_rect:
#                 file.write("%d %d %d %d\n" % (rect[0],rect[1],rect[2],rect[3]) )
#             else:
#                 file.write("None\n")
#
#
#         # Finally generate the images with a parallel run of image_apply_affine.py
#
#         # self.task_queue = task_queue.TaskQueue(n_tasks=n_tasks)
#         n_tasks = em.getNumImportedImages()
#         cpus = min(psutil.cpu_count(logical=False), 48)
#         main_window.hud.post("Starting Task Queue with %d CPUs" % cpus)
#         main_window.hud.post("%d Tasks to Run" % n_tasks)
#         self.task_queue = task_queue.TaskQueue(n_tasks=n_tasks)
#         self.task_queue.start(cpus)
#
#         my_path = os.path.split(os.path.realpath(__file__))[0]
#         # apply_affine_job = os.path.join(my_path, 'source/Qt/package/image_apply_affine.py')
#         apply_affine_job = os.path.join(my_path, 'image_apply_affine.py')
#         print("project_runnner | class=project_runner | apply_affine_job=",apply_affine_job)
#         scale_key = "scale_%d" % self.use_scale
#         alstack = self.project['data']['scales'][scale_key]['alignment_stack']
#
#         if self.num_layers == -1:
#             end_layer = len(alstack)
#         else:
#             end_layer = self.start_layer + self.num_layers
#
#         # Previous code at top of main loop:
#         #      for tnum in range(len(tasks_by_start_layer)):
#         #        tdata = tasks_by_start_layer[tnum]
#         #        layer_index = int(tdata['args'][5])  # Note the hard-coded index of 5 here is not the best way to go!!
#         #        layer = self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'][layer_index]
#
#         main_window.hud.post('Generating aligned images...')
#         pbar = tqdm(total = n)
#         i=0
#         for layer in alstack[self.start_layer:end_layer + 1]:
#             i+=1
#             pbar.update()
#             # self.progress_callback.emit(int((i/n)*100))
#
#             base_name = layer['images']['base']['filename']
#             ref_name = layer['images']['ref']['filename']
#
#             al_path, fn = os.path.split(base_name)
#             al_name = os.path.join(os.path.split(al_path)[0], 'img_aligned', fn)
#
#             layer['images']['aligned'] = {}
#             layer['images']['aligned']['filename'] = al_name
#
#             cafm = layer['align_to_ref_method']['method_results']['cumulative_afm']
#
#             # print_debug ( -1, 'Run processes for: python image_apply_affine.py [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name' )
#
#             if use_bounding_rect:
#                 args = [sys.executable,
#                         apply_affine_job,
#                         '-gray',
#                         '-rect',
#                         str(rect[0]),
#                         str(rect[1]),
#                         str(rect[2]),
#                         str(rect[3]),
#                         '-afm',
#                         str(cafm[0][0]),
#                         str(cafm[0][1]),
#                         str(cafm[0][2]),
#                         str(cafm[1][0]),
#                         str(cafm[1][1]),
#                         str(cafm[1][2]),
#                         base_name,
#                         al_name
#                         ]
#             else:
#                 args = [sys.executable,
#                         apply_affine_job,
#                         '-gray',
#                         '-afm',
#                         str(cafm[0][0]),
#                         str(cafm[0][1]),
#                         str(cafm[0][2]),
#                         str(cafm[1][0]),
#                         str(cafm[1][1]),
#                         str(cafm[1][2]),
#                         base_name,
#                         al_name
#                         ]
#
#             '''
#             self.task_queue.add_task ( cmd=sys.executable,
#                                        args=args,
#                                        wd='.' )
#                                        # wd=self.project['data']['destination_path'] )
#             '''
#
#             self.task_queue.add_task(args)
#
#         # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })
#
#         print_debug(-1, 'Waiting for ImageApplyAffine Tasks to Complete...')
#         t1 = time.time()
#         self.task_queue.collect_results()
#         t3 = time.time()
#         dt = t3 - t1
#
#         print('-----------------------------------------------------')
#         print_debug(-1, 'ImageApplyAffine Tasks Completed in %.2f seconds' % (dt))
#         if self.t0 != 0:
#             tt = t3 - self.t0
#             print_debug(-1, 'Total Alignment Time: %.2f seconds' % (tt))
#         print('ImageApplyAffine Tasks Completed in 16.05 seconds')
#         print('-----------------------------------------------------')
#
#
#         print('project_runner.generate_aligned_images | Stopping the TaskQueue tasks')
#         self.task_queue.stop()
#
#         print('project_runner.generate_aligned_images | Garbage collecting the TaskQueue object')
#         del self.task_queue
#         self.task_queue = None
#
#         print('<<<<<<<< project_runner.generate_aligned_images')
#
#     def get_updated_data_model ( self ):
#         '''This is an important little function'''
#         print("project_runner.get_updated_data_model:")
#         # print ( "Returning the updated data model" )
#         # return self.updated_model
#         return self.project