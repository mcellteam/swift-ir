import argparse
from datetime import date
from cmath import exp as cexp
from cmath import phase as cpha
import os
from multiprocessing import Pool
from psutil import cpu_count
from pickle import dump, load
from sys import argv
import subprocess as sp
from time import perf_counter
import numpy as np
from get_image_size import get_image_size
from tqdm import tqdm


def swim_input(ww, i, w, f, b, t, k, tgt, pt, src, ps, shi):

    if b is not None:
        if (t is not None) and (k is not None):
            btk = f'-b {b} -t {t} -k {k} '
        else:
            btk = f'-b {b} '
    else:
        btk = ''
    arg = f'ww_{ww} -i {i} -w {w} -f{f} {btk}' \
          f'{tgt} {pt[0]} {pt[1]} {src} {ps[0]} {ps[1]} ' \
          f'{shi[0]} {shi[1]} {shi[2]} {shi[3]}'

    if f is None:
         arg = arg.replace(' -fNone', '')

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


def run_swim(ww, i, w, tgt, pt, src, ps, shi,
             f=None, b=None, t=None, k=None, log=True):

    # b, t, and k should be given without JPG extension
    # example of popping arg 'b' but set to some default value if b was not given
    # b = kwargs.pop('b', None)

    # example of getting arg 'b' but default value is always None if b was not given
    # b = kwargs.get('b')

    swim = 'swim'
    _ww = f'{ww[0]}x{ww[1]}'
    com = [f'{swim}', f'{_ww}']

    _input = ''
    for j in range(pt.shape[0]):
        idj = f'mp_w{j}' if pt.shape[0] > 1 else f'sp_w{j}'
        _b = f'{b}_{idj}.JPG' if b is not None else b
        _t = f'{t}_{idj}.JPG' if t is not None else t
        _k = f'{k}_{idj}.JPG' if k is not None else k
        _input += swim_input(_ww, i, w, f, _b, _t, _k,
                             tgt, pt[j], src, ps[j], shi) + '\n'

    with sp.Popen(com, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE,
                  universal_newlines=True) as proc:
        outs, errs = proc.communicate(_input)

    if log:
        print(f'\ncom = {com}')
        print(f'\ninput:\n{_input}')
        print(f'\nouts:\n{outs}')
        print(f'errs:\n{errs}')
        print(f'proc.returncode: {proc.returncode}')

    if (not log) and proc.returncode:
        print(f'\ncom = {com}')
        print(f'\ninput:\n{_input}')
        print(f'\nouts:\n{outs}')
        print(f'errs:\n{errs}')

    snr, pt, ps, dx, dy, m0 = parse_swim_out(outs[:-1]) # remove last '\n'

    return snr, pt, ps, shi, dx, dy, m0
    # return {'snr':snr, 'pt': pt, 'ps': ps, 'shi': shi,
    #         'dx': dx, 'dy': dy, 'm0': m0}


def calc_snr(ww, w, tgt, pt, src, ps, shi, f=None, b=None, t=None, k=None, log=False):

    return run_swim(ww, 1, w, tgt, pt, src, ps, shi, f=f, b=b, t=t, k=k, log=log)[0]


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
def protocol_1(img_size, ww, iters, w, img_tgt, pt, img_src, ps, shi,
               f, b, t, k, log=True):
#form 1: pt and ps are None  --> perform initial alignment at coarsest scale
#form 2: pt and ps are not None  --> perform alignment at finer scales

    if (pt is None) and (ps is None):
        # 1x1 step
        pt_1 = img_size.reshape(-1, 2) / 2
        ps_1 = img_size.reshape(-1, 2) / 2

        swim_out_1 = run_swim(ww, iters, w,
                              img_tgt, pt_1,
                              img_src, ps_1, shi,
                              f=f, b=b, t=t, k=k, log=log)

        # setup for 2x2_0 step
        _off = np.array([[-1, -1],
                         [1, -1],
                         [-1, 1],
                         [1, 1]])

        off = ww // 4 * _off

        pt_2_0 = swim_out_1[1] + off
        ps_2_0 = swim_out_1[2] + off

    else:
        pt_2_0 = pt
        ps_2_0 = ps

    ww_h = ww // 2

    swim_out_2_0 = run_swim(ww_h, iters, w,
                            img_tgt, pt_2_0,
                            img_src, ps_2_0, shi,
                            f=f, b=None, t=None, k=None, log=log)

    mir_out_2_0 = run_mir(pt=swim_out_2_0[1], ps=swim_out_2_0[2], log=log)

    # 2x2_1

    mask = [True, True, False, True, True, False]
    swim_out_2_1 = run_swim(ww_h, iters, w,
                            img_tgt, swim_out_2_0[1],
                            img_src, swim_out_2_0[2],
                            mir_out_2_0[1][mask],
                            f=f, b=None, t=None, k=None, log=log)

    mir_out_2_1 = run_mir(pt=swim_out_2_1[1], ps=swim_out_2_1[2], log=log)

    # 2x2_2

    swim_out_2_2 = run_swim(ww_h, iters, w,
                            img_tgt, swim_out_2_1[1],
                            img_src, swim_out_2_1[2],
                            mir_out_2_1[1][mask],
                            f=f, b=None, t=None, k=None, log=log)

    mir_out_2_2 = run_mir(pt=swim_out_2_2[1], ps=swim_out_2_2[2], log=log)

    # 2x2_3

    final_snr = calc_snr(ww_h, w,
                         img_tgt, swim_out_2_2[1],
                         img_src, swim_out_2_2[2],
                         mir_out_2_2[1][mask],
                         f=f, b=b, t=t, k=k, log=log)

    # Return snr from calc_snr, points from step 2_2, af and ai from mir_out_2_2
    return (final_snr, *swim_out_2_2[1:3], *mir_out_2_2)


def run_protocol_1(img_dir, res_dir, iter, w=-0.65, f=None,
                   save_render=True, save_signals=True, log=False,
                   n_proc=None, chunksize=1, s=None, tq=False):

    # get image stack
    dirs = sorted([os.path.join(img_dir, dir) for dir in os.listdir(img_dir)
                   if dir.startswith('s')], key=lambda x: int(x[x.rfind('s')+1:]))[::-1]
    scale_factors = [ int(dir[dir.rfind('s')+1:]) for dir in dirs ]
    _iter = iter
    _f = f
    _w = w

    dm = {}

    # Loop over scales, e.g. s4, s2, s1
    _dirs = [d for d in dirs[:s]]
    for scale_idx, dir in enumerate(_dirs):
        print(f'\nscale = {scale_factors[scale_idx]}\n')

        t0 = perf_counter()

        print('    initializing ...')
        t1 = perf_counter()
        scale_dir = 's' + str(scale_factors[scale_idx])

        if save_signals:
            sig_dir = f'{res_dir}/{scale_dir}/sig'
            tgt_dir = f'{res_dir}/{scale_dir}/tgt'
            src_dir = f'{res_dir}/{scale_dir}/src'
            os.makedirs(sig_dir, exist_ok=True)
            os.makedirs(tgt_dir, exist_ok=True)
            os.makedirs(src_dir, exist_ok=True)

        img_size, img_stack = get_img_stack(dir)
        print(f'    processing {len(img_stack)} images ...')
        tgt_src_indices = [ (j, j+1) for j in range(len(img_stack) - 1) ]
        tgt_src_indices.insert(0, (None, 0))  # prepend reference image index None for the 0th image for future use

        # Initialize input and results for this scale
        dm[scale_dir] = {}
        dm[scale_dir]['img_stack'] = img_stack
        dm[scale_dir]['img_size'] = img_size
        dm[scale_dir]['iter'] = _iter
        dm[scale_dir]['f'] = _f
        dm[scale_dir]['w'] = _w
        dm[scale_dir]['snrs'] = [None]
        dm[scale_dir]['pts'] = [None]
        dm[scale_dir]['pss'] = [None]
        dm[scale_dir]['afms'] = [np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])]    # 1D-array form of identity matrix for affine forward matrix
        dm[scale_dir]['aims'] = [np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])]    # 1D-array form of identity matrix for affine inverse matrix
        dm[scale_dir]['cafms'] = [np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])]    # 1D-array form of identity matrix for cumulative affine forward matrix

        mask = [True, True, False, True, True, False]
        if scale_idx == 0:
            # Aligning coarsest scale, begin protocol_1 with 1x1 window
            sf = 1
            __ww = np.asarray(0.8125 * img_size, dtype=np.int64) # size of 1x1 window at coarsest scale
            __pt = None
            __ps = None
            __ai = np.array([1., 0., 0., 0., 1., 0.])
        else:
            # Aligning finer scales, begin protocol_1 with 2x2 window
            sf = scale_factors[scale_idx - 1] // scale_factors[scale_idx]    # scale factor for each finer scale
            __ww = dm['s' + str(scale_factors[scale_idx - 1])]['ww']    # size of 2x2 window at previous scale
            __pt = dm['s' + str(scale_factors[scale_idx - 1])]['pts']    # target points at previous scale
            __ps = dm['s' + str(scale_factors[scale_idx - 1])]['pss']    # source points at previous scale
            __ai = dm['s' + str(scale_factors[scale_idx - 1])]['aims']    # affine inverse at previous scale

        zf = len(str(len(img_stack) - 1))
        multiargs = []
        # Run protocol_1 for all tgt, src pairs
        for pair_idx in range(1, len(tgt_src_indices)):
            tgt_idx = tgt_src_indices[pair_idx][0]
            src_idx = tgt_src_indices[pair_idx][1]
            img_tgt = img_stack[tgt_idx]
            img_src = img_stack[src_idx]
            _tgt_idx = str(tgt_idx).zfill(zf)
            _src_idx = str(src_idx).zfill(zf)
            if save_signals:
                _sig = f'{sig_dir}/sig_{scale_dir}_{_tgt_idx}_{_src_idx}'    # base name for match signal images for this tgt, src pair
                _tgt = f'{tgt_dir}/tgt_{scale_dir}_{_tgt_idx}'    # base name for target match window images for this tgt, src pair
                _src = f'{src_dir}/src_{scale_dir}_{_src_idx}'    # base name for source match window images for this tgt, src pair
            else:
                _sig = None
                _tgt = None
                _src = None

            if (__pt is not None) and (__ps is not None) and (__ai is not None):
                # for finer scales, scale the 2x2 window size, target points, source points, and get affine inverse from previous scale to provide shi
                _ww = sf * __ww
                _pt = sf * __pt[pair_idx]
                _ps = sf * __ps[pair_idx]
                _shi = __ai[pair_idx][mask]
            else:
                # for coarsest scale, use the 1x1 window size, and do not scale target points, source points
                _ww = __ww
                _pt = __pt
                _ps = __ps
                _shi = __ai[mask]

            dm[scale_dir]['ww'] = _ww
            # Create multi-args to be passed to the Pool object for running protocol_1 parallel
            multiargs.append((img_size, _ww, _iter, _w,
                              img_tgt, _pt, img_src, _ps, _shi,
                              _f, _sig, _tgt, _src, log))

        print(f'        completed in {perf_counter() - t1: .2f} sec')

        print('\n    running protocol_1 ...')
        t2 = perf_counter()
        # Run protocol_1 parallel
        with Pool(n_proc) as p:
            if not tq:
                res = p.starmap(protocol_1, multiargs, chunksize=chunksize)
            else:
                res = p.starmap(protocol_1, tqdm(multiargs), chunksize=chunksize)
        print(f'        completed in {perf_counter() - t2: .2f} sec')

        print('\n    append results to data model ...')
        t3 = perf_counter()

        # Append results for this scale to data model and run mir for the final cumulative affine matrix for all other images
        for res_idx in range(len(tgt_src_indices) - 1):
            dm[scale_dir]['snrs'].append(res[res_idx][0])
            dm[scale_dir]['pts'].append(res[res_idx][1])
            dm[scale_dir]['pss'].append(res[res_idx][2])
            dm[scale_dir]['afms'].append(res[res_idx][3])
            dm[scale_dir]['aims'].append(res[res_idx][4])
            chfm = np.array((*dm[scale_dir]['cafms'][res_idx], 0.0, 0.0, 1.0)).reshape(3, -1)    # convert 1D-form of cumulative affine forward matrix to 3x3 homogeneous matrix
            hfm = np.array((*dm[scale_dir]['afms'][res_idx + 1], 0.0, 0.0, 1.0)).reshape(3, -1)    # convert 1D-form of affine forward matrix to 3x3 homogeneous matrix
            chfm = chfm @ hfm    # calculate cumulative affine forward matrix for this image
            dm[scale_dir]['cafms'].append(chfm[:2, :].reshape(-1))    # convert 3x3 homogeneous cumulative affine forward matrix to 1D-form of cumulative affine forward matrix and append to list

        print(f'        completed in {perf_counter() - t3: .2f} sec')
        if save_render:
            print('\n    rendering images ...')
            t4 = perf_counter()
            ren_dir = f'{res_dir}/{scale_dir}/ren'
            os.makedirs(ren_dir, exist_ok=True)
            ren_args = []
            for i in range(len(img_stack)):
                _idx = str(i).zfill(zf)
                _img_src = img_stack[i]
                _img_out = _img_src[_img_src.rfind('/') + 1: _img_src.rfind('.')]    # base name for rendered images
                _ren = f'{ren_dir}/{_img_out}_ren_{scale_dir}_{_idx}.JPG'
                ren_args.append((None, None, _img_src, _ren, dm[scale_dir]['cafms'][i], None, log))
            with Pool(n_proc) as p:
                if not tq:
                    p.starmap(run_mir, ren_args, chunksize=chunksize)
                else:
                    p.starmap(run_mir, tqdm(ren_args), chunksize=chunksize)
            print(f'        completed in {perf_counter() - t4: .2f} sec')

        print(f'\ntime elapsed = {perf_counter() - t0: .2f} sec\n')

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

    return dm[f's{scale}']['aims'][[True, True, False, True, True, False]]


def afms_(dm, scale):

    return dm[f's{scale}']['afms']


def hfm_(dm, scale, i):

    afm = afms_(dm, scale)[i]

    return np.array([*afm, 0.0, 0.0, 1.0]).reshape(3, -1)


def aims_(dm, scale):

    return dm[f's{scale}']['aims']


def him_(dm, scale, i):

    aim = aims_(dm, scale)[i]

    return np.array([*aim, 0.0, 0.0, 1.0]).reshape(3, -1)


def cafms_(dm, scale):

    return dm[f's{scale}']['cafms']


def chfm_(dm, scale, i):

    cafm = cafms_(dm, scale)[i]

    return np.array([*cafm, 0.0, 0.0, 1.0]).reshape(3, -1)


def chim_(dm, scale, i):

    _hcfm = chfm_(dm, scale, i)

    return np.linalg.inv(_hcfm)


def cshi_(dm, scale, i):

    cafm = dm[f's{scale}']['cafms'][i]
    hafm = np.array([*cafm, 0.0, 0.0, 1.0]).reshape(3, -1)
    haim = np.linalg.inv(hafm)

    return haim[:2, :2].reshape(-1)


def hp_(arg):

    return np.apply_along_axis(lambda x: np.array([*x, 1.]), arg.ndim - 1, arg)


def hm_(arg):

    return np.array([*arg, 0.0, 0.0, 1.0]).reshape(3, -1)


def affine_decompose(arg):

    tx = arg[2]
    ty = arg[5]
    th = np.arctan2(arg[3], arg[0])
    sx = np.sqrt(arg[0] ** 2 + arg[3] ** 2)
    sy = 1 / sx * (arg[0] * arg[4] - arg[1] * arg[3])
    sh = 1 / sx**2 * (arg[0] * arg[1] + arg[3] * arg[4])

    return tx.item(), ty.item(), th.item(), sx.item(), sy.item(), sh.item()


def affine_decompose_matrix(arg):

    tx = arg[2]
    ty = arg[5]
    th = np.arctan2(arg[3], arg[0])
    sx = np.sqrt(arg[0] ** 2 + arg[3] ** 2)
    sy = 1 / sx * (arg[0] * arg[4] - arg[1] * arg[3])
    sh = 1 / sx**2 * (arg[0] * arg[1] + arg[3] * arg[4])

    tm = np.array([[1.0, 0.0, tx],
                   [0.0, 1.0, ty],
                   [0.0, 0.0, 1.0]])

    rm = 1 / sx * np.array([[arg[0], - arg[3], 0],
                            [arg[3], arg[0], 0.0],
                            [0.0, 0.0, sx]])

    scm = np.array([[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]])

    shm = np.array([[1.0, sh, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])

    return tm, rm, scm, shm


def affine_compose(tx, ty, th, sx, sy, sh):

    return np.array([sx * np.cos(th), sh * sx * np.cos(th) - sy * np.sin(th), tx,
                     sx * np.sin(th), sh * sx * np.sin(th) + sy * np.cos(th), ty])


def angle(arg):

    return cpha(cexp(arg * 1j))


def bias_mat(cfms, po):

    adp = [affine_decompose(cfm) for cfm in cfms]
    pars = list(zip(*adp))
    pars[2] = [angle(x) for x in pars[2]]
    x = range(len(pars[0]))

    bias_tx = np.polyfit(x, pars[0], po)
    bias_ty = np.polyfit(x, pars[1], po)
    bias_th = np.polyfit(x, pars[2], po)
    bias_sx = np.polyfit(x, pars[3], po)
    bias_sy = np.polyfit(x, pars[4], po)
    bias_sh = np.polyfit(x, pars[5], po)

    res = [affine_compose(pars[0][i] - np.poly1d(bias_tx)(i),
                          pars[1][i] - np.poly1d(bias_ty)(i),
                          angle(pars[2][i] - np.poly1d(bias_th)(i)),
                          pars[3][i] * (1 - np.poly1d(bias_sx)(i)),
                          pars[4][i] * (1 - np.poly1d(bias_sy)(i)),
                          pars[5][i] - np.poly1d(bias_sh)(i)) for i in range(len(cfms))]

    return pars, res


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='swim-mir protocol 1')
    parser.add_argument('img_dir', type=str, help='image directory')
    parser.add_argument('res_dir', type=str, help='result directory')
    parser.add_argument('-i', type=int, default=3, help='number of internal swim iterations (default: 3)')
    parser.add_argument('-w', type=float, default=-0.65, help='whitening factor (default: -0.65)')
    parser.add_argument('-f', type=int, default=None, help='fixed pattern noise filter (default: None)')
    parser.add_argument('-sr', action='store_false', help='disable saving rendered images')
    parser.add_argument('-ss', action='store_false', help='disable saving match signals, target and source images')
    parser.add_argument('-l', action='store_true', help='log the command, output and error')
    parser.add_argument('-n', type=int,  default=cpu_count(logical=False), help='number of cores (default: number of physical cores)')
    parser.add_argument('-c', type=int, default=1, help='chunksize for multiprocessing (default: 1)')
    parser.add_argument('-s', type=int, default=None, help='number of scales to process starting from the coarsest (default: None -> all scales)')
    parser.add_argument('-t', action='store_true', help='use tqdm for progress bar')
    args = parser.parse_args()

    os.makedirs(args.res_dir, exist_ok=True)

    fp = f"{args.res_dir}/{args.img_dir[args.img_dir.rfind('/')+1:]}_{date.today().strftime('%Y%m%d')}.pkl"

    print(f'\niter : {args.i}  w : {args.w}  f : {args.f}  s : {args.s}' \
          f'\nn_proc : {args.n}  chunksize : {args.c}' \
          f'\nsave_render : {args.sr}  save_signals : {args.ss}  log : {args.l}  tqdm : {args.t}\n')
    print(f'running on {args.n} physical cores')

    dm = run_protocol_1(args.img_dir, args.res_dir, args.i, w=args.w, f=args.f,
                        save_render=args.sr, save_signals=args.ss,
                        log=args.l, n_proc=args.n, chunksize=args.c, s=args.s, tq=args.t)

    save_pkl(dm, fp)


#####

# hp_tgt = hfm @ hp_src  # hfm is the homogeneous forward affine matrix, hp_* should be given in the homogeneous form as well.
# hp_src = him @ hp_tgt

#####

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
