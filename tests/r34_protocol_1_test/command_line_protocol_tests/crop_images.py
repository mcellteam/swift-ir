import argparse
from multiprocessing import Pool
import os
from psutil import cpu_count
import subprocess as sp
from time import perf_counter


def crop_image(fin, fout, offset, rec_size):
    # fin: input file path + input file name
    # fout: output file path + output file name
    
    x, y = offset
    w, h = rec_size
    inp = f'B {w} {h} 1\n' \
          f'F {fin}\n' \
          f'0 0 {x} {y}\n' \
          f'{w} 0 {x + w} {y}\n' \
          f'{w} {h} {x + w} {y + h}\n' \
          f'{0} {h} {x} {y + h}\n' \
          f'RW {fout}'

    with sp.Popen('mir', stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE,
                  universal_newlines=True) as proc:
        outs, errs = proc.communicate(inp)


def crop_images(dir_in, offset, rec_size, pat=''):
    # dir_in: input directory path

    dir_out = f'{dir_in}_cropped'
    os.makedirs(dir_out, exist_ok=True)

    args = []
    for f in os.listdir(dir_in):
        if pat in f:
            f_in = os.path.join(dir_in, f)
            f_out = os.path.join(dir_out, f)
            args.append((f_in, f_out, offset, rec_size))

    t0 = perf_counter()        
    with Pool(cpu_count()) as p:
        p.starmap(crop_image, args)
    print(f'images cropped in {perf_counter() - t0:.2f} sec')


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Crop images')
    parser.add_argument('dir_in', type=str, help='input directory path')
    parser.add_argument('offset', type=int, nargs=2, help='offset')
    parser.add_argument('rec_size', type=int, nargs=2, help='rectangle size')
    parser.add_argument('--pat', type=str, default='', help='pattern to filter files')
    args = parser.parse_args()

    crop_images(args.dir_in, args.offset, args.rec_size, args.pat)