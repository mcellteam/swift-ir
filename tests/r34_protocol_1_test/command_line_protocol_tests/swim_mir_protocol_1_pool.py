import os
from multiprocessing import cpu_count, Pool
from pickle import dump, load
import subprocess as sp
import numpy as np
from get_image_size import get_image_size


def swim_input(size, i, f, w, b, t, k, tgt, pt, src, ps, shi):

    arg = f'ww_{size}x{size} -i {i} -f{f} -w {w} -b {b} -t {t} -k {k} ' \
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


def run_swim(size, i, f, w, tgt, pt, src, ps, shi=None,
             id='1x1', b=None, t=None, k=None, log=True):

    # b, t, and k should be given without JPG extension
    # example of popping arg 'b' but set to some default value if b was not given
    # b = kwargs.pop('b', None)

    # example of getting arg 'b' but default value is always None if b was not given
    # b = kwargs.get('b')

    swim = 'swim'
    com = [f'{swim}', f'{size}']

    if shi is None:
        shi = np.array([1.0, 0.0, 0.0, 1.0])

    if id == '1x1':
        idj = f'{id}_w0'
        _b = f'sig_{idj}.JPG' if b is None else f'{b}_{idj}.JPG'
        _t = f'tar_{idj}.JPG' if t is None else f'{t}_{idj}.JPG'
        _k = f'src_{idj}.JPG' if k is None else f'{k}_{idj}.JPG'
        _input = swim_input(size, i, f, w, _b, _t, _k,
                            tgt, pt, src, ps, shi)

    if id == '2x2':
        _input = ''
        for j in range(len(pt)):
            idj = f'{id}_w{j}'
            _b = f'sig_{idj}.JPG' if b is None else f'{b}_{idj}.JPG'
            _t = f'tar_{idj}.JPG' if t is None else f'{t}_{idj}.JPG'
            _k = f'src_{idj}.JPG' if k is None else f'{k}_{idj}.JPG'
            _input += swim_input(size, i, f, w, _b, _t, _k,
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
    # form 1. pt, ps, af=None   --> img_src and img_out are ignored
    # form 2. img_src, img_out, af!=None  --> pt and ps are ignored

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

        swim_out_1 = run_swim(ww[0], iters, f, w,
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

    swim_out_2_0 = run_swim(ww[0]//2, iters, f, w,
                            img_tgt, pt_2_0,
                            img_src, ps_2_0, shi,
                            id='2x2', b=b, t=t, k=k, log=log)

    ren = f'ren_{k[4:]}.JPG'
    mir_out_2_0 = run_mir(swim_out_2_0[1], swim_out_2_0[2],
                          img_src, ren, log=log)

    # 2x2_1

    mask = [True, True, False, True, True, False]
    swim_out_2_1 = run_swim(ww[0]//2, iters, f, w,
                            img_tgt, swim_out_2_0[1],
                            img_src, swim_out_2_0[2],
                            mir_out_2_0[1][mask], id='2x2',
                            b=b, t=t, k=k, log=log)

    mir_out_2_1 = run_mir(swim_out_2_1[1], swim_out_2_1[2],
                          img_src, ren, log=log)

    # 2x2_2

    swim_out_2_2 = run_swim(ww[0]//2, iters, f, w,
                            img_tgt, swim_out_2_1[1],
                            img_src, swim_out_2_1[2],
                            mir_out_2_1[1][mask], id='2x2',
                            b=b, t=t, k=k, log=log)

    mir_out_2_2 = run_mir(swim_out_2_2[1], swim_out_2_2[2],
                          img_src, ren, log=log)
    # 2x2_3

    swim_out_2_3 = run_swim(ww[0]//2, 1, f, w,
                            img_tgt, swim_out_2_2[1],
                            img_src, swim_out_2_2[2],
                            mir_out_2_2[1][mask], id='2x2',
                            b=b, t=t, k=k, log=log)

    return (*swim_out_2_3[:4], *mir_out_2_2)


def get_img_stack(dir):
    # use image library
    img_stack = sorted([os.path.join(dir, x) for x in os.listdir(dir)])  # get list of images in dir arg
    img_size = np.array(get_image_size(img_stack[0]))

    return img_size, img_stack


def save_pkl(dm, fn):
    with open(f'{fn}.pkl', 'wb') as fout:
        dump(dm, fout)


def load_pkl(fn):
    with open(f'{fn}.pkl', 'rb') as fin:
        dm = load(fin)

    return dm


class DataModel (dict):
    # DataModel Schema:
    # {
    #     'img_path': img_dir,
    #     'scale_S': {    # where S is the scale value,
    #       'affine_mode': 'init_affine' or 'refine_affine',
    #       'img_size': [siz_x, siz_y],
    #       'img_stack': [img_dict_1, ... img_dict_N, ...],
    #     },
    # }
    #
    # where img_dict_N is:
    # {
    #     'img_idx': N,
    #     'img_tgt': img_tgt,
    #     'img_src': img_src,
    #     'include': True or False,
    #     'alignment_method': 'grid' or 'manual_hint' or 'manual_scrict'
    #     'ww_1x1': [832, 832],
    #     'ww_2x2': [416, 416],
    #     'ww_manual': [ww_x, ww_y],
    #     'iters': 3,
    #     'f': 3,
    #     'w': -0.65,
    #     'pt_init': [[pt_1_x, pt_1_y], ... [pt_N_x, pt_N_y], ...], or []
    #     'ps_init': [[ps_1_x, ps_1_y], ... [ps_N_x, ps_N_y], ...], or []
    #     'shape_inv_init': [shi_0, shi_1, shi_2, shi_3], or []
    #     'result': {
    #        'pt': [[pt_1_x, pt_1_y], ... [pt_N_x, pt_N_y], ...],
    #        'ps': [[ps_1_x, ps_1_y], ... [ps_N_x, ps_N_y], ...],
    #        'afm': [afm_1, afm_2, ...],
    #        'cafm': [cafm_1, cafm_2, ...],
    #        'snr': [snr_1, snr_2, ...],
    #     }
    # }


    def __init__(self, *args, **kwargs):
        super(DataModel, self).__init__(*args, **kwargs)

    def update(self, *args, **kwargs):
        super(DataModel, self).update(*args, **kwargs)

    def __setitem__(self, key, value):
        super(DataModel, self).__setitem__(key, value)

    def __getitem__(self, key):
        return super(DataModel, self).__getitem__(key)

    def __delitem__(self, key):
        super(DataModel, self).__delitem__(key)

    def __str__(self):
        return super(DataModel, self).__str__()

    def __repr__(self):
        return super(DataModel, self).__repr__()


if __name__ == '__main__':

    _log = False
    # get image stack
    img_dir = '../images/'
    dirs = sorted([os.path.join(img_dir, dir) for dir in os.listdir(img_dir)])[::-1]
    scale_factors = [ int(dir[dir.rfind('s')+1:]) for dir in dirs ]
    _iters = 3
    _f = 3
    _w = -0.65

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

        scale_dir = 's' + str(scale_factors[i])
        img_size, img_stack = get_img_stack(dir)
        tgt_src_indices = [ (j, j+1) for j in range(len(img_stack) - 1) ]

        # Initialize input and results for this scale
        dm[scale_dir] = {}
        dm[scale_dir]['img_stack'] = img_stack
        dm[scale_dir]['img_size'] = img_size
        dm[scale_dir]['iters'] = _iters
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

        multiargs= []
        # Run protocol_1 for all tgt, src pairs
        for j, (tgt_idx, src_idx) in enumerate(tgt_src_indices):
            img_tgt = img_stack[tgt_idx]
            img_src = img_stack[src_idx]
            _sig = f'sig_{scale_dir}_{tgt_idx}_{src_idx}'    # base name for match signal images for this tgt, src pair
            _tar = f'tar_{scale_dir}_{tgt_idx}'    # base name for target match window images for this tgt, src pair
            _src = f'src_{scale_dir}_{src_idx}'    # base name for source match window images for this tgt, src pair

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
            multiargs.append((img_size, _ww, _iters, _f, _w,
                              img_tgt, _pt, img_src, _ps, _shi,
                              _sig, _tar, _src, _log))

        # Run protocol_1 parallel
        with Pool(cpu_count() // 2) as p:
            res = p.starmap(protocol_1, multiargs)

        # Run mir for the final cumulative affine matrix for image 0
        _ren = f'ren_{scale_dir}_0.JPG'
        run_mir(img_src=img_stack[0], img_out=_ren,
                af=dm[scale_dir]['cafms'][0], log=_log)

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
            run_mir(img_src=img_stack[src_idx], img_out=f'ren_{_src[4:]}.JPG',
                    af=dm[scale_dir]['cafms'][j+1], log=_log)

        print(f"snrs =\n{dm[scale_dir]['snrs']}")
