/* Image Alignment Tool based on SWiFT */

import java.io.*;

import java.awt.*;
import java.awt.event.*;
import java.awt.image.*;
import javax.imageio.ImageIO;
import javax.swing.*;
import javax.swing.filechooser.FileNameExtensionFilter;
import java.util.*;


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

class ImageFileChooser extends JFileChooser {
  ImageFileChooser ( String path ) {
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

class alignment_settings {
  swift_gui_frame prev_frame=null;
  swift_gui_frame next_frame=null;
  int window_size=1024;
  int addx=800;
  int addy=800;
  int output_level=0;
}

class swift_gui_frame {
  public File image_file_path=null;
  public boolean valid=false;
  public BufferedImage image=null;

  alignment_settings prev_alignment=null;
  alignment_settings next_alignment=null;

  swift_gui_frame ( File image_file_path, boolean load ) {
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
  private swift_gui parent_frame=null;

  public FileListDialog(Frame par_frame, swift_gui parent) {
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
        // Build the text from the current model every time it's shown
        if (parent_frame != null) {
          // Get the list of files from the parent_frame
          if (parent_frame.frames != null) {
            textArea.setText ( "Frames:\n" );
            for (int fnum=0; fnum<parent_frame.frames.size(); fnum++) {
              textArea.append ( "File: " + parent_frame.frames.get(fnum).image_file_path + "\n" );
            }
          }
        }
        textArea.requestFocusInWindow();
      }
    });
  }
}


class AlignmentPanel extends JPanel {
  public swift_gui swift;
  AlignmentPanel (swift_gui swift) {
    this.swift = swift;
  }
	public void paint (Graphics g) {
	  int w = size().width;
	  int h = size().height;
    g.setColor ( new Color ( 60, 60, 60 ) );
    g.fillRect ( 0, 0, w, h );

    if (swift.frames != null) {
      if (swift.frames.size() > 0) {
        if ( (swift.frame_index >= 0) && (swift.frame_index < swift.frames.size()) ) {
          if (swift.frames.get(swift.frame_index).image != null) {
            BufferedImage frame_image = swift.frames.get(swift.frame_index).image;

		        int img_w = frame_image.getWidth();
		        int img_h = frame_image.getHeight();

		        // Calculate the size to fit the image in the side pane (assuming width constrained)
		        int padding = 10;
		        int xoff = padding;
		        double img_scale = (w-(2.0*padding)) / img_w;
		        int scaled_w = (int)(img_w * img_scale);
		        int scaled_h = (int)(img_h * img_scale);

		        if ( ( (3*scaled_h) + (4*padding) ) > h ) {
		          // Images are actually height constrained, so recalculate
		          img_scale = (h-(4.0*padding)) / (3*img_h);
		          scaled_w = (int)(img_w * img_scale);
		          scaled_h = (int)(img_h * img_scale);
		          xoff = (w-scaled_w) / 2;
		        }

            if (swift.frame_index >= 1) {
              g.drawImage ( swift.frames.get(swift.frame_index-1).image, xoff, padding, scaled_w, scaled_h, this );
            }
            g.drawImage ( frame_image, xoff, (h/2)-(scaled_h/2), scaled_w, scaled_h, this );
            if (swift.frame_index < (swift.frames.size()-1)) {
              g.drawImage ( swift.frames.get(swift.frame_index+1).image, xoff, h-(padding+scaled_h), scaled_w, scaled_h, this );
            }
          }

          //frame_image = frames.get(frame_index).image;
        }
      }
    }
	}
}


class ControlPanel extends JPanel {
  public swift_gui swift;

  public JTextField image_name;

  public JLabel project_label;

  public JLabel image_label;
  public JLabel image_size;
  public JLabel image_bits;

  public JTextField window_size;
  public JTextField addx;
  public JTextField addy;
  public JTextField output_level;

  ControlPanel (swift_gui swift) {
    this.swift = swift;

    this.setLayout ( new BorderLayout( 0, 20 ) );

    image_name = new JTextField("", 40);
    // image_name.setBounds ( 10, 10, 300, 20 );
    // add ( image_name );

    project_label = new JLabel("Project File: "+swift.project_file);
    add ( project_label, BorderLayout.NORTH );

    JPanel center_panel = new JPanel();

    image_label = new JLabel("");
    center_panel.add ( image_label );

    center_panel.add ( new JLabel("  Size:") );
    image_size = new JLabel("");
    center_panel.add ( image_size );

    center_panel.add ( new JLabel("  Depth:") );
    image_bits = new JLabel("");
    center_panel.add ( image_bits );

    center_panel.add ( new JLabel("  WW:") );
    window_size = new JTextField("",8);
    window_size.addActionListener ( this.swift );
    window_size.setActionCommand ( "window_size" );
    center_panel.add ( window_size );

    center_panel.add ( new JLabel("  Addx:") );
    addx = new JTextField("",6);
    addx.addActionListener ( this.swift );
    addx.setActionCommand ( "addx" );
    center_panel.add ( addx );

    center_panel.add ( new JLabel("  Addy:") );
    addy = new JTextField("",6);
    addy.addActionListener ( this.swift );
    addy.setActionCommand ( "addy" );
    center_panel.add ( addy );

    center_panel.add ( new JLabel("  Output Level:") );
    output_level = new JTextField("",4);
    output_level.addActionListener ( this.swift );
    output_level.setActionCommand ( "output_level" );
    center_panel.add ( output_level );

    add ( center_panel, BorderLayout.CENTER );
  }
}


public class swift_gui extends ZoomPanLib implements ActionListener, MouseMotionListener, MouseListener, KeyListener {

  JFrame parent_frame = null;
  AlignmentPanel alignment_panel = null;
  ControlPanel control_panel = null;

  File project_file=null;

	static int w=1024, h=768;

  String current_directory = "";
  ImageFileChooser image_file_chooser = null;
  ProjectFileChooser project_file_chooser = null;

  FileListDialog file_list_dialog = null;

  int ref_image_w = 1000;
  int ref_image_h = 1000;


	public ArrayList<swift_gui_frame> frames = new ArrayList<swift_gui_frame>();  // Argument (if any) specifies initial capacity (default 10)
  public int frame_index = -1;


  public void repaint_panels () {
    alignment_panel.repaint();
    control_panel.repaint();
  }

  public void link_frames() {
    if (frames != null) {
      if (frames.size() > 1) {
        for (int fnum=0; fnum<(frames.size()-1); fnum++) {
          swift_gui_frame prev = frames.get(fnum);
          swift_gui_frame next = frames.get(fnum+1);
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
        frame_image = frames.get(frame_index).image;
      }
    }

		g.setColor ( new Color ( 60, 60, 60 ) );  // Main window
	  g.fillRect ( 0, 0, win_w, win_h );

		if (frame_image == null) {
		  // System.out.println ( "Image is null" );
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
      if (frames != null) {
        if (frames.size() > 0) {
          File image_file_path = frames.get(frame_index).image_file_path;
          control_panel.image_name.setText ( image_file_path.getName() );
          swift_gui_frame frame = frames.get(frame_index);
          if (frame != null) {
            if (frame.image != null) {
              BufferedImage frame_image = frames.get(frame_index).image;
              control_panel.image_size.setText ( ""+frame_image.getWidth()+"x"+frame_image.getHeight() );
              control_panel.image_bits.setText ( ""+frame_image.getColorModel().getPixelSize() );
            }
            if (frame.next_alignment == null) {
              control_panel.window_size.setText ( "" );
              control_panel.addx.setText ( "" );
              control_panel.addy.setText ( "" );
              control_panel.output_level.setText ( "" );
            } else {
              control_panel.window_size.setText ( "" + frame.next_alignment.window_size );
              control_panel.addx.setText ( "" + frame.next_alignment.addx );
              control_panel.addy.setText ( "" + frame.next_alignment.addy );
              control_panel.output_level.setText ( "" + frame.next_alignment.output_level );
            }
          }
        } else {
          control_panel.image_name.setText ( "" );
          control_panel.image_size.setText ( "" );
          control_panel.image_bits.setText ( "" );
          control_panel.window_size.setText ( "" );
          control_panel.addx.setText ( "" );
          control_panel.addy.setText ( "" );
          control_panel.output_level.setText ( "" );
        }
      } else {
        control_panel.image_name.setText ( "" );
        control_panel.image_size.setText ( "" );
        control_panel.image_bits.setText ( "" );
        control_panel.window_size.setText ( "" );
        control_panel.addx.setText ( "" );
        control_panel.addy.setText ( "" );
        control_panel.output_level.setText ( "" );
      }
      control_panel.image_label.setText ( control_panel.image_name.getText() );
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
    // System.out.println ( "Key Typed: " + e );
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

  JMenuItem import_images_menu_item = null;
  JMenuItem refresh_images_menu_item = null;
  JMenuItem center_image_menu_item = null;
  JMenuItem zoom_actual_menu_item = null;
  JMenuItem clear_all_images_menu_item = null;
  JMenuItem list_all_images_menu_item = null;

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
		    File selected_files[] = image_file_chooser.getSelectedFiles();
		    if (selected_files.length > 0) {
		      // Use the current size as the new index (if size is 0, then the new index will be 0 which points to the first)
		      int num_previous = this.frames.size();
		      int new_frame_index = this.frames.size();
		      for (int i=0; i<selected_files.length; i++) {
            System.out.println ( "You chose this file: " + selected_files[i] );
            this.frames.add ( new swift_gui_frame ( selected_files[i], load_images ) );
		      }
          link_frames();
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
        json_parser parser = new json_parser ( "{}" );
        /*
        try {
        } catch ( FileNotFoundException fnfe ) {
        }
        */
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
        try {
          PrintStream f = new PrintStream ( project_file );
          f.println ( "{" );
          f.println ( "  \"version\": 0.0," );
          f.println ( "  \"method\": \"SWiFT-IR\"," );
          f.println ( "  \"data\": {" );
          f.println ( "    \"source_path\": \"\"," );
          f.println ( "    \"defaults\": {" );
          f.println ( "      \"align_to_next_pars\": {" );
          f.println ( "        \"window_size\": \"" + "1024" + "\"," );
          f.println ( "        \"addx\": \"" + "800" + "\"," );
          f.println ( "        \"addy\": \"" + "800" + "\"," );
          f.println ( "        \"output_level\": \"" + "0" + "\"" );
          f.println ( "      }" );
          f.println ( "    }," );

          f.println ( "    \"imagestack\": [" );

	        for (int i=0; i<this.frames.size(); i++) {
            swift_gui_frame frame = this.frames.get(i);

            f.println ( "      { " );
            f.print   ( "        \"skip\": false," );
            f.print   ( "        \"filename\": \"" + frame + "\"" );
            if (frame.next_alignment == null) {
              f.println ( "" );
            } else {
              f.println ( "," );
              alignment_settings settings = frame.next_alignment;
              f.println ( "        \"align_to_next_pars\": {" );
              f.println ( "          \"window_size\": \"" + settings.window_size + "\"," );
              f.println ( "          \"addx\": \"" + settings.addx + "\"," );
              f.println ( "          \"addy\": \"" + settings.addy + "\"," );
              f.println ( "          \"output_level\": \"" + settings.output_level + "\"" );
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
        /*
        update_control_panel();
        repaint();
        repaint_panels();
        */
		  }
		  set_title();
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
      this.frames = new ArrayList<swift_gui_frame>();
      this.frame_index = -1;
      repaint();
      update_control_panel();
      repaint_panels();
		  set_title();
    } else if ( action_source == list_all_images_menu_item ) {
      if (file_list_dialog != null) {
        file_list_dialog.setVisible(true);
      }
      //repaint();
		  //set_title();
		} else if (cmd.equalsIgnoreCase("window_size")) {
			System.out.println ( "Got a window_size change with " + ((JTextField)action_source).getText() );
      if (frames != null) {
        if (frames.size() > 1) {
          swift_gui_frame frame = frames.get(frame_index);
          if (frame.next_alignment != null) {
            frame.next_alignment.window_size = Integer.parseInt ( ((JTextField)action_source).getText() );
          }
        }
      }
		} else if (cmd.equalsIgnoreCase("addx")) {
			System.out.println ( "Got an addx change with " + ((JTextField)action_source).getText() );
      if (frames != null) {
        if (frames.size() > 1) {
          swift_gui_frame frame = frames.get(frame_index);
          if (frame.next_alignment != null) {
            frame.next_alignment.addx = Integer.parseInt ( ((JTextField)action_source).getText() );
          }
        }
      }
		} else if (cmd.equalsIgnoreCase("addy")) {
			System.out.println ( "Got an addy change with " + ((JTextField)action_source).getText() );
      if (frames != null) {
        if (frames.size() > 1) {
          swift_gui_frame frame = frames.get(frame_index);
          if (frame.next_alignment != null) {
            frame.next_alignment.addy = Integer.parseInt ( ((JTextField)action_source).getText() );
          }
        }
      }
		} else if (cmd.equalsIgnoreCase("output_level")) {
			System.out.println ( "Got an output_level change with " + ((JTextField)action_source).getText() );
      if (frames != null) {
        if (frames.size() > 1) {
          swift_gui_frame frame = frames.get(frame_index);
          if (frame.next_alignment != null) {
            frame.next_alignment.output_level = Integer.parseInt ( ((JTextField)action_source).getText() );
          }
        }
      }
		} else if (cmd.equalsIgnoreCase("Exit")) {
			System.exit ( 0 );
		}
  }

	public static ArrayList<String> actual_file_names = new ArrayList<String>();

  static boolean load_images = true;

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
    
    /* I'm not sure why this was needed in run_swift.java but causes problems here.
    {
      File current_directory = new File ( "." );
      System.out.println ( "File = " + current_directory );
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
    */
    for (int i=0; i<file_name_args.size(); i++) {
      actual_file_names.add ( file_name_args.get(i) );
    }

    System.out.println ( "Command line specified " + actual_file_names.size() + " actual files:" );
    for (int i=0; i<actual_file_names.size(); i++) {
      System.out.println ( "  " + actual_file_names.get(i) );
    }
    

		System.out.println ( "swift_gui: Use the mouse wheel to zoom, and drag to pan." );


		javax.swing.SwingUtilities.invokeLater ( new Runnable() {
			public void run() {
			  JFrame app_frame = new JFrame("swift_gui");
				app_frame.setDefaultCloseOperation ( JFrame.EXIT_ON_CLOSE );

        swift_gui swift_gui_panel = new swift_gui();
        swift_gui_panel.parent_frame = app_frame;
        swift_gui_panel.current_directory = System.getProperty("user.dir");

        swift_gui_panel.alignment_panel = new AlignmentPanel(swift_gui_panel);
        swift_gui_panel.control_panel = new ControlPanel(swift_gui_panel);
        swift_gui_panel.alignment_panel.setBackground ( new Color (60,60,60) );
        // swift_gui_panel.alignment_panel.swift = swift_gui_panel;
        // swift_gui_panel.control_panel.swift = swift_gui_panel;

				JSplitPane image_split_pane = new JSplitPane(JSplitPane.HORIZONTAL_SPLIT, true, swift_gui_panel, swift_gui_panel.alignment_panel );
				image_split_pane.setOneTouchExpandable( true );
				image_split_pane.setResizeWeight( 0.78 );

				JSplitPane split_pane = new JSplitPane(JSplitPane.VERTICAL_SPLIT, true, image_split_pane, swift_gui_panel.control_panel );
				split_pane.setResizeWeight( 0.9 );
				split_pane.setOneTouchExpandable( true );


				swift_gui_panel.setBackground ( new Color (60,60,60) );
		    swift_gui_panel.project_file_chooser = new ProjectFileChooser ( swift_gui_panel.current_directory );
		    swift_gui_panel.image_file_chooser = new ImageFileChooser ( swift_gui_panel.current_directory );

        for (int i=0; i<actual_file_names.size(); i++) {
          System.out.println ( "Adding file " + actual_file_names.get(i) + " to stack" );
          swift_gui_panel.frames.add ( new swift_gui_frame ( new File (actual_file_names.get(i)), load_images ) );  /// Note: use i<=n to only load first n images
          swift_gui_panel.frame_index = 0; // set to the first if any frames are loaded
        }
        swift_gui_panel.link_frames();
        swift_gui_panel.file_list_dialog = new FileListDialog(app_frame, swift_gui_panel);
        swift_gui_panel.file_list_dialog.pack();

        swift_gui_panel.set_title();

				app_frame.add ( split_pane );

        swift_gui_panel.addKeyListener ( swift_gui_panel );
				app_frame.pack();
				app_frame.setSize ( w, h );
				app_frame.setVisible ( true );
			  // Request the focus to make the drawing window responsive to keyboard commands without any clicking required
				swift_gui_panel.requestFocus();

				JMenuBar menu_bar = new JMenuBar();
          JMenuItem mi;

          JMenu file_menu = new JMenu("File");

            file_menu.add ( mi = swift_gui_panel.new_project_menu_item = new JMenuItem("New Project") );
            mi.addActionListener(swift_gui_panel);

            file_menu.add ( mi = swift_gui_panel.open_project_menu_item = new JMenuItem("Open Project") );
            mi.addActionListener(swift_gui_panel);

            file_menu.add ( mi = swift_gui_panel.save_project_menu_item = new JMenuItem("Save Project") );
            mi.addActionListener(swift_gui_panel);

            file_menu.add ( mi = swift_gui_panel.save_project_as_menu_item = new JMenuItem("Save Project As") );
            mi.addActionListener(swift_gui_panel);

            file_menu.addSeparator();

            JMenu import_menu = new JMenu("Import");
              import_menu.add ( mi = swift_gui_panel.import_images_menu_item = new JMenuItem("Images...") );
              mi.addActionListener(swift_gui_panel);
            file_menu.add ( import_menu );

            // NOTE: Adding the same JMenuItem to multiple JMenus doesn't work
            //   The explanation given is that a JMenuItem can only have one parent.
            //   It's not clear that adding a JMenuItem to a JMenu changes parenting,
            //      but it appears to be true.
            //   The solution is to use Action objects and create both menu items
            //      using the same Action object. This hasn't been done here (yet).
            //   For this reason, clear_all_images_menu_item isn't added here.
            //JMenu clear_menu = new JMenu("Clear");
            //  clear_menu.add ( swift_gui_panel.clear_all_images_menu_item );
            //file_menu.add ( clear_menu );

            JMenu list_menu = new JMenu("List");
              list_menu.add ( mi = swift_gui_panel.list_all_images_menu_item = new JMenuItem("All Images") );
              mi.addActionListener(swift_gui_panel);
            file_menu.add ( list_menu );

            file_menu.add ( mi = new JMenuItem("Print") );
            mi.addActionListener(swift_gui_panel);

            file_menu.addSeparator();

            file_menu.add ( mi = swift_gui_panel.clear_all_images_menu_item = new JMenuItem("Clear All") );
            mi.addActionListener(swift_gui_panel);

            file_menu.addSeparator();

            file_menu.add ( mi = new JMenuItem("Exit") );
            mi.addActionListener(swift_gui_panel);

            menu_bar.add ( file_menu );

          JMenu tools_menu = new JMenu("Images");

            // tools_menu.add ( mi = swift_gui_panel.refresh_images_menu_item = new JMenuItem("Refresh") );
            // mi.addActionListener(swift_gui_panel);

            // tools_menu.addSeparator();

            tools_menu.add ( mi = swift_gui_panel.refresh_images_menu_item = new JMenuItem("Refresh") );
            mi.addActionListener(swift_gui_panel);

            tools_menu.addSeparator();

            tools_menu.add ( mi = swift_gui_panel.center_image_menu_item = new JMenuItem("Center") );
            mi.addActionListener(swift_gui_panel);

            tools_menu.addSeparator();

            tools_menu.add ( mi = swift_gui_panel.zoom_actual_menu_item = new JMenuItem("Actual Size") );
            mi.addActionListener(swift_gui_panel);

            menu_bar.add ( tools_menu );

          JMenu help_menu = new JMenu("Help");
            help_menu.add ( mi = new JMenuItem("Commands") );
            mi.addActionListener(swift_gui_panel);
            help_menu.add ( mi = new JMenuItem("Version...") );
            mi.addActionListener(swift_gui_panel);
            menu_bar.add ( help_menu );


				app_frame.setJMenuBar ( menu_bar );
				swift_gui_panel.update_control_panel();
				swift_gui_panel.center_current_image();

			}
		} );

	}

}

