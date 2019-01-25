import java.io.*;
import java.util.*;


public class json_parser {
  String text = "";
  //int first;
  //int last;
  Vector elements = new Vector();
  public int element_index=0;

  json_parser(String text) {
    this.text = text;
    elements = new Vector();
  }


  class json_element {
    public static final int JSON_VAL_UNDEF=-1;
    public static final int JSON_VAL_NULL=0;
    public static final int JSON_VAL_TRUE=1;
    public static final int JSON_VAL_FALSE=2;
    public static final int JSON_VAL_NUMBER=3;
    public static final int JSON_VAL_STRING=4;
    public static final int JSON_VAL_ARRAY=5;
    public static final int JSON_VAL_OBJECT=6;
    public static final int JSON_VAL_KEYVAL=7;
    int type  = JSON_VAL_UNDEF;
    int start = 0;
    int end   = 0;
    int depth = 0;
    public json_element(int what, int start, int end, int depth) {
      this.type = what;
      this.start = start;
      this.end = end;
      this.depth = depth;
    }
    public void update_element(int what, int start, int end, int depth) {
      this.type = what;
      this.start = start;
      this.end = end;
      this.depth = depth;
    }
    public String get_type () {
      if (type == JSON_VAL_UNDEF) return ( "Undefined" );
      if (type == JSON_VAL_NULL) return ( "NULL" );
      if (type == JSON_VAL_TRUE) return ( "True" );
      if (type == JSON_VAL_FALSE) return ( "False" );
      if (type == JSON_VAL_NUMBER) return ( "Number" );
      if (type == JSON_VAL_STRING) return ( "String" );
      if (type == JSON_VAL_ARRAY) return ( "Array" );
      if (type == JSON_VAL_OBJECT) return ( "Object" );
      if (type == JSON_VAL_KEYVAL) return ( "Key:Val" );
      return ( "Unknown" );
    }
  }


  json_element pre_store_skipped ( int what, int start, int end, int depth ) {
    json_element je = new json_element ( what, start, end, depth );
    elements.addElement(je);
    //System.out.println ( "Pre-Skipped " + what + " at depth " + depth + " from " + start + " to " + end );
    return je;
  }

  void post_store_skipped ( int what, int start, int end, int depth ) {
    json_element je = new json_element ( what, start, end, depth );
    elements.addElement(je);
    //System.out.println ( "Post-Skipped " + what + " at depth " + depth + " from " + start + " to " + end );
  }

  void post_store_skipped ( int what, int start, int end, int depth, json_element je ) {
    // json_element je = new json_element ( what, start, end, depth );
    // elements.addElement(je);
    je.update_element ( what, start, end, depth );
    //System.out.println ( "Post-Skipped " + what + " at depth " + depth + " from " + start + " to " + end );
  }

  public void dump ( int max_len ) {
    json_element j;
    for (int i=0; i<elements.size(); i++) {
      j = (json_element)(elements.elementAt(i));
      // System.out.println ( "E[" + i + "] is a " + j.get_type() + " at depth " + j.depth + " from " + j.start + " to " + (j.end-1) );
      for (int d=0; d<j.depth; d++) {
        System.out.print ( "    " );
      }
      String display;
      if ( (j.end - j.start) <= max_len ) {
        display = text.substring(j.start,j.end);
      } else {
        display = text.substring(j.start,j.start+max_len-4) + " ... " + text.substring(j.end-20,j.end);
      }
      System.out.println ( "|-" + j.get_type() + " at depth " + j.depth + " from " + j.start + " to " + (j.end-1) + " = " + display );
    }
  }

  public Object convert_to_object_tree ( Object parent ) {
    if (element_index < elements.size()) {
      json_element j, jj;
      j = (json_element)(elements.elementAt(element_index++));

      //for (int d=0; d<j.depth; d++) { System.out.print ( "    " ); }
      //System.out.println ( "|-" + j.get_type() + " at depth " + j.depth + " from " + j.start + " to " + (j.end-1) );

      if (j.type == json_element.JSON_VAL_ARRAY) {

        // Make and fill a list
        ArrayList<Object> obj_list = new ArrayList<Object>();
        if (element_index < elements.size()) {
          jj = (json_element)(elements.elementAt(element_index));
          while (jj.depth > j.depth) {
            Object child = convert_to_object_tree ( j );
            obj_list.add ( child );
            if (element_index < elements.size()) {
              jj = (json_element)(elements.elementAt(element_index));
            } else {
              break;
            }
          }
        }
        return ( obj_list );

      } else if (j.type == json_element.JSON_VAL_OBJECT) {

        // Make and fill a dictionary
        HashMap<String,Object> obj_dict = new HashMap<String,Object>();

        if (element_index < elements.size()) {
          jj = (json_element)(elements.elementAt(element_index));
          while (jj.depth > j.depth) {
            if (jj.type == json_element.JSON_VAL_KEYVAL) {
              json_element key_element = (json_element)(elements.elementAt(element_index + 1));
              json_element val_element = (json_element)(elements.elementAt(element_index + 2));
              String key = text.substring(key_element.start,key_element.end);
              element_index += 2;
              Object child = convert_to_object_tree ( val_element );
              obj_dict.put ( key, child );
              if (element_index < elements.size()) {
                jj = (json_element)(elements.elementAt(element_index));
              } else {
                break;
              }
            } else {
              System.out.println ( "All elements in a dictionary must be key-val pairs" );
              System.exit(10);
            }
          }
        }

        return obj_dict;


      } else if (j.type == json_element.JSON_VAL_KEYVAL) {

        // Add key value to parent dictionary
        return ( "KV-Pair" );

      } else if (j.type == json_element.JSON_VAL_STRING) {
        // Make and return a string
        return ( text.substring(j.start,j.end) );
      } else if (j.type == json_element.JSON_VAL_NUMBER) {
        try {
          return ( Integer.parseInt(text.substring(j.start,j.end)) );
        } catch (NumberFormatException nfe) {
          return ( Double.parseDouble(text.substring(j.start,j.end)) );
        }
      } else if (j.type == json_element.JSON_VAL_NULL) {
        return ( null );
      } else if (j.type == json_element.JSON_VAL_TRUE) {
        return ( true );
      } else if (j.type == json_element.JSON_VAL_FALSE) {
        return ( false );
      } else if (j.type == json_element.JSON_VAL_UNDEF) {
        return ( null );
      } else {
        return ( null );
      }
    }
    return null;
  }

  public Object generate_object_tree () {
	  skip_element ( 0, 0 );
	  // p.dump(70);
	  // Set the first element to 0
	  element_index = 0;
	  // Convert the text into an actual object tree (usually a List or a HashMap)
	  Object o = convert_to_object_tree( null );
	  // Return the object tree
	  return ( o );
  }

  int skip_whitespace ( int index, int depth ) {
    int i = index;
    int max = text.length();
    while ( Character.isWhitespace(text.charAt(i)) ) {
      i++;
      if (i >= max) {
        return ( -1 );
      }
    }
    // post_store_skipped ( json_element.JSON_VAL_UNDEF, index, i, depth );
    return i;
  }

  int skip_sepspace ( int index, int depth ) {
    int i = index;
    int max = text.length();
    while ( (text.charAt(i)==',') || Character.isWhitespace(text.charAt(i)) ) {
      i++;
      if (i >= max) {
        return ( -1 );
      }
    }
    // post_store_skipped ( json_element.JSON_VAL_UNDEF, index, i, depth );
    return i;
  }

  int skip_element ( int index, int depth ) {
    int start = skip_whitespace ( index, depth );
    if (start >= 0) {
      if ( text.charAt(start) == '{' ) {
        start = skip_object ( start, depth );
      } else if ( text.charAt(start) == '[' ) {
        start = skip_array ( start, depth );
      } else if ( text.charAt(start) == '\"' ) {
        start = skip_string ( start, depth );
      } else if ( (new String("-0123456789")).indexOf(text.charAt(start)) >= 0 ) {
        start = skip_number ( start, depth );
      } else if ( (new String("null")).regionMatches(0,text,start,4) ) {
        post_store_skipped ( json_element.JSON_VAL_NULL, start, start+4, depth );
        start += 4;
      } else if ( (new String("true")).regionMatches(0,text,start,4) ) {
        post_store_skipped ( json_element.JSON_VAL_TRUE, start, start+4, depth );
        start += 4;
      } else if ( (new String("false")).regionMatches(0,text,start,5) ) {
        post_store_skipped ( json_element.JSON_VAL_FALSE, start, start+5, depth );
        start += 5;
      } else {
        int lead = Math.max(0,start-10);
        int trail = Math.min(start+10,text.length()-1);
        System.out.println ( "Unexpected char (\"" + text.charAt(start) + "\") in JSON: \"" + text.substring(lead,trail) + "\"" );
        System.exit(12);
      }
    }
    return start;
  }

  int skip_keyval ( int index, int depth ) {
    json_element je = pre_store_skipped ( json_element.JSON_VAL_KEYVAL, index, index, depth );
    index = skip_whitespace ( index, depth );
    int end = index;
    end = skip_string ( end, depth );
    end = skip_whitespace ( end, depth );
    end = end + 1;  // This is the colon separator (:)
    end = skip_element ( end, depth );
    post_store_skipped ( json_element.JSON_VAL_KEYVAL, index, end, depth, je );
    return (end);
  }

  int skip_object ( int index, int depth ) {
    json_element je = pre_store_skipped ( json_element.JSON_VAL_OBJECT, index, index, depth );
    int end = index+1;
    depth += 1;
    while (text.charAt(end) != '}') {
      end = skip_keyval ( end, depth );
      end = skip_sepspace ( end, depth );
    }
    depth += -1;
    post_store_skipped ( json_element.JSON_VAL_OBJECT, index, end+1, depth, je );
    return (end + 1);
  }

  int skip_array ( int index, int depth ) {
    json_element je = pre_store_skipped ( json_element.JSON_VAL_ARRAY, index, index, depth );
    int end = index+1;
    depth += 1;
    while (text.charAt(end) != ']') {
      end = skip_element ( end, depth );
      end = skip_sepspace ( end, depth );
    }
    depth += -1;
    post_store_skipped ( json_element.JSON_VAL_ARRAY, index, end+1, depth, je );
    return (end + 1);
  }

  int skip_string ( int index, int depth ) {
    int end = index+1;
    while (text.charAt(end) != '"') {
      end++;
    }
    post_store_skipped ( json_element.JSON_VAL_STRING, index, end+1, depth );
    return (end + 1);
  }

  int skip_number ( int index, int depth ) {
    int end = index;
    String number_chars = "0123456789.-+eE";
    while (number_chars.indexOf(text.charAt(end)) >= 0 ) {
      end++;
    }
    post_store_skipped ( json_element.JSON_VAL_NUMBER, index, end, depth );
    return (end);
  }

}

