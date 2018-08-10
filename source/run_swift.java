import java.io.*;

public class run_swift {

  public static void main(String[] args) throws java.io.FileNotFoundException {

    try {

      int window_size = 2048;
      
      String image_files[] = {
        "Tile_r1-c1_LM9R5CA1series_049.tif",
        "Tile_r1-c1_LM9R5CA1series_050.tif",
        "Tile_r1-c1_LM9R5CA1series_051.tif"
      };

    	int num_image_files = image_files.length;

    	if (num_image_files < 2) {
    	  System.out.println ( "Need more than 1 image to do alignments" );
    	  System.exit ( 1 );
    	}

    	int golden_section = num_image_files / 2;
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

      //////////////////////////////////////
      // Step 0 - Run first swim
      //////////////////////////////////////

      line = "swim " + window_size;
      cmd_proc = rt.exec ( line );

      proc_in = new BufferedOutputStream ( cmd_proc.getOutputStream() );
      proc_out = new BufferedInputStream ( cmd_proc.getInputStream() );
      proc_err = new BufferedInputStream ( cmd_proc.getErrorStream() );

      line = "unused -i 2 -k keep.JPG " + image_files[golden_section] + " " + image_files[golden_section+1] + "\n";

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
        line += image_files[golden_section] + " " + tarx + " " + tary + " ";
        line += image_files[golden_section+1] + " " + patx + " " + paty + "\n";
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

      line = "F " + image_files[golden_section+1] + "\n";
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
        line += image_files[golden_section] + " " + tarx + " " + tary + " ";
        line += image_files[golden_section+1] + " " + patx + " " + paty + " ";
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

      line = "F " + image_files[golden_section+1] + "\n";
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
        line += image_files[golden_section] + " " + tarx + " " + tary + " ";
        line += image_files[golden_section+1] + " " + patx + " " + paty + " ";
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

      line = "F " + image_files[golden_section+1] + "\n";
      line += parts[2] + " " + parts[3] + " " + parts[5] + " " + parts[6] + "\n";
      line += parts[13] + " " + parts[14] + " " + parts[16] + " " + parts[17] + "\n";
      line += parts[24] + " " + parts[25] + " " + parts[27] + " " + parts[28] + "\n";
      line += parts[35] + " " + parts[36] + " " + parts[38] + " " + parts[39] + "\n";

      line += parts[46] + " " + parts[47] + " " + parts[49] + " " + parts[50] + "\n";

      line += parts[57] + " " + parts[58] + " " + parts[60] + " " + parts[61] + "\n";
      line += parts[68] + " " + parts[69] + " " + parts[71] + " " + parts[72] + "\n";
      line += parts[79] + " " + parts[80] + " " + parts[82] + " " + parts[83] + "\n";
      line += parts[90] + " " + parts[91] + " " + parts[93] + " " + parts[94] + "\n";
      line += "RW iter3_mir_out.JPG\n";

      System.out.println ( "Passing to mir:\n" + line );


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
    }

  }

}
