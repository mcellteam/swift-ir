#!/usr/bin/env python3
print('running...')
import os
import sys
import time
import logging

# context = os.path.dirname(os.path.split(os.path.realpath(__file__))[0]) + '/src'
context = os.path.dirname(os.path.split(os.path.realpath(__file__))[0])
print('adding ' + context + ' to context...')
sys.path.insert(1, context)


from src.data_model import DataModel
from src.autoscale import autoscale
from src.helpers import create_project_structure_directories, get_scale_val, natural_sort, initLogFiles

def absoluteFilePaths(directory):
    for dirpath,_,filenames in os.walk(directory):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))


if __name__ == '__main__':
    logging.info('Running ' + __file__ + '.__main__()')

    # with open(path, 'r') as f:
    #     data = json.load(f)

    wd = os.getcwd()
    print('working directory: %s' % wd)
    pd = os.path.join(os.getcwd(), 'tests', 'test_project')
    print('test project directory: %s' % pd)

    dm = DataModel(name=pd)
    # scales = ['scale_1', 'scale_2', 'scale_4']
    scales = ['scale_1']
    create_project_structure_directories(dm.dest(), scales, gui=False)
    test_images = natural_sort(absoluteFilePaths(os.path.join(wd,'tests','test_images')))
    print('test images:\n  %s' % '\n  '.join(test_images))
    print('appending images...')
    dm.append_images(test_images)
    dm.set_source_path(os.path.dirname(test_images[0]))  # Critical!
    print('scales: ' + str(dm.scales()))

    print('setting defaults...')
    dm.set_scales_from_string('1 2 4')
    dm.set_method_options()
    dm.set_use_bounding_rect(False)
    dm['data']['defaults']['initial-rotation'] = float(0.0)
    dm['data']['clevel'] = int(5)
    dm['data']['cname'] = 'None'
    dm['data']['chunkshape'] = (512, 512, 1)
    for scale in dm.scales():
        scale_val = get_scale_val(scale)
        res_x = 2 * scale_val
        res_y = 2 * scale_val
        res_z = 50
        dm.set_resolution(s=scale, res_x=res_x, res_y=res_y, res_z=res_z)

    dm.set_defaults()
    initLogFiles(dm)

    print('autoscaling...')
    t0 = time.time()
    autoscale(dm=dm, make_thumbnails=False, gui=False)
    t1 = time.time()
    dt = t1 - t0
    print(f'dt: {dt:.3f}')







    # dm = compute_affines(scale=scale, path=path, start=0, end=None, use_gui=False, bounding_box=False)
