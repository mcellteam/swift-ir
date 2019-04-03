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

  ControlPanel (swim_lab swift) {
    this.swift = swift;

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

  public double get_double_from_textfield ( JTextComponent c ) {
    String s = c.getText();
    if (s.length() > 0) {
      return ( Double.parseDouble ( s ) );
    } else {
      return ( 0.0 );
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
    if (frames == null) {
      super.mouseWheelMoved ( e );
    } else {
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
  }

	public static ArrayList<String> actual_file_names = new ArrayList<String>();

  static boolean load_images = true;
}

public class swim_lab extends JFrame implements ActionListener {

  swim_lab_panel image_panel_1;
  swim_lab_panel image_panel_2;
  swim_lab_panel image_panel_3;

  JTextField ww;
  JTextField x;
  JTextField y;
  JTextField outlev;

  JMenuItem new_proj_menu_item = null;

  public swim_lab ( String s ) {
    super(s);

		JMenuBar menu_bar = new JMenuBar();
      JMenuItem mi=null;

      JMenu file_menu = new JMenu("File");

        file_menu.add ( new_proj_menu_item = new JMenuItem("New Project") );
        new_proj_menu_item.addActionListener(this);
        menu_bar.add ( file_menu );

      JMenu help_menu = new JMenu("Help");

        help_menu.add ( mi = new JMenuItem("Commands") );
        mi.addActionListener(this);
        help_menu.add ( mi = new JMenuItem("Version...") );
        mi.addActionListener(this);
        menu_bar.add ( help_menu );

		setJMenuBar ( menu_bar );
  }

  public int get_int_from_textfield ( JTextComponent c ) {
    String s = c.getText();
    if (s.length() > 0) {
      return ( Integer.parseInt ( s ) );
    } else {
      return ( 0 );
    }
  }

  public double get_double_from_textfield ( JTextComponent c ) {
    String s = c.getText();
    if (s.length() > 0) {
      return ( Double.parseDouble ( s ) );
    } else {
      return ( 0.0 );
    }
  }

	public void actionPerformed(ActionEvent e) {
    Object action_source = e.getSource();

		String cmd = e.getActionCommand();
		// System.out.println ( "ActionPerformed got \"" + cmd + "\" from " + action_source );

		if (cmd.equalsIgnoreCase("Version...")) {
		  System.out.println ( "Version: " );
		} else if (cmd.equalsIgnoreCase("Commands")) {
		  System.out.println ( "Commands: " );
    } else if (cmd.equalsIgnoreCase("run_swim")) {
      Runtime rt = Runtime.getRuntime();
      String results[] = run_swift.run_swim (
                        rt,
                        "vj_097_shift_rot_skew_crop_1.jpg",
                        "vj_097_shift_rot_skew_crop_2.jpg",
                        ww.getText(),
                        x.getText(),
                        y.getText(),
                        get_int_from_textfield ( outlev ) );
      try {
        image_panel_3.frame_image = ImageIO.read ( new File ("best.JPG") );
      } catch ( Exception ex ) {
        System.out.println ( "Unable to open panel_3 image" );
      }
      repaint();

		} else if ( action_source == new_proj_menu_item ) {
      System.out.println ( "New Project" );
    }
  }

	public static void main ( String[] args ) {

    System.out.println ( "swim_lab frame is main" );

		javax.swing.SwingUtilities.invokeLater ( new Runnable() {
			public void run() {

			  swim_lab swim_lab_frame = new swim_lab("swim_lab");
				swim_lab_frame.setDefaultCloseOperation ( JFrame.EXIT_ON_CLOSE );
				
				JPanel main_panel = new JPanel();
				main_panel.setLayout ( new BorderLayout() );


				JPanel main_box_panel = new JPanel();
				main_box_panel.setLayout ( new BoxLayout ( main_box_panel, BoxLayout.X_AXIS ) );
				
				JPanel image_container_1 = new JPanel ( new BorderLayout() );
        swim_lab_frame.image_panel_1 = new swim_lab_panel();
        try {
          swim_lab_frame.image_panel_1.frame_image = ImageIO.read ( new File ("vj_097_shift_rot_skew_crop_1.jpg") );
        } catch ( Exception e ) {
          System.out.println ( "Unable to open panel_1 image" );
        }
        image_container_1.add ( swim_lab_frame.image_panel_1, BorderLayout.CENTER );
        image_container_1.add ( new JButton ( "B1"), BorderLayout.SOUTH );
        main_box_panel.add ( image_container_1 );

				JPanel image_container_2 = new JPanel ( new BorderLayout() );
        swim_lab_frame.image_panel_2 = new swim_lab_panel();
        try {
          swim_lab_frame.image_panel_2.frame_image = ImageIO.read ( new File ("vj_097_shift_rot_skew_crop_2.jpg") );
        } catch ( Exception e ) {
          System.out.println ( "Unable to open panel_2 image" );
        }
        image_container_2.add ( swim_lab_frame.image_panel_2, BorderLayout.CENTER );
        image_container_2.add ( new JButton ( "B2"), BorderLayout.SOUTH );
        main_box_panel.add ( image_container_2 );

				JPanel image_container_3 = new JPanel ( new BorderLayout() );
        swim_lab_frame.image_panel_3 = new swim_lab_panel();
        try {
          swim_lab_frame.image_panel_3.frame_image = ImageIO.read ( new File ("best.JPG") );
        } catch ( Exception e ) {
          System.out.println ( "Unable to open panel_3 image" );
        }
        image_container_3.add ( swim_lab_frame.image_panel_3, BorderLayout.CENTER );
        image_container_3.add ( new JButton ( "B3"), BorderLayout.SOUTH );
        main_box_panel.add ( image_container_3 );


        main_panel.add ( main_box_panel, BorderLayout.CENTER );
        
        JPanel swim_controls = new JPanel();

        swim_lab_frame.ww = new JTextField("1024",6);
        swim_controls.add ( new JLabel("ww: ") );
        swim_controls.add ( swim_lab_frame.ww );

        swim_lab_frame.x = new JTextField("",6);
        swim_controls.add ( new JLabel("x: ") );
        swim_controls.add ( swim_lab_frame.x );

        swim_controls.add ( new JLabel("   ") );

        swim_lab_frame.y = new JTextField("",6);
        swim_controls.add ( new JLabel("y: ") );
        swim_controls.add ( swim_lab_frame.y );

        swim_controls.add ( new JLabel("   ") );

        swim_lab_frame.outlev = new JTextField("50",6);
        swim_controls.add ( new JLabel("out: ") );
        swim_controls.add ( swim_lab_frame.outlev );

        swim_controls.add ( new JLabel("   ") );

        JButton run = new JButton("Run");
        run.addActionListener ( swim_lab_frame );
        run.setActionCommand ( "run_swim" );
        swim_controls.add ( run );

        main_panel.add ( swim_controls, BorderLayout.SOUTH );

        swim_lab_frame.add ( main_panel );

				swim_lab_frame.pack();
				swim_lab_frame.setSize ( 1600, 800 );
				swim_lab_frame.setVisible ( true );

			}
		} );

  }

}




