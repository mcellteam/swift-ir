import java.io.*;
import java.util.*;


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

	public static ArrayList<String> actual_file_names = new ArrayList<String>();


  public String[] lines_from_stdout ( String stdout ) {
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


  public void dump_lines_from_stdout ( String stdout ) {
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
    return ( s );
  }

  public static void align_files_by_index ( Runtime rt, String image_files[], int fixed_index, int align_index, 
                                            int window_size, int addx, int addy, int output_level ) {

    String command_line;
    String interactive_commands;
    Process cmd_proc;

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

    String AI1, AI2, AI3, AI4;

    try {

      //////////////////////////////////////
      // Step 0 - Run first swim
      //////////////////////////////////////

      command_line = "swim " + window_size;
      if (output_level > 0) System.out.println ( "*** Running: " + command_line + " ***" );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      interactive_commands = "unused -i 2 -k keep.JPG " + image_files[fixed_index] + " " + image_files[align_index] + "\n";

      if (output_level > 1) System.out.println ( "Passing to swim:\n" + interactive_commands );

      proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      cmd_proc.waitFor();

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 8) System.out.print ( stdout );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 8) System.out.print ( stderr );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      //////////////////////////////////////
      // Step 1a - Run second swim
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 8) System.out.println ( "Step 1a: Part " + i + " = " + parts[i] );
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
      if (output_level > 0) System.out.println ( "*** Running: " + command_line + " ***" );
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

      cmd_proc.waitFor();

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 8) System.out.print ( stdout );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 8) System.out.print ( stderr );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      //////////////////////////////////////
      // Step 1b - Run first mir
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 8) System.out.println ( "Step 1b: Part " + i + " = " + parts[i] );
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
      interactive_commands += "RW iter1_mir_out.JPG\n";

      f = new File ( System.getenv("PWD") + File.separator + "first.mir" );
      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = "mir first.mir";
      if (output_level > 0) System.out.println ( "*** Running: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      cmd_proc.waitFor();

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 8) System.out.print ( stdout );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 8) System.out.print ( stderr );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      //////////////////////////////////////
      // Step 2a - Run third swim
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 8) System.out.println ( "Step 2a: Part " + i + " = " + parts[i] );
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
      if (output_level > 0) System.out.println ( "*** Running: " + command_line + " ***" );
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

      cmd_proc.waitFor();

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 8) System.out.print ( stdout );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 8) System.out.print ( stderr );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      //////////////////////////////////////
      // Step 2b - Run second mir
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 8) System.out.println ( "Step 2b: Part " + i + " = " + parts[i] );
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
      interactive_commands += "RW iter2_mir_out.JPG\n";

      f = new File ( System.getenv("PWD") + File.separator + "second.mir" );
      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = "mir second.mir";
      if (output_level > 0) System.out.println ( "*** Running: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      cmd_proc.waitFor();

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 8) System.out.print ( stdout );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 8) System.out.print ( stderr );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      //////////////////////////////////////
      // Step 3a - Run fourth swim
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 8) System.out.println ( "Step 3a: Part " + i + " = " + parts[i] );
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
      if (output_level > 0) System.out.println ( "*** Running: " + command_line + " ***" );
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

      cmd_proc.waitFor();

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 8) System.out.print ( stdout );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 8) System.out.print ( stderr );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      //////////////////////////////////////
      // Step 3b - Run third mir
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 8) System.out.println ( "Step 3b: Part " + i + " = " + parts[i] );
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
      // interactive_commands += "RW iter3_mir_out.JPG\n";
      interactive_commands += "RW " + "aligned_" + align_index + ".JPG\n";


      // Change the name of the file in this slot to use the newly aligned image:
      image_files[align_index] = "aligned_" + align_index + ".JPG";


      f = new File ( System.getenv("PWD") + File.separator + "third.mir" );
      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = "mir third.mir";
      if (output_level > 0) System.out.println ( "*** Running: " + command_line + " ***" );
      if (output_level > 2) System.out.println ( "    Number of parts = " + parts.length );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      cmd_proc.waitFor();

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 8) System.out.print ( stdout );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 8) System.out.print ( stderr );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      //////////////////////////////////////
      // Step 3c - Best guess transform
      //////////////////////////////////////

      parts = stdout.split ( "[\\s]+" );
      for (int i=0; i<parts.length; i++) {
        if (output_level > 8) System.out.println ( "Step 3c: Part " + i + " = " + parts[i] );
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
      if (output_level > 1) System.out.println ( "=================================================================================" );
      if (output_level > 1) System.out.println ();
      if (output_level > 1) System.out.println ();

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


	  ArrayList<String> file_name_args = new ArrayList<String>();

    int arg_index = 0;
    while (arg_index < args.length) {
		  if (output_level > 8) System.out.println ( "Arg[" + arg_index + "] = \"" + args[arg_index] + "\"" );
		  if (args[arg_index].startsWith("-") ) {
		    if (args[arg_index].equals("-?")) {
		      System.out.println ( "Command Line Arguments:" );
		      System.out.println ( "  -v # amount of output (0 to 9)" );
		      System.out.println ( "  -g # specifies \"golden\" image number" );
		      System.out.println ( "  -w # specifies windows size" );
		      System.out.println ( "  -ax # specifies addx (-x option to swim)" );
		      System.out.println ( "  -ay # specifies addy (-y option to swim)" );
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
		    } else {
		      if (output_level > 0) System.out.println ( "Unrecognized option: " + args[arg_index] );
		    }
		  } else {
		    file_name_args.add ( args[arg_index] );
		  }
		  arg_index++;
    }

    if (output_level > 6) System.out.println ( "Command line specified " + file_name_args.size() + " file name patterns." );

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
      interactive_commands += "RW " + "aligned_" + golden_section + ".JPG\n";

      f = new File ( System.getenv("PWD") + File.separator + "zeroth.mir" );
      bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
      bw.write ( interactive_commands, 0, interactive_commands.length() );
      bw.close();

      command_line = "mir zeroth.mir";
      if (output_level > 0) System.out.println ( "*** Running: " + command_line + " ***" );
      if (output_level > 1) System.out.println ( "Passing to mir:\n" + interactive_commands );
      cmd_proc = rt.exec ( command_line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      //proc_in.write ( interactive_commands.getBytes() );
      proc_in.close();

      cmd_proc.waitFor();

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );

      stdout = read_string_from ( proc_out );

      if (output_level > 8) System.out.print ( stdout );

      if (output_level > 8) System.out.println ( "=================================================================================" );

      if (output_level > 8) System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );

      stderr = read_string_from ( proc_err );

      if (output_level > 8) System.out.print ( stderr );

      if (output_level > 8) System.out.println ( "=================================================================================" );

    } catch ( Exception some_exception ) {

      if (output_level > 0) System.out.println ( "Error: " + some_exception );
      if (output_level > 0) System.out.println ( some_exception.getStackTrace() );
      some_exception.printStackTrace();

    }

    image_files[golden_section] = "aligned_" + golden_section + ".JPG";

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
