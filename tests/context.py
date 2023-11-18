import os
import sys
# sys.file_path.insert(0, os.file_path.abspath(os.file_path.join(os.file_path.dirname(__file__), '..')))
# print(os.file_path.abspath(os.file_path.join(os.file_path.dirname(__file__), '..')))

src_path = os.path.dirname(os.path.split(os.path.realpath(__file__))[0]) + '/src'
print('adding ' + src_path + ' to context...')
sys.path.insert(1, src_path)

from src.models.data import DataModel