import hashlib
import json
import os

def get_hash_and_rev ( source_list=None, hash_file_name="source_info.json" ):

    if source_list == None:
      source_list = [ __file__ ]

    hash_dict = {}  # { current_hash:value, tagged_versions:{hash:{version:v}, hash:{version:v} } }
    if os.path.exists (hash_file_name):
      f = open (hash_file_name, 'r')
      text = f.read ()
      hash_dict = json.loads (text)

    m = hashlib.sha1()
    for source_name in source_list:
      f = open ( source_name, "rb" )
      d = f.read()
      m.update(d)
      f.close()

    current_source_hash =  m.hexdigest()

    new_hash = None
    if "current_hash" in hash_dict:
      if hash_dict['current_hash'] != current_source_hash:
        new_hash = current_source_hash
    else:
      new_hash = current_source_hash

    if new_hash != None:
      # Need to update the JSON file
      hash_dict['current_hash'] = new_hash
      f = open (hash_file_name, 'w')
      jde = json.JSONEncoder (indent=2, separators=(",", ": "), sort_keys=True)
      json_hash = jde.encode (hash_dict)
      f.write (json_hash)
      f.close ()

    tag_value = None
    if 'tagged_versions' in hash_dict:
      if current_source_hash in hash_dict['tagged_versions']:
        tag_value = hash_dict['tagged_versions'][current_source_hash]

    return ( (current_source_hash, tag_value) )


if __name__ == "__main__":
  # get_hash_and_rev ( source_list=None, hash_file_name="source_hash.json" )
  hash, rev = get_hash_and_rev()

  if rev == None:
    print ("SHA1: " + str (hash) + " is an untagged version.")
  else:
    print ("SHA1: " + str (hash) + " is tagged with " + str (rev))

  # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
