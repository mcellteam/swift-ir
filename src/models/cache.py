#!/usr/bin/env python3
'''
A hash table class.

'''
import os
import json
import pickle
import logging
from pathlib import Path
from src.utils.helpers import path_to_str

logger = logging.getLogger(__name__)


class Cache:
    def __init__(self, dm, name='cache.pickle'):
        self.dm = dm
        self.data = {}
        self.name = name
        self.path = path_to_str(Path(self.dm.data_dir_path).with_suffix('') / self.name)
        self.unpickle()

    def __len__(self):
        return self.count

    def clear(self):
        logger.warn('Clearing cached data!')
        self.data = {}

    @property
    def count(self):
        return len(self.data)

    def to_json(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            # json.dump(self.data, f, ensure_ascii=False, indent=4)
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def pickle(self):
        print(f'Pickling {self.path}...')
        with open(self.path, 'wb') as f:
            pickle.dump(self.data, f)

    def unpickle(self):
        print(f'Unpickling {self.path}...')
        p = Path(self.path)
        fileExist = p.exists()
        if fileExist:
            print(f'Unpickling cache file {self.path}...')
            with open(self.path, "rb") as f:
                self.data = pickle.load(f)
            self._migrate_hash_keys()
        else:
            logger.info('Cache file does not exist.')

    def _migrate_hash_keys(self):
        """Re-key cache data using deterministic hashes and normalize keys.

        Fixes two issues in old cache files:
        1. Python's session-dependent hash() was used as dict keys (PYTHONHASHSEED).
        2. Keys contained numpy types (float64, tuples) that don't match JSON-loaded
           plain Python types, breaking both hash lookups and equality comparisons.

        Directory renames are done atomically with cache re-keying, using the
        old_hash → new_hash mapping that is only available before the cache is
        re-keyed. This correctly handles multiple hash directories per section
        (from alignments with different swim_settings).
        """
        from src.models.data import HashableDict, _normalize
        migrated = {}
        dir_renames = []  # (index, level, old_hash_str, new_hash_str)
        n_migrated = 0
        for old_hash, bucket in self.data.items():
            for key, value in bucket:
                norm_key = HashableDict(_normalize(key))
                new_hash = self._hash(norm_key)
                if new_hash != old_hash:
                    n_migrated += 1
                    idx = key.get('index')
                    level = key.get('level')
                    if idx is not None and level is not None:
                        dir_renames.append((idx, level, str(old_hash), str(new_hash)))
                if new_hash not in migrated:
                    migrated[new_hash] = []
                migrated[new_hash].append((norm_key, value))
        self.data = migrated
        if n_migrated > 0:
            logger.info(f'Migrated {n_migrated} cache entries to deterministic hashes')
            self._rename_data_dirs(dir_renames)
            self.pickle()

    def _rename_data_dirs(self, renames):
        """Rename on-disk data directories from old hash to new hash.

        Signal/match files are stored under {data_dir}/data/{index}/{level}/{hash}/.
        Each rename entry comes from a specific cache entry with a known old_hash →
        new_hash mapping, so this is precise even when multiple hash directories
        exist (from alignments with different swim_settings).
        """
        data_dir = os.path.join(self.dm.data_dir_path, 'data')
        if not os.path.isdir(data_dir):
            return
        n_renamed = 0
        for idx, level, old_hash_str, new_hash_str in renames:
            old_path = os.path.join(data_dir, str(idx), level, old_hash_str)
            new_path = os.path.join(data_dir, str(idx), level, new_hash_str)
            if os.path.isdir(old_path) and not os.path.exists(new_path):
                try:
                    os.rename(old_path, new_path)
                    n_renamed += 1
                except OSError as e:
                    logger.warning(f'Failed to rename {old_path} -> {new_path}: {e}')
        if n_renamed > 0:
            logger.info(f'Renamed {n_renamed} data directories to new hash names')

    def _hash(self, key):
        """Generate a deterministic hash value for the given key."""
        return hash(key)  # Delegates to HashableDict.__hash__() which uses SHA-256

    def put(self, key, value):
        """Insert a key-value pair into the hash data."""
        hashkey = self._hash(key)
        # print(f'Putting data at hash key {hashkey}')
        if hashkey not in self.data:
            self.data[hashkey] = []
        self.data[hashkey].append((key, value))

    def get(self, key):
        """Retrieve the value associated with the given key."""
        hashkey = self._hash(key)
        if hashkey in self.data:
            for k, v in self.data[hashkey]:
                if k == key:
                    return v
        logger.warning(f"[{key['index']}] data not found: {key['name']}, {hashkey}")
        # raise KeyError(f"Key '{key}' not found in the hash data.")

    def geti(self, i):
        """Retrieve the value associated with the given key."""
        key = self.dm.swim_settings(s=self.dm.scale, l=i)
        hashkey = self._hash(key)
        if hashkey in self.data:
            for k, v in self.data[hashkey]:
                if k == key:
                    return v
        raise KeyError(f"Key '{key}' not found in the hash data.")

    def haskey(self, key):
        hashkey = self._hash(key)
        if hashkey in self.data:
            for k, v in self.data[hashkey]:
                if k == key:
                    return True
        return False

    def remove(self, key):
        """Remove a key-value pair from the hash data."""
        hashkey = self._hash(key)
        if hashkey in self.data:
            for i, (k, v) in enumerate(self.data[hashkey]):
                if k == key:
                    del self.data[hashkey][i]
                    return
        raise KeyError(f"Key '{key}' not found in the hash data.")

    def __str__(self):
        """Return a string representation of the hash data."""
        items = []
        for bucket in self.data:
            if bucket is not None:
                items.extend(bucket)
        return "{" + ", ".join([f"{k}: {v}" for k, v in items]) + "}"


if __name__ == '__main__':
    # Example usage:
    hash_table = Cache(10)
    hash_table.put("example", "item")
    hash_table.put("amount", 20)
    print(hash_table.get("example"))
    print(hash_table)
    hash_table.remove("amount")
    print(hash_table)
