import numpy as np
import argparse
import pandas as pd

def invertAffine(afm):
    '''INVERTAFFINE - Invert affine transform
    INVERTAFFINE(afm), where AFM is a 2x3 affine transformation matrix,
    returns the inverse transform.'''
    afm = np.vstack((afm, [0,0,1]))
    ifm = np.linalg.inv(afm)
    return ifm[0:2,:]

if __name__ == '__main__':
    ap = argparse.ArgumentParser()

    # df = pd.read_csv('src/utils/cafm.csv', sep=',', header=None)
    df = pd.read_csv('src/utils/cafm.csv', sep=',', header=None)
    print(df.values)

    print(df.shape)