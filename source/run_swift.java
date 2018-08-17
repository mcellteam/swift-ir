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

  public static void main(String[] args) throws java.io.FileNotFoundException {


    int align_to = -1;
    int window_size = 2048;


	  ArrayList<String> file_name_args = new ArrayList<String>();

    int arg_index = 0;
    while (arg_index < args.length) {
		  System.out.println ( "Arg[" + arg_index + "] = \"" + args[arg_index] + "\"" );
		  if (args[arg_index].startsWith("-") ) {
		    if (args[arg_index].equals("-?")) {
		      System.out.println ( "Command Line Arguments:" );
		      System.out.println ( "  -g # specifies \"golden\" image number" );
		      System.out.println ( "  -w # specifies windows size" );
          System.exit ( 0 );
		    } else if (args[arg_index].equals("-w")) {
		      arg_index++;
		      window_size = new Integer ( args[arg_index] );
		    } else if (args[arg_index].equals("-g")) {
		      arg_index++;
		      align_to = new Integer ( args[arg_index] );
		    } else {
		      System.out.println ( "Unrecognized option: " + args[arg_index] );
		    }
		  } else {
		    file_name_args.add ( args[arg_index] );
		  }
		  arg_index++;
    }

    System.out.println ( "Command line specified " + file_name_args.size() + " file name patterns." );

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

    System.out.println ( "Command line specified " + actual_file_names.size() + " actual files:" );
    for (int i=0; i<actual_file_names.size(); i++) {
      System.out.println ( "  " + actual_file_names.get(i) );
    }

    if ( actual_file_names.size() < 2 ) {
      System.out.println ( "Must specify at least 2 images to align" );
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
  	  System.out.println ( "Need more than 1 image to do alignments" );
  	  System.exit ( 1 );
  	}

    int golden_section = (num_image_files-1) / 2;
    if (align_to >= 0) {
      golden_section = align_to;
    }

    int num_before_golden = golden_section;
    int num_after_golden = num_image_files - (golden_section+1);

    System.out.println ( num_before_golden + " before, and " + num_after_golden + " after" );

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
      System.out.println ( "Align " + alignment_sequence[i][0] + " to " + alignment_sequence[i][1] );
    }

    for (alignment_index=0; alignment_index<alignment_sequence.length; alignment_index++) {

      int fixed_index = alignment_sequence[alignment_index][1];
      int align_index = alignment_sequence[alignment_index][0];

      String line;
      Runtime rt = Runtime.getRuntime();
      Process cmd_proc;

      BufferedOutputStream proc_in;
      BufferedInputStream proc_out;
      BufferedInputStream proc_err;

      int loop_signs_2x2[][] = { {1,1}, {1,-1}, {-1,-1}, {-1,1} };
      int loop_signs_3x3[][] = { {1,1}, {1,-1}, {-1,-1}, {-1,1}, {0,0}, {1,0}, {0,1}, {-1,0}, {0,-1} };

      int num_left;
      String stdout;
      String stderr;

      String parts[];

      File f;
      BufferedWriter bw;

      String AI1, AI2, AI3, AI4;

      try {

        //////////////////////////////////////
        // Step 0 - Run first swim
        //////////////////////////////////////

        line = "swim " + window_size;
        cmd_proc = rt.exec ( line );

        proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
        proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
        proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

        line = "unused -i 2 -k keep.JPG " + image_files[fixed_index] + " " + image_files[align_index] + "\n";

        proc_in.write ( line.getBytes() );
        proc_in.close();

        cmd_proc.waitFor();

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );
        stdout = "";
        while ( ( num_left = proc_out.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_out.read ( b );
          stdout += new String(b);
        }
        System.out.print ( stdout );

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );
        stderr = "";
        while ( ( num_left = proc_err.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_err.read ( b );
          stderr += new String(b);
        }
        System.out.print ( stderr );

        System.out.println ( "=================================================================================" );

        //////////////////////////////////////
        // Step 1a - Run second swim
        //////////////////////////////////////

        parts = stdout.split ( "[\\s]+" );
        for (int i=0; i<parts.length; i++) {
          System.out.println ( "Part " + i + " = " + parts[i] );
        }
        String tarx = "" + parts[2];
        String tary = "" + parts[3];
        String patx = "" + parts[5];
        String paty = "" + parts[6];

        line = "swim " + window_size;
        cmd_proc = rt.exec ( line );

        proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
        proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
        proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

        line = "";
        for (int loop_index=0; loop_index<loop_signs_2x2.length; loop_index++) {
          int x = loop_signs_2x2[loop_index][0];
          int y = loop_signs_2x2[loop_index][1];
          line += "unused -i 2 -x " + (2000*x) + " -y " + (2000*y) + " ";
          line += image_files[fixed_index] + " " + tarx + " " + tary + " ";
          line += image_files[align_index] + " " + patx + " " + paty + "\n";
        }
        System.out.println ( "Passing to swim:\n" + line );

        proc_in.write ( line.getBytes() );
        proc_in.close();

        cmd_proc.waitFor();

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );
        stdout = "";
        while ( ( num_left = proc_out.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_out.read ( b );
          stdout += new String(b);
        }
        System.out.print ( stdout );

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );
        stderr = "";
        while ( ( num_left = proc_err.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_err.read ( b );
          stderr += new String(b);
        }
        System.out.print ( stderr );

        System.out.println ( "=================================================================================" );

        //////////////////////////////////////
        // Step 1b - Run first mir
        //////////////////////////////////////

        parts = stdout.split ( "[\\s]+" );
        for (int i=0; i<parts.length; i++) {
          System.out.println ( "Part " + i + " = " + parts[i] );
        }

        line = "F " + image_files[align_index] + "\n";
        line += parts[2] + " " + parts[3] + " " + parts[5] + " " + parts[6] + "\n";
        line += parts[13] + " " + parts[14] + " " + parts[16] + " " + parts[17] + "\n";
        line += parts[24] + " " + parts[25] + " " + parts[27] + " " + parts[28] + "\n";
        line += parts[35] + " " + parts[36] + " " + parts[38] + " " + parts[39] + "\n";
        line += "RW iter1_mir_out.JPG\n";

        System.out.println ( "Passing to mir:\n" + line );

        f = new File ( System.getenv("PWD") + File.separator + "first.mir" );
        bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
        bw.write ( line, 0, line.length() );
        bw.close();

        line = "mir first.mir";
        cmd_proc = rt.exec ( line );

        proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
        proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
        proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

        //proc_in.write ( line.getBytes() );
        proc_in.close();

        cmd_proc.waitFor();

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );
        stdout = "";
        while ( ( num_left = proc_out.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_out.read ( b );
          stdout += new String(b);
        }
        System.out.print ( stdout );

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );
        stderr = "";
        while ( ( num_left = proc_err.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_err.read ( b );
          stderr += new String(b);
        }
        System.out.print ( stderr );

        System.out.println ( "=================================================================================" );

        //////////////////////////////////////
        // Step 2a - Run third swim
        //////////////////////////////////////

        parts = stdout.split ( "[\\s]+" );
        for (int i=0; i<parts.length; i++) {
          System.out.println ( "Part " + i + " = " + parts[i] );
        }
        AI1 = "" + parts[10];
        AI2 = "" + parts[11];
        AI3 = "" + parts[13];
        AI4 = "" + parts[14];

        line = "swim " + window_size;
        cmd_proc = rt.exec ( line );

        proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
        proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
        proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

        line = "";
        for (int loop_index=0; loop_index<loop_signs_2x2.length; loop_index++) {
          int x = loop_signs_2x2[loop_index][0];
          int y = loop_signs_2x2[loop_index][1];
          line += "unused -i 2 -x " + (2000*x) + " -y " + (2000*y) + " ";
          line += image_files[fixed_index] + " " + tarx + " " + tary + " ";
          line += image_files[align_index] + " " + patx + " " + paty + " ";
          line += AI1 + " " + AI2 + " " + AI3 + " " + AI4 + " " + "\n";
        }
        System.out.println ( "Passing to swim:\n" + line );

        proc_in.write ( line.getBytes() );
        proc_in.close();

        cmd_proc.waitFor();

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );
        stdout = "";
        while ( ( num_left = proc_out.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_out.read ( b );
          stdout += new String(b);
        }
        System.out.print ( stdout );

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );
        stderr = "";
        while ( ( num_left = proc_err.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_err.read ( b );
          stderr += new String(b);
        }
        System.out.print ( stderr );

        System.out.println ( "=================================================================================" );

        //////////////////////////////////////
        // Step 2b - Run second mir
        //////////////////////////////////////

        parts = stdout.split ( "[\\s]+" );
        for (int i=0; i<parts.length; i++) {
          System.out.println ( "Part " + i + " = " + parts[i] );
        }

        line = "F " + image_files[align_index] + "\n";
        line += parts[2] + " " + parts[3] + " " + parts[5] + " " + parts[6] + "\n";
        line += parts[13] + " " + parts[14] + " " + parts[16] + " " + parts[17] + "\n";
        line += parts[24] + " " + parts[25] + " " + parts[27] + " " + parts[28] + "\n";
        line += parts[35] + " " + parts[36] + " " + parts[38] + " " + parts[39] + "\n";
        line += "RW iter2_mir_out.JPG\n";

        System.out.println ( "Passing to mir:\n" + line );


        f = new File ( System.getenv("PWD") + File.separator + "second.mir" );
        bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
        bw.write ( line, 0, line.length() );
        bw.close();

        line = "mir second.mir";
        cmd_proc = rt.exec ( line );

        proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
        proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
        proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

        //proc_in.write ( line.getBytes() );
        proc_in.close();

        cmd_proc.waitFor();

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );
        stdout = "";
        while ( ( num_left = proc_out.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_out.read ( b );
          stdout += new String(b);
        }
        System.out.print ( stdout );

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );
        stderr = "";
        while ( ( num_left = proc_err.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_err.read ( b );
          stderr += new String(b);
        }
        System.out.print ( stderr );

        System.out.println ( "=================================================================================" );

        //////////////////////////////////////
        // Step 3a - Run fourth swim
        //////////////////////////////////////

        parts = stdout.split ( "[\\s]+" );
        for (int i=0; i<parts.length; i++) {
          System.out.println ( "Part " + i + " = " + parts[i] );
        }

        AI1 = "" + parts[10];
        AI2 = "" + parts[11];
        AI3 = "" + parts[13];
        AI4 = "" + parts[14];

        line = "swim " + window_size;
        cmd_proc = rt.exec ( line );

        proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
        proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
        proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

        line = "";
        for (int loop_index=0; loop_index<loop_signs_3x3.length; loop_index++) {
          int x = loop_signs_3x3[loop_index][0];
          int y = loop_signs_3x3[loop_index][1];
          line += "unused -i 2 -x " + (2000*x) + " -y " + (2000*y) + " ";
          line += image_files[fixed_index] + " " + tarx + " " + tary + " ";
          line += image_files[align_index] + " " + patx + " " + paty + " ";
          line += AI1 + " " + AI2 + " " + AI3 + " " + AI4 + " " + "\n";
        }
        System.out.println ( "Passing to swim:\n" + line );

        proc_in.write ( line.getBytes() );
        proc_in.close();

        cmd_proc.waitFor();

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );
        stdout = "";
        while ( ( num_left = proc_out.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_out.read ( b );
          stdout += new String(b);
        }
        System.out.print ( stdout );

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );
        stderr = "";
        while ( ( num_left = proc_err.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_err.read ( b );
          stderr += new String(b);
        }
        System.out.print ( stderr );

        System.out.println ( "=================================================================================" );

        //////////////////////////////////////
        // Step 3b - Run third mir
        //////////////////////////////////////

        parts = stdout.split ( "[\\s]+" );
        for (int i=0; i<parts.length; i++) {
          System.out.println ( "Part " + i + " = " + parts[i] );
        }

        line = "F " + image_files[align_index] + "\n";
        line += parts[2] + " " + parts[3] + " " + parts[5] + " " + parts[6] + "\n";
        line += parts[13] + " " + parts[14] + " " + parts[16] + " " + parts[17] + "\n";
        line += parts[24] + " " + parts[25] + " " + parts[27] + " " + parts[28] + "\n";
        line += parts[35] + " " + parts[36] + " " + parts[38] + " " + parts[39] + "\n";

        line += parts[46] + " " + parts[47] + " " + parts[49] + " " + parts[50] + "\n";

        line += parts[57] + " " + parts[58] + " " + parts[60] + " " + parts[61] + "\n";
        line += parts[68] + " " + parts[69] + " " + parts[71] + " " + parts[72] + "\n";
        line += parts[79] + " " + parts[80] + " " + parts[82] + " " + parts[83] + "\n";
        line += parts[90] + " " + parts[91] + " " + parts[93] + " " + parts[94] + "\n";
        // line += "RW iter3_mir_out.JPG\n";
        line += "RW " + "aligned_" + align_index + ".JPG\n";

        System.out.println ( "Passing to mir:\n" + line );



        // Change the name of the file in this slot to use the newly aligned image:
        image_files[align_index] = "aligned_" + align_index + ".JPG";




        f = new File ( System.getenv("PWD") + File.separator + "third.mir" );
        bw = new BufferedWriter ( new OutputStreamWriter ( new FileOutputStream ( f ) ) );
        bw.write ( line, 0, line.length() );
        bw.close();

        line = "mir third.mir";
        cmd_proc = rt.exec ( line );

        proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
        proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
        proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

        //proc_in.write ( line.getBytes() );
        proc_in.close();

        cmd_proc.waitFor();

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_out.available() + " bytes of output:" );
        stdout = "";
        while ( ( num_left = proc_out.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_out.read ( b );
          stdout += new String(b);
        }
        System.out.print ( stdout );

        System.out.println ( "=================================================================================" );

        System.out.println ( "Command finished with " + proc_err.available() + " bytes of error:" );
        stderr = "";
        while ( ( num_left = proc_err.available() ) > 0 ) {
          byte b[] = new byte[num_left];
          proc_err.read ( b );
          stderr += new String(b);
        }
        System.out.print ( stderr );

        System.out.println ( "=================================================================================" );

        //////////////////////////////////////
        // Step 3c - Best guess transform
        //////////////////////////////////////

        parts = stdout.split ( "[\\s]+" );
        for (int i=0; i<parts.length; i++) {
          System.out.println ( "Part " + i + " = " + parts[i] );
        }

        System.out.println ( "Final best guess transform:" );
        System.out.println ( "  " + patx + " " + paty + " " + parts[10] + " " + parts[11] + " " + parts[13] + " " + parts[14] );

      } catch ( Exception some_exception ) {
        System.out.println ( "Error: " + some_exception );
        System.out.println ( some_exception.getStackTrace() );
        some_exception.printStackTrace();
      }

    }

  }

}
