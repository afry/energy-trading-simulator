import pickle

import bz2file as bz2


def bz2_compress_pickle(title, data):

    with bz2.BZ2File(title, 'wb') as f:
        pickle.dump(data, f)


def bz2_decompress_pickle(file):

    data = bz2.BZ2File(file, 'rb')
    data = pickle.load(data)
    return data
