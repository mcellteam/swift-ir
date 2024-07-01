import subprocess as sp
import numpy as np


def swim_input(size, i, f, w, b, t, k, tgt, pt, src, ps, shi, id):

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


def run_swim(size, i, f, tgt, pt, src, ps, shi=None,
             id='1x1', w=-0.65, b=None, t=None, k=None, log=True):

    # set a hardcoded path to swim command if needed
    # swim = '/nadata/cnl/home/bkaynak/Desktop/xxx/python/swift-ir/src/lib/bin_linux/swim'

    # example of popping arg 'b' but set to some default value if b was not given
    # b = kwargs.pop('b', None)

    # example of getting arg 'b' but default value is always None if b was not given
    # b = kwargs.get('b')

    swim = 'swim'
    com = [f'{swim}', f'{size}']

    if shi is None:
        shi = np.array([1.0, 0.0, 0.0, 1.0])

    if id == '1x1':
        idj = f'{id}_q0'
        _b = f'sig_{idj}.jpg' if b is None else b
        _t = f'tar_{idj}.jpg' if t is None else t
        _k = f'src_{idj}.jpg' if k is None else k
        _input = swim_input(size, i, f, w, _b, _t, _k, tgt, pt, src, ps, shi, idj)

    if id == '2x2':
        _input = ''
        for j in range(len(pt)):
            idj = f'{id}_q{j}'
            _b = f'sig_{idj}.jpg' if b is None else b
            _t = f'tar_{idj}.jpg' if t is None else t
            _k = f'src_{idj}.jpg' if k is None else k
            _input += swim_input(size, i, f, w, _b, _t, _k, tgt, pt[j], src, ps[j],
                                 shi, idj) + '\n'
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


def mir_input(src, pt, ps, rw):

    arg = f'F {src}\n'
    for i in range(len(pt)):
        arg += f'{pt[i][0]} {pt[i][1]} {ps[i][0]} {ps[i][1]}\n'

    arg += f'RW {rw}'

    return arg


def parse_mir_out(arg):

    out = arg.split('\n')
    af = np.array([float(x) for x in out[0].split()[2:]])
    ai = np.array([float(x) for x in out[1].split()[2:]])

    return af, ai


def run_mir(src, pt, ps, rw, log=True):

    # mir = '/nadata/cnl/home/bkaynak/Desktop/xxx/python/swift-ir/src/lib/bin_linux/mir'
    mir = 'mir'
    com = [f'{mir}']

    _input = mir_input(src, pt, ps, rw)

    with sp.Popen(com, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE,
                  universal_newlines=True) as proc:
        outs, errs = proc.communicate(_input)

    if log:
        print(f'\ncom = {com}')
        print(f'\ninput:\n{_input}')
        print(f'\nouts:\n{outs}')
        print(f'errs:\n{errs}')
        print(f'proc.returncode: {proc.returncode}')

    af, ai = parse_mir_out(outs[:-1]) # remove last '\n'

    return af, ai
    # return {'af': af, 'ai': ai}



# MAIN ROUTINE HERE

# Protocol 1 consists of:
# 1) swim (iters = 3) of 1x1 window to get initial estimate of translation term
# 2) swim (iters = 3) of 2x2 window quadrants using initial translation estimate
# 3) mir of result of step 2 to get AI (affine inverse matrix)  
# 4) swim (iters = 3) of 2x2 quadrants using shape part of AI from step 3
# 5) mir of result of step 4 to get refined AI
# 6) swim (iters = 3) of 2x2 quadrants using shape part of refined AI from step 5
# 7) mir of result of step 6 to get final AI
# 8) swim (iters = 1) of 2x2 quadrants using shape part of final AI to get final SNRs


# 1x1 step

img_size = 1024

cx = cy = img_size/2

pt_1 = ps_1 = np.array([cx, cy])

swim_out_1 = run_swim(832, 3, 3,
                      '../images/s4/R34CA1-BS12.101.tif', pt_1,
                      '../images/s4/R34CA1-BS12.102.tif', ps_1,
                      id='1x1', log=True)

# 2x2_0

off = np.array([[-208.0, -208.0],
                [+208.0, -208.0],
                [-208.0, +208.0],
                [+208.0, +208.0]])

pt_2_0 = swim_out_1[1] + off
ps_2_0 = swim_out_1[2] + off

swim_out_2_0 = run_swim(416, 3, 3,
                        '../images/s4/R34CA1-BS12.101.tif', pt_2_0,
                        '../images/s4/R34CA1-BS12.102.tif', ps_2_0,
                        id='2x2')

mir_out_2_0 = run_mir('../images/s4/R34CA1-BS12.102.tif',
                      swim_out_2_0[1], swim_out_2_0[2],
                      'rendered_102.jpg')

# 2x2_1

mask = [True, True, False, True, True, False]
swim_out_2_1 = run_swim(416, 3, 3,
                        '../images/s4/R34CA1-BS12.101.tif', swim_out_2_0[1],
                        '../images/s4/R34CA1-BS12.102.tif', swim_out_2_0[2],
                        mir_out_2_0[1][mask], id='2x2')

mir_out_2_1 = run_mir('../images/s4/R34CA1-BS12.102.tif',
                      swim_out_2_1[1], swim_out_2_1[2],
                      'rendered_102.jpg')

# 2x2_2

swim_out_2_2 = run_swim(416, 3, 3,
                        '../images/s4/R34CA1-BS12.101.tif', swim_out_2_1[1],
                        '../images/s4/R34CA1-BS12.102.tif', swim_out_2_1[2],
                        mir_out_2_1[1][mask], id='2x2')

mir_out_2_2 = run_mir('../images/s4/R34CA1-BS12.102.tif',
                      swim_out_2_2[1], swim_out_2_2[2],
                      'rendered_102.jpg')
# 2x2_3

swim_out_2_3 = run_swim(416, 1, 3,
                        '../images/s4/R34CA1-BS12.101.tif', swim_out_2_2[1],
                        '../images/s4/R34CA1-BS12.102.tif', swim_out_2_2[2],
                        mir_out_2_2[1][mask], id='2x2')
