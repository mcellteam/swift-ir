import hashlib
import json
import os
import inspect

def get_hash_and_rev ( source_list=None, hash_file_name="source_info.json" ):
    print("source_tracker.get_hash_and_rev was called by " + inspect.stack()[1].function)

    if source_list == None:
      source_list = [ __file__ ]

    hash_dict = {}  # { current_hash:value, tagged_versions:{hash:{version:v}, hash:{version:v} } }
    if os.path.exists (hash_file_name):
      f = open (hash_file_name, 'r')
      text = f.read ()
      if (7*'<' in text) or (7*'=' in text) or (7*'>' in text):
        # This has likely resulted from a merge, so check if it fits the proper pattern and remove
        # Start by splitting the source_info file into lines using the OS linesep or '\n' as needed
        split_by = os.linesep
        if not split_by in text:
            split_by = '\n'
        lines = text.split(split_by)
        # Use a nested list comprehension ("incomprehension"?) to find and count merge markers
        if [ [ 7*c in l for l in lines ].count(True) for c in ['<','=','>'] ] == [1,1,1]:
          # There is only one line for each merge marker, so find them with another list incomprehension
          marker_line_numbers = [[lines.index (l) for l in lines if l.startswith (7 * c)] [0] for c in ['<', '=', '>']]
          if (marker_line_numbers[0] == marker_line_numbers[1] - 2) and (marker_line_numbers[1] == marker_line_numbers[2] - 2):
            # The marker line numbers are in the expected order and spacing, so remove all lines between them (inclusive)
            good_lines = lines[0:marker_line_numbers[0]] + lines[marker_line_numbers[2]+1:]
            # Replace "text" with a new version without the merge lines:
            text = os.linesep.join ( good_lines )
            # At this point, the text should be valid JSON without any of the merge lines.
            # This also means it will not have the "current_hash" key in the dictionary (removed above).
            # That's important so that subsequent code will add the "current_hash" and rewrite the file.
            print ( "\nSource Text:\n" + str(text) + "\n\n")
          else:
            # The JSON file contains an unexpected ordering/spacing of merge markers (not [<,=,>]) ... so exit with an error
            print ("Unexpected ordering or spacing of merge markers in " + str (hash_file_name))
            exit (98)
        else:
          # The JSON file contains an unexpected configuration of merge markers (not [1,1,1]) ... so exit with an error
          print ( "Unexpected configuration of merge markers in " + str(hash_file_name))
          exit(99)
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
