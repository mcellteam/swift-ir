#!/usr/bin/env python3
'''
A hash table class.

'''
import os
import json
import pickle
import logging

logger = logging.getLogger(__name__)


class HashTable:
    def __init__(self, dm, name='data.pickle'):
        self.dm = dm
        self.data = {}
        self.name = name
        self.path = os.path.join(self.dm.data_location, self.name)
        self.unpickle()

    def __len__(self):
        return self.count

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
        fileExist = os.path.exists(self.path)
        print(f'pickle found? {fileExist}')
        if not fileExist:
            print(f'Touching {self.path}...')
            open(self.path, 'a').close()
        else:
            print(f'Unpickling {self.path}...')
            with open(self.path, "rb") as f:
                self.data = pickle.load(f)

    def _hash(self, key):
        """Generate a hash value for the given key."""
        return hash(key)


    # def put(self, key, value):
    #     """Insert a key-value pair into the hash data."""
    #     index = self._hash(key)
    #     if self.data[index] is None:
    #         self.data[index] = []
    #     self.data[index].append((key, value))

    def put(self, key, value):
        """Insert a key-value pair into the hash data."""
        hashkey = self._hash(key)
        print(f'Putting data at hash key {hashkey}')
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
        logger.warning(f"hashkey not found: {hashkey}")
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
    hash_table = HashTable(10)
    hash_table.put("example", "item")
    hash_table.put("amount", 20)
    print(hash_table.get("example"))
    print(hash_table)
    hash_table.remove("amount")
    print(hash_table)
