import os
import sys
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# print(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

src_path = os.path.dirname(os.path.split(os.path.realpath(__file__))[0]) + '/src'
print('adding ' + src_path + ' to context...')
sys.path.insert(1, src_path)

import data_model