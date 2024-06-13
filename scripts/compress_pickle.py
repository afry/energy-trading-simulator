import os
import pickle

import bz2file as bz2

import statsmodels.api as sm


# Testing out compressing large model file.
# https://srivastavprojyot.medium.com/compress-large-ml-pickle-files-for-deployment-6f6afe315380
# The repo now only contains the resulting .pbz2 file. So, this can be ignored, it is just here to show what has been
# done previously, to a model .pickle file which was created in another project.

def bz2_compressed_pickle(title, data):
    with bz2.BZ2File(title, 'w') as f:
        pickle.dump(data, f)


def bz2_decompress_pickle(file):
    data = bz2.BZ2File(file, 'rb')
    data = pickle.load(data)
    return data


path = os.path.abspath("../tradingplatformpoc/data/models/household_electricity_model.pickle")
new_path = os.path.abspath("../tradingplatformpoc/data/models/household_electricity_model.pbz2")
m = sm.load(path)
bz2_compressed_pickle(new_path, m)
model = bz2_decompress_pickle(new_path)
