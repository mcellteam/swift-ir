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



public class swim_lab extends JFrame implements ActionListener {

  swim_lab_panel image_panel_1;
  swim_lab_panel image_panel_2;
  swim_lab_panel image_panel_3;

  JTextField ww;
  JTextField x;
  JTextField y;
  JTextField outlev;

  JMenuItem new_proj_menu_item = null;
  JMenuItem center_menu_item = null;

  public swim_lab ( String s ) {
    super(s);

		JMenuBar menu_bar = new JMenuBar();
      JMenuItem mi=null;

      JMenu file_menu = new JMenu("File");

        file_menu.add ( new_proj_menu_item = new JMenuItem("New Project") );
        new_proj_menu_item.addActionListener(this);
        menu_bar.add ( file_menu );

      JMenu set_menu = new JMenu("Set");

        set_menu.add ( center_menu_item = new JMenuItem("Center") );
        center_menu_item.addActionListener(this);
        menu_bar.add ( set_menu );

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
      System.out.println();
      System.out.println();
      System.out.println( "#################################################################################################################" );
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

		} else if ( (action_source == center_menu_item) || cmd.equalsIgnoreCase("center_image") ) {

      System.out.println ( "Centering all ..." );
      swim_lab_panel panels[] = new swim_lab_panel[3];
      panels[0] = image_panel_1;
      panels[1] = image_panel_2;
      panels[2] = image_panel_3;
      for (int i=0; i<3; i++) {
        int h = panels[i].frame_image.getHeight();
        int w = panels[i].frame_image.getWidth();
        // System.out.println ( "Image = " + panels[i].frame_image );
        // System.out.println ( " Image Size = " + w + "x" + h );
        panels[i].recalculate = true;
        // System.out.println ( "iPanel.parent: " + panels[i].getParent() );
        Component[] siblings = panels[i].getParent().getComponents();
        for (int sibling=0; sibling<siblings.length; sibling++) {
          // System.out.println ( "  Sibling " + sibling + " = " + siblings[sibling] );
          if (sibling == 1) {
            /// NOTE: This should be checking for type rather than position!!!!!
            JButton jb = (JButton)(siblings[sibling]);
            jb.setText ( "" + w + "x" + h );
          }
        }
        // System.out.println ( "this: " + this );
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

        JButton center = new JButton("Center");
        center.addActionListener ( swim_lab_frame );
        center.setActionCommand ( "center_image" );
        swim_controls.add ( center );

        main_panel.add ( swim_controls, BorderLayout.SOUTH );

        swim_lab_frame.add ( main_panel );

				swim_lab_frame.pack();
				swim_lab_frame.setSize ( 1600, 800 );
				swim_lab_frame.setVisible ( true );

			}
		} );

  }

}




