import os
import subprocess as sp
import numpy as np


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
        _input = swim_input(size, i, f, w, _b, _t, _k, tgt, pt, src, ps, shi)

    if id == '2x2':
        _input = ''
        for j in range(len(pt)):
            idj = f'{id}_w{j}'
            _b = f'sig_{idj}.JPG' if b is None else f'{b}_{idj}.JPG'
            _t = f'tar_{idj}.JPG' if t is None else f'{t}_{idj}.JPG'
            _k = f'src_{idj}.JPG' if k is None else f'{k}_{idj}.JPG'
            _input += swim_input(size, i, f, w, _b, _t, _k, tgt, pt[j], src, ps[j],
                                 shi) + '\n'
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


def mir_input(pt, ps, img_src, img_out):

    arg = f'F {img_src}\n'
    for i in range(len(pt)):
        arg += f'{pt[i][0]} {pt[i][1]} {ps[i][0]} {ps[i][1]}\n'

    arg += f'RW {img_out}'

    return arg


def parse_mir_out(arg):

    out = arg.split('\n')
    af = np.array([float(x) for x in out[0].split()[2:]])
    ai = np.array([float(x) for x in out[1].split()[2:]])

    return af, ai


def run_mir(pt, ps, img_src, img_out, log=True):
            # pt=None, ps=None, img_src=None, img_out=None, af=None, img_size=None, log=True
    # form 1. pt, ps, img_src=None, img_out=None
    # form 2. img_src, img_out, af

    mir = 'mir'
    com = [f'{mir}']

    # if (pt is not None) and (ps is not None):
    #     # pt and ps must be given together!
    #     _input = mir_input(pt, ps, img_src, img_out)

    # if (img_src is not None) and (img_out is not None) and (af is not None):
    #     # img_src, img_out, and af must be given together!
    #     _input = mir_input(img_src, img_out, af)

    _input = mir_input(pt, ps, img_src, img_out)

    with sp.Popen(com, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE,
                  universal_newlines=True) as proc:
        outs, errs = proc.communicate(_input)

    if log:
        print(f'\ncom = {com}')
        print(f'\ninput:\n{_input}')
        print(f'\nouts:\n{outs}')
        print(f'errs:\n{errs}')
        print(f'proc.returncode: {proc.returncode}')

    # if (pt is not None) and (ps is not None):
    af, ai = parse_mir_out(outs[:-1]) # remove last '\n'

    return af, ai
    # return {'af': af, 'ai': ai}

# Protocol 1 consists of:
# 1) swim (iters = 3) of 1x1 window to get initial estimate of translation term
# 2) swim (iters = 3) of 2x2 window quadrants using initial translation estimate
# 3) mir of result of step 2 to get AI (affine inverse matrix)  
# 4) swim (iters = 3) of 2x2 quadrants using shape part of AI from step 3
# 5) mir of result of step 4 to get refined AI
# 6) swim (iters = 3) of 2x2 quadrants using shape part of refined AI from step 5
# 7) mir of result of step 6 to get final AI
# 8) swim (iters = 1) of 2x2 quadrants using shape part of final AI to get final SNRs
def protocol_1(img_size, ww, iters, f, w, img_tgt, img_src, b, t, k, log=True):

    # 1x1 step

    # img_size = np.array([1024, 1024])

    # ww = np.array([832, 832])

    pt_1 = ps_1 = img_size / 2

    swim_out_1 = run_swim(ww[0], iters, f, w,
                          img_tgt, pt_1,
                          img_src, ps_1,
                          id='1x1', b=b, t=t, k=k, log=log)

    # 2x2_0

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

    swim_out_2_0 = run_swim(ww[0]//2, iters, f, w, 
                            img_tgt, pt_2_0,
                            img_src, ps_2_0,
                            id='2x2', b=b, t=t, k=k, log=log)

    ren = f'ren_{k[4:]}.JPG'
    mir_out_2_0 = run_mir(swim_out_2_0[1], swim_out_2_0[2],
                          img_src, ren, log=log)

    # 2x2_1

    mask = [True, True, False, True, True, False]
    swim_out_2_1 = run_swim(ww[0]//2, iters, f, w, 
                            img_tgt, swim_out_2_0[1],
                            img_src, swim_out_2_0[2],
                            mir_out_2_0[1][mask], id='2x2', b=b, t=t, k=k, log=log)

    mir_out_2_1 = run_mir(swim_out_2_1[1], swim_out_2_1[2],
                          img_src, ren, log=log)

    # 2x2_2

    swim_out_2_2 = run_swim(ww[0]//2, iters, f, w,
                            img_tgt, swim_out_2_1[1],
                            img_src, swim_out_2_1[2],
                            mir_out_2_1[1][mask], id='2x2', b=b, t=t, k=k, log=log)

    mir_out_2_2 = run_mir(swim_out_2_2[1], swim_out_2_2[2],
                          img_src, ren, log=log)
    # 2x2_3

    swim_out_2_3 = run_swim(ww[0]//2, 1, f, w,
                            img_tgt, swim_out_2_2[1],
                            img_src, swim_out_2_2[2],
                            mir_out_2_2[1][mask], id='2x2', b=b, t=t, k=k, log=log)


def get_img_stack(dir):
    # use image library 
    img_size = np.array([1024, 1024]) # for a rectangular image use something like img_size = np.array([2048, 1024])
    img_stack = sorted([os.path.join(dir, x) for x in os.listdir(dir)])  # get list of images in dir arg
    return img_size, img_stack


if __name__ == '__main__':

    # get image stack
    img_size, img_stack = get_img_stack('../images/s4')
    tgt_src_indices = [ (i-1, i) for i in range(1, len(img_stack)) ] 

    # protocol_1(img_size, np.array([832, 832]), 3, 3, -0.65, img_stack[0], img_stack[1], b=None, t=None, k=None, log=True)

    # run protocol_1 for all tgt, src pairs
    for tgt_idx, src_idx in tgt_src_indices:
        tgt = img_stack[tgt_idx].split('.')[-2]
        src = img_stack[src_idx].split('.')[-2]
        _sig = f'sig_s4_{tgt}_{src}'
        _tar = f'tar_s4_{tgt}'
        _src = f'src_s4_{src}'
        protocol_1(img_size, np.array([832, 832]), 3, 3, -0.65,
                   img_stack[tgt_idx], img_stack[src_idx],
                   b=_sig, t=_tar, k=_src, log=True)
