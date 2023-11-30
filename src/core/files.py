#!/usr/bin/env python3

'''This class validates alignment data.


FileExistsError

'''

import logging
import os
import pathlib
import inspect
import shutil
from pprint import pformat
from pathlib import Path
from typing import TypeVar
from collections import Counter
from src.utils.readers import read
from src.utils.writers import write

from qtpy.QtCore import QObject, QFileSystemWatcher, Signal

import src.config as cfg

logger = logging.getLogger(__name__)

__all__ = ['DirectoryStructure', 'DirectoryWatcher']

PathLike = TypeVar("PathLike", str, pathlib.Path, None)

class DirectoryStructure:

    def __init__(self, dm):
        self.dm = dm
        self.levels = self.dm.levels
        self.count = self.dm.count
        self.p = Path(self.dm.data_dir_path)
        self.data = dict.fromkeys(range(self.count), dict.fromkeys(self.levels, {}))
        self.updateData()

    def updateData(self):
        for i in range(self.count):
            for level in self.levels:
                path = self.p / 'data' / str(i) / level
                Counter(path.suffix for path in Path.cwd().iterdir())
                Counter({'.tif': 2, '.gif': 4})


    def getKey(self, level: str, index: int):
        return self.data[index][level]

    def getCurKey(self):
        return self.data[self.dm.zpos][self.dm.level]


    def initDirectory(self, overwrite=False):
        cfg.mw.hud('Making directory structure...')
        if overwrite:
            shutil.rmtree(self.p, ignore_errors=True)
        if not os.path.exists(cfg.preferences['alignments_root']):
            os.makedirs(cfg.preferences['alignments_root'], exist_ok=True)
        if not os.path.exists(cfg.preferences['images_root']):
            os.makedirs(cfg.preferences['images_root'], exist_ok=True)
        self.initLogs()
        for l in self.levels:
            (self.p / 'zarr' / l).mkdir(parents=True, exist_ok=True)
            for i in range(self.count):
                (self.p / 'data' / str(i) / l).mkdir(parents=True, exist_ok=True)

    def initLogs(self):
        logger.info('')
        _files = ['exceptions.log', 'thumbnails.log',
                  'recipemaker.log', 'swim.log', 'multiprocessing.log']
        Path(self.p / 'logs').mkdir(parents=True, exist_ok=True)
        for f in _files:
            (self.p / 'logs' / f).touch()



class DirectoryWatcher(QObject):
    fsChanged = Signal(str)

    def __init__(self, suffixes, preferences, key):
        super().__init__()
        self._suffixes = suffixes
        self._preferences = preferences
        self._key = key
        self._searchPaths = preferences[key]
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self.onDirChanged)
        # self._watcher.directoryChanged.connect(lambda file_path: print(f"Directory '{file_path}' changed!"))
        self._watcher.fileChanged.connect(self.onFileChanged)
        # self._watcher.fileChanged.connect(lambda file_path: print(f"File '{file_path}' changed!"))

        self._known = []

        self._events = {}
        self._updateKnown()

        self._updateVersions()

    def _updateVersions(self):
        caller = inspect.stack()[1].function
        logger.info(f"[{caller}] Upgrading data model...")
        to_update = []
        if '.alignment' in self._suffixes:
            for p in self._known:
                if Path(p).suffix == '.alignment':
                    _stem = Path(p).stem
                    _check_for = Path(p) / Path(_stem).with_suffix('.swiftir')
                    if _check_for.exists():
                        to_update.append(_check_for)
        if to_update:
            msg = f"Automatically UPDATING compatibility for: {pformat(to_update)}"
            logger.warning(msg)
            for p in to_update:
                # p is a '.swiftir' file inside of the data directory
                old_cache = p.parent / 'data.pickle'
                new_cache= p.parent / 'cache.pickle'
                if old_cache.exists():
                    shutil.move(old_cache, new_cache)  # Move To New File
                shutil.copy(p, p.with_suffix('.OLD'))  # Copy To Backup File
                newpath = p.parent.parent / Path(p.stem).with_suffix('.align')
                shutil.move(p, newpath) # Move To New File
                try:
                    os.remove(p)  # Remove Old File
                except OSError:
                    pass
                data = read('json')(newpath)
                data['info']['file_path'] = str(newpath)
                write('json')(newpath, data) # Modify New File
                shutil.move(p.parent, newpath.with_suffix('')) # Rename Data Dir


    def _loadSearchPaths(self):
        for path in self._searchPaths:
            self.watch(path)

    def _updateKnown(self):
        # logger.info(f"_updateKnown:")
        self._loadSearchPaths()
        self._known = []
        found = []
        for path in self.watched:
            for ext in self._suffixes:
                found += list(Path(path).glob('*%s' % ext))
            self._known.extend(map(str, found))

    @property
    def watched(self):
        return self._watcher.directories() + self._watcher.files()

    @property
    def known(self):
        self._updateKnown()
        return self._known

    def watch(self, path):
        self._watcher.addPath(path)

    def clearWatches(self):
        print('Clearing watch paths...')
        self._watcher.removePaths(self.watched)

    def onDirChanged(self, path):
        self._updateKnown()
        print(f'onDirChanged: {path}')
        self.fsChanged.emit(path)

    def onFileChanged(self, path):
        print(f'onFileChanged: {path}')
        self.fsChanged.emit(path)





'''


#Example
p = pathlib.Path("temp/")
p.mkdir(parents=True, exist_ok=True)
fn = "test.txt" # I don't know what is your fn
filepath = p / fn
with filepath.open("w", encoding ="utf-8") as f:
    f.write(result)



# Move a file avoiding race conditions
# Avoid race conditions with exclusive creation

source = Path("hello.py")
destination = Path("goodbye.py")

try:
    with destination.open(mode="xb") as file:
        file.write(source.read_bytes())
except FileExistsError:
    print(f"File {destination} exists already.")
else:
    source.unlink()


# Count files
>>> from pathlib import Path
>>> from collections import Counter
>>> Counter(file_path.suffix for file_path in Path.cwd().iterdir())
Counter({'.md': 2, '.txt': 4, '.pdf': 2, '.py': 1})


# Find most recently modified file
>>> from pathlib import Path
>>> from datetime import datetime
>>> directory = Path.cwd()
>>> time, file_path = max((f.stat().st_mtime, f) for f in directory.iterdir())
>>> print(datetime.fromtimestamp(time), file_path)
2023-03-28 19:23:56.977817 /home/gahjelle/realpython/test001.txt




# Walk a directory tree
root_directory = Path(".")
for path_object in root_directory.rglob('*'):
    if path_object.is_file():
        print(f"hi, I'm a file: {path_object}")
    elif path_object.is_dir():
        print(f"hi, I'm a dir: {path_object}")


# Symlinking
destination_path = Path('/home/user/my_folder/my_file.txt')  # Initial file
symlink_path = Path('my_symlink.txt')                        # Shortcut
symlink_path.symlink_to(destination_path)                    # creating the symlink

# Check if file exists
file_path.exists():


# Read text file
file_path = Path('my_folder/my_file.txt')  # creating a file_path object
content = file_path.read_text()            # reading the file

'''