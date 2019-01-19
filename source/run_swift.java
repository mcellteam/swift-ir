import java.io.*;
import java.util.*;

class global_io {
  public static boolean wait_enabled = false;
  static BufferedReader command_line_reader = null;
  public static String read_line() {
    if ( wait_enabled ) {
      try {
        if (command_line_reader == null) {
          command_line_reader = new BufferedReader ( new InputStreamReader ( System.in ) );
        }
        String command_line = command_line_reader.readLine();
        return ( command_line );
      } catch ( IOException ioe ) {
        return ( null );
      }
    } else {
      return ( null );
    }
  }
  public static void wait_for_enter() {
    if (wait_enabled) {
      read_line();
    }
  }
  public static void wait_for_enter ( String prompt ) {
    System.out.print ( prompt );
    if (wait_enabled) {
      wait_for_enter();
    } else {
      System.out.println();
    }
  }

  public static boolean log_enabled = false;
  static BufferedWriter log_file_writer = null;
  public static void log_command ( String command ) {
    if (log_enabled) {
      try {
        if (log_file_writer == null) {
          File f = new File ( System.getenv("PWD") + File.separator + "command_log.bat" );
          log_file_writer = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
        }
        System.out.println ( "LOG: " + command );
        log_file_writer.write ( command, 0, command.length() );
        log_file_writer.flush();
      } catch ( IOException ioe ) {
      }
    }
  }
}


class glob_filter implements FilenameFilter {

  /* http://shengwangi.blogspot.com/2015/11/glob-in-java-file-related-match.html
    Here are the rules for glob:
        * match any char except a directory boundary
        ** match any char include a directory boundary
        ? match any ONE char
        [] same as regular express, like [0-9] match any ONE digit.
        {} match a collection of patten separated by comma ','. Such as {A*, b} means either a string start with 'A' or a single char 'b'.
  */

  String search_pattern = null;

  public glob_filter ( String search_pattern ) {
    super();
    this.search_pattern = search_pattern;
  }

  public boolean matches(String text, String pattern) {
    String rest = null;
    int pos = pattern.indexOf('*');
    if (pos != -1) {
      rest = pattern.substring(pos + 1);
      pattern = pattern.substring(0, pos);
    }

    if (pattern.length() > text.length())
      return false;

    // handle the part up to the first *
    for (int i = 0; i < pattern.length(); i++)
      if (pattern.charAt(i) != '?' && !pattern.substring(i, i + 1).equalsIgnoreCase(text.substring(i, i + 1)))
        return false;

    // recurse for the part after the first *, if any
    if (rest == null) {
      return pattern.length() == text.length();
    } else {
      for (int i = pattern.length(); i <= text.length(); i++) {
        if (matches(text.substring(i), rest))
          return true;
      }
      return false;
    }
  }

  public boolean accept ( File dir, String name ) {
    /*
      Tests if a specified file should be included in a file list.

      Parameters:
          dir - the directory in which the file was found.
          name - the name of the file.
      Returns:
          true if and only if the name should be included in the file list; false otherwise.
    */
    boolean match = matches ( name, this.search_pattern );
    // System.out.println ( "accept{" + this.search_pattern + "} called with: " + dir + ", and " + name + " ==> " + match );
    return ( match );
  }

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

class json_parser {
  String text = "";
  //int first;
  //int last;
  Vector elements = new Vector();
  public int element_index=0;

  json_parser(String text) {
    this.text = text;
    elements = new Vector();
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




public class run_swift {

	public static ArrayList<String> actual_file_names = new ArrayList<String>();
	public static String image_type_extension = "JPG";

  public static String translate_exit ( int exit_status ) {
    String exit_string = " " + exit_status;
    if (exit_status > 128) {
      exit_string += " (signal " + (exit_status-128);
      switch (exit_status-128) {
        case  1: exit_string += " = SIGHUP";  break;
        case  2: exit_string += " = SIGINT";  break;
        case  3: exit_string += " = SIGQUIT"; break;
        case  4: exit_string += " = SIGILL";  break;
        case  5: exit_string += " = SIGTRAP"; break;
        case  6: exit_string += " = SIGABRT"; break;
        case  7: exit_string += " = SIGBUS";  break;
        case  8: exit_string += " = SIGFPE";  break;
        case  9: exit_string += " = SIGKILL"; break;
        case 10: exit_string += " = SIGUSR1"; break;
        case 11: exit_string += " = SIGSEGV"; break;
        case 13: exit_string += " = SIGPIPE"; break;
        case 14: exit_string += " = SIGALRM"; break;
        case 15: exit_string += " = SIGTERM"; break;
        default: break;
      }
      exit_string += ")";
    }
    return (exit_string);
  }


  public static String[] lines_from_stdout ( String stdout ) {
    // Note that line ending handling hasn't been tested on non-Linux platforms yet.
    stdout = stdout.replace ( '\r', '\n' );
    String split_lines[] = stdout.split("\n");
    int num_non_empty = 0;
    for (int i=0; i<split_lines.length; i++) {
      if (split_lines[i].trim().length() > 0) {
        num_non_empty += 1;
      }
    }
    String lines[] = new String[num_non_empty];
    int next = 0;
    for (int i=0; i<split_lines.length; i++) {
      if (split_lines[i].trim().length() > 0) {
        lines[next] = split_lines[i].trim();
        next += 1;
      }
    }
    return lines;
  }

  public static String[][] parts_from_stdout ( String stdout ) {
    String stdout_lines[] = lines_from_stdout ( stdout );
    String stdout_parts[][] = new String[stdout_lines.length][];

    for (int i=0; i<stdout_lines.length; i++) {
      stdout_parts[i] = stdout_lines[i].split ( "[\\s]+" );
    }
    return stdout_parts;
  }


  public static void dump_lines_from_stdout ( String stdout ) {
    String lines[] = lines_from_stdout(stdout);
    for (int i=0; i<lines.length; i++) {
      System.out.println ( "  [\"" + lines[i] + "\"]" );
    }
  }

  public static String read_string_from ( BufferedInputStream bis ) throws IOException {
    String s = "";
    int num_left = 0;
    while ( ( num_left = bis.available() ) > 0 ) {
      byte b[] = new byte[num_left];
      bis.read ( b );
      s += new String(b);
    }
    // dump_lines_from_stdout ( s );
    return ( s );
  }

  public static void align_files_by_index ( Runtime rt, String image_files[], int fixed_index, int align_index, 
                                            int window_size, int addx, int addy, int output_level ) {

    boolean use_line_parts = true;

    String command_line;
    String interactive_commands;
    Process cmd_proc;
    int exit_value;

    BufferedOutputStream proc_in;
    BufferedInputStream proc_out;
    BufferedInputStream proc_err;

    File f;
    BufferedWriter bw;

    int num_left;
    String stdout;
    String stderr;

    int loop_signs_2x2[][] = { {1,1}, {1,-1}, {-1,-1}, {-1,1} };
    int loop_signs_3x3[][] = { {1,1}, {1,-1}, {-1,-1}, {-1,1}, {0,0}, {1,0}, {0,1}, {-1,0}, {0,-1} };

    String parts[];
    String line_parts[][];

    String AI1, AI2, AI3, AI4;

    try {

      //////////////////////////////////////
      // Step 0 - Run first swim
      //////////////////////////////////////

      command_line = "swim " + window_size;
      if (output_level > 0) System.out.println ( "\n*** Running first swim with command line: " + command_line + " ***" );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      interactive_commands = "unused -i 2 -k keep."+image_type_extension+" " + image_files[fixed_index] + " " + image_files[align_index] + "\n";

      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      cmd_proc.waitFor();
      if ((exit_value = cmd_proc.exitValue()) != 0) System.out.println ( "\n\nWARNING: Command " + command_line + " finished with exit status " + translate_exit(exit_value) + "\n\n" );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 4) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 4) System.out.print ( stdout );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 11) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 11) System.out.print ( stderr );

      if (output_level > 11) System.out.println ( "=================================================================================" );


      global_io.wait_for_enter ( "Completed Step 0 (first swim) > " );


      //////////////////////////////////////
      // Step 1a - Run second swim
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 1a: Part " + i + " = " + parts[i] );
      }

      if (parts.length < 7) {
        System.out.println ( "Error: expected at least 7 parts, but only got " + parts.length + "\n" + stdout );
        System.exit ( 5 );
      }

      String tarx = "" + parts[2];
      String tary = "" + parts[3];
      String patx = "" + parts[5];
      String paty = "" + parts[6];

      command_line = "swim " + window_size;
      if (output_level > 0) System.out.println ( "\n*** Running second swim with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      interactive_commands = "";
      for (int loop_index=0; loop_index<loop_signs_2x2.length; loop_index++) {
        int x = loop_signs_2x2[loop_index][0];
        int y = loop_signs_2x2[loop_index][1];
        interactive_commands += "unused -i 2 -x " + (addx*x) + " -y " + (addy*y) + " ";
        interactive_commands += image_files[fixed_index] + " " + tarx + " " + tary + " ";
        interactive_commands += image_files[align_index] + " " + patx + " " + paty + "\n";
      }
      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      cmd_proc.waitFor();
      if ((exit_value = cmd_proc.exitValue()) != 0) System.out.println ( "\n\nWARNING: Command " + command_line + " finished with exit status " + translate_exit(exit_value) + "\n\n" );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 4) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 4) System.out.print ( stdout );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 11) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 11) System.out.print ( stderr );

      if (output_level > 11) System.out.println ( "=================================================================================" );


      global_io.wait_for_enter ( "Completed Step 1a (second swim) > " );


      //////////////////////////////////////
      // Step 1b - Run first mir
      //////////////////////////////////////

if (use_line_parts) {

      //String stdout_lines[] = lines_from_stdout ( stdout );
      line_parts = parts_from_stdout ( stdout );

      for (int i=0; i<line_parts.length; i++) {
        for (int j=0; j<line_parts[i].length; j++) {
          if (output_level > 10) System.out.println ( "Step 1b: Part[" + i + "][" + j + "] = " + line_parts[i][j] );
        }
      }

      interactive_commands = "F " + image_files[align_index] + "\n";
      interactive_commands += line_parts[0][2] + " " + line_parts[0][3] + " " + line_parts[0][5] + " " + line_parts[0][6] + "\n";
      interactive_commands += line_parts[1][2] + " " + line_parts[1][3] + " " + line_parts[1][5] + " " + line_parts[1][6] + "\n";
      interactive_commands += line_parts[2][2] + " " + line_parts[2][3] + " " + line_parts[2][5] + " " + line_parts[2][6] + "\n";
      interactive_commands += line_parts[3][2] + " " + line_parts[3][3] + " " + line_parts[3][5] + " " + line_parts[3][6] + "\n";
      interactive_commands += "RW iter1_mir_out."+image_type_extension+"\n";

} else {

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 1b: Part " + i + " = " + parts[i] );
      }

      if (parts.length < 40) {
        System.out.println ( "Error: expected at least 40 parts, but only got " + parts.length + "\n" + stdout );
        System.exit ( 5 );
      }

      interactive_commands = "F " + image_files[align_index] + "\n";
      interactive_commands += parts[2] + " " + parts[3] + " " + parts[5] + " " + parts[6] + "\n";
      interactive_commands += parts[13] + " " + parts[14] + " " + parts[16] + " " + parts[17] + "\n";
      interactive_commands += parts[24] + " " + parts[25] + " " + parts[27] + " " + parts[28] + "\n";
      interactive_commands += parts[35] + " " + parts[36] + " " + parts[38] + " " + parts[39] + "\n";
      interactive_commands += "RW iter1_mir_out."+image_type_extension+"\n";
}

      f = new File ( System.getenv("PWD") + File.separator + "first.mir" );
      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = "mir first.mir";
      if (output_level > 0) System.out.println ( "\n*** Running first mir with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      cmd_proc.waitFor();
      if ((exit_value = cmd_proc.exitValue()) != 0) System.out.println ( "\n\nWARNING: Command " + command_line + " finished with exit status " + translate_exit(exit_value) + "\n\n" );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 4) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 4) System.out.print ( stdout );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 11) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 11) System.out.print ( stderr );

      if (output_level > 11) System.out.println ( "=================================================================================" );


      global_io.wait_for_enter ( "Completed Step 1b (first mir) > " );


      //////////////////////////////////////
      // Step 2a - Run third swim
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 2a: Part " + i + " = " + parts[i] );
      }

      if (parts.length < 15) {
        System.out.println ( "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout );
        System.exit ( 5 );
      }

      AI1 = "" + parts[10];
      AI2 = "" + parts[11];
      AI3 = "" + parts[13];
      AI4 = "" + parts[14];

      command_line = "swim " + window_size;
      if (output_level > 0) System.out.println ( "\n*** Running third swim with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      interactive_commands = "";
      for (int loop_index=0; loop_index<loop_signs_2x2.length; loop_index++) {
        int x = loop_signs_2x2[loop_index][0];
        int y = loop_signs_2x2[loop_index][1];
        interactive_commands += "unused -i 2 -x " + (addx*x) + " -y " + (addy*y) + " ";
        interactive_commands += image_files[fixed_index] + " " + tarx + " " + tary + " ";
        interactive_commands += image_files[align_index] + " " + patx + " " + paty + " ";
        interactive_commands += AI1 + " " + AI2 + " " + AI3 + " " + AI4 + " " + "\n";
      }
      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      cmd_proc.waitFor();
      if ((exit_value = cmd_proc.exitValue()) != 0) System.out.println ( "\n\nWARNING: Command " + command_line + " finished with exit status " + translate_exit(exit_value) + "\n\n" );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 4) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 4) System.out.print ( stdout );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 11) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 11) System.out.print ( stderr );

      if (output_level > 11) System.out.println ( "=================================================================================" );


      global_io.wait_for_enter ( "Completed Step 2a (third swim) > " );


      //////////////////////////////////////
      // Step 2b - Run second mir
      //////////////////////////////////////


if (use_line_parts) {
      //String stdout_lines[] = lines_from_stdout ( stdout );
      line_parts = parts_from_stdout ( stdout );

      for (int i=0; i<line_parts.length; i++) {
        for (int j=0; j<line_parts[i].length; j++) {
          if (output_level > 10) System.out.println ( "Step 2b: Part[" + i + "][" + j + "] = " + line_parts[i][j] );
        }
      }

      interactive_commands = "F " + image_files[align_index] + "\n";
      interactive_commands += line_parts[0][2] + " " + line_parts[0][3] + " " + line_parts[0][5] + " " + line_parts[0][6] + "\n";
      interactive_commands += line_parts[1][2] + " " + line_parts[1][3] + " " + line_parts[1][5] + " " + line_parts[1][6] + "\n";
      interactive_commands += line_parts[2][2] + " " + line_parts[2][3] + " " + line_parts[2][5] + " " + line_parts[2][6] + "\n";
      interactive_commands += line_parts[3][2] + " " + line_parts[3][3] + " " + line_parts[3][5] + " " + line_parts[3][6] + "\n";
      interactive_commands += "RW iter2_mir_out."+image_type_extension+"\n";

} else {
      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 2b: Part " + i + " = " + parts[i] );
      }

      interactive_commands = "F " + image_files[align_index] + "\n";
      interactive_commands += parts[2] + " " + parts[3] + " " + parts[5] + " " + parts[6] + "\n";
      interactive_commands += parts[13] + " " + parts[14] + " " + parts[16] + " " + parts[17] + "\n";
      interactive_commands += parts[24] + " " + parts[25] + " " + parts[27] + " " + parts[28] + "\n";
      interactive_commands += parts[35] + " " + parts[36] + " " + parts[38] + " " + parts[39] + "\n";
      interactive_commands += "RW iter2_mir_out."+image_type_extension+"\n";
}

      f = new File ( System.getenv("PWD") + File.separator + "second.mir" );
      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = "mir second.mir";
      if (output_level > 0) System.out.println ( "\n*** Running second mir with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      cmd_proc.waitFor();
      if ((exit_value = cmd_proc.exitValue()) != 0) System.out.println ( "\n\nWARNING: Command " + command_line + " finished with exit status " + translate_exit(exit_value) + "\n\n" );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 4) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 4) System.out.print ( stdout );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 11) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 11) System.out.print ( stderr );

      if (output_level > 11) System.out.println ( "=================================================================================" );


      global_io.wait_for_enter ( "Completed Step 2b (second mir) > " );


      //////////////////////////////////////
      // Step 3a - Run fourth swim
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 3a: Part " + i + " = " + parts[i] );
      }

      if (parts.length < 15) {
        System.out.println ( "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout );
        System.exit ( 5 );
      }

      AI1 = "" + parts[10];
      AI2 = "" + parts[11];
      AI3 = "" + parts[13];
      AI4 = "" + parts[14];

      command_line = "swim " + window_size;
      if (output_level > 0) System.out.println ( "\n*** Running fourth swim with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      interactive_commands = "";
      for (int loop_index=0; loop_index<loop_signs_3x3.length; loop_index++) {
        int x = loop_signs_3x3[loop_index][0];
        int y = loop_signs_3x3[loop_index][1];
        interactive_commands += "unused -i 2 -x " + (addx*x) + " -y " + (addy*y) + " ";
        interactive_commands += image_files[fixed_index] + " " + tarx + " " + tary + " ";
        interactive_commands += image_files[align_index] + " " + patx + " " + paty + " ";
        interactive_commands += AI1 + " " + AI2 + " " + AI3 + " " + AI4 + " " + "\n";
      }
      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      cmd_proc.waitFor();
      if ((exit_value = cmd_proc.exitValue()) != 0) System.out.println ( "\n\nWARNING: Command " + command_line + " finished with exit status " + translate_exit(exit_value) + "\n\n" );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 4) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 4) System.out.print ( stdout );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 11) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 11) System.out.print ( stderr );

      if (output_level > 11) System.out.println ( "=================================================================================" );


      global_io.wait_for_enter ( "Completed Step 3a (fourth swim) > " );


      //////////////////////////////////////
      // Step 3b - Run third mir
      //////////////////////////////////////


if (use_line_parts) {
      //String stdout_lines[] = lines_from_stdout ( stdout );
      line_parts = parts_from_stdout ( stdout );

      for (int i=0; i<line_parts.length; i++) {
        for (int j=0; j<line_parts[i].length; j++) {
          if (output_level > 10) System.out.println ( "Step 3b: Part[" + i + "][" + j + "] = " + line_parts[i][j] );
        }
      }

      interactive_commands = "F " + image_files[align_index] + "\n";
      interactive_commands += line_parts[0][2] + " " + line_parts[0][3] + " " + line_parts[0][5] + " " + line_parts[0][6] + "\n";
      interactive_commands += line_parts[1][2] + " " + line_parts[1][3] + " " + line_parts[1][5] + " " + line_parts[1][6] + "\n";
      interactive_commands += line_parts[2][2] + " " + line_parts[2][3] + " " + line_parts[2][5] + " " + line_parts[2][6] + "\n";
      interactive_commands += line_parts[3][2] + " " + line_parts[3][3] + " " + line_parts[3][5] + " " + line_parts[3][6] + "\n";

      interactive_commands += line_parts[4][2] + " " + line_parts[4][3] + " " + line_parts[4][5] + " " + line_parts[4][6] + "\n";

      interactive_commands += line_parts[5][2] + " " + line_parts[5][3] + " " + line_parts[5][5] + " " + line_parts[5][6] + "\n";
      interactive_commands += line_parts[6][2] + " " + line_parts[6][3] + " " + line_parts[6][5] + " " + line_parts[6][6] + "\n";
      interactive_commands += line_parts[7][2] + " " + line_parts[7][3] + " " + line_parts[7][5] + " " + line_parts[7][6] + "\n";
      interactive_commands += line_parts[8][2] + " " + line_parts[8][3] + " " + line_parts[8][5] + " " + line_parts[8][6] + "\n";

      interactive_commands += "RW " + "aligned_" + String.format("%03d", align_index) + "."+image_type_extension+"\n";
} else {
      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 3b: Part " + i + " = " + parts[i] );
      }

      if (parts.length < 95) {
        System.out.println ( "Error: expected at least 95 parts, but only got " + parts.length + "\n" + stdout );
        System.exit ( 5 );
      }

      interactive_commands = "F " + image_files[align_index] + "\n";
      interactive_commands += parts[2] + " " + parts[3] + " " + parts[5] + " " + parts[6] + "\n";
      interactive_commands += parts[13] + " " + parts[14] + " " + parts[16] + " " + parts[17] + "\n";
      interactive_commands += parts[24] + " " + parts[25] + " " + parts[27] + " " + parts[28] + "\n";
      interactive_commands += parts[35] + " " + parts[36] + " " + parts[38] + " " + parts[39] + "\n";

      interactive_commands += parts[46] + " " + parts[47] + " " + parts[49] + " " + parts[50] + "\n";

      interactive_commands += parts[57] + " " + parts[58] + " " + parts[60] + " " + parts[61] + "\n";
      interactive_commands += parts[68] + " " + parts[69] + " " + parts[71] + " " + parts[72] + "\n";
      interactive_commands += parts[79] + " " + parts[80] + " " + parts[82] + " " + parts[83] + "\n";
      interactive_commands += parts[90] + " " + parts[91] + " " + parts[93] + " " + parts[94] + "\n";
      // interactive_commands += "RW iter3_mir_out."+image_type_extension+"\n";
      interactive_commands += "RW " + "aligned_" + String.format("%03d", align_index) + "."+image_type_extension+"\n";
}


      // Change the name of the file in this slot to use the newly aligned image:
      image_files[align_index] = "aligned_" + String.format("%03d", align_index) + "."+image_type_extension+"";


      f = new File ( System.getenv("PWD") + File.separator + "third.mir" );
      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = "mir third.mir";
      if (output_level > 0) System.out.println ( "\n*** Running third mir with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      cmd_proc.waitFor();
      if ((exit_value = cmd_proc.exitValue()) != 0) System.out.println ( "\n\nWARNING: Command " + command_line + " finished with exit status " + translate_exit(exit_value) + "\n\n" );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 4) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 4) System.out.print ( stdout );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 11) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 11) System.out.print ( stderr );

      if (output_level > 11) System.out.println ( "=================================================================================" );


      global_io.wait_for_enter ( "Completed Step 3b (third mir) > " );


      //////////////////////////////////////
      // Step 3c - Best guess transform
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 3c: Part " + i + " = " + parts[i] );
      }
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );

      if (parts.length < 15) {
        System.out.println ( "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout );
        System.exit ( 5 );
      }

      if (output_level > 1) System.out.println ( "=================================================================================" );
      if (output_level > 1) System.out.println ( "---------------------------------------------------------------------------------" );
      if (output_level > 1) System.out.println ( "Final best guess transform:" );
      if (output_level > 1) System.out.println ( "  " + patx + " " + paty + " " + parts[10] + " " + parts[11] + " " + parts[13] + " " + parts[14] );
      if (output_level > 1) System.out.println ( "---------------------------------------------------------------------------------" );
      if (output_level > 1) System.out.println ( "Final best guess mir forward matrix (use with mir \"A\" command):" );
      if (output_level > 1) System.out.println ( "  " + parts[10] + " " + parts[11] + " " + parts[12] + " " + parts[13] + " " + parts[14] + " " + parts[15] );
      if (output_level > 1) System.out.println ( "---------------------------------------------------------------------------------" );
      if (output_level > 1) System.out.println ( "Final best guess mir reverse matrix (use with mir \"a\" command):" );
      if (output_level > 1) System.out.println ( "  " + parts[2] + " " + parts[3] + " " + parts[4] + " " + parts[5] + " " + parts[6] + " " + parts[7] );
      if (output_level > 1) System.out.println ( "---------------------------------------------------------------------------------" );
      if (output_level > 1) System.out.println ( "=================================================================================" );
      if (output_level > 1) System.out.println ();
      if (output_level > 1) System.out.println ();


      global_io.wait_for_enter ( "Completed Step 3c (best guess) > " );


    } catch ( Exception some_exception ) {

      if (output_level > 0) System.out.println ( "Error: " + some_exception );
      if (output_level > 0) System.out.println ( some_exception.getStackTrace() );
      some_exception.printStackTrace();

    }

  }









  public static void main(String[] args) throws java.io.FileNotFoundException {


    int output_level = 5;
    int align_to = -1;
    int window_size = 2048;
    int addx = 2000;
    int addy = 2000;

    boolean test2 = false;

	  ArrayList<String> file_name_args = new ArrayList<String>();

    boolean bad_args = false;
    int arg_index = 0;
    while (arg_index < args.length) {
		  if (output_level > 4) System.out.println ( "Arg[" + arg_index + "] = \"" + args[arg_index] + "\"" );
		  if (args[arg_index].startsWith("-") ) {
		    if (args[arg_index].equals("-?")) {
		      System.out.println ( "Command Line Arguments:" );
		      System.out.println ( "  -v #    amount of output (0 to 9 or higher)" );
		      System.out.println ( "  -g #    specifies \"golden\" image number" );
		      System.out.println ( "  -w #    specifies window size" );
		      System.out.println ( "  -ax #   specifies addx (-x option to swim)" );
		      System.out.println ( "  -ay #   specifies addy (-y option to swim)" );
		      System.out.println ( "  -jpg    produces all output files with \".JPG\" extension" );
		      System.out.println ( "  -tif    produces all output files with \".TIF\" extension" );
		      System.out.println ( "  -wait   pauses for a carriage return after each step" );
		      System.out.println ( "  -log    writes a log of commands to command_log.bat" );
		      System.out.println ( "  -test2  forces a test mode using only 2 images" );
          System.exit ( 0 );
		    } else if (args[arg_index].equals("-v")) {
		      arg_index++;
		      output_level = new Integer ( args[arg_index] );
		    } else if (args[arg_index].equals("-g")) {
		      arg_index++;
		      align_to = new Integer ( args[arg_index] );
		    } else if (args[arg_index].equals("-w")) {
		      arg_index++;
		      window_size = new Integer ( args[arg_index] );
		    } else if (args[arg_index].equals("-ax")) {
		      arg_index++;
		      addx = new Integer ( args[arg_index] );
		    } else if (args[arg_index].equals("-ay")) {
		      arg_index++;
		      addy = new Integer ( args[arg_index] );
        } else if (args[arg_index].equals("-jpg")) {
	        image_type_extension = "JPG";
        } else if (args[arg_index].equals("-tif")) {
	        image_type_extension = "TIF";
        } else if (args[arg_index].equals("-wait")) {
	        global_io.wait_enabled = true;
        } else if (args[arg_index].equals("-log")) {
	        global_io.log_enabled = true;
        } else if (args[arg_index].equals("-test2")) {
		      test2 = true;
		    } else {
		      if (output_level > 0) System.out.println ( "Unrecognized option: " + args[arg_index] );
		      bad_args = true;
		    }
		  } else {
		    file_name_args.add ( args[arg_index] );
		  }
		  arg_index++;
    }

    if (output_level > 6) System.out.println ( "Command line specified " + file_name_args.size() + " file name patterns." );

    if (bad_args) {
      System.out.println ( "\n\nERROR: Unrecognized option, use \"-?\" to list valid options\n\n" );
    }

    {
      File current_directory = new File ( "." );
      // System.out.println ( "File = " + current_directory );
      for (int i=0; i<file_name_args.size(); i++) {
        try {
          String files[] = current_directory.list ( new glob_filter(file_name_args.get(i)) );
          for (int j=0; j<files.length; j++) {
            actual_file_names.add ( files[j] );
          }
        } catch (Exception e) {
        }
      }
    }

    if (output_level > 7) System.out.println ( "Command line specified " + actual_file_names.size() + " actual files:" );
    for (int i=0; i<actual_file_names.size(); i++) {
      if (output_level > 7) System.out.println ( "  " + actual_file_names.get(i) );
    }

    if ( actual_file_names.size() < 2 ) {
      if (output_level > -1) System.out.println ( "Must specify at least 2 images to align" );
      System.exit ( 1 );
    }

    if ( test2 && (actual_file_names.size()!=2) ) {
      if (output_level > -1) System.out.println ( "The -test2 option can only be used with exactly 2 image files" );
      System.exit ( 1 );
    }

    // Convert the list to a normal array (which the code below expects)
    String image_files[] = new String[actual_file_names.size()];

    for (int i=0; i<actual_file_names.size(); i++) {
      image_files[i] = actual_file_names.get(i);
    }

    /*
    String image_files[] = {
      "Tile_r1-c1_LM9R5CA1series_049.tif",
      "Tile_r1-c1_LM9R5CA1series_050.tif",
      "Tile_r1-c1_LM9R5CA1series_051.tif"
    };
    */

  	int num_image_files = image_files.length;

  	if (num_image_files < 2) {
      if (output_level > -1) System.out.println ( "Need more than 1 image to do alignments" );
      System.exit ( 1 );
  	}

    int golden_section = (num_image_files-1) / 2;
    if (align_to >= 0) {
      golden_section = align_to;
    }

    int num_before_golden = golden_section;
    int num_after_golden = num_image_files - (golden_section+1);

    if (output_level > 7) System.out.println ( num_before_golden + " before, and " + num_after_golden + " after" );

    int alignment_sequence[][] = new int[num_image_files-1][2];
    int alignment_index = 0;

    for (int i=golden_section-1; i>=0; i--) {
      alignment_sequence[alignment_index][0] = i;
      alignment_sequence[alignment_index][1] = i+1;
      alignment_index++;
    }

    for (int i=golden_section+1; i<num_image_files; i++) {
      alignment_sequence[alignment_index][0] = i;
      alignment_sequence[alignment_index][1] = i-1;
      alignment_index++;
    }

    for (int i=0; i<alignment_sequence.length; i++) {
      if (output_level > 0) System.out.println ( "Align " + alignment_sequence[i][0] + " to " + alignment_sequence[i][1] );
    }



    String command_line;
    String interactive_commands;
    Runtime rt = Runtime.getRuntime();
    Process cmd_proc;
    int exit_value;

    BufferedOutputStream proc_in;
    BufferedInputStream proc_out;
    BufferedInputStream proc_err;

    File f;
    BufferedWriter bw;

    int num_left;
    String stdout;
    String stderr;

    if (output_level > 0) System.out.println ();

    try {

      // Use mir to copy the "golden section" to its proper location

      interactive_commands = "F " + image_files[golden_section] + "\n";
      interactive_commands += "RW " + "aligned_" + String.format("%03d", golden_section) + "."+image_type_extension+"\n";

      f = new File ( System.getenv("PWD") + File.separator + "zeroth.mir" );
      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = "mir zeroth.mir";
      if (output_level > 0) System.out.println ( "\n*** Running zeroth mir with command line: " + command_line + " ***" );
      if (output_level > 0) System.out.println ( "Copying " + image_files[golden_section] + " to " + "aligned_" + String.format("%03d", golden_section) + "."+image_type_extension );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      cmd_proc.waitFor();
      if ((exit_value = cmd_proc.exitValue()) != 0) System.out.println ( "\n\nWARNING: Command " + command_line + " finished with exit status " + translate_exit(exit_value) + "\n\n" );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 4) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 4) System.out.print ( stdout );

      if (output_level > 4) System.out.println ( "=================================================================================" );

      if (output_level > 11) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 11) System.out.print ( stderr );

      if (output_level > 11) System.out.println ( "=================================================================================" );

    } catch ( Exception some_exception ) {

      if (output_level > 0) System.out.println ( "Error: " + some_exception );
      if (output_level > 0) System.out.println ( some_exception.getStackTrace() );
      some_exception.printStackTrace();

    }


    global_io.wait_for_enter ( "Completed copy (zeroth mir) > " );


    if (!test2) {
      // Set the golden section to be the computed JPEG file
      // NOTE: Commenting out the following line will allow aligning two original ".tif" files without an intermediate "aligned_000.JPG"
      image_files[golden_section] = "aligned_" + String.format("%03d", golden_section) + "."+image_type_extension+"";
    }

    // Align all of the other images to the golden section

    for (alignment_index=0; alignment_index<alignment_sequence.length; alignment_index++) {

      if (output_level > 0) System.out.println ( "=================================================================================" );
      if (output_level > 0) System.out.println ( "=================================================================================" );
      if (output_level > 0) System.out.println ( "=================================================================================" );
      if (output_level > 0) System.out.println ( " Top of alignment loop with alignment index = " + alignment_index );
      if (output_level > 0) System.out.println ( "   Aligning " + alignment_sequence[alignment_index][0] + " to " + alignment_sequence[alignment_index][1] );
      if (output_level > 0) System.out.println ( "   Aligning file " + image_files[alignment_sequence[alignment_index][0]] + " to " + image_files[alignment_sequence[alignment_index][1]] );
      if (output_level > 0) System.out.println ( "=================================================================================" );
      if (output_level > 0) System.out.println ( "=================================================================================" );
      if (output_level > 0) System.out.println ( "=================================================================================" );




      align_files_by_index ( rt, image_files, alignment_sequence[alignment_index][1], alignment_sequence[alignment_index][0],
                             window_size, addx, addy, output_level );




    }

  }

}
