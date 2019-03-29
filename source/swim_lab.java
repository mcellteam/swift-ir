/* Image Alignment Tool based on SWiFT */

import java.io.*;
import java.awt.*;
import java.awt.event.*;
import java.awt.image.*;
import javax.imageio.ImageIO;
import javax.swing.*;
import javax.swing.filechooser.FileNameExtensionFilter;
import java.util.*;
import javax.swing.text.*;
import javax.swing.event.*;
// import java.net.*;


import java.nio.*;  // Needed for relativize function.


class ProjectFileChooser extends JFileChooser {
  ProjectFileChooser ( String path ) {
    super(path);
  }
  protected JDialog createDialog(Component parent) throws HeadlessException {
    JDialog dialog = super.createDialog(parent);
    dialog.setLocation(300, 200);
    dialog.setSize ( 1024, 768 );
    // dialog.setResizable(false);
    return dialog;
  }
}

class DestinationChooser extends JFileChooser {
  DestinationChooser ( String path ) {
    super(path);
  }
  protected JDialog createDialog(Component parent) throws HeadlessException {
    JDialog dialog = super.createDialog(parent);
    dialog.setLocation(300, 200);
    dialog.setSize ( 1024, 768 );
    // dialog.setResizable(false);
    return dialog;
  }
}

class ImageFileChooser extends JFileChooser {
  ImageFileChooser ( String path ) {
    super(path);
  }
  protected JDialog createDialog(Component parent) throws HeadlessException {
    JDialog dialog = super.createDialog(parent);
    dialog.setLocation(300, 200);
    dialog.setSize ( 1024, 768 );
    // dialog.setResizable(false);
    // dialog.add ( new JLabel ( "----- NEW -----" ) );
    return dialog;
  }
}

class alignment_settings {
  swim_lab_image_frame prev_frame=null;
  swim_lab_image_frame next_frame=null;
  int window_size=1024;
  int addx=500;
  int addy=500;
  int output_level=5;
  String[] alignment_values = null;
}

class swim_lab_image_frame {
  public File image_file_path=null;
  public boolean skip=false;
  public boolean valid=false;
  public BufferedImage image=null;

  alignment_settings prev_alignment=null;
  alignment_settings next_alignment=null;

  double[] affine_transform_from_prev=null;
  double[] affine_transform_from_start=null;

  swim_lab_image_frame ( File image_file_path, boolean load ) {
    this.image_file_path = image_file_path;
    if (load) {
      this.load_file();
    }
  }

  public void load_file () {
    this.valid = false;
    if ( image_file_path != null ) {
      try {
        this.image = ImageIO.read(image_file_path);
        if (this.image == null) {
          JOptionPane.showMessageDialog(null, "Can't open: " + this.image_file_path, "Image Error", JOptionPane.WARNING_MESSAGE);
        } else {
          this.valid = true;
        }
      } catch (OutOfMemoryError mem_err) {
        this.image = null;
        this.valid = false;
        JOptionPane.showMessageDialog(null, "Out of Memory for: " + this.image_file_path, "Memory Error", JOptionPane.WARNING_MESSAGE);
      } catch (Exception oe) {
        this.image = null;
        this.valid = false;
        JOptionPane.showMessageDialog(null, "File error for: " + this.image_file_path, "File Path Error", JOptionPane.WARNING_MESSAGE);
      }
    }
  }

  public void reload() {
    this.load_file();
  }

  public String toString() {
    return ( "" + this.image_file_path );
  }
}


class FileListDialog extends JDialog {
  private JTextArea textArea;
  private swim_lab parent_frame=null;
  public String dialog_text=null;

  public void set_text ( String text ) {
    this.dialog_text = text;
  }

  public FileListDialog(Frame par_frame, swim_lab parent) {
    super(par_frame, true);
    parent_frame = parent;

    setTitle("File List");

    textArea = new JTextArea(41, 80);  // Rows, Columns

    JScrollPane scroll_pane = new JScrollPane(textArea);

    setContentPane(scroll_pane);

    // Don't perform any default operations on closing
    setDefaultCloseOperation(DO_NOTHING_ON_CLOSE);

    // Set the custom closing code
    addWindowListener(new WindowAdapter() {
      public void windowClosing(WindowEvent we) {
        // Build the model from the current text
        System.out.println ( "Dialog closing with text:" );
        System.out.println ( textArea.getText() );
        setVisible ( false );
        parent_frame.repaint();
      }
    });

    addComponentListener(new ComponentAdapter() {
      public void componentShown(ComponentEvent ce) {
        if (dialog_text != null) {
          textArea.setText ( dialog_text );
        } else {
          // Build the text from the current model every time it's shown
          /*
          if (parent_frame != null) {
            // Get the list of files from the parent_frame
            if (parent_frame.frames != null) {
              textArea.setText ( "Frames:\n" );
              for (int fnum=0; fnum<parent_frame.frames.size(); fnum++) {
                textArea.append ( "File: " + parent_frame.frames.get(fnum).image_file_path + "\n" );
              }
            }
          }
          */
        }
        textArea.requestFocusInWindow();
      }
    });
  }
}


class AlignmentPanel extends JPanel {
  public swim_lab swift;
  AlignmentPanel (swim_lab swift) {
    this.swift = swift;
  }
	public void paint (Graphics g) {
	  int w = size().width;
	  int h = size().height;
    g.setColor ( new Color ( 60, 60, 60 ) );
    g.fillRect ( 0, 0, w, h );
	}
}

class RespTextField extends JTextField {
  public swim_lab swift;
  RespTextField(swim_lab swift) {
    super();
    this.swift = swift;
  }
  RespTextField(swim_lab swift, String s, int w) {
    super(s,w);
    this.swift = swift;
  }
  protected void processKeyEvent ( KeyEvent e ) {
    super.processKeyEvent(e);
    // swift.handle_key_event(e);
  }
}



class ControlPanel extends JPanel {
  public swim_lab swift;

  // Input/Output Header
  public JLabel project_label;
  public JLabel destination_label;
  public JTextField image_name;
  public JLabel image_label;
  public JLabel image_size;
  public JLabel image_bits;


  // Resizing
  public JTextField scale_factor;
  public JButton run_resize;


  // Alignment
  public RespTextField window_size;
  public RespTextField addx;
  public RespTextField addy;
  public RespTextField output_level;
  public JCheckBox skip;

  public JButton set_all;
  public JButton set_fwd;
  public JButton align_all;
  public JButton align_fwd;

  public RespTextField num_to_align;

  public JCheckBox pairwise;

/*
  JPanel make_resize_panel(swim_lab swift) {
    JPanel resize_panel = new JPanel();

    resize_panel.add ( new JLabel("Scale Factor:") );
    scale_factor = new JTextField("2",6);
    scale_factor.addKeyListener ( this.swift );
    scale_factor.addActionListener ( this.swift );
    scale_factor.setActionCommand ( "addx" );
    resize_panel.add ( scale_factor );

    resize_panel.add ( new JLabel("  ") );
    run_resize = new JButton("Resize");
    run_resize.addActionListener ( this.swift );
    run_resize.setActionCommand ( "run_resize" );
    resize_panel.add ( run_resize );

    return ( resize_panel );
  }

  JPanel make_alignment_panel(swim_lab swift) {
    JPanel alignment_panel = new JPanel();
    alignment_panel.setLayout ( new BorderLayout( 0, 20 ) );

    JPanel alignment_panel_top = new JPanel();
    JPanel alignment_panel_mid = new JPanel();
    JPanel alignment_panel_bot = new JPanel();

    alignment_panel_top.add ( new JLabel("  WW:") );
    window_size = new RespTextField(this.swift,"",8);
    window_size.addKeyListener ( this.swift );
    window_size.addActionListener ( this.swift );
    window_size.setActionCommand ( "window_size" );
    alignment_panel_top.add ( window_size );

    alignment_panel_top.add ( new JLabel("  Addx:") );
    addx = new RespTextField(this.swift,"",6);
    addx.addKeyListener ( this.swift );
    addx.addActionListener ( this.swift );
    addx.setActionCommand ( "addx" );
    alignment_panel_top.add ( addx );

    alignment_panel_top.add ( new JLabel("  Addy:") );
    addy = new RespTextField(this.swift,"",6);
    addy.addKeyListener ( this.swift );
    addy.addActionListener ( this.swift );
    addy.setActionCommand ( "addy" );
    alignment_panel_top.add ( addy );

    alignment_panel_top.add ( new JLabel("  Output Level:") );
    output_level = new RespTextField(this.swift,"",4);
    output_level.addKeyListener ( this.swift );
    output_level.addActionListener ( this.swift );
    output_level.setActionCommand ( "output_level" );
    alignment_panel_top.add ( output_level );

    alignment_panel_top.add ( new JLabel("  Skip:") );
    skip = new JCheckBox("",false);
    skip.addActionListener ( this.swift );
    skip.setActionCommand ( "skip" );
    alignment_panel_top.add ( skip );

    alignment_panel_mid.add ( new JLabel("  ") );
    set_all = new JButton("Set All");
    set_all.addActionListener ( this.swift );
    set_all.setActionCommand ( "set_all" );
    alignment_panel_mid.add ( set_all );

    alignment_panel_mid.add ( new JLabel("  ") );
    set_fwd = new JButton("Set Forward");
    set_fwd.addActionListener ( this.swift );
    set_fwd.setActionCommand ( "set_fwd" );
    alignment_panel_mid.add ( set_fwd );

    alignment_panel_bot.add ( new JLabel("  ") );
    align_all = new JButton("Align All");
    align_all.addActionListener ( this.swift );
    align_all.setActionCommand ( "align_all" );
    alignment_panel_bot.add ( align_all );

    alignment_panel_bot.add ( new JLabel("  ") );
    align_fwd = new JButton("Align Forward");
    align_fwd.addActionListener ( this.swift );
    align_fwd.setActionCommand ( "align_fwd" );
    alignment_panel_bot.add ( align_fwd );

    alignment_panel_bot.add ( new JLabel("  #") );
    num_to_align = new RespTextField(this.swift,"",6);
    num_to_align.addKeyListener ( this.swift );
    num_to_align.addActionListener ( this.swift );
    num_to_align.setActionCommand ( "num_to_align" );
    alignment_panel_bot.add ( num_to_align );

    alignment_panel_bot.add ( new JLabel("  Pairwise:") );
    pairwise = new JCheckBox("",false);
    pairwise.addActionListener ( this.swift );
    pairwise.setActionCommand ( "pairwise" );
    alignment_panel_bot.add ( pairwise );

    alignment_panel.add ( alignment_panel_top, BorderLayout.NORTH );
    alignment_panel.add ( alignment_panel_mid, BorderLayout.CENTER );
    alignment_panel.add ( alignment_panel_bot, BorderLayout.SOUTH );

    return ( alignment_panel );
  }
*/
  ControlPanel (swim_lab swift) {
    this.swift = swift;
/*
    this.setLayout ( new BorderLayout( 0, 20 ) );

    JPanel top_panel = new JPanel();

    top_panel.setLayout ( new BorderLayout( 0, 20 ) );

    project_label = new JLabel("Project File: "+swift.project_file);
    top_panel.add ( project_label, BorderLayout.NORTH );
    destination_label = new JLabel("Destination: "+swift.destination);
    top_panel.add ( destination_label, BorderLayout.CENTER );

    JPanel file_data_panel = new JPanel();
    file_data_panel.setLayout ( new FlowLayout( FlowLayout.LEFT ) );

    image_name = new JTextField("", 40);
    // image_name.setBounds ( 10, 10, 300, 20 );
    // add ( image_name );

    file_data_panel.add ( new JLabel("Name:") );
    image_label = new JLabel("");
    file_data_panel.add ( image_label );

    file_data_panel.add ( new JLabel("  Size:") );
    image_size = new JLabel("");
    file_data_panel.add ( image_size );

    file_data_panel.add ( new JLabel("  Depth:") );
    image_bits = new JLabel("");
    file_data_panel.add ( image_bits );

    top_panel.add ( file_data_panel, BorderLayout.SOUTH );

    add ( top_panel, BorderLayout.NORTH );


    JTabbedPane tabbed_pane = new JTabbedPane();
    
    JPanel alignment_panel = make_alignment_panel(swift);
    tabbed_pane.addTab ( "Resizing", make_resize_panel(swift) );
    tabbed_pane.addTab ( "Alignment", alignment_panel );

    add ( tabbed_pane, BorderLayout.CENTER );
  }

  public void update ( swim_lab swift ) {
    if (swift != null) {

      if (swift.frames != null) {
        if (swift.frames.size() > 0) {
          File image_file_path = swift.frames.get(swift.frame_index).image_file_path;
          this.image_name.setText ( image_file_path.getName() );
          swim_lab_image_frame frame = swift.frames.get(swift.frame_index);
          if (frame != null) {
            if (frame.image != null) {
              BufferedImage frame_image = swift.frames.get(swift.frame_index).image;
              this.image_size.setText ( ""+frame_image.getWidth()+"x"+frame_image.getHeight() );
              this.image_bits.setText ( ""+frame_image.getColorModel().getPixelSize() );
            }
            if (frame.next_alignment == null) {
              this.window_size.setText ( "" );
              this.addx.setText ( "" );
              this.addy.setText ( "" );
              this.output_level.setText ( "" );
              this.skip.setSelected ( false );
            } else {
              this.window_size.setText ( "" + frame.next_alignment.window_size );
              this.addx.setText ( "" + frame.next_alignment.addx );
              this.addy.setText ( "" + frame.next_alignment.addy );
              this.output_level.setText ( "" + frame.next_alignment.output_level );
              this.skip.setSelected ( frame.skip );
            }
          }
        } else {
          this.image_name.setText ( "" );
          this.image_size.setText ( "" );
          this.image_bits.setText ( "" );
          this.window_size.setText ( "" );
          this.addx.setText ( "" );
          this.addy.setText ( "" );
          this.output_level.setText ( "" );
          this.skip.setSelected ( false );
        }
      } else {
        this.image_name.setText ( "" );
        this.image_size.setText ( "" );
        this.image_bits.setText ( "" );
        this.window_size.setText ( "" );
        this.addx.setText ( "" );
        this.addy.setText ( "" );
        this.output_level.setText ( "" );
        this.skip.setSelected ( false );
      }
      this.image_label.setText ( this.image_name.getText() );

    }
*/
  }

}


class swim_lab_panel extends ZoomPanLib implements MouseListener {

  public BufferedImage frame_image = null;
  
  /*
  public swim_lab_panel ( BufferedImage frame_image ) {
    this.frame_image = frame_image;
  }*/

	public void paint_frame (Graphics g) {
	  Dimension win_s = getSize();
	  int win_w = win_s.width;
	  int win_h = win_s.height;
	  if (recalculate) {
	    if (frame_image != null) {
        set_scale_to_fit ( 0, frame_image.getWidth(), -frame_image.getHeight(), 0, win_w, win_h );
	      recalculate = false;
	    }
	  }

	  /*
    if (frames != null) {
      if (frames.size() > 0) {
        if (frame_index < 0) frame_index = 0;
        if (frame_index >= frames.size()) frame_index = frames.size()-1;
        swim_lab_image_frame f = frames.get(frame_index);
        if (f != null) {
          frame_image = f.image;
        }
      }
    } */

		g.setColor ( new Color ( 160, 60, 60 ) );  // Main window
	  g.fillRect ( 0, 0, win_w, win_h );

		g.setColor ( new Color ( 0, 0, 0 ) );  // Main window
	  g.drawRect ( 0, 0, win_w-1, win_h-1 );

		if (frame_image == null) {
		  System.out.println ( "Image is null" );
		  g.setColor ( new Color ( 160, 60, 60 ) );  // Main window
	    g.fillRect ( 0, 0, win_w, win_h );
		} else {
      /*
      System.out.println ( "Image is NOT null" );
      int img_w = frame_image.getWidth();
      int img_h = frame_image.getHeight();
      double img_wf = 200;
      double img_hf = 200;
      if (img_w >= img_h) {
        // Make the image wider to fit
        img_wf = img_w * img_wf / img_h;
      } else {
        // Make the height shorter to fit
        img_hf = img_h * img_hf / img_w;
      }
      int draw_x = x_to_pxi(-img_wf/2.0);
      int draw_y = y_to_pyi(-img_hf/2.0);
      int draw_w = x_to_pxi(img_wf/2.0) - draw_x;
      int draw_h = y_to_pyi(img_hf/2.0) - draw_y;
      g.drawImage ( frame_image, draw_x, draw_y, draw_w, draw_h, this );
      */


      // priority_println ( 50, "Image is NOT null" );
		  int img_w = frame_image.getWidth();
		  int img_h = frame_image.getHeight();

      double img_wf = img_w;
      double img_hf = img_h;

      int draw_x = x_to_pxi(0);
      int draw_y = y_to_pyi(0);
      int draw_w = x_to_pxi(img_wf) - draw_x;
      int draw_h = y_to_pyi(img_hf) - draw_y;

      g.drawImage ( frame_image, draw_x, draw_y-draw_h, draw_w, draw_h, this );
      //g.drawImage ( frame_image, (win_w-img_w)/2, (win_h-img_h)/2, img_w, img_h, this );

    }
	}


  //  MouseListener methods:


	Cursor current_cursor = null;
	Cursor b_cursor = null;
	int cursor_size = 33;

  public void mouseEntered ( MouseEvent e ) {
    super.mouseEntered(e);
  }

  public void mouseExited ( MouseEvent e ) {
    super.mouseExited(e);
  }

  public void mouseClicked ( MouseEvent e ) {
    super.mouseClicked(e);
  }

  public void mousePressed ( MouseEvent e ) {
    if (e.getButton() == 3) {
      recalculate = true;
      repaint();
    }
    super.mousePressed(e);
  }

  public void mouseReleased ( MouseEvent e ) {
    super.mouseReleased(e);
  }


}


class swim_lab_window extends ZoomPanLib implements ActionListener, MouseMotionListener, MouseListener, KeyListener {

  public String get_absolute_file_name ( String project_file_name, String other_file_name ) {
    // This function returns an absolute file name when "other_file" is relative
    if ( other_file_name.startsWith ( File.separator ) ) {
      // The other file is absolute already
      return ( other_file_name );
    } else {
      File project_file = new File ( project_file_name );
      File other_file = new File ( other_file_name );
      File full_project_file = project_file.getAbsoluteFile();
      return ( full_project_file.getParent() + File.separator + other_file_name );
    }
  }

  String get_relative_file_name ( String project_file_name, String other_file_name ) {
    // This function could be written without "relativize" to eliminate the need for importing nio.
    File project_file_path = new File(project_file_name).getParentFile();
    File other_file_path = new File(other_file_name);
    File other_file_parent = other_file_path.getParentFile();
    String relative_path = project_file_path.toPath().relativize(other_file_parent.toPath()).toString();
    if (relative_path.length() > 0) {
      relative_path = relative_path + File.separator + other_file_path.getName();
    } else {
      relative_path = other_file_path.getName();
    }
    // System.out.println ( "Project:  " + project_file_name );
    // System.out.println ( "Other:    " + other_file_name );
    // System.out.println ( "Relative: " + relative_path );
    return ( relative_path );
  }

  public int get_int_from_textfield ( JTextComponent c ) {
    String s = c.getText();
    if (s.length() > 0) {
      return ( Integer.parseInt ( s ) );
    } else {
      return ( 0 );
    }
  }

  public void handle_key_event(KeyEvent e) {
    if (frames != null) {
      if (frames.size() > 0) {
        swim_lab_image_frame frame = frames.get(frame_index);
        if (e.getComponent() == control_panel.window_size) {
          frame.next_alignment.window_size = get_int_from_textfield ( control_panel.window_size );
        } else if (e.getComponent() == control_panel.addx) {
          frame.next_alignment.addx = get_int_from_textfield ( control_panel.addx );
        } else if (e.getComponent() == control_panel.addy) {
          frame.next_alignment.addy = get_int_from_textfield ( control_panel.addy );
        } else if (e.getComponent() == control_panel.output_level) {
          frame.next_alignment.output_level = get_int_from_textfield ( control_panel.output_level );
        } else {
          // System.out.println ( "  --> ????" );
        }
      }
    }

  }

  JFrame parent_frame = null;
  AlignmentPanel alignment_panel = null;
  ControlPanel control_panel = null;

  File project_file=null;
  File destination=null;
  public File install_code_source=null;

	static int w=1200, h=1024;

  String current_directory = "";
  ImageFileChooser image_file_chooser = null;
  ProjectFileChooser project_file_chooser = null;
  DestinationChooser destination_chooser = null;

  FileListDialog file_list_dialog = null;

  int ref_image_w = 1000;
  int ref_image_h = 1000;


	public ArrayList<swim_lab_image_frame> frames = new ArrayList<swim_lab_image_frame>();  // Argument (if any) specifies initial capacity (default 10)
  public int frame_index = -1;

  public void set_install_location() {
    String install_path_string = getClass().getProtectionDomain().getCodeSource().getLocation().toString();
    if (install_path_string.startsWith ( "file:" ) ) {
      install_path_string = install_path_string.substring(5);
    }
    install_code_source = new File ( install_path_string );
  }

  public void repaint_panels () {
    alignment_panel.repaint();
    control_panel.repaint();
  }

  public void make_alignments() {
    if (frames != null) {
      if (frames.size() > 1) {
        for (int fnum=0; fnum<(frames.size()-1); fnum++) {
          swim_lab_image_frame prev = frames.get(fnum);
          swim_lab_image_frame next = frames.get(fnum+1);
          if ((prev.next_alignment == null) && (next.prev_alignment == null) ) {
            // Make a new one
            prev.next_alignment = new alignment_settings();
            next.prev_alignment = prev.next_alignment;
          } else if (prev.next_alignment == null) {
            // Attach the previous to the next
            prev.next_alignment = next.prev_alignment;
          } else if (next.prev_alignment == null) {
            // Attach the next to the previous
            next.prev_alignment = prev.next_alignment;
          }
          // Ensure that the shared alignment is properly linked
          prev.next_alignment.prev_frame = prev;
          prev.next_alignment.next_frame = next;
        }
      }
    }
  }

	public void paint_frame (Graphics g) {
	  Dimension win_s = getSize();
	  int win_w = win_s.width;
	  int win_h = win_s.height;
	  if (recalculate) {
      set_scale_to_fit ( 0, ref_image_w, -ref_image_h, 0, win_w, win_h );
	    recalculate = false;
	  }

    BufferedImage frame_image = null;

    if (frames != null) {
      if (frames.size() > 0) {
        if (frame_index < 0) frame_index = 0;
        if (frame_index >= frames.size()) frame_index = frames.size()-1;
        swim_lab_image_frame f = frames.get(frame_index);
        if (f != null) {
          frame_image = f.image;
        }
      }
    }

		g.setColor ( new Color ( 60, 60, 60 ) );  // Main window
	  g.fillRect ( 0, 0, win_w, win_h );

		if (frame_image == null) {
		  // System.out.println ( "Image is null" );
		  g.setColor ( new Color ( 60, 60, 60 ) );  // Main window
	    g.fillRect ( 0, 0, win_w, win_h );
		} else {
      /*
      // System.out.println ( "Image is NOT null" );
      int img_w = frame_image.getWidth();
      int img_h = frame_image.getHeight();
      double img_wf = 200;
      double img_hf = 200;
      if (img_w >= img_h) {
        // Make the image wider to fit
        img_wf = img_w * img_wf / img_h;
      } else {
        // Make the height shorter to fit
        img_hf = img_h * img_hf / img_w;
      }
      int draw_x = x_to_pxi(-img_wf/2.0);
      int draw_y = y_to_pyi(-img_hf/2.0);
      int draw_w = x_to_pxi(img_wf/2.0) - draw_x;
      int draw_h = y_to_pyi(img_hf/2.0) - draw_y;
      g.drawImage ( frame_image, draw_x, draw_y, draw_w, draw_h, this );
      */


      // priority_println ( 50, "Image is NOT null" );
		  int img_w = frame_image.getWidth();
		  int img_h = frame_image.getHeight();

      double img_wf = img_w;
      double img_hf = img_h;

      int draw_x = x_to_pxi(0);
      int draw_y = y_to_pyi(0);
      int draw_w = x_to_pxi(img_wf) - draw_x;
      int draw_h = y_to_pyi(img_hf) - draw_y;

      g.drawImage ( frame_image, draw_x, draw_y-draw_h, draw_w, draw_h, this );
      //g.drawImage ( frame_image, (win_w-img_w)/2, (win_h-img_h)/2, img_w, img_h, this );

    }
	}


  //  MouseListener methods:


	Cursor current_cursor = null;
	Cursor b_cursor = null;
	int cursor_size = 33;

  public void mouseEntered ( MouseEvent e ) {
    if ( b_cursor == null ) {
      Toolkit tk = Toolkit.getDefaultToolkit();
      Graphics2D cg = null;
      BufferedImage cursor_image = null;
      Polygon p = null;
      int h = cursor_size;
      int w = cursor_size;

      // Create the move cursor

      int cw2 = w/2;   // Cursor width / 2
      int ch2 = h/2;   // Cursor height / 2

      int clw = w/12;  // Arrow line width / 2
      int caw = w/6;   // Arrow head width / 2
      int cal = (int)(w/3.5);   // Arrow head length

      p = new Polygon();
      p.addPoint (       -cw2,           0 );  // Left Point

      p.addPoint ( -(cw2-cal),         caw );  // Left arrow lower outside corner
      p.addPoint ( -(cw2-cal),         clw );  // Left arrow lower inside corner

      p.addPoint (       -clw,         clw );  // Left/Bottom corner

      p.addPoint (       -clw,     ch2-cal );  // Bottom arrow left inside corner
      p.addPoint (       -caw,     ch2-cal );  // Bottom arrow left outside corner

      p.addPoint (          0,         ch2 );  // Bottom Point

      p.addPoint (        caw,     ch2-cal );  // Bottom arrow right outside corner
      p.addPoint (        clw,     ch2-cal );  // Bottom arrow right inside corner

      p.addPoint (        clw,         clw );  // Right/Bottom corner

      p.addPoint (  (cw2-cal),         clw );  // Right arrow lower inside corner
      p.addPoint (  (cw2-cal),         caw );  // Right arrow lower outside corner

      p.addPoint (        cw2,           0 );  // Right Point

      p.addPoint (  (cw2-cal),        -caw );  // Right arrow upper outside corner
      p.addPoint (  (cw2-cal),        -clw );  // Right arrow upper inside corner

      p.addPoint (        clw,        -clw );  // Right/Top corner

      p.addPoint (        clw,  -(ch2-cal) );  // Top arrow right inside corner
      p.addPoint (        caw,  -(ch2-cal) );  // Top arrow right outside corner

      p.addPoint (          0,        -ch2 );  // Top Point

      p.addPoint (       -caw,  -(ch2-cal) );  // Top arrow left outside corner
      p.addPoint (       -clw,  -(ch2-cal) );  // Top arrow left inside corner

      p.addPoint (       -clw,        -clw );  // Left/Top corner

      p.addPoint ( -(cw2-cal),        -clw );  // Left arrow upper inside corner
      p.addPoint ( -(cw2-cal),        -caw );  // Left arrow upper outside corner

      p.addPoint (       -cw2,           0 );  // Left Point


      p.translate ( w/2, h/2 );

      cursor_image = new BufferedImage(cursor_size,cursor_size,BufferedImage.TYPE_4BYTE_ABGR);
      cg = cursor_image.createGraphics();
      cg.setColor ( new Color(255,255,255) );
      cg.fillPolygon ( p );
      cg.setColor ( new Color(0,0,0) );
      cg.drawPolygon ( p );

      b_cursor = tk.createCustomCursor ( cursor_image, new Point(cursor_size/2,cursor_size/2), "Both" );

    }
    if (current_cursor == null) {
      current_cursor = b_cursor;
      // current_cursor = Cursor.getPredefinedCursor ( Cursor.MOVE_CURSOR );
    }
    setCursor ( current_cursor );
  }

  public void mouseExited ( MouseEvent e ) {
    // System.out.println ( "Mouse exited" );
    super.mouseExited(e);
  }

  public void mouseClicked ( MouseEvent e ) {
    // System.out.println ( "Mouse clicked" );
    super.mouseClicked(e);
  }

  public void mousePressed ( MouseEvent e ) {
    // System.out.println ( "Mouse pressed" );
    super.mousePressed(e);
  }

  public void mouseReleased ( MouseEvent e ) {
    // System.out.println ( "Mouse released" );
    super.mouseReleased(e);
  }


  // MouseMotionListener methods:

  public void mouseDragged ( MouseEvent e ) {
    // System.out.println ( "Mouse dragged" );
    super.mouseDragged(e);
  }

  public void mouseMoved ( MouseEvent e ) {
    // System.out.println ( "Mouse moved" );
    super.mouseMoved ( e );
  }

  public void set_title() {
    if (this.parent_frame != null) {
      String title = "No Frames";
      if (frames != null) {
        if ( (frames.size() > 0) && (frame_index >= 0) ) {
          title = "Section: " + (frame_index+1);
          File image_file_path = frames.get(frame_index).image_file_path;
          title += ", File: " + image_file_path.getName();
        }
      }
      this.parent_frame.setTitle ( title );
      System.out.println ( title );
    }
  }

  public void update_control_panel() {
    if (control_panel != null) {
      // control_panel.update ( this );
    }
  }


  public JTextField addx;
  public JTextField addy;
  public JTextField output_level;



  public void change_frame ( int delta ) {
    if (frames != null) {
      if (frames.size() > 0) {
        frame_index += delta;
        if (frame_index < 0) frame_index = 0;
        if (frame_index >= frames.size()) frame_index = frames.size()-1;
        set_title();
        repaint_panels();
      }
    }
    update_control_panel();
  }

  // MouseWheelListener methods:
  public void mouseWheelMoved ( MouseWheelEvent e ) {
    // System.out.println ( "Mouse wheel moved with shiftDown: " + e.isShiftDown() + " ... full event: " + e );
    /*
    if (e.isShiftDown()) System.out.println ( "Wheel Event with Shift" );
    if (e.isControlDown()) System.out.println ( "Wheel Event with Control" );
    if (e.isAltDown()) System.out.println ( "Wheel Event with Alt" );
    if (e.isMetaDown()) System.out.println ( "Wheel Event with Meta" );
    */
    if (frames == null) {
      super.mouseWheelMoved ( e );
    } else {
      //if (modify_mode == true) {
      if (!e.isShiftDown()) {
        if (frames != null) {
          if (frames.size() > 0) {
            change_frame ( -e.getWheelRotation() );
          }
        }
      } else {
        super.mouseWheelMoved ( e );
      }
    }
    repaint();
  }


  // KeyListener methods:

  public void keyTyped ( KeyEvent e ) {
    if (Character.toUpperCase(e.getKeyChar()) == ' ') {
      // Space bar toggles between drawing mode and move mode
    } else if (Character.toUpperCase(e.getKeyChar()) == 'P') {
    } else {
      // System.out.println ( "KeyEvent = " + e );
    }
    repaint();
  }
  public void keyPressed ( KeyEvent e ) {
    // System.out.println ( "Key Pressed, e = " + e );
    if ( (e.getKeyCode() == 33) || (e.getKeyCode() == 34) || (e.getKeyCode() == 38) || (e.getKeyCode() == 40) ) {
      // Figure out if there's anything to do
      if (frames != null) {
        if (frames.size() > 0) {
          int delta = 0;
          if ((e.getKeyCode() == 33) || (e.getKeyCode() == 38)) {
            System.out.println ( "Page Up with " + frames.size() + " frames" );
            delta = 1;
          } else if ((e.getKeyCode() == 34) || (e.getKeyCode() == 40)) {
            System.out.println ( "Page Down with " + frames.size() + " frames" );
            delta = -1;
          }
          change_frame ( delta );
          repaint();
        }
      }
    }
    //super.keyPressed ( e );
  }
  public void keyReleased ( KeyEvent e ) {
    // System.out.println ( "Key Released" );
    //super.keyReleased ( e );
  }


  JMenuItem new_project_menu_item = null;
  JMenuItem open_project_menu_item = null;
  JMenuItem save_project_menu_item = null;
  JMenuItem save_project_as_menu_item = null;

  JMenuItem set_destination_menu_item = null;

  JCheckBox load_files_on_import = null;

  JMenuItem import_images_menu_item = null;
  JMenuItem refresh_images_menu_item = null;
  JMenuItem center_image_menu_item = null;
  JMenuItem zoom_actual_menu_item = null;
  JMenuItem clear_all_images_menu_item = null;
  JMenuItem list_all_images_menu_item = null;
  JMenuItem list_align_shell_script = null;

  public void center_current_image() {
    if (frames != null) {
      if (frames.size() > 0) {
        if (frame_index >= 0) {
          if (frame_index < frames.size()) {
            BufferedImage frame_image = frames.get(frame_index).image;
            if (frame_image != null) {
              ref_image_w = frame_image.getWidth();
              ref_image_h = frame_image.getHeight();
              recalculate = true;
            }
          }
        }
      }
    }
  }

  public void write_project_file ( File project_file ) {
    try {
      PrintStream f = new PrintStream ( project_file );
      f.println ( "{" );
      f.println ( "  \"version\": 0.0," );
      f.println ( "  \"method\": \"SWiFT-IR\"," );
      f.println ( "  \"data\": {" );
      f.println ( "    \"source_path\": \"\"," );
      f.println ( "    \"destination_path\": \"" + get_relative_file_name ( project_file.getPath(), destination.toString() ) + "\"," );
      if (control_panel.pairwise.isSelected()) {
        f.println ( "    \"pairwise_alignment\": " + "true" + "," );
      } else {
        f.println ( "    \"pairwise_alignment\": " + "false" + "," );
      }
      f.println ( "    \"defaults\": {" );
      f.println ( "      \"align_to_next_pars\": {" );
      f.println ( "        \"window_size\": 1024," );
      f.println ( "        \"addx\": 800," );
      f.println ( "        \"addy\": 800," );
      f.println ( "        \"output_level\": 0" );
      f.println ( "      }" );
      f.println ( "    }," );

      f.println ( "    \"imagestack\": [" );

      for (int i=0; i<this.frames.size(); i++) {
        swim_lab_image_frame frame = this.frames.get(i);

        f.println ( "      { " );
        f.println ( "        \"skip\": " + frame.skip + "," );  // JSON and Java both use lower case for true and false
        f.print   ( "        \"filename\": \"" + get_relative_file_name ( project_file.getPath(), frame.toString() ) + "\"" );
        if (frame.next_alignment == null) {
          f.println ( "" );
        } else {
          f.println ( "," );
          alignment_settings settings = frame.next_alignment;
          f.println ( "        \"align_to_next_pars\": {" );
          f.println ( "          \"window_size\": " + settings.window_size + "," );
          f.println ( "          \"addx\": " + settings.addx + "," );
          f.println ( "          \"addy\": " + settings.addy + "," );
          f.println ( "          \"output_level\": " + settings.output_level + "" );
          //f.println ( "          \"affine_fwd\": null," );
          //f.println ( "          \"affine_rev\": null," );
          //f.println ( "          \"mir_fwd\": null," );
          //f.println ( "          \"mir_rev\": null" );
          f.println ( "        }" );
        }
        f.print   ( "      }" );
        if (i < this.frames.size()-1) {
          f.println ( "," );
        } else {
          f.println ( "" );
        }
      }

      f.println ( "    ]" );
      f.println ( "  }" );
      f.println ( "}" );
      f.close();
    } catch ( FileNotFoundException fnfe ) {
    }
  }

  double[] concat_affine ( double[] a, double[] d ) {
    double[] r = new double[6];
    r[0] = (a[0] * d[0]) + (a[1] * d[3]);
    r[1] = (a[0] * d[1]) + (a[1] * d[4]);
    r[2] = (a[0] * d[2]) + (a[1] * d[5]) + a[2];
    r[3] = (a[3] * d[0]) + (a[4] * d[3]);
    r[4] = (a[3] * d[1]) + (a[4] * d[4]);
    r[5] = (a[3] * d[2]) + (a[4] * d[5]) + a[5];
    return ( r );
  }

  double[] propagate_affine ( int first, int last ) {
    double[] cumulative = { 1.0, 0.0, 0.0, 0.0, 1.0, 0.0 };
    swim_lab_image_frame frame;
    for (int i=first; i<=last; i++) {
      frame = frames.get(i);
      if (frame != null) {
        //if (!frame.skip) {
          if (frame.affine_transform_from_prev != null) {
            cumulative = concat_affine ( cumulative, frame.affine_transform_from_prev );
          }
        //}
      }
    }
    return ( cumulative );
  }

  // ActionPerformed methods (mostly menu responses):

	public void actionPerformed(ActionEvent e) {
    Object action_source = e.getSource();

		String cmd = e.getActionCommand();
		System.out.println ( "ActionPerformed got \"" + cmd + "\" from " + action_source );

		if (cmd.equalsIgnoreCase("Print")) {
		  System.out.println ( "Images:" );
	    for (int i=0; i<this.frames.size(); i++) {
        System.out.println ( "  " + this.frames.get(i) );
      }
    } else if ( action_source == refresh_images_menu_item ) {
      System.out.println ( "Reloading all images:" );
      // Reload the visible frame first for faster response
      if (frame_index >= 0) {
        System.out.println ( "  Reloading image " + frames.get(frame_index).image_file_path.getName() );
        this.frames.get(frame_index).reload();
      }
      // Reload all the other frames
	    for (int i=0; i<this.frames.size(); i++) {
	      if (i != frame_index) {
          System.out.println ( "  Reloading image " + frames.get(i).image_file_path.getName() );
          this.frames.get(i).reload();
        }
      }
      update_control_panel();
      repaint();
      repaint_panels();
		  set_title();
    } else if ( action_source == import_images_menu_item ) {
		  image_file_chooser.setMultiSelectionEnabled(true);
		  image_file_chooser.resetChoosableFileFilters();
      FileNameExtensionFilter filter = new FileNameExtensionFilter("Image Files", "jpg", "jpeg", "gif", "png", "tif", "tiff");
      image_file_chooser.setFileFilter(filter);
      image_file_chooser.setSelectedFiles(new File[0]); // This is a failed attempt to clear the files in the text line list
		  int returnVal = image_file_chooser.showDialog(this, "Import Selected Images");
		  if ( returnVal == JFileChooser.APPROVE_OPTION ) {
        boolean load_on_import = load_files_on_import.isSelected();
        System.out.println ( "\nImporting with Load on Import = " + load_on_import );

		    File selected_files[] = image_file_chooser.getSelectedFiles();
		    if (selected_files.length > 0) {
		      // Use the current size as the new index (if size is 0, then the new index will be 0 which points to the first)
		      int num_previous = this.frames.size();
		      int new_frame_index = this.frames.size();
		      for (int i=0; i<selected_files.length; i++) {
            System.out.println ( "You chose this file: " + selected_files[i] );
            this.frames.add ( new swim_lab_image_frame ( selected_files[i], load_on_import ) );
		      }
          make_alignments();
		      // Set the frame index to the first file just added
		      if (new_frame_index >= this.frames.size()) {
		        new_frame_index = this.frames.size() - 1;
		      }
		      frame_index = new_frame_index;
		      if ( (frame_index >= 0) && (num_previous <= 0) ) {
		        // Automatically center if there were no previous images
		        center_current_image();
		      }
          update_control_panel();
	        repaint();
          repaint_panels();
		    }
		  }
		  set_title();
    } else if ( action_source == set_destination_menu_item ) {
		  destination_chooser.setMultiSelectionEnabled(false);
		  destination_chooser.setFileSelectionMode ( JFileChooser.DIRECTORIES_ONLY );
		  if (destination != null) {
		    // Set the default to the current destination
		    destination_chooser.setCurrentDirectory ( destination );
		  }
		  int returnVal = destination_chooser.showDialog(this, "Choose Destination");
		  if ( returnVal == JFileChooser.APPROVE_OPTION ) {
		    destination = destination_chooser.getSelectedFile();
	      System.out.println ( "Destination = " + destination );
        control_panel.destination_label.setText ( "Destination: "+destination );
        update_control_panel();
        repaint();
        repaint_panels();
		  }
		  set_title();
    } else if ( action_source == open_project_menu_item ) {
		  project_file_chooser.setMultiSelectionEnabled(false);
		  project_file_chooser.resetChoosableFileFilters();
      FileNameExtensionFilter filter = new FileNameExtensionFilter("JSON Project", "json");
      project_file_chooser.setFileFilter(filter);
      project_file_chooser.setSelectedFiles(new File[0]); // This is a failed attempt to clear the files in the text line list
		  int returnVal = project_file_chooser.showDialog(this, "Open Project");
		  if ( returnVal == JFileChooser.APPROVE_OPTION ) {
		    project_file = project_file_chooser.getSelectedFile();
	      System.out.println ( "Project File = " + project_file );
        control_panel.project_label.setText ( "Project File: "+project_file );
        try {
          BufferedInputStream f = new BufferedInputStream ( new FileInputStream(project_file) );
          String text = run_swift.read_string_from(f);
          json_parser parser = new json_parser ( text );
          Object o = parser.generate_object_tree();
          System.out.println ( "\n\nObject = " + o );
          HashMap<String,Object> obj_dict = (HashMap<String,Object>)o;
          System.out.println ( "\n\nHashMap = " + obj_dict );
          System.out.println ( "\n\n" );

          if (obj_dict.containsKey("version")) {
            if ( ((Double)(obj_dict.get("version")) == 0.0) &&
                 (obj_dict.get("method") != null) &&
                 (obj_dict.get("data") != null) ) {
              // Assume that everything is fine at this point
              HashMap<String,Object> data = (HashMap<String,Object>)(obj_dict.get("data"));
              destination = new File ( get_absolute_file_name ( project_file.getAbsolutePath(), (String)(data.get("destination_path")) ) );
              control_panel.destination_label.setText ( "Destination: "+destination );

              if (data.containsKey("pairwise_alignment")) {
                control_panel.pairwise.setSelected ( (Boolean)(data.get("pairwise_alignment")) );
              }

              ArrayList<Object> image_stack = (ArrayList<Object>)(data.get("imagestack"));

              frames = new ArrayList<swim_lab_image_frame>();
              actual_file_names = new ArrayList<String>();
              frame_index = -1;

              for (int i=0; i<image_stack.size(); i++) {
                HashMap<String,Object> stack_image = (HashMap<String,Object>)(image_stack.get(i));
                System.out.println ( "stack_image keys = " + stack_image.keySet() );
                String stack_image_file_name = get_absolute_file_name ( project_file.getAbsolutePath(), (String)(stack_image.get("filename")) );
                System.out.println ( "stack_image_file_name = " + stack_image_file_name );
                actual_file_names.add ( stack_image_file_name );

                System.out.println ( "Adding file " + actual_file_names.get(i) + " to stack" );
                swim_lab_image_frame new_frame = new swim_lab_image_frame ( new File (actual_file_names.get(i)), load_images );
                if (stack_image.containsKey("skip")) {
                  new_frame.skip = (Boolean)(stack_image.get("skip"));
                }
                frames.add ( new_frame );  /// Note: use i<=n to only load first n images
                frame_index = 0; // set to the first if any frames are loaded
              }
              make_alignments();

              // Update the alignments based on the JSON input

              for (int i=0; i<image_stack.size(); i++) {
                HashMap<String,Object> stack_image = (HashMap<String,Object>)(image_stack.get(i));
                if (stack_image.containsKey ("align_to_next_pars")) {
                  HashMap<String,Object> alignment_pars = (HashMap<String,Object>)(stack_image.get("align_to_next_pars"));
                  // System.out.println ( "alignment_pars keys = " + alignment_pars.keySet() );
                  System.out.println ( "alignment_pars = " + alignment_pars );
                  swim_lab_image_frame frame = frames.get(i);
                  alignment_settings settings = frame.next_alignment;
                  if (settings != null) {
                    settings.window_size = (Integer)(alignment_pars.get("window_size"));
                    settings.addx = (Integer)(alignment_pars.get("addx"));
                    settings.addy = (Integer)(alignment_pars.get("addy"));
                    settings.output_level = (Integer)(alignment_pars.get("output_level"));
                  }
                }
              }

            } else {
              System.out.println ( "Project file version does not match program version or other problem" );
            }
          } else {
            System.out.println ( "Project file has no version" );
          }
        } catch ( Exception open_exception ) {
          System.out.println ( "Unable to open or read from " + project_file );
          System.out.println ( "  Exception: " + open_exception );
        }
        update_control_panel();
        repaint();
        repaint_panels();
		  }
		  set_title();
    } else if ( action_source == save_project_as_menu_item ) {
		  project_file_chooser.setMultiSelectionEnabled(false);
		  project_file_chooser.resetChoosableFileFilters();
      FileNameExtensionFilter filter = new FileNameExtensionFilter("JSON Project", "json");
      project_file_chooser.setFileFilter(filter);
      project_file_chooser.setSelectedFiles(new File[0]); // This is a failed attempt to clear the files in the text line list
		  int returnVal = project_file_chooser.showDialog(this, "Save Project");
		  if ( returnVal == JFileChooser.APPROVE_OPTION ) {
		    project_file = project_file_chooser.getSelectedFile();
	      System.out.println ( "Project File = " + project_file );
        control_panel.project_label.setText ( "Project File: "+project_file );
        write_project_file ( project_file );

        /*
        update_control_panel();
        repaint();
        repaint_panels();
        */
		  }
		  set_title();
    } else if ( action_source == save_project_menu_item ) {
      System.out.println ( "Saving to Project File = " + project_file );
      write_project_file ( project_file );
    } else if ( action_source == center_image_menu_item ) {
      System.out.println ( "Center image" );
      center_current_image();
      repaint();
		  set_title();
    } else if ( action_source == zoom_actual_menu_item ) {
      System.out.println ( "Setting zoom and scale to 1.0" );
      zoom_exp = 0;
	    scale = 1.0;
	    scroll_wheel_position = 0;
	    mx = 1.0;
	    my = 1.0;
      recalculate = false;
      update_control_panel();
      repaint();
		  set_title();
    } else if ( action_source == clear_all_images_menu_item ) {
      this.frames = new ArrayList<swim_lab_image_frame>();
      this.frame_index = -1;
      repaint();
      update_control_panel();
      repaint_panels();
		  set_title();
    } else if ( action_source == list_all_images_menu_item ) {
      if (file_list_dialog != null) {
        file_list_dialog.setTitle ( "Original Image Files" );
        file_list_dialog.setVisible(true);
      }
      //repaint();
		  //set_title();
    } else if ( action_source == list_align_shell_script ) {
      if (file_list_dialog != null) {
        file_list_dialog.setVisible(false);
        file_list_dialog.setTitle ( "Alignment Script" );
        String text = "";
        if (frames != null) {
          if (frames.size() > 1) {
            String fname = frames.get(0).image_file_path.getName();
            String bars = "==========";

            text += "mkdir -p mir_only_output\n";
            text += "\n";
            text += "echo " + bars + " Using mir to copy " + fname + " " + bars + "\n";
            text += "\n";
            text += "./mir <<'EOF'\n";
            text += "F " + fname + "\n";
            text += "A 1 0 0 0 1 0\n";
            text += "R\n";
            text += "W mir_only_output/" + fname + "\n";
            text += "EOF\n";

	          for (int i=1; i<frames.size(); i++) {
	            swim_lab_image_frame prev_frame = frames.get(i-1);
	            swim_lab_image_frame this_frame = frames.get(i);
              fname = this_frame.image_file_path.getName();

              text += "\n";
              text += "echo " + bars + " Using mir to align " + fname + " " + bars + "\n";
              text += "\n";
              // Display all of the values with the echo command for debugging
              text += "echo ";
              for (int j=1; j<7; j++) {
                text += " " + prev_frame.next_alignment.alignment_values[j];
              }
              text += "\necho ";
              for (int j=7; j<13; j++) {
                text += " " + prev_frame.next_alignment.alignment_values[j];
              }
              text += "\necho ";
              for (int j=13; j<19; j++) {
                text += " " + prev_frame.next_alignment.alignment_values[j];
              }
              text += "\n";
              text += "\n";
              text += "./mir <<'EOF'\n";
              text += "F " + fname + "\n";
              text += "A";
              // Extract the values for the forward matrix to put in the "A" command
              for (int j=7; j<13; j++) {
                text += " " + prev_frame.next_alignment.alignment_values[j];
              }
              text += "\n";
              text += "R\n";
              text += "W mir_only_output/" + fname + "\n";
              text += "EOF\n";
            }
            text += "\n";
            text += "echo " + bars + " Done aligning images " + bars + "\n";
          }
        }
        file_list_dialog.set_text ( text );
        file_list_dialog.setVisible(true);
      }
      //repaint();
		  //set_title();
		} else if (cmd.equalsIgnoreCase("window_size")) {
		  JTextField txt = (JTextField)action_source;
			System.out.println ( "Got a window_size change with " + txt.getText() );
      if (frames != null) {
        if (frames.size() > 1) {
          swim_lab_image_frame frame = frames.get(frame_index);
          if (frame.next_alignment != null) {
            frame.next_alignment.window_size = get_int_from_textfield ( txt );
          }
        }
      }
		} else if (cmd.equalsIgnoreCase("addx")) {
		  JTextField txt = (JTextField)action_source;
			System.out.println ( "Got an addx change with " + txt.getText() );
      if (frames != null) {
        if (frames.size() > 1) {
          swim_lab_image_frame frame = frames.get(frame_index);
          if (frame.next_alignment != null) {
            frame.next_alignment.addx = get_int_from_textfield ( txt );
          }
        }
      }
		} else if (cmd.equalsIgnoreCase("addy")) {
		  JTextField txt = (JTextField)action_source;
			System.out.println ( "Got an addy change with " + txt.getText() );
      if (frames != null) {
        if (frames.size() > 1) {
          swim_lab_image_frame frame = frames.get(frame_index);
          if (frame.next_alignment != null) {
            frame.next_alignment.addy = get_int_from_textfield ( txt );
          }
        }
      }
		} else if (cmd.equalsIgnoreCase("output_level")) {
		  JTextField txt = (JTextField)action_source;
			System.out.println ( "Got an output_level change with " + txt.getText() );
      if (frames != null) {
        if (frames.size() > 1) {
          swim_lab_image_frame frame = frames.get(frame_index);
          if (frame.next_alignment != null) {
            frame.next_alignment.output_level = get_int_from_textfield ( txt );
          }
        }
      }
		} else if (cmd.equalsIgnoreCase("skip")) {
			JCheckBox box = (JCheckBox)action_source;
			System.out.println ( "\n\nGot a skip change with Selected = " + box.isSelected() );
      if (frames != null) {
        if (frames.size() > 1) {
          swim_lab_image_frame frame = frames.get(frame_index);
          if (frame.next_alignment != null) {
            frame.skip = box.isSelected();
          }
        }
      }
		} else if ( (cmd.equalsIgnoreCase("set_all")) || (cmd.equalsIgnoreCase("set_fwd")) ) {
			System.out.println ( "\n\nGot a set_all / set_fwd command" );
      if (frames != null) {
        int start = 0;
        if (cmd.equalsIgnoreCase("set_fwd")) {
          start = frame_index;
        }
        // Copy these values to all frames
	      for (int i=start; i<this.frames.size(); i++) {
	        swim_lab_image_frame frame = frames.get(i);
	        frame.skip = control_panel.skip.isSelected();
          if (frame.next_alignment != null) {
            frame.next_alignment.window_size = get_int_from_textfield ( control_panel.window_size );
            frame.next_alignment.addx = get_int_from_textfield ( control_panel.addx );
            frame.next_alignment.addy = get_int_from_textfield ( control_panel.addy );
            frame.next_alignment.output_level = get_int_from_textfield ( control_panel.output_level );
          }
        }
      }
		} else if (cmd.equalsIgnoreCase("run_resize")) {
			int scale_factor = get_int_from_textfield ( control_panel.scale_factor );
			int output_level = get_int_from_textfield ( control_panel.output_level );
			System.out.println ( "\n\nGot a run_resize command with scale factor of " + scale_factor );
      if (frames != null) {
        System.out.println ( "Scaling with destination = \"" + destination + "\"" );
        if (destination == null) {
          System.out.println ( "Error: Destination must be set." );
        } else {
          String prefix = "";
          if (destination != null) {
            if (destination.toString().length() > 0) {
              prefix = destination + File.separator;
            }
          }
          Runtime rt = Runtime.getRuntime();
	        for (int i=0; i<this.frames.size(); i++) {
	          swim_lab_image_frame frame = frames.get(i);
	          if (frame.skip) {
	            // Omit this frame
	          } else {
              run_swift.scale_file_with_iscale ( rt, frame.image_file_path.getAbsolutePath(), prefix, scale_factor, output_level );
            }
          }
          System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
          System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
          System.out.println ( "Resizing completed" );
          System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
          System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
        }
      }
		} else if ( (cmd.equalsIgnoreCase("align_all")) || (cmd.equalsIgnoreCase("align_fwd")) ) {
			System.out.println ( "\n\nGot an align_all or align_fwd command with dest=" + destination );

      if ( (destination == null) || (destination.toString().length() <= 0) ) {  // This depends on Java's short-circuit || operator to not throw an exception

        // Keep from overwriting existing files unless explicitly requested
        System.out.println ( "Please set an explicit destination before performing an alignment." );
        JOptionPane.showMessageDialog(this, "Please set an explicit destination before performing an alignment.", "Note", JOptionPane.ERROR_MESSAGE);

      } else {

        boolean pairwise = control_panel.pairwise.isSelected();
        System.out.println ( "Pairwise is " + pairwise );

        if (frames != null) {

          int num_to_align = 1 + get_int_from_textfield ( control_panel.num_to_align );

          int start = 0;
          int end = this.frames.size();

          if (cmd.equalsIgnoreCase("align_fwd")) {
            start = frame_index;
            end = frame_index + num_to_align;
          }

          if ( (end <= 0) || (end > this.frames.size()) ) {
            end = this.frames.size();
          }

          System.out.println ( "Running an alignment with destination = \"" + destination + "\"" );
          String prefix = "";
          if (destination != null) {
            if (destination.toString().length() > 0) {
              prefix = destination + File.separator;
            }
          }
          Runtime rt = Runtime.getRuntime();
          int fixed_frame_num = start-1;
          boolean first_pass = true;
          if (start > 0) {
            first_pass = false;
          }
	        for (int i=start; i<end; i++) {
	          System.out.println ( "Working on frame " + i );
	          swim_lab_image_frame align_frame = frames.get(i);
	          if (align_frame.skip) {
	            // Omit this frame
	          } else {
	            if (fixed_frame_num < start) {
	              // This is the first non-skipped frame, so use it as the fixed frame
	              fixed_frame_num = i;
	            } else {
	              // There is a valid fixed frame and this (to be aligned) frame
                swim_lab_image_frame fixed_frame = frames.get(fixed_frame_num);
                if (fixed_frame.next_alignment != null) {
                  // The fixed frame defines an alignment to the next frame
                  String fixed_image_name;
                  // Use the previously aligned image name
                  // fixed_image_name = prefix + "aligned_" + String.format("%03d",(fixed_frame_num)) + ".JPG";
                  if (pairwise) {
                    fixed_image_name = (new File(fixed_frame.image_file_path.toString())).getAbsolutePath();
                    //fixed_image_name = prefix + fixed_frame.image_file_path.getName();
                  } else {
                    fixed_image_name = prefix + fixed_frame.image_file_path.getName();
                  }
                  if (first_pass) {
                    // This is the first alignment, so copy the original image
                    if (pairwise) {
                      run_swift.copy_file_by_name ( rt, fixed_frame.image_file_path.toString(), prefix + fixed_frame.image_file_path.getName(), fixed_frame.next_alignment.output_level );
                    } else {
                      run_swift.copy_file_by_name ( rt, fixed_frame.image_file_path.toString(), fixed_image_name, fixed_frame.next_alignment.output_level );
                    }
                    first_pass = false;
                  }
                  String results[] = run_swift.align_files_by_name (
                        rt,
                        (new File(fixed_image_name)).getAbsolutePath(),
                        (new File(align_frame.image_file_path.toString())).getAbsolutePath(),
                        prefix + (new File(align_frame.image_file_path.toString())).getName(),
                        fixed_frame.next_alignment.window_size,
                        fixed_frame.next_alignment.addx,
                        fixed_frame.next_alignment.addy,
                        fixed_frame.next_alignment.output_level );

                  fixed_frame.next_alignment.alignment_values = results;

                  if (results != null) {
                    System.out.println ( "Results from run_swift.align_files_by_name: " + results[0] );
                    if (results.length == 19) {
                      // This is 3 transform matrix format (each is 2x3)
                      for (int m=0; m<3; m++) {
                        for (int r=0; r<2; r++) {
                          for (int c=0; c<3; c++) {
                            System.out.print ( "  " + results[(m*6)+(r*3)+c+1] );
                          }
                          System.out.println();
                        }
                        System.out.println();
                      }
                      if (pairwise) {
                        if (align_frame.affine_transform_from_prev == null) {
                          align_frame.affine_transform_from_prev = new double[6];
                        }
                        try {
                          System.out.println ( "*************************************************************************" );
                          System.out.println ( "Affine transform from " + (i-1) + " to " + i + ":" );
                          System.out.print ( "    " );
                          for (int m=7; m<13; m++) {
                            align_frame.affine_transform_from_prev[m-7] = Double.parseDouble(results[m]);
                            // System.out.print ( results[m] + " " );
                            System.out.print ( "" + align_frame.affine_transform_from_prev[m-7] + " " );
                          }
                          System.out.println ();

                          double[] propagated = propagate_affine ( start, i );

                          System.out.println ( "Affine transform from " + start + " to " + i + ":" );
                          System.out.print ( "    " );
                          for (int m=0; m<6; m++) {
                            System.out.print ( "" + propagated[m] + " " );
                          }
                          System.out.println ();

                          System.out.println ( "*************************************************************************" );

                          run_swift.transform_file_by_name (
                                rt,
                                (new File(align_frame.image_file_path.toString())).getAbsolutePath(),
                                prefix + (new File(align_frame.image_file_path.toString())).getName(),
                                propagated, // fixed_frame.affine_transform_from_prev,
                                fixed_frame.next_alignment.output_level );
                        } catch (Exception fmtex) {
                          System.out.println ( "\n\n Exception: " + fmtex );
                          align_frame.affine_transform_from_prev = null;  // Signal that it couldn't be done.
                        }
                      }
                    } else {
                      // This is some other format
                      for (int r=1; r<results.length; r++) {
                        System.out.println ( "    " + results[r] );
                      }
                    }
                  }
                  fixed_frame_num = i;
                }
              }
            }
          }
          System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
          System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
          System.out.println ( "Alignment completed" );
          if (pairwise) {
	          for (int i=0; i<this.frames.size(); i++) {
	            swim_lab_image_frame frame = frames.get(i);
	            if (frame.affine_transform_from_prev == null) {
	              System.out.println ( "  Pairwise Affine Transform " + i + " to " + (i+1) + " is null" );
	            } else {
	              System.out.print ( "  Pairwise Affine Transform " + i + " to " + (i+1) + " is [ " );
	              for (int j=0; j<frame.affine_transform_from_prev.length; j++) {
	                System.out.print ( "" + frame.affine_transform_from_prev[j] + " " );
	              }
	              System.out.println ( " ]" );
	            }
            }
          }
          System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
          System.out.println ( "|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||" );
        }
      }
		} else if (cmd.equalsIgnoreCase("Exit")) {
			System.exit ( 0 );
		}
  }


	public static ArrayList<String> actual_file_names = new ArrayList<String>();

  static boolean load_images = true;
/*
	public static void main ( String[] args ) {

    System.out.println ( "Translation of 15: " + run_swift.translate_exit ( 128+15 ) );

	  ArrayList<String> file_name_args = new ArrayList<String>();

    int arg_index = 0;
    while (arg_index < args.length) {
		  System.out.println ( "Arg[" + arg_index + "] = \"" + args[arg_index] + "\"" );
		  if (args[arg_index].startsWith("-") ) {
		    if (args[arg_index].equals("-l")) {
		      System.out.println ( "Loading images" );
		      load_images = true;
		    } else if (args[arg_index].equals("-nl")) {
		      System.out.println ( "Not loading images" );
		      load_images = false;
		    } else {
		      System.out.println ( "Unrecognized option: " + args[arg_index] );
		    }
		  } else {
		    file_name_args.add ( args[arg_index] );
		  }
		  arg_index++;
    }

    System.out.println ( "Command line specified " + file_name_args.size() + " file name patterns." );
    
    for (int i=0; i<file_name_args.size(); i++) {
      actual_file_names.add ( file_name_args.get(i) );
    }

    System.out.println ( "Command line specified " + actual_file_names.size() + " actual files:" );
    for (int i=0; i<actual_file_names.size(); i++) {
      System.out.println ( "  " + actual_file_names.get(i) );
    }
    

		System.out.println ( "swim_lab: Use the mouse wheel to zoom, and drag to pan." );


		javax.swing.SwingUtilities.invokeLater ( new Runnable() {
			public void run() {

			  swim_lab_frame app_frame = new swim_lab_frame("swim_lab");
				app_frame.setDefaultCloseOperation ( JFrame.EXIT_ON_CLOSE );

        swim_lab_window swim_lab_panel_1 = new swim_lab_window();
        swim_lab_panel swim_lab_panel_2 = new swim_lab_panel();
        try {
          System.out.println ( "Opening panel2 image" );
          swim_lab_panel_2.frame_image = ImageIO.read ( new File ("vj_097_shift_rot_skew_crop_1.jpg") );
        } catch ( Exception e ) {
          System.out.println ( "Unable to open panel_2 image" );
        }


        swim_lab_panel_1.set_install_location();
        //swim_lab_panel_2.set_install_location();
        System.out.println ( "Install Code: " + swim_lab_panel_1.install_code_source );
        System.out.println ( "Install Path: " + swim_lab_panel_1.install_code_source.getParent() );

        run_swift.code_source = swim_lab_panel_1.install_code_source.getParent() + File.separator;

        swim_lab_panel_1.parent_frame = app_frame;
        // swim_lab_panel_2.parent_frame = app_frame;
        swim_lab_panel_1.current_directory = System.getProperty("user.dir");
        //swim_lab_panel_2.current_directory = System.getProperty("user.dir");

        swim_lab_panel_1.alignment_panel = new AlignmentPanel(swim_lab_panel_1);
        swim_lab_panel_1.control_panel = new ControlPanel(swim_lab_panel_1);
        swim_lab_panel_1.alignment_panel.setBackground ( new Color (60,60,60) );


        //swim_lab_panel_2.alignment_panel = swim_lab_panel_1.alignment_panel;
        //swim_lab_panel_2.control_panel = swim_lab_panel_1.control_panel;
        //swim_lab_panel_2.setBackground ( new Color (60,60,60) );


				JSplitPane image_split_pane = new JSplitPane(JSplitPane.HORIZONTAL_SPLIT, true, swim_lab_panel_1, swim_lab_panel_2 );
				// JSplitPane image_split_pane = new JSplitPane(JSplitPane.HORIZONTAL_SPLIT, true, swim_lab_panel_1, swim_lab_panel_1.alignment_panel );
				image_split_pane.setOneTouchExpandable( false );
				image_split_pane.setResizeWeight( 0.5 );

				JSplitPane split_pane = new JSplitPane(JSplitPane.VERTICAL_SPLIT, true, image_split_pane, swim_lab_panel_1.control_panel );
				split_pane.setResizeWeight( 0.9 );
				split_pane.setOneTouchExpandable( false );


				swim_lab_panel_1.setBackground ( new Color (60,60,60) );
		    swim_lab_panel_1.project_file_chooser = new ProjectFileChooser ( swim_lab_panel_1.current_directory );
		    swim_lab_panel_1.destination_chooser = new DestinationChooser ( swim_lab_panel_1.current_directory );
		    swim_lab_panel_1.image_file_chooser = new ImageFileChooser ( swim_lab_panel_1.current_directory );
		    try {

		      //System.out.println ( "image_file_chooser:\n  " + swim_lab_panel_1.image_file_chooser );
		      BorderLayout chooser_layout = (BorderLayout)(swim_lab_panel_1.image_file_chooser.getLayout());
		      //System.out.println ( "image_file_chooser.layout:\n  " + chooser_layout );
		      JPanel chooser_controls_panel = (JPanel)(chooser_layout.getLayoutComponent(BorderLayout.SOUTH));
		      //System.out.println ( "image_file_chooser's chooser_controls_panel:\n  " + chooser_controls_panel );

		      Component parts[] = chooser_controls_panel.getComponents();
		      //for (int c=0; c<parts.length; c++) {
		        //System.out.println ( "Component " + c + " = " + parts[c] );
		      //}

		      JPanel button_area = (JPanel)(parts[3]);
		      //System.out.println ( "Button area = " + button_area );

		      swim_lab_panel_1.load_files_on_import = new JCheckBox ( "Load", true );
		      // This appears to fail on the Macintosh. That dialog box may have a different set of containers
		      //button_area.add ( swim_lab_panel_1.load_files_on_import, 0 );


		      // chooser_controls_panel.add ( swim_lab_panel_1.load_files_on_import );

		      //BoxLayout chooser_controls_box = (BoxLayout)(chooser_controls_panel.getLayout());
		      //System.out.println ( "chooer_controls_box = " + chooser_controls_box );
		      //System.out.println ( "chooer_controls_box.axis = " + chooser_controls_box.getAxis() );  // returns 1:  0=X_AXIS, 1=Y_AXIS, 2=LINE_AXIS, 3=PAGE_AXIS

		      //BoxLayout chooser_controls_layout = (BoxLayout)(chooser_layout.getLayoutComponent(BorderLayout.SOUTH).getLayout() );
		      //System.out.println ( "image_file_chooser.layout.controls:\n  " + chooser_controls_layout );
		      // dialog.add ( new JLabel ( "----- NEW -----" ) );
		    } catch (Exception bad_layout_ex) {
		      System.out.println ( "Got an exception trying to add the load check box to file import panel: " + bad_layout_ex );
		    }


        for (int i=0; i<actual_file_names.size(); i++) {
          System.out.println ( "Adding file " + actual_file_names.get(i) + " to stack" );
          swim_lab_panel_1.frames.add ( new swim_lab_image_frame ( new File (actual_file_names.get(i)), load_images ) );  /// Note: use i<=n to only load first n images
          swim_lab_panel_1.frame_index = 0; // set to the first if any frames are loaded
        }
        swim_lab_panel_1.make_alignments();
        swim_lab_panel_1.file_list_dialog = new FileListDialog(app_frame, swim_lab_panel_1);
        swim_lab_panel_1.file_list_dialog.pack();

        swim_lab_panel_1.set_title();

				app_frame.add ( split_pane );

        swim_lab_panel_1.addKeyListener ( swim_lab_panel_1 );
				app_frame.pack();
				app_frame.setSize ( w, h );
				app_frame.setVisible ( true );
			  // Request the focus to make the drawing window responsive to keyboard commands without any clicking required
				swim_lab_panel_1.requestFocus();

				JMenuBar menu_bar = new JMenuBar();
          JMenuItem mi;

          JMenu file_menu = new JMenu("File");

            file_menu.add ( mi = swim_lab_panel_1.new_project_menu_item = new JMenuItem("New Project") );
            mi.addActionListener(swim_lab_panel_1);

            file_menu.add ( mi = swim_lab_panel_1.open_project_menu_item = new JMenuItem("Open Project") );
            mi.addActionListener(swim_lab_panel_1);

            file_menu.add ( mi = swim_lab_panel_1.save_project_menu_item = new JMenuItem("Save Project") );
            mi.addActionListener(swim_lab_panel_1);

            file_menu.add ( mi = swim_lab_panel_1.save_project_as_menu_item = new JMenuItem("Save Project As") );
            mi.addActionListener(swim_lab_panel_1);

            file_menu.addSeparator();

            file_menu.add ( mi = swim_lab_panel_1.set_destination_menu_item = new JMenuItem("Set Destination") );
            mi.addActionListener(swim_lab_panel_1);

            file_menu.addSeparator();

            JMenu import_menu = new JMenu("Import");
              import_menu.add ( mi = swim_lab_panel_1.import_images_menu_item = new JMenuItem("Images...") );
              mi.addActionListener(swim_lab_panel_1);
            file_menu.add ( import_menu );

            // NOTE: Adding the same JMenuItem to multiple JMenus doesn't work
            //   The explanation given is that a JMenuItem can only have one parent.
            //   It's not clear that adding a JMenuItem to a JMenu changes parenting,
            //      but it appears to be true.
            //   The solution is to use Action objects and create both menu items
            //      using the same Action object. This hasn't been done here (yet).
            //   For this reason, clear_all_images_menu_item isn't added here.
            //JMenu clear_menu = new JMenu("Clear");
            //  clear_menu.add ( swim_lab_panel_1.clear_all_images_menu_item );
            //file_menu.add ( clear_menu );

            JMenu list_menu = new JMenu("List");
              list_menu.add ( mi = swim_lab_panel_1.list_all_images_menu_item = new JMenuItem("All Images") );
              mi.addActionListener(swim_lab_panel_1);
              list_menu.add ( mi = swim_lab_panel_1.list_align_shell_script = new JMenuItem("Alignment Script") );
              mi.addActionListener(swim_lab_panel_1);

            file_menu.add ( list_menu );

            file_menu.add ( mi = new JMenuItem("Print") );
            mi.addActionListener(swim_lab_panel_1);

            file_menu.addSeparator();

            file_menu.add ( mi = swim_lab_panel_1.clear_all_images_menu_item = new JMenuItem("Clear All") );
            mi.addActionListener(swim_lab_panel_1);

            file_menu.addSeparator();

            file_menu.add ( mi = new JMenuItem("Exit") );
            mi.addActionListener(swim_lab_panel_1);

            menu_bar.add ( file_menu );

          JMenu tools_menu = new JMenu("Images");

            // tools_menu.add ( mi = swim_lab_panel_1.refresh_images_menu_item = new JMenuItem("Refresh") );
            // mi.addActionListener(swim_lab_panel_1);

            // tools_menu.addSeparator();

            tools_menu.add ( mi = swim_lab_panel_1.refresh_images_menu_item = new JMenuItem("Refresh") );
            mi.addActionListener(swim_lab_panel_1);

            tools_menu.addSeparator();

            tools_menu.add ( mi = swim_lab_panel_1.center_image_menu_item = new JMenuItem("Center") );
            mi.addActionListener(swim_lab_panel_1);

            tools_menu.addSeparator();

            tools_menu.add ( mi = swim_lab_panel_1.zoom_actual_menu_item = new JMenuItem("Actual Size") );
            mi.addActionListener(swim_lab_panel_1);

            menu_bar.add ( tools_menu );

          JMenu help_menu = new JMenu("Help");
            help_menu.add ( mi = new JMenuItem("Commands") );
            mi.addActionListener(swim_lab_panel_1);
            help_menu.add ( mi = new JMenuItem("Version...") );
            mi.addActionListener(swim_lab_panel_1);
            menu_bar.add ( help_menu );


				////////////////  app_frame.setJMenuBar ( menu_bar );


				swim_lab_panel_1.update_control_panel();
				swim_lab_panel_1.center_current_image();

        // Force the top pane to be as large as possible
        split_pane.setDividerLocation ( 0.8 );

			  // Request the focus again?
				swim_lab_panel_1.requestFocus();

			}
		} );

	}
*/
}

public class swim_lab extends JFrame implements ActionListener {

  public swim_lab ( String s ) {
    super(s);

		JMenuBar menu_bar = new JMenuBar();
      JMenuItem mi;

      JMenu file_menu = new JMenu("File");

        file_menu.add ( mi = new JMenuItem("New Project") );
        mi.addActionListener(this);
        menu_bar.add ( file_menu );

      JMenu help_menu = new JMenu("Help");
        help_menu.add ( mi = new JMenuItem("Commands") );
        mi.addActionListener(this);
        help_menu.add ( mi = new JMenuItem("Version...") );
        mi.addActionListener(this);
        menu_bar.add ( help_menu );

		setJMenuBar ( menu_bar );
  }

	public void actionPerformed(ActionEvent e) {
    Object action_source = e.getSource();

		String cmd = e.getActionCommand();
		System.out.println ( "ActionPerformed got \"" + cmd + "\" from " + action_source );

		if (cmd.equalsIgnoreCase("Print")) {
		  System.out.println ( "Images:" );
    //} else if ( action_source == refresh_images_menu_item ) {
      //System.out.println ( "Reloading all images:" );
    }
  }

	public static void main ( String[] args ) {

    System.out.println ( "swim_lab frame is main" );

		javax.swing.SwingUtilities.invokeLater ( new Runnable() {
			public void run() {

			  swim_lab app_frame = new swim_lab("swim_lab");
				app_frame.setDefaultCloseOperation ( JFrame.EXIT_ON_CLOSE );
				
				JPanel main_panel = new JPanel();
				main_panel.setLayout ( new BoxLayout ( main_panel, BoxLayout.X_AXIS ) );
				
				JPanel image_container_1 = new JPanel ( new BorderLayout() );
        swim_lab_panel image_panel_1 = new swim_lab_panel();
        try {
          image_panel_1.frame_image = ImageIO.read ( new File ("vj_097_shift_rot_skew_crop_1.jpg") );
        } catch ( Exception e ) {
          System.out.println ( "Unable to open panel_1 image" );
        }
        image_container_1.add ( image_panel_1, BorderLayout.CENTER );
        image_container_1.add ( new JButton ( "B1"), BorderLayout.SOUTH );
        main_panel.add ( image_container_1 );

				JPanel image_container_2 = new JPanel ( new BorderLayout() );
        swim_lab_panel image_panel_2 = new swim_lab_panel();
        try {
          image_panel_2.frame_image = ImageIO.read ( new File ("vj_097_shift_rot_skew_crop_2.jpg") );
        } catch ( Exception e ) {
          System.out.println ( "Unable to open panel_2 image" );
        }
        image_container_2.add ( image_panel_2, BorderLayout.CENTER );
        image_container_2.add ( new JButton ( "B2"), BorderLayout.SOUTH );
        main_panel.add ( image_container_2 );

				JPanel image_container_3 = new JPanel ( new BorderLayout() );
        swim_lab_panel image_panel_3 = new swim_lab_panel();
        try {
          image_panel_3.frame_image = ImageIO.read ( new File ("best.JPG") );
        } catch ( Exception e ) {
          System.out.println ( "Unable to open panel_3 image" );
        }
        image_container_3.add ( image_panel_3, BorderLayout.CENTER );
        image_container_3.add ( new JButton ( "B3"), BorderLayout.SOUTH );
        main_panel.add ( image_container_3 );
        
        app_frame.add ( main_panel );

				app_frame.pack();
				app_frame.setSize ( 1600, 800 );
				app_frame.setVisible ( true );

			}
		} );

  }

}




