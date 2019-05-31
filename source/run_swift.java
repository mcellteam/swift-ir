import java.io.*;
import java.util.*;

class global_io {
  public static String end_of_line = "\n";
  public static boolean is_windows_set = false;
  public static boolean is_windows_true = false;
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

  public static boolean log_enabled = false;
  static BufferedWriter log_file_writer = null;
  public static void log_command ( String command ) {
    if (log_enabled) {
      try {
        if (log_file_writer == null) {
          File f = new File ( System.getProperty("user.dir") + File.separator + "command_log.bat" );
          log_file_writer = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
        }
        System.out.println ( "LOG: " + command );
        log_file_writer.write ( command, 0, command.length() );
        log_file_writer.flush();
      } catch ( IOException ioe ) {
      }
    }
  }

  public static boolean is_windows() {
  if ( !is_windows_set ) {
    is_windows_true = System.getProperty("os.name").trim().toLowerCase().startsWith("win");
    is_windows_set = true;
  }
  return ( is_windows_true );
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



  public static int wait_for_proc ( Process proc ) {
    int exit_value = 0;
    System.out.println ( "In wait_for_proc" );
    try {
      System.out.println ( "Checking Exit value" );
      exit_value = proc.exitValue(); // If the process has not yet terminated, this will throw an exception
      System.out.println ( "Got an Exit value = " + exit_value );
    } catch ( Exception e ) {
      // The process is still active, so wait
      System.out.println ( "proc.exitValue() threw exception: " + e );
      try {
        System.out.println ( "Call proc.waitFor() to wait for process to actually finish" );
        proc.waitFor();
      } catch ( Exception ie ) {
      }
    }
    return ( exit_value );
  }



  public static String[] wait_for_proc_streams ( Process cmd_proc,
                                                 BufferedOutputStream proc_in,
                                                 BufferedInputStream proc_out,
                                                 BufferedInputStream proc_err,
                                                 int output_level,
                                                 String command_line,
                                                 String interactive_commands,
                                                 String step_title ) {

    System.out.println ( "In wait_for_proc_streams" );

    String stdout = "";
    String stderr = "";
    int exit_value = 0;

    if ( false && ( ! global_io.is_windows() ) ) {

      /// Don't do this in Windows because this fourth swim seems to hang:

      exit_value = global_io.wait_for_proc ( cmd_proc );

      try {
        stdout = read_string_from ( proc_out );
        stderr = read_string_from ( proc_err );
      } catch ( IOException ioe ) {
      }

    } else {

      /// Do this in Windows:

      try {
        stdout = read_string_from ( proc_out );
        stderr = read_string_from ( proc_err );
      } catch ( IOException ioe ) {
      }

      boolean waiting = true;
      do {
        // if (output_level > 10) System.out.println ( "Waiting for fourth swim ..." );
        try {
          // if (output_level > 20) System.out.println ( "Checking Exit value" );
          exit_value = cmd_proc.exitValue(); // If the process has not yet terminated, this will throw an exception
          // if (output_level > 20) System.out.println ( "Got an Exit value = " + exit_value );
          try {
            stdout += read_string_from ( proc_out );
            stderr += read_string_from ( proc_err );
          } catch ( IOException ioe ) {
          }
          waiting = false;
        } catch ( Exception e ) {
          // The process is still active, so read and wait
          // if (output_level > 20) System.out.println ( "cmd_proc.exitValue() threw exception: " + e );
          // if (output_level > 20) System.out.println ( "Read more data" );
          try {
            stdout += read_string_from ( proc_out );
            stderr += read_string_from ( proc_err );
          } catch ( IOException ioe ) {
          }
          /*
          try {
            System.out.println ( "Call cmd_proc.waitFor() to wait for process to actually finish" );
            cmd_proc.waitFor();
          } catch ( Exception ie ) {
          }
          */
        }
      } while (waiting);
    }

    if ((exit_value = cmd_proc.exitValue()) != 0) System.out.println ( "\n\nWARNING: Command " + command_line + " finished with exit status " + global_io.translate_exit(exit_value) + "\n\n" );

    if (output_level > 4) {
      System.out.println ( "Process finished!!!" );
      System.out.println ( "=================================================================================" );
      System.out.println ( "Command finished with " + stdout.length() + " bytes of output:" );
      System.out.print ( stdout );
      System.out.println ( "=================================================================================" );
      if (output_level > 11) {
        System.out.println ( "Command finished with " + stderr.length() + " bytes of error:" );
        System.out.print ( stderr );
        System.out.println ( "=================================================================================" );
      }
    }

    global_io.wait_for_enter ( step_title + " > " );

    String[] stdoe = new String[2];
    stdoe[0] = stdout;
    stdoe[1] = stderr;

    return ( stdoe );
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



public class run_swift {

  public static String code_source = "";
  public static ArrayList<String> actual_file_names = new ArrayList<String>();
  public static String image_type_extension = "JPG";

  public static String swim_cmd = "swim";
  public static String mir_cmd = "mir";
  // public static String mir_cmd = "mirb";


  public static String translate_exit ( int exit_status ) {
    return (global_io.translate_exit(exit_status));
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


  public static String[] make_string_array ( String code, String description ) {
    String s[] = new String[2];
    s[0] = code;
    s[1] = description;
    return ( s );
  }


  public static String[] make_string_array ( String code,
                                             String t00, String t01, String t02, String t10, String t11, String t12,
                                             String A00, String A01, String A02, String A10, String A11, String A12,
                                             String a00, String a01, String a02, String a10, String a11, String a12 ) {
    String s[] = new String[19];
    s[0] = code;
    s[1] = t00;
    s[2] = t01;
    s[3] = t02;
    s[4] = t10;
    s[5] = t11;
    s[6] = t12;
    s[7] = A00;
    s[8] = A01;
    s[9] = A02;
    s[10] = A10;
    s[11] = A11;
    s[12] = A12;
    s[13] = a00;
    s[14] = a01;
    s[15] = a02;
    s[16] = a10;
    s[17] = a11;
    s[18] = a12;
    return ( s );
  }


  public static void scale_file_with_iscale ( Runtime rt, String original_file_name, String subdirectory, int factor, int output_level ) {

    if (output_level > 0) {
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "scale_file_with_iscale called with:" );
      System.out.println ( "    original_file_name = " + original_file_name );
      System.out.println ( "    subdirectory       = " + subdirectory );
      System.out.println ( "    scale_factor       = " + factor );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
    }

    String command_line;
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

    try {

      command_line = code_source + "iscale p=" + subdirectory + " +" + factor + " " + original_file_name;
      if (output_level > 0) System.out.println ( "\n*** Running iscale with command line: " + command_line + " ***" );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      proc_in.close();

      global_io.log_command ( command_line + "\n" );

      global_io.wait_for_proc ( cmd_proc );
      if ((exit_value = cmd_proc.exitValue()) != 0) System.out.println ( "\n\nWARNING: Command " + command_line + " finished with exit status " + global_io.translate_exit(exit_value) + "\n\n" );

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
  }


  public static String normalize_file_name ( String file_name ) {
    try {
      file_name = new File(file_name).getCanonicalPath();
    } catch (Exception e) {
      file_name = new File(file_name).getAbsolutePath();
    }
    return ( file_name );
  }


  public static void write_to_proc ( BufferedOutputStream proc_in, String data ) throws Exception {
    proc_in.write ( data.getBytes() );
    System.out.println ( "Sending end of line and end of file" );
    proc_in.write ( new byte[]{ 0x04, 0x1a } );  // , 0x0a, 0x04, 0x0d, 0x0a, 0x04 } );
    System.out.println ( "Flushing proc_in" );
    proc_in.flush();
  }


  public static void copy_file_by_name ( Runtime rt, String original_file_name, String new_file_name, int output_level ) {

    if (output_level > 0) {
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "copy_file_by_name called with:" );
      System.out.println ( "    original_file_name = " + original_file_name );
      System.out.println ( "    new_file_name      = " + new_file_name );
      System.out.println ( "    output_level       = " + output_level );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
    }

    original_file_name = normalize_file_name ( original_file_name );
    new_file_name = normalize_file_name ( new_file_name );
    System.out.println ( "    Translated original_file_name = " + original_file_name );
    System.out.println ( "    Translated new_file_name      = " + new_file_name );

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

    try {

      // Use mir to copy the "golden section" to its proper location

      interactive_commands = "F " + original_file_name + "\n";
      interactive_commands += "RW " + new_file_name+"\n";

      f = new File ( System.getProperty("user.dir") + File.separator + "zeroth.mir" );

      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = code_source + mir_cmd + " zeroth.mir";
      if (output_level > 0) System.out.println ( "\n*** Running zeroth mir with command line: " + command_line + " ***" );
      if (output_level > 0) System.out.println ( "Copying " + original_file_name + " to " + new_file_name );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      global_io.wait_for_proc ( cmd_proc );
      if ((exit_value = cmd_proc.exitValue()) != 0) System.out.println ( "\n\nWARNING: Command " + command_line + " finished with exit status " + global_io.translate_exit(exit_value) + "\n\n" );

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
  }


  public static void transform_file_by_name ( Runtime rt, String original_file_name, String new_file_name, double affine_transform[], int output_level ) {
    if (output_level > 0) {
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "transform_file_by_name with:" );
      System.out.println ( "    original_file_name = " + original_file_name );
      System.out.println ( "    new_file_name      = " + new_file_name );
      System.out.print ( "    affine_transform   = [" );
      for (int i=0; i<affine_transform.length; i++) {
        System.out.print (" " + affine_transform[i] );
      }
      System.out.println ( " ]" );
      System.out.println ( "    output_level       = " + output_level );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
    }

    original_file_name = normalize_file_name ( original_file_name );
    new_file_name = normalize_file_name ( new_file_name );
    System.out.println ( "    Translated original_file_name = " + original_file_name );
    System.out.println ( "    Translated new_file_name      = " + new_file_name );

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

    try {

      // Use mir to copy the "golden section" to its proper location

      interactive_commands = "F " + original_file_name + global_io.end_of_line;
      interactive_commands += "A";
      for (int i=0; i<affine_transform.length; i++) {
        interactive_commands += " " + affine_transform[i];
      }
      interactive_commands += global_io.end_of_line;
      interactive_commands += "RW " + new_file_name+global_io.end_of_line;

      f = new File ( System.getProperty("user.dir") + File.separator + "pairwise.mir" );

      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = code_source + mir_cmd + " pairwise.mir";
      if (output_level > 0) System.out.println ( "\n*** Running pairwise mir with command line: " + command_line + " ***" );
      if (output_level > 0) System.out.println ( "Copying " + original_file_name + " to " + new_file_name );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + global_io.end_of_line );

      global_io.wait_for_proc ( cmd_proc );
      if ((exit_value = cmd_proc.exitValue()) != 0) System.out.println ( "\n\nWARNING: Command " + command_line + " finished with exit status " + global_io.translate_exit(exit_value) + "\n\n" );

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
  }


  public static String[] run_swim ( Runtime rt, String fixed_image_file, String align_image_file, String window_size, String parameters, int output_level ) {
    // The "parameters" should be of the form: "options % more options % more options" where the two "%" characters represent the two mandatory file names.
    System.out.println ( "Running Swim with:\n  " + fixed_image_file + "\n  " + align_image_file + "\n  " + window_size + "\n  " + parameters + "\n  " + output_level );

    String parameter_sections[] = parameters.trim().split ( "%" );

    if (parameter_sections.length < 2) {
      System.out.println ( "run_swim expects a parameters string containing two file placeholders (\"%\")." );
      return (null);
    }

    // Trim the parameter sections
    for (int i=0; i<parameter_sections.length; i++) {
      parameter_sections[i] = parameter_sections[i].trim();
    }

    // Insert the file names and trim
    String swim_params = parameter_sections[0] + " " + fixed_image_file + " " + parameter_sections[1] + " " + align_image_file;
    if (parameter_sections.length >= 3) {
      swim_params += " " + parameter_sections[2];
    }
    swim_params = swim_params.trim();

    System.out.println ( "Final parameters: \"" + swim_params + "\"" );

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

    if (global_io.is_windows()) {
      System.out.println ( "Running in Windows!!" );
      swim_cmd = "swim.exe";
      mir_cmd = "mir.exe";
    }

    String streams[] = null;

    try {

      command_line = code_source + swim_cmd + " " + window_size;

      if (output_level > 0) System.out.println ( "\n*** Running swim with command line: " + command_line + " ***" );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      interactive_commands = "unused " + swim_params + "\n";

      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed run_swim" );
      stdout = streams[0];
      stderr = streams[1];

    } catch ( Exception some_exception ) {

      if (output_level > 0) System.out.println ( "Error: " + some_exception );
      if (output_level > 0) System.out.println ( some_exception.getStackTrace() );
      some_exception.printStackTrace();

    }

    return ( streams );
  }


  public static String[] run_swim ( Runtime rt, String fixed_image_file, String align_image_file, String window_size, String x, String y, int output_level ) {

    // This supports the older format by writing a parameter string to pass to the new string based version
    String swim_params = "-i 2 -k keep."+image_type_extension;
    if (x.trim().length() > 0) swim_params += " -x " + x;
    if (y.trim().length() > 0) swim_params += " -y " + y;
    swim_params += " % %\n";

    return run_swim ( rt, fixed_image_file, align_image_file, window_size, swim_params, output_level );
  }


  public static String convert_to_windows ( String cmd ) {
    if (cmd.toLowerCase().endsWith(".exe")) {
      return ( cmd );
    } else {
      return ( cmd + ".exe" );
    }
  }


  public static String[] align_files_by_name ( Runtime rt, String fixed_image_file, String align_image_file, String aligned_image_file,
                                               int window_size, int addx, int addy, int output_level ) {

    if (output_level > 0) {
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "align_files_by_name called with:" );
      System.out.println ( "    fixed_image_file   = " + fixed_image_file );
      System.out.println ( "    align_image_file   = " + align_image_file );
      System.out.println ( "    aligned_image_file = " + aligned_image_file );
      System.out.println ( "    window_size        = " + window_size );
      System.out.println ( "    addx               = " + addx );
      System.out.println ( "    addy               = " + addy );
      System.out.println ( "    output_level       = " + output_level );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
    }

    fixed_image_file = normalize_file_name ( fixed_image_file );
    aligned_image_file = normalize_file_name ( aligned_image_file );
    System.out.println ( "    Translated fixed_image_file   = " + fixed_image_file );
    System.out.println ( "    Translated aligned_image_file = " + aligned_image_file );

    if (global_io.is_windows()) {
      System.out.println ( "Running in Windows!!" );
      swim_cmd = convert_to_windows ( swim_cmd );
      mir_cmd  = convert_to_windows ( mir_cmd );
    }

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

    String streams[];

    try {

      //////////////////////////////////////
      // Step 0 - Run first swim
      //////////////////////////////////////

      command_line = code_source + swim_cmd + " " + window_size;
      if (output_level > 0) System.out.println ( "\n*** Running first swim with command line: " + command_line + " ***" );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      interactive_commands = "unused -i 2 -k keep."+image_type_extension+" " + fixed_image_file + " " + align_image_file + global_io.end_of_line;

      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      write_to_proc ( proc_in, interactive_commands );
      proc_in.close();


      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 0 (first swim)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //    0                  1                     2   3               4                       5       6     7    8        9       10
      // 36.3771: Tile_r1-c1_LM9R5CA1series_017.jpg 512 512 Tile_r1-c1_LM9R5CA1series_018.jpg 506.866 504.853  0 (-5.13367 -7.14676 8.79947)


      //////////////////////////////////////
      // Step 1a - Run second swim
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 1a: Part " + i + " = " + parts[i] );
      }

      if (parts.length < 7) {
        System.out.println ( "Error: expected at least 7 parts, but only got " + parts.length + "\n" + stdout );
        return ( make_string_array ( "5", "Error: expected at least 7 parts, but only got " + parts.length + "\n" ) );
        // System.exit ( 5 );
      }

      String tarx = "" + parts[2];
      String tary = "" + parts[3];
      String patx = "" + parts[5];
      String paty = "" + parts[6];

      command_line = code_source + swim_cmd + " " + window_size;
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
        interactive_commands += fixed_image_file + " " + tarx + " " + tary + " ";
        interactive_commands += align_image_file + " " + patx + " " + paty + global_io.end_of_line;
      }
      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 1a (second swim)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //    0                         1                     2   3                4                       5       6        7    8        9       10
      // 49.1292: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012 1012 Tile_r1-c1_LM9R5CA1series_018.jpg 1009.16 1004.7     0 (2.29333 -0.15564 2.29861)
      // 22.4931: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012   12 Tile_r1-c1_LM9R5CA1series_018.jpg 1003.49 -0.523743  0 (-3.37482 -5.38275 6.35322)
      // 31.2584: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12   12 Tile_r1-c1_LM9R5CA1series_018.jpg 2.7988  2.21826    0 (-4.06619 -2.64075 4.84845)
      // 58.7499: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12 1012 Tile_r1-c1_LM9R5CA1series_018.jpg 8.69444 1007.01    0 (1.82945 2.14697 2.82071)


      //////////////////////////////////////
      // Step 1b - Run first mir
      //////////////////////////////////////

      //String stdout_lines[] = lines_from_stdout ( stdout );
      line_parts = parts_from_stdout ( stdout );

      for (int i=0; i<line_parts.length; i++) {
        for (int j=0; j<line_parts[i].length; j++) {
          if (output_level > 10) System.out.println ( "Step 1b: Part[" + i + "][" + j + "] = " + line_parts[i][j] );
        }
      }

      interactive_commands = "F " + align_image_file + global_io.end_of_line;
      interactive_commands += line_parts[0][2] + " " + line_parts[0][3] + " " + line_parts[0][5] + " " + line_parts[0][6] + global_io.end_of_line;
      interactive_commands += line_parts[1][2] + " " + line_parts[1][3] + " " + line_parts[1][5] + " " + line_parts[1][6] + global_io.end_of_line;
      interactive_commands += line_parts[2][2] + " " + line_parts[2][3] + " " + line_parts[2][5] + " " + line_parts[2][6] + global_io.end_of_line;
      interactive_commands += line_parts[3][2] + " " + line_parts[3][3] + " " + line_parts[3][5] + " " + line_parts[3][6] + global_io.end_of_line;
      interactive_commands += "RW iter1_mir_out."+image_type_extension+global_io.end_of_line;

      f = new File ( System.getProperty("user.dir") + File.separator + "first.mir" );

      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = code_source + mir_cmd + " first.mir";
      if (output_level > 0) System.out.println ( "\n*** Running first mir with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 1b (first mir)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //              0                     1    2         3           4         5          6        7
      // Tile_r1-c1_LM9R5CA1series_018.jpg AF  0.999407 -0.00575053  9.15865   0.00251182 0.995003 9.89321
      // Tile_r1-c1_LM9R5CA1series_018.jpg AI  1.00058   0.00578275 -9.22115  -0.0025259  1.00501 -9.91962


      //////////////////////////////////////
      // Step 2a - Run third swim
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 2a: Part " + i + " = " + parts[i] );
      }

      if (parts.length < 15) {
        System.out.println ( "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout );
        return ( make_string_array ( "5", "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout ) );
        // System.exit ( 5 );
      }

      AI1 = "" + parts[10];
      AI2 = "" + parts[11];
      AI3 = "" + parts[13];
      AI4 = "" + parts[14];

      command_line = code_source + swim_cmd + " " + window_size;
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
        interactive_commands += fixed_image_file + " " + tarx + " " + tary + " ";
        interactive_commands += align_image_file + " " + patx + " " + paty + " ";
        interactive_commands += AI1 + " " + AI2 + " " + AI3 + " " + AI4 + " " + global_io.end_of_line;
      }
      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 2a (third swim)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //    0                         1                      2    3               4                       5       6        7      8        9       10
      // 59.4171: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012 1012 Tile_r1-c1_LM9R5CA1series_018.jpg 1009.19  1003.47  1024 (-0.858154 -2.62854 2.76508)
      // 30.0668: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012   12 Tile_r1-c1_LM9R5CA1series_018.jpg 1002.23 -1.42319  1024 (-2.03265  -2.51425 3.23313)
      // 38.8941: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12   12 Tile_r1-c1_LM9R5CA1series_018.jpg  2.3043  2.22272  1024 (-1.37932  -1.39422 1.96122)
      // 59.5567: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12 1012 Tile_r1-c1_LM9R5CA1series_018.jpg   9.077  1006.68  1024 (-0.3894   -1.95184 1.99031)


      //////////////////////////////////////
      // Step 2b - Run second mir
      //////////////////////////////////////


      //String stdout_lines[] = lines_from_stdout ( stdout );
      line_parts = parts_from_stdout ( stdout );

      for (int i=0; i<line_parts.length; i++) {
        for (int j=0; j<line_parts[i].length; j++) {
          if (output_level > 10) System.out.println ( "Step 2b: Part[" + i + "][" + j + "] = " + line_parts[i][j] );
        }
      }

      interactive_commands = "F " + align_image_file + global_io.end_of_line;
      interactive_commands += line_parts[0][2] + " " + line_parts[0][3] + " " + line_parts[0][5] + " " + line_parts[0][6] + global_io.end_of_line;
      interactive_commands += line_parts[1][2] + " " + line_parts[1][3] + " " + line_parts[1][5] + " " + line_parts[1][6] + global_io.end_of_line;
      interactive_commands += line_parts[2][2] + " " + line_parts[2][3] + " " + line_parts[2][5] + " " + line_parts[2][6] + global_io.end_of_line;
      interactive_commands += line_parts[3][2] + " " + line_parts[3][3] + " " + line_parts[3][5] + " " + line_parts[3][6] + global_io.end_of_line;
      interactive_commands += "RW iter2_mir_out."+image_type_extension+global_io.end_of_line;

      f = new File ( System.getProperty("user.dir") + File.separator + "second.mir" );

      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = code_source + mir_cmd + " second.mir";
      if (output_level > 0) System.out.println ( "\n*** Running second mir with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 2b (second mir)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //              0                     1    2         3           4         5          6        7
      // Tile_r1-c1_LM9R5CA1series_018.jpg AF  0.999957 -0.00683413  9.75702   0.00341172 0.995323 9.88854
      // Tile_r1-c1_LM9R5CA1series_018.jpg AI  1.00002   0.00686638 -9.82511  -0.00342782 1.00468 -9.90133


      //////////////////////////////////////
      // Step 3a - Run fourth swim
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 3a: Part " + i + " = " + parts[i] );
      }

      if (parts.length < 15) {
        System.out.println ( "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout );
        return ( make_string_array ( "5", "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout ) );
        // System.exit ( 5 );
      }

      AI1 = "" + parts[10];
      AI2 = "" + parts[11];
      AI3 = "" + parts[13];
      AI4 = "" + parts[14];

      command_line = code_source + swim_cmd + " " + window_size;
      if (output_level > 0) System.out.println ( "\n*** Running fourth swim with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      cmd_proc = rt.exec ( command_line );
      System.out.println ( "Started subprocess" );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      interactive_commands = "";
      for (int loop_index=0; loop_index<loop_signs_3x3.length; loop_index++) {
        int x = loop_signs_3x3[loop_index][0];
        int y = loop_signs_3x3[loop_index][1];
        interactive_commands += "unused -i 2 -x " + (addx*x) + " -y " + (addy*y) + " ";
        interactive_commands += fixed_image_file + " " + tarx + " " + tary + " ";
        interactive_commands += align_image_file + " " + patx + " " + paty + " ";
        interactive_commands += AI1 + " " + AI2 + " " + AI3 + " " + AI4 + " " + global_io.end_of_line;
      }
      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      System.out.println ( "Writing to subprocess" );
      write_to_proc ( proc_in, interactive_commands );
      System.out.println ( "Flushing stream to subprocess" );
      proc_in.flush();
      System.out.println ( "Closing stream to subprocess" );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 3a (fourth swim)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //    0                         1                      2    3               4                       5        6       7      8        9       10
      // 59.6657: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012 1012 Tile_r1-c1_LM9R5CA1series_018.jpg 1009.25  1003.41  1024 (-1.05634 -2.07587 2.32918)
      // 31.8235: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012   12 Tile_r1-c1_LM9R5CA1series_018.jpg 1001.96 -1.63561  1024 (-1.48199 -2.4407  2.8554)
      // 35.8937: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12   12 Tile_r1-c1_LM9R5CA1series_018.jpg 2.36482  2.51362  1024 (-1.05696 -1.71926 2.01817)
      // 58.2213: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12 1012 Tile_r1-c1_LM9R5CA1series_018.jpg 9.33534  1006.78  1024 (-0.95284 -2.13593 2.33882)
      // 55.3926: output/Tile_r1-c1_LM9R5CA1series_017.jpg  512  512 Tile_r1-c1_LM9R5CA1series_018.jpg 505.187  503.068  1024 (-1.67838 -1.79062 2.45423)
      // 61.4603: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012  512 Tile_r1-c1_LM9R5CA1series_018.jpg 1005.33  501.508  1024 (-1.54633 -1.63705 2.2519)
      // 51.5881: output/Tile_r1-c1_LM9R5CA1series_017.jpg  512 1012 Tile_r1-c1_LM9R5CA1series_018.jpg 508.613  1005.08  1024 (-1.68539 -2.12262 2.71036)
      // 59.0445: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12  512 Tile_r1-c1_LM9R5CA1series_018.jpg 5.80735  505.496  1024 (-1.04763 -1.07721 1.50263)
      // 41.8738: output/Tile_r1-c1_LM9R5CA1series_017.jpg  512   12 Tile_r1-c1_LM9R5CA1series_018.jpg 501.536  1.02411  1024 (-1.89609 -1.49487 2.41449)


      //////////////////////////////////////
      // Step 3b - Run third mir
      //////////////////////////////////////

      //String stdout_lines[] = lines_from_stdout ( stdout );
      line_parts = parts_from_stdout ( stdout );

      for (int i=0; i<line_parts.length; i++) {
        for (int j=0; j<line_parts[i].length; j++) {
          if (output_level > 10) System.out.println ( "Step 3b: Part[" + i + "][" + j + "] = " + line_parts[i][j] );
        }
      }

      interactive_commands = "F " + align_image_file + global_io.end_of_line;
      interactive_commands += line_parts[0][2] + " " + line_parts[0][3] + " " + line_parts[0][5] + " " + line_parts[0][6] + global_io.end_of_line;
      interactive_commands += line_parts[1][2] + " " + line_parts[1][3] + " " + line_parts[1][5] + " " + line_parts[1][6] + global_io.end_of_line;
      interactive_commands += line_parts[2][2] + " " + line_parts[2][3] + " " + line_parts[2][5] + " " + line_parts[2][6] + global_io.end_of_line;
      interactive_commands += line_parts[3][2] + " " + line_parts[3][3] + " " + line_parts[3][5] + " " + line_parts[3][6] + global_io.end_of_line;

      interactive_commands += line_parts[4][2] + " " + line_parts[4][3] + " " + line_parts[4][5] + " " + line_parts[4][6] + global_io.end_of_line;

      interactive_commands += line_parts[5][2] + " " + line_parts[5][3] + " " + line_parts[5][5] + " " + line_parts[5][6] + global_io.end_of_line;
      interactive_commands += line_parts[6][2] + " " + line_parts[6][3] + " " + line_parts[6][5] + " " + line_parts[6][6] + global_io.end_of_line;
      interactive_commands += line_parts[7][2] + " " + line_parts[7][3] + " " + line_parts[7][5] + " " + line_parts[7][6] + global_io.end_of_line;
      interactive_commands += line_parts[8][2] + " " + line_parts[8][3] + " " + line_parts[8][5] + " " + line_parts[8][6] + global_io.end_of_line;

      interactive_commands += "RW " + aligned_image_file + global_io.end_of_line;

      // Change the name of the file in this slot to use the newly aligned image:
      // NOTE: This is now done outside of this alignment function
      // image_files[align_index] = "aligned_" + String.format("%03d", align_index) + "."+image_type_extension+"";
      // image_files[align_index] = aligned_image_file;


      f = new File ( System.getProperty("user.dir") + File.separator + "third.mir" );

      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = code_source + mir_cmd + " third.mir";
      if (output_level > 0) System.out.println ( "\n*** Running third mir with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 3b (third mir)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //              0                     1    2        3          4         5          6        7
      // Tile_r1-c1_LM9R5CA1series_018.jpg AF  1.0003  -0.00708304 9.92646   0.00381993 0.995537 9.28708
      // Tile_r1-c1_LM9R5CA1series_018.jpg AI  0.999677 0.0071125 -9.98931  -0.00383582 1.00446 -9.29038


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
        return ( make_string_array ( "5", "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout ) );
        // System.exit ( 5 );
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



      return ( make_string_array ( "m", patx, paty, parts[10], parts[11], parts[13], parts[14],
                                        parts[10], parts[11], parts[12], parts[13], parts[14], parts[15],
                                        parts[2], parts[3], parts[4], parts[5], parts[6], parts[7] ) );

      // return ( make_string_array ( "5", "Error: expected at least 7 parts, but only got " + parts.length + "\n" ) );

    } catch ( Exception some_exception ) {

      if (output_level > 0) System.out.println ( "Error: " + some_exception );
      if (output_level > 0) System.out.println ( some_exception.getStackTrace() );
      some_exception.printStackTrace();

    }

    return ( null );
  }





  public static String[] align_files_by_name_2 ( Runtime rt, String fixed_image_file, String align_image_file, String aligned_image_file,
                                                 int trans_window_size, int trans_addx, int trans_addy,
                                                 int window_size, int addx, int addy,
                                                 int output_level ) {

    if (output_level > 0) {
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "align_files_by_name_2 called with:" );
      System.out.println ( "    fixed_image_file   = " + fixed_image_file );
      System.out.println ( "    align_image_file   = " + align_image_file );
      System.out.println ( "    aligned_image_file = " + aligned_image_file );
      System.out.println ( "    window_size        = " + window_size );
      System.out.println ( "    addx               = " + addx );
      System.out.println ( "    addy               = " + addy );
      System.out.println ( "    output_level       = " + output_level );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
      System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
    }

    fixed_image_file = normalize_file_name ( fixed_image_file );
    aligned_image_file = normalize_file_name ( aligned_image_file );
    System.out.println ( "    Translated fixed_image_file   = " + fixed_image_file );
    System.out.println ( "    Translated aligned_image_file = " + aligned_image_file );

    if (global_io.is_windows()) {
      System.out.println ( "Running in Windows!!" );
      swim_cmd = convert_to_windows ( swim_cmd );
      mir_cmd  = convert_to_windows ( mir_cmd );
    }

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

    String streams[];

    try {

      //////////////////////////////////////
      // Step 0 - Run first swim
      //////////////////////////////////////

      command_line = code_source + swim_cmd + " " + trans_window_size;
      if (output_level > 0) System.out.println ( "\n*** Running first swim with command line: " + command_line + " ***" );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      interactive_commands = "unused -i 2 -x " + trans_addx + " -y " + trans_addy + " -k keep."+image_type_extension+" " + fixed_image_file + " " + align_image_file + global_io.end_of_line;

      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      write_to_proc ( proc_in, interactive_commands );
      proc_in.close();


      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 0 (first swim)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //    0                  1                     2   3               4                       5       6     7    8        9       10
      // 36.3771: Tile_r1-c1_LM9R5CA1series_017.jpg 512 512 Tile_r1-c1_LM9R5CA1series_018.jpg 506.866 504.853  0 (-5.13367 -7.14676 8.79947)


      //////////////////////////////////////
      // Step 1a - Run second swim
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 1a: Part " + i + " = " + parts[i] );
      }

      if (parts.length < 7) {
        System.out.println ( "Error: expected at least 7 parts, but only got " + parts.length + "\n" + stdout );
        return ( make_string_array ( "5", "Error: expected at least 7 parts, but only got " + parts.length + "\n" ) );
        // System.exit ( 5 );
      }

      String tarx = "" + parts[2];
      String tary = "" + parts[3];
      String patx = "" + parts[5];
      String paty = "" + parts[6];

      command_line = code_source + swim_cmd + " " + window_size;
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
        interactive_commands += fixed_image_file + " " + tarx + " " + tary + " ";
        interactive_commands += align_image_file + " " + patx + " " + paty + global_io.end_of_line;
      }
      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 1a (second swim)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //    0                         1                     2   3                4                       5       6        7    8        9       10
      // 49.1292: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012 1012 Tile_r1-c1_LM9R5CA1series_018.jpg 1009.16 1004.7     0 (2.29333 -0.15564 2.29861)
      // 22.4931: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012   12 Tile_r1-c1_LM9R5CA1series_018.jpg 1003.49 -0.523743  0 (-3.37482 -5.38275 6.35322)
      // 31.2584: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12   12 Tile_r1-c1_LM9R5CA1series_018.jpg 2.7988  2.21826    0 (-4.06619 -2.64075 4.84845)
      // 58.7499: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12 1012 Tile_r1-c1_LM9R5CA1series_018.jpg 8.69444 1007.01    0 (1.82945 2.14697 2.82071)


      //////////////////////////////////////
      // Step 1b - Run first mir
      //////////////////////////////////////

      //String stdout_lines[] = lines_from_stdout ( stdout );
      line_parts = parts_from_stdout ( stdout );

      for (int i=0; i<line_parts.length; i++) {
        for (int j=0; j<line_parts[i].length; j++) {
          if (output_level > 10) System.out.println ( "Step 1b: Part[" + i + "][" + j + "] = " + line_parts[i][j] );
        }
      }

      interactive_commands = "F " + align_image_file + global_io.end_of_line;
      interactive_commands += line_parts[0][2] + " " + line_parts[0][3] + " " + line_parts[0][5] + " " + line_parts[0][6] + global_io.end_of_line;
      interactive_commands += line_parts[1][2] + " " + line_parts[1][3] + " " + line_parts[1][5] + " " + line_parts[1][6] + global_io.end_of_line;
      interactive_commands += line_parts[2][2] + " " + line_parts[2][3] + " " + line_parts[2][5] + " " + line_parts[2][6] + global_io.end_of_line;
      interactive_commands += line_parts[3][2] + " " + line_parts[3][3] + " " + line_parts[3][5] + " " + line_parts[3][6] + global_io.end_of_line;
      interactive_commands += "RW iter1_mir_out."+image_type_extension+global_io.end_of_line;

      f = new File ( System.getProperty("user.dir") + File.separator + "first.mir" );

      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = code_source + mir_cmd + " first.mir";
      if (output_level > 0) System.out.println ( "\n*** Running first mir with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 1b (first mir)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //              0                     1    2         3           4         5          6        7
      // Tile_r1-c1_LM9R5CA1series_018.jpg AF  0.999407 -0.00575053  9.15865   0.00251182 0.995003 9.89321
      // Tile_r1-c1_LM9R5CA1series_018.jpg AI  1.00058   0.00578275 -9.22115  -0.0025259  1.00501 -9.91962


      //////////////////////////////////////
      // Step 2a - Run third swim
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 2a: Part " + i + " = " + parts[i] );
      }

      if (parts.length < 15) {
        System.out.println ( "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout );
        return ( make_string_array ( "5", "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout ) );
        // System.exit ( 5 );
      }

      AI1 = "" + parts[10];
      AI2 = "" + parts[11];
      AI3 = "" + parts[13];
      AI4 = "" + parts[14];

      command_line = code_source + swim_cmd + " " + window_size;
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
        interactive_commands += fixed_image_file + " " + tarx + " " + tary + " ";
        interactive_commands += align_image_file + " " + patx + " " + paty + " ";
        interactive_commands += AI1 + " " + AI2 + " " + AI3 + " " + AI4 + " " + global_io.end_of_line;
      }
      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 2a (third swim)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //    0                         1                      2    3               4                       5       6        7      8        9       10
      // 59.4171: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012 1012 Tile_r1-c1_LM9R5CA1series_018.jpg 1009.19  1003.47  1024 (-0.858154 -2.62854 2.76508)
      // 30.0668: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012   12 Tile_r1-c1_LM9R5CA1series_018.jpg 1002.23 -1.42319  1024 (-2.03265  -2.51425 3.23313)
      // 38.8941: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12   12 Tile_r1-c1_LM9R5CA1series_018.jpg  2.3043  2.22272  1024 (-1.37932  -1.39422 1.96122)
      // 59.5567: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12 1012 Tile_r1-c1_LM9R5CA1series_018.jpg   9.077  1006.68  1024 (-0.3894   -1.95184 1.99031)


      //////////////////////////////////////
      // Step 2b - Run second mir
      //////////////////////////////////////


      //String stdout_lines[] = lines_from_stdout ( stdout );
      line_parts = parts_from_stdout ( stdout );

      for (int i=0; i<line_parts.length; i++) {
        for (int j=0; j<line_parts[i].length; j++) {
          if (output_level > 10) System.out.println ( "Step 2b: Part[" + i + "][" + j + "] = " + line_parts[i][j] );
        }
      }

      interactive_commands = "F " + align_image_file + global_io.end_of_line;
      interactive_commands += line_parts[0][2] + " " + line_parts[0][3] + " " + line_parts[0][5] + " " + line_parts[0][6] + global_io.end_of_line;
      interactive_commands += line_parts[1][2] + " " + line_parts[1][3] + " " + line_parts[1][5] + " " + line_parts[1][6] + global_io.end_of_line;
      interactive_commands += line_parts[2][2] + " " + line_parts[2][3] + " " + line_parts[2][5] + " " + line_parts[2][6] + global_io.end_of_line;
      interactive_commands += line_parts[3][2] + " " + line_parts[3][3] + " " + line_parts[3][5] + " " + line_parts[3][6] + global_io.end_of_line;
      interactive_commands += "RW iter2_mir_out."+image_type_extension+global_io.end_of_line;

      f = new File ( System.getProperty("user.dir") + File.separator + "second.mir" );

      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = code_source + mir_cmd + " second.mir";
      if (output_level > 0) System.out.println ( "\n*** Running second mir with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 2b (second mir)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //              0                     1    2         3           4         5          6        7
      // Tile_r1-c1_LM9R5CA1series_018.jpg AF  0.999957 -0.00683413  9.75702   0.00341172 0.995323 9.88854
      // Tile_r1-c1_LM9R5CA1series_018.jpg AI  1.00002   0.00686638 -9.82511  -0.00342782 1.00468 -9.90133


      //////////////////////////////////////
      // Step 3a - Run fourth swim
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 10) System.out.println ( "Step 3a: Part " + i + " = " + parts[i] );
      }

      if (parts.length < 15) {
        System.out.println ( "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout );
        return ( make_string_array ( "5", "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout ) );
        // System.exit ( 5 );
      }

      AI1 = "" + parts[10];
      AI2 = "" + parts[11];
      AI3 = "" + parts[13];
      AI4 = "" + parts[14];

      command_line = code_source + swim_cmd + " " + window_size;
      if (output_level > 0) System.out.println ( "\n*** Running fourth swim with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      cmd_proc = rt.exec ( command_line );
      System.out.println ( "Started subprocess" );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      interactive_commands = "";
      for (int loop_index=0; loop_index<loop_signs_3x3.length; loop_index++) {
        int x = loop_signs_3x3[loop_index][0];
        int y = loop_signs_3x3[loop_index][1];
        interactive_commands += "unused -i 2 -x " + (addx*x) + " -y " + (addy*y) + " ";
        interactive_commands += fixed_image_file + " " + tarx + " " + tary + " ";
        interactive_commands += align_image_file + " " + patx + " " + paty + " ";
        interactive_commands += AI1 + " " + AI2 + " " + AI3 + " " + AI4 + " " + global_io.end_of_line;
      }
      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      System.out.println ( "Writing to subprocess" );
      write_to_proc ( proc_in, interactive_commands );
      System.out.println ( "Flushing stream to subprocess" );
      proc_in.flush();
      System.out.println ( "Closing stream to subprocess" );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 3a (fourth swim)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //    0                         1                      2    3               4                       5        6       7      8        9       10
      // 59.6657: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012 1012 Tile_r1-c1_LM9R5CA1series_018.jpg 1009.25  1003.41  1024 (-1.05634 -2.07587 2.32918)
      // 31.8235: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012   12 Tile_r1-c1_LM9R5CA1series_018.jpg 1001.96 -1.63561  1024 (-1.48199 -2.4407  2.8554)
      // 35.8937: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12   12 Tile_r1-c1_LM9R5CA1series_018.jpg 2.36482  2.51362  1024 (-1.05696 -1.71926 2.01817)
      // 58.2213: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12 1012 Tile_r1-c1_LM9R5CA1series_018.jpg 9.33534  1006.78  1024 (-0.95284 -2.13593 2.33882)
      // 55.3926: output/Tile_r1-c1_LM9R5CA1series_017.jpg  512  512 Tile_r1-c1_LM9R5CA1series_018.jpg 505.187  503.068  1024 (-1.67838 -1.79062 2.45423)
      // 61.4603: output/Tile_r1-c1_LM9R5CA1series_017.jpg 1012  512 Tile_r1-c1_LM9R5CA1series_018.jpg 1005.33  501.508  1024 (-1.54633 -1.63705 2.2519)
      // 51.5881: output/Tile_r1-c1_LM9R5CA1series_017.jpg  512 1012 Tile_r1-c1_LM9R5CA1series_018.jpg 508.613  1005.08  1024 (-1.68539 -2.12262 2.71036)
      // 59.0445: output/Tile_r1-c1_LM9R5CA1series_017.jpg   12  512 Tile_r1-c1_LM9R5CA1series_018.jpg 5.80735  505.496  1024 (-1.04763 -1.07721 1.50263)
      // 41.8738: output/Tile_r1-c1_LM9R5CA1series_017.jpg  512   12 Tile_r1-c1_LM9R5CA1series_018.jpg 501.536  1.02411  1024 (-1.89609 -1.49487 2.41449)


      //////////////////////////////////////
      // Step 3b - Run third mir
      //////////////////////////////////////

      //String stdout_lines[] = lines_from_stdout ( stdout );
      line_parts = parts_from_stdout ( stdout );

      for (int i=0; i<line_parts.length; i++) {
        for (int j=0; j<line_parts[i].length; j++) {
          if (output_level > 10) System.out.println ( "Step 3b: Part[" + i + "][" + j + "] = " + line_parts[i][j] );
        }
      }

      interactive_commands = "F " + align_image_file + global_io.end_of_line;
      interactive_commands += line_parts[0][2] + " " + line_parts[0][3] + " " + line_parts[0][5] + " " + line_parts[0][6] + global_io.end_of_line;
      interactive_commands += line_parts[1][2] + " " + line_parts[1][3] + " " + line_parts[1][5] + " " + line_parts[1][6] + global_io.end_of_line;
      interactive_commands += line_parts[2][2] + " " + line_parts[2][3] + " " + line_parts[2][5] + " " + line_parts[2][6] + global_io.end_of_line;
      interactive_commands += line_parts[3][2] + " " + line_parts[3][3] + " " + line_parts[3][5] + " " + line_parts[3][6] + global_io.end_of_line;

      interactive_commands += line_parts[4][2] + " " + line_parts[4][3] + " " + line_parts[4][5] + " " + line_parts[4][6] + global_io.end_of_line;

      interactive_commands += line_parts[5][2] + " " + line_parts[5][3] + " " + line_parts[5][5] + " " + line_parts[5][6] + global_io.end_of_line;
      interactive_commands += line_parts[6][2] + " " + line_parts[6][3] + " " + line_parts[6][5] + " " + line_parts[6][6] + global_io.end_of_line;
      interactive_commands += line_parts[7][2] + " " + line_parts[7][3] + " " + line_parts[7][5] + " " + line_parts[7][6] + global_io.end_of_line;
      interactive_commands += line_parts[8][2] + " " + line_parts[8][3] + " " + line_parts[8][5] + " " + line_parts[8][6] + global_io.end_of_line;

      interactive_commands += "RW " + aligned_image_file + global_io.end_of_line;

      // Change the name of the file in this slot to use the newly aligned image:
      // NOTE: This is now done outside of this alignment function
      // image_files[align_index] = "aligned_" + String.format("%03d", align_index) + "."+image_type_extension+"";
      // image_files[align_index] = aligned_image_file;


      f = new File ( System.getProperty("user.dir") + File.separator + "third.mir" );

      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = code_source + mir_cmd + " third.mir";
      if (output_level > 0) System.out.println ( "\n*** Running third mir with command line: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //write_to_proc ( proc_in, interactive_commands );
      proc_in.close();

      global_io.log_command ( command_line + "\n" );
      global_io.log_command ( interactive_commands + "\n" );

      System.out.println ( "Waiting for subprocess to finish ..." );

      streams = global_io.wait_for_proc_streams ( cmd_proc, proc_in, proc_out, proc_err, output_level, command_line, interactive_commands, "Completed Step 3b (third mir)" );
      stdout = streams[0];
      stderr = streams[1];

      // stdout will look like:
      //              0                     1    2        3          4         5          6        7
      // Tile_r1-c1_LM9R5CA1series_018.jpg AF  1.0003  -0.00708304 9.92646   0.00381993 0.995537 9.28708
      // Tile_r1-c1_LM9R5CA1series_018.jpg AI  0.999677 0.0071125 -9.98931  -0.00383582 1.00446 -9.29038


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
        return ( make_string_array ( "5", "Error: expected at least 15 parts, but only got " + parts.length + "\n" + stdout ) );
        // System.exit ( 5 );
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



      return ( make_string_array ( "m", patx, paty, parts[10], parts[11], parts[13], parts[14],
                                        parts[10], parts[11], parts[12], parts[13], parts[14], parts[15],
                                        parts[2], parts[3], parts[4], parts[5], parts[6], parts[7] ) );

      // return ( make_string_array ( "5", "Error: expected at least 7 parts, but only got " + parts.length + "\n" ) );

    } catch ( Exception some_exception ) {

      if (output_level > 0) System.out.println ( "Error: " + some_exception );
      if (output_level > 0) System.out.println ( some_exception.getStackTrace() );
      some_exception.printStackTrace();

    }

    return ( null );
  }











  public static void main(String[] args) throws java.io.FileNotFoundException {

    if ( System.getProperty("os.name").trim().toLowerCase().startsWith("win") ) {
      System.out.println ( "Running in Windows (from main)" );
    }

    int output_level = 1;
    int align_to = -1;
    int window_size = 2048;
    int addx = 2000;
    int addy = 2000;

    int scale_factor = -1;

    boolean test2 = false;

    ArrayList<String> file_name_args = new ArrayList<String>();

    boolean bad_args = false;
    int arg_index = 0;
    while (arg_index < args.length) {
      if (output_level > 4) System.out.println ( "Arg[" + arg_index + "] = \"" + args[arg_index] + "\"" );
      if (args[arg_index].startsWith("-") ) {
        if (args[arg_index].equals("-?")) {
          System.out.println ( "Git Revision:\n " + revision.githash );
          System.out.println ( "Command Line Arguments:" );
          System.out.println ( "  -is #   run iscale with # as scale (no other processing)" );
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
          System.out.println ( "  images  all arguments not prefixed with \"-\" are image files" );
          System.exit ( 0 );
        } else if (args[arg_index].equals("-is")) {
          arg_index++;
          scale_factor = new Integer ( args[arg_index] );
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

    if (scale_factor > 0) {
      // Just scale and then exit
      Runtime rt = Runtime.getRuntime();
      for (int i=0; i<actual_file_names.size(); i++) {
        String image_file_name = actual_file_names.get(i);
        scale_file_with_iscale ( rt, image_file_name, "."+File.separator, scale_factor, output_level );
      }

      System.exit ( 0 );
    }

    if ( actual_file_names.size() < 2 ) {
      if (output_level > -1) System.out.println ( "Must specify at least 2 images to align. Try using -? option for help." );
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

    copy_file_by_name ( rt, image_files[golden_section], "aligned_" + String.format("%03d", golden_section) + "."+image_type_extension, output_level );

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

      String new_aligned_image_file_name = "aligned_" + String.format("%03d", alignment_sequence[alignment_index][0]) + "."+image_type_extension;

      String results[] = align_files_by_name ( rt,
                            image_files[alignment_sequence[alignment_index][1]],
                            image_files[alignment_sequence[alignment_index][0]],
                            new_aligned_image_file_name,
                            window_size, addx, addy, output_level );

      if (results != null) {
        if (output_level > 0) System.out.println ( results );
      }

      // Update the name being used in that slot
      image_files[alignment_sequence[alignment_index][0]] = new_aligned_image_file_name;


    }

  }

}
