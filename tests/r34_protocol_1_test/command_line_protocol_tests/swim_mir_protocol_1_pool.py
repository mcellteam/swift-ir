from datetime import date
import os
from multiprocessing import cpu_count, Pool
from pickle import dump, load
from sys import argv
import subprocess as sp
from time import perf_counter
import numpy as np
from get_image_size import get_image_size


def swim_input(ww, i, f, w, b, t, k, tgt, pt, src, ps, shi):

    if b is not None:
        btk = f'-b {b} -t {t} -k {k} '
    else:
        btk = ''
    arg = f'ww_{ww} -i {i} -f{f} -w {w} {btk}' \
          f'{tgt} {pt[0]} {pt[1]} {src} {ps[0]} {ps[1]} ' \
          f'{shi[0]} {shi[1]} {shi[2]} {shi[3]}'

    return arg


def parse_swim_out(arg):

    out = arg.split('\n')
    snr = []
    pt = []
    ps = []
    dx = []
    dy = []
    m0 = []
    for x in out:
        tmp = x.split()
        snr.append(float(tmp[0][:-1]))
        pt.append([float(tmp[2]), float(tmp[3])])
        ps.append([float(tmp[5]), float(tmp[6])])
        pix = x[x.find('(')+1:x.rfind(')')].split()
        dx.append(float(pix[0]))
        dy.append(float(pix[1]))
        m0.append(float(pix[2]))

    return (np.array(snr), np.array(pt), np.array(ps),
            np.array(dx), np.array(dy), np.array(m0))


def run_swim(ww, i, f, w, tgt, pt, src, ps, shi=None,
             id='1x1', b=None, t=None, k=None, log=True):

    # b, t, and k should be given without JPG extension
    # example of popping arg 'b' but set to some default value if b was not given
    # b = kwargs.pop('b', None)

    # example of getting arg 'b' but default value is always None if b was not given
    # b = kwargs.get('b')

    swim = 'swim'
    _ww = f'{ww[0]}x{ww[1]}'
    com = [f'{swim}', f'{_ww}']

    if shi is None:
        shi = np.array([1.0, 0.0, 0.0, 1.0])

    if id == '1x1':
        idj = f'{id}_w0'
        _b = f'{b}_{idj}.JPG' if b is not None else b
        _t = f'{t}_{idj}.JPG' if t is not None else t
        _k = f'{k}_{idj}.JPG' if k is not None else k
        _input = swim_input(_ww, i, f, w, _b, _t, _k,
                            tgt, pt, src, ps, shi)

    if id == '2x2':
        _input = ''
        for j in range(len(pt)):
            idj = f'{id}_w{j}'
            _b = f'{b}_{idj}.JPG' if b is not None else b
            _t = f'{t}_{idj}.JPG' if t is not None else t
            _k = f'{k}_{idj}.JPG' if k is not None else k
            _input += swim_input(_ww, i, f, w, _b, _t, _k,
                                 tgt, pt[j], src, ps[j], shi) + '\n'
        _input = _input[:-1]

    with sp.Popen(com, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE,
                  universal_newlines=True) as proc:
        outs, errs = proc.communicate(_input)

    if log:
        print(f'\ncom = {com}')
        print(f'\ninput:\n{_input}')
        print(f'\nouts:\n{outs}')
        print(f'errs:\n{errs}')
        print(f'proc.returncode: {proc.returncode}')

    snr, pt, ps, dx, dy, m0 = parse_swim_out(outs[:-1]) # remove last '\n'

    if id == '1x1':
        return snr, pt[0], ps[0], shi, dx, dy, m0
        # return {'snr':snr, 'pt': pt[0], 'ps': ps[0], 'shi': shi,
        #         'dx': dx, 'dy': dy, 'm0': m0}

    if id == '2x2':
        return snr, pt, ps, shi, dx, dy, m0
        # return {'snr':snr, 'pt': pt, 'ps': ps, 'shi': shi,
        #         'dx': dx, 'dy': dy, 'm0': m0}


def mir_input(pt=None, ps=None, img_src=None, img_out=None, af=None,
              img_size=None):

    if (pt is not None) and (ps is not None):
        arg = ''
        for i in range(len(pt)):
            arg += f'{pt[i][0]} {pt[i][1]} {ps[i][0]} {ps[i][1]}\n'
        arg += 'R'

        return arg

    if (img_src is not None) and (img_out is not None) and (af is not None):
        arg = f'F {img_src}\n'
        arg += f'a {af[0]} {af[1]} {af[2]} {af[3]} {af[4]} {af[5]}\n'
        arg += f'RW {img_out}'

        return arg


def parse_mir_out(arg):

    out = arg.split('\n')
    af = np.array([float(x) for x in out[0].split()[1:]])
    ai = np.array([float(x) for x in out[1].split()[1:]])

    return af, ai


def run_mir(pt=None, ps=None, img_src=None, img_out=None, af=None, img_size=None,
            log=True):
    # form 1. pt, ps, af=None   --> img_src and img_out are ignored --> calculate af/i only from points
    # form 2. img_src, img_out, af!=None  --> pt and ps are ignored --> apply af onto src image and render it

    mir = 'mir'
    com = [f'{mir}']

    if (pt is not None) and (ps is not None) and (af is None):
        # pt and ps must be given together!
        _input = mir_input(pt=pt, ps=ps)

    if (img_src is not None) and (img_out is not None) and (af is not None):
        # img_src, img_out, and af must be given together!
        _input = mir_input(img_src=img_src, img_out=img_out, af=af)

    # _input = mir_input(pt, ps, img_src, img_out)

    with sp.Popen(com, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE,
                  universal_newlines=True) as proc:
        outs, errs = proc.communicate(_input)

    if log:
        print(f'\ncom = {com}')
        print(f'\ninput:\n{_input}')
        print(f'\nouts:\n{outs}')
        print(f'errs:\n{errs}')
        print(f'proc.returncode: {proc.returncode}')

    if (pt is not None) and (ps is not None) and (af is None):
        af, ai = parse_mir_out(outs[:-1]) # remove last '\n'
        return af, ai
        # return {'af': af, 'ai': ai}
    else:
        return None


# Protocol 1 consists of:
# 1) swim (iters = 3) of 1x1 window to get initial estimate of translation term
# 2) swim (iters = 3) of 2x2 window quadrants using initial translation estimate
# 3) mir of result of step 2 to get AI (affine inverse matrix)
# 4) swim (iters = 3) of 2x2 quadrants using shape part of AI from step 3
# 5) mir of result of step 4 to get refined AI
# 6) swim (iters = 3) of 2x2 quadrants using shape part of refined AI from step 5
# 7) mir of result of step 6 to get final AI
# 8) swim (iters = 1) of 2x2 quadrants using shape part of final AI to get final SNRs
#
def protocol_1(img_size, ww, iters, f, w, img_tgt, pt, img_src, ps, shi,
               b, t, k, log=True):
#form 1: pt and ps are None  --> perform initial alignment at coarsest scale
#form 2: pt and ps are not None  --> perform alignment at finer scales


    # img_size = np.array([1024, 1024])

    # ww = np.array([832, 832])

    if (pt is None) and (ps is None):
        # 1x1 step
        pt_1 = ps_1 = img_size / 2

        swim_out_1 = run_swim(ww, iters, f, w,
                            img_tgt, pt_1,
                            img_src, ps_1, shi,
                            id='1x1', b=b, t=t, k=k, log=log)

        # setup for 2x2_0 step
        off_x = ww[0] / 4
        off_y = ww[1] / 4
        off = np.array([[-off_x, -off_y],
                        [+off_x, -off_y],
                        [-off_x, +off_y],
                        [+off_x, +off_y]])

        # off = np.array([[-208.0, -208.0],
        #                 [+208.0, -208.0],
        #                 [-208.0, +208.0],
        #                 [+208.0, +208.0]])

        pt_2_0 = swim_out_1[1] + off
        ps_2_0 = swim_out_1[2] + off

    else:
        pt_2_0 = pt
        ps_2_0 = ps

    ww_h = ww // 2

    swim_out_2_0 = run_swim(ww_h, iters, f, w,
                            img_tgt, pt_2_0,
                            img_src, ps_2_0, shi,
                            id='2x2', b=b, t=t, k=k, log=log)

    mir_out_2_0 = run_mir(swim_out_2_0[1], swim_out_2_0[2], log=log)

    # 2x2_1

    mask = [True, True, False, True, True, False]
    swim_out_2_1 = run_swim(ww_h, iters, f, w,
                            img_tgt, swim_out_2_0[1],
                            img_src, swim_out_2_0[2],
                            mir_out_2_0[1][mask], id='2x2',
                            b=b, t=t, k=k, log=log)

    mir_out_2_1 = run_mir(swim_out_2_1[1], swim_out_2_1[2], log=log)

    # 2x2_2

    swim_out_2_2 = run_swim(ww_h, iters, f, w,
                            img_tgt, swim_out_2_1[1],
                            img_src, swim_out_2_1[2],
                            mir_out_2_1[1][mask], id='2x2',
                            b=b, t=t, k=k, log=log)

    mir_out_2_2 = run_mir(swim_out_2_2[1], swim_out_2_2[2], log=log)
    # 2x2_3

    swim_out_2_3 = run_swim(ww_h, 1, f, w,
                            img_tgt, swim_out_2_2[1],
                            img_src, swim_out_2_2[2],
                            mir_out_2_2[1][mask], id='2x2',
                            b=b, t=t, k=k, log=log)

    return (*swim_out_2_3[:4], *mir_out_2_2)


def run_protocol_1(img_dir, res_dir, iter, f, w=-0.65,
                   save_signals=True, save_render=True, log=False,
                   n_proc=None, chunksize=1):

    # get image stack
    dirs = sorted([os.path.join(img_dir, dir) for dir in os.listdir(img_dir)])[::-1]
    scale_factors = [ int(dir[dir.rfind('s')+1:]) for dir in dirs ]
    _iter = iter
    _f = f
    _w = w

    dm = {}

    # Loop over scales, e.g. s4, s2, s1
    for i, dir in enumerate(dirs):
        # if i == 0:
        #     # aligning coarsest scale, begin protocol_1 with 1x1 window
        #     # initialize data model here:
        #     # dm = DataModel()
        #     affine_mode = 'init_affine'
        # else:
        #     affine_mode = 'refine_affine'

        print(f'\nscale = {scale_factors[i]}\n')

        t0 = perf_counter()

        scale_dir = 's' + str(scale_factors[i])
        img_size, img_stack = get_img_stack(dir)
        tgt_src_indices = [ (j, j+1) for j in range(len(img_stack) - 1) ]

        # Initialize input and results for this scale
        dm[scale_dir] = {}
        dm[scale_dir]['img_stack'] = img_stack
        dm[scale_dir]['img_size'] = img_size
        dm[scale_dir]['iter'] = _iter
        dm[scale_dir]['f'] = _f
        dm[scale_dir]['w'] = _w
        dm[scale_dir]['snrs'] = []
        dm[scale_dir]['pts'] = []
        dm[scale_dir]['pss'] = []
        dm[scale_dir]['shis'] = []
        dm[scale_dir]['afms'] = [np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])]    # 1D-array form of identity matrix for affine forward matrix
        dm[scale_dir]['cafms'] = [np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])]    # 1D-array form of identity matrix for cumulative affine forward matrix

        if i == 0:
            # Aligning coarsest scale, begin protocol_1 with 1x1 window
            sf = 1
            __ww = np.asarray(0.8125 * img_size, dtype=np.int64) # size of 1x1 window at coarsest scale
            __pt = None
            __ps = None
            __shi = None
        else:
            # Aligning finer scales, begin protocol_1 with 2x2 window
            sf = scale_factors[i-1] // scale_factors[i]    # scale factor for each finer scale
            __ww = dm['s' + str(scale_factors[i-1])]['ww']    # size of 2x2 window at previous scale
            __pt = dm['s' + str(scale_factors[i-1])]['pts']    # target points at previous scale
            __ps = dm['s' + str(scale_factors[i-1])]['pss']    # source points at previous scale
            __shi = dm['s' + str(scale_factors[i-1])]['shis']    # shape inverse at previous scale

        multiargs = []
        # Run protocol_1 for all tgt, src pairs
        for j, (tgt_idx, src_idx) in enumerate(tgt_src_indices):
            img_tgt = img_stack[tgt_idx]
            img_src = img_stack[src_idx]
            if save_signals:
                _sig = f'{res_dir}/sig_{scale_dir}_{tgt_idx}_{src_idx}'    # base name for match signal images for this tgt, src pair
                _tgt = f'{res_dir}/tgt_{scale_dir}_{tgt_idx}'    # base name for target match window images for this tgt, src pair
                _src = f'{res_dir}/src_{scale_dir}_{src_idx}'    # base name for source match window images for this tgt, src pair
            else:
                _sig = None
                _tgt = None
                _src = None

            if (__pt is not None) and (__ps is not None) and (__shi is not None):
                # for finer scales, scale the 2x2 window size, target points, source points, and get shape inverse from previous scale
                _ww = sf * __ww
                _pt = sf * __pt[j]
                _ps = sf * __ps[j]
                _shi = __shi[j]
            else:
                # for coarsest scale, use the 1x1 window size, and do not scale target points, source points
                _ww = __ww
                _pt = __pt
                _ps = __ps
                _shi = __shi

            dm[scale_dir]['ww'] = _ww
            # Create multi-args to be passed to the Pool object for running protocol_1 parallel
            multiargs.append((img_size, _ww, _iter, _f, _w,
                              img_tgt, _pt, img_src, _ps, _shi,
                              _sig, _tgt, _src, log))

        # Run protocol_1 parallel
        with Pool(n_proc) as p:
            res = p.starmap(protocol_1, multiargs, chunksize=chunksize)

        # Run mir for the final cumulative affine matrix for image 0
        if save_render:
            _ren = f'{res_dir}/ren_{scale_dir}_0.JPG'
            run_mir(img_src=img_stack[0], img_out=_ren,
                    af=dm[scale_dir]['cafms'][0], log=log)
        else:
            pass

        # Append results for this scale to data model and run mir for the final cumulative affine matrix for all other images
        for j in range(len(tgt_src_indices)):
            dm[scale_dir]['snrs'].append(res[j][0])
            dm[scale_dir]['pts'].append(res[j][1])
            dm[scale_dir]['pss'].append(res[j][2])
            dm[scale_dir]['shis'].append(res[j][3])
            dm[scale_dir]['afms'].append(res[j][4])
            chfm = np.array((*dm[scale_dir]['cafms'][j], 0.0, 0.0, 1.0)).reshape(3, -1)    # convert 1D-form of cumulative affine forward matrix to 3x3 homogeneous matrix
            hfm = np.array((*dm[scale_dir]['afms'][j+1], 0.0, 0.0, 1.0)).reshape(3, -1)    # convert 1D-form of affine forward matrix to 3x3 homogeneous matrix
            chfm = chfm @ hfm    # calculate cumulative affine forward matrix for this image
            dm[scale_dir]['cafms'].append(chfm[:2, :].reshape(-1))    # convert 3x3 homogeneous cumulative affine forward matrix to 1D-form of cumulative affine forward matrix and append to list
            src_idx = tgt_src_indices[j][1]    # get source image index
            _src = f'src_{scale_dir}_{src_idx}'    #  suffix for rendered image
            # Run mir to generate transformed and aligned image
            if save_render:
                run_mir(img_src=img_stack[src_idx], img_out=f'{res_dir}/ren_{_src[4:]}.JPG',
                        af=dm[scale_dir]['cafms'][j+1], log=log)
            else:
                pass

        print(f'time elapsed = {round(perf_counter() - t0, 2)} seconds\n')

    return dm


def get_img_stack(dir):
    # use image library
    img_stack = sorted([os.path.join(dir, x) for x in os.listdir(dir)])  # get list of images in dir arg
    img_size = np.array(get_image_size(img_stack[0]))

    return img_size, img_stack


def save_pkl(dm, fn):
    with open(f'{fn}', 'wb') as fout:
        dump(dm, fout)


def load_pkl(fn):
    with open(f'{fn}', 'rb') as fin:
        dm = load(fin)

    return dm


def img_stack_(dm, scale):

    return dm[f's{scale}']['img_stack']


def img_size_(dm, scale):

    return dm[f's{scale}']['img_size']


def ww_(dm, scale):

    return dm[f's{scale}']['ww']


def iter_(dm, scale):

    return dm[f's{scale}']['iter']


def f_(dm, scale):

    return dm[f's{scale}']['f']


def w_(dm, scale):

    return dm[f's{scale}']['w']


def snrs_(dm, scale):

    return dm[f's{scale}']['snrs']


def pts_(dm, scale):

    return dm[f's{scale}']['pts']


def pss_(dm, scale):

    return dm[f's{scale}']['pss']


def shis_(dm, scale):

    return dm[f's{scale}']['shis']


def afms_(dm, scale):

    return dm[f's{scale}']['afms']


def cafms_(dm, scale):

    return dm[f's{scale}']['cafms']


if __name__ == '__main__':

    log = False

    if len(argv) < 3:
        print(f'\nUsage: {argv[0]} img_dir res_dir\n')
        exit()

    if argv[1][-1] == '/':
        img_dir = argv[1][:-1]
    else:
        img_dir = argv[1]

    if argv[2][-1] == '/':
        res_dir = argv[2][:-1]
    else:
        res_dir = argv[2]

    if os.path.isdir(res_dir):
        pass
    else:
        os.mkdir(res_dir)

    fp = f"{res_dir}/{img_dir[img_dir.rfind('/')+1:]}_{date.today().strftime('%Y%m%d')}.pkl"

    n_proc = cpu_count() // 2
    chunksize = 1

    _iter = 3
    _f = 3
    _w = -0.65

    dm = run_protocol_1(img_dir, res_dir, _iter, _f, w=_w,
                        save_signals=True, save_render=True,
                        log=log, n_proc=n_proc, chunksize=chunksize)

    save_pkl(dm, fp)


# class DataModel(dict):
#     # DataModel Schema:
#     # {
#     #     'img_path': img_dir,
#     #     'scale_S': {    # where S is the scale value,
#     #       'affine_mode': 'init_affine' or 'refine_affine',
#     #       'img_size': [siz_x, siz_y],
#     #       'img_stack': [img_dict_1, ... img_dict_N, ...],
#     #     },
#     # }
#     #
#     # where img_dict_N is:
#     # {
#     #     'img_idx': N,
#     #     'img_tgt': img_tgt,
#     #     'img_src': img_src,
#     #     'include': True or False,
#     #     'alignment_method': 'grid' or 'manual_hint' or 'manual_scrict'
#     #     'ww_1x1': [832, 832],
#     #     'ww_2x2': [416, 416],
#     #     'ww_manual': [ww_x, ww_y],
#     #     'iters': 3,
#     #     'f': 3,
#     #     'w': -0.65,
#     #     'pt_init': [[pt_1_x, pt_1_y], ... [pt_N_x, pt_N_y], ...], or []
#     #     'ps_init': [[ps_1_x, ps_1_y], ... [ps_N_x, ps_N_y], ...], or []
#     #     'shape_inv_init': [shi_0, shi_1, shi_2, shi_3], or []
#     #     'result': {
#     #        'pt': [[pt_1_x, pt_1_y], ... [pt_N_x, pt_N_y], ...],
#     #        'ps': [[ps_1_x, ps_1_y], ... [ps_N_x, ps_N_y], ...],
#     #        'afm': [afm_1, afm_2, ...],
#     #        'cafm': [cafm_1, cafm_2, ...],
#     #        'snr': [snr_1, snr_2, ...],
#     #     }
#     # }


#     def __init__(self, *args, **kwargs):
#         super(DataModel, self).__init__(*args, **kwargs)

#     def update(self, *args, **kwargs):
#         super(DataModel, self).update(*args, **kwargs)

#     def __setitem__(self, key, value):
#         super(DataModel, self).__setitem__(key, value)

#     def __getitem__(self, key):
#         return super(DataModel, self).__getitem__(key)

#     def __delitem__(self, key):
#         super(DataModel, self).__delitem__(key)

#     def __str__(self):
#         return super(DataModel, self).__str__()

#     def __repr__(self):
#         return super(DataModel, self).__repr__()
