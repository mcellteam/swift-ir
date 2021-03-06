/* This Class provides zooming and panning for subclasses. */

import javax.swing.*;
import java.awt.*;
import java.awt.event.*;
import java.util.*;


class ImagePane extends ZoomPanLib {
  // This class shows one image with possible decorations
  ImagePaneFrame parent_frame=null;

	public void paint_frame (Graphics g) {
	  if (recalculate) {
      set_scale_to_fit ( -100, 100, -100, 100, getSize().width, getSize().height );
	    recalculate = false;
	  }
	  fill_background(g);
    for (int r=0; r<100; r++) {
  		g.setColor ( new Color ( 255*(r&0x04)/4, 255*(r&0x02)/2, 255*(r&0x01) ) );
		  g.drawLine (  x_to_pxi(-r),  y_to_pyi(-r),  x_to_pxi(-r),  y_to_pyi(r) );
		  g.drawLine (  x_to_pxi(-r),  y_to_pyi(r),   x_to_pxi(r),   y_to_pyi(r) );
		  g.drawLine (  x_to_pxi(r),   y_to_pyi(r),   x_to_pxi(r),   y_to_pyi(-r) );
		  g.drawLine (  x_to_pxi(r),   y_to_pyi(-r),  x_to_pxi(-r),  y_to_pyi(-r) );
		}
	}

}

class ImagePaneFrame extends JFrame implements ActionListener, WindowListener {
  // This is the main application frame.
  ImagePane base_pane = null;
  ImagePane adjust_pane = null;
  ImagePane other_pane_1 = null;
  ImagePane other_pane_2 = null;
  public JPanel image_box = null;
  int view_mode = 2;
  int border_dim = 2;

  ImagePaneFrame ( String title ) {
    super(title);
    this.addWindowListener(this);
  }

  public void build_panels() {
    if (base_pane == null) {
      base_pane = new ImagePane();
      base_pane.setBackground ( new Color (0,0,0) );
      base_pane.addMouseListener ( base_pane );
      base_pane.addMouseWheelListener ( base_pane );
      base_pane.addMouseMotionListener ( base_pane );
    }

    if (adjust_pane == null) {
      adjust_pane = new ImagePane();
      adjust_pane.setBackground ( new Color (0,0,0) );
      adjust_pane.addMouseListener ( adjust_pane );
      adjust_pane.addMouseWheelListener ( adjust_pane );
      adjust_pane.addMouseMotionListener ( adjust_pane );
    }

    if (other_pane_1 == null) {
      other_pane_1 = new ImagePane();
      other_pane_1.setBackground ( new Color (0,0,0) );
      other_pane_1.addMouseListener ( other_pane_1 );
      other_pane_1.addMouseWheelListener ( other_pane_1 );
      other_pane_1.addMouseMotionListener ( other_pane_1 );
    }

    if (other_pane_2 == null) {
      other_pane_2 = new ImagePane();
      other_pane_2.setBackground ( new Color (0,0,0) );
      other_pane_2.addMouseListener ( other_pane_2 );
      other_pane_2.addMouseWheelListener ( other_pane_2 );
      other_pane_2.addMouseMotionListener ( other_pane_2 );
    }

    if (image_box == null) {
      image_box = new JPanel();
      BoxLayout hbox = new BoxLayout(image_box, BoxLayout.X_AXIS);
      image_box.setLayout ( hbox );
      image_box.setBorder(BorderFactory.createEmptyBorder(border_dim, border_dim, border_dim, border_dim));
    }

    image_box.removeAll();

    image_box.add ( base_pane );
    image_box.add(Box.createRigidArea(new Dimension(border_dim,0)));
    image_box.add ( adjust_pane );

    if (view_mode == 4) {
      image_box.add(Box.createRigidArea(new Dimension(border_dim,0)));
      image_box.add ( other_pane_1 );
      image_box.add(Box.createRigidArea(new Dimension(border_dim,0)));
      image_box.add ( other_pane_2 );
    }
    image_box.validate();

  }

  void view_2_image() {
    System.out.println ( "View 2 Image" );
    view_mode = 2;
    this.build_panels();
  }

  void view_4_image() {
    System.out.println ( "View 4 Image" );
    view_mode = 4;
    this.build_panels();
  }

  void exit_as_needed() {
    int response = JOptionPane.showConfirmDialog(this, "Exit from ImageAlign?", "Confirm Exit", JOptionPane.INFORMATION_MESSAGE, JOptionPane.YES_NO_OPTION);
    if (response == JOptionPane.YES_OPTION) {
      System.exit ( 0 );
    }
  }

  /** ActionListener Interface Methods **/
  public void actionPerformed(ActionEvent e) {
    Object action_source = e.getSource();
    String cmd = e.getActionCommand();
    if (cmd.equalsIgnoreCase("Exit")) {
      exit_as_needed();
    } else if (cmd.equalsIgnoreCase("2 Image")) {
      view_2_image();
    } else if (cmd.equalsIgnoreCase("4 Image")) {
      view_4_image();
    } else {
      System.out.println ( "Unknown command: " + cmd );
    }
  }

  /** WindowListener Interface Methods **/
  public void windowActivated(WindowEvent e) {}
  public void windowClosed(WindowEvent e) {}
  public void windowClosing(WindowEvent e) { exit_as_needed(); }
  public void windowDeactivated(WindowEvent e) {}
  public void windowDeiconified(WindowEvent e) {}
  public void windowIconified(WindowEvent e) {}
  public void windowOpened(WindowEvent e) {}
}

public class ImageAlign {

	static int w=1200, h=600;

	public static void main ( String[] args ) {
		System.out.println ( "Use the mouse wheel to zoom, and drag to pan." );
		javax.swing.SwingUtilities.invokeLater ( new Runnable() {
			public void run() {
			  ImagePaneFrame app_frame = new ImagePaneFrame("ImageAlign");
				app_frame.setDefaultCloseOperation(ImagePaneFrame.DO_NOTHING_ON_CLOSE);
				
				app_frame.build_panels();
        app_frame.add ( app_frame.image_box );

        JMenuBar menu_bar = new JMenuBar();
          JMenuItem mi;

          JMenu file_menu = new JMenu("File");

            file_menu.add ( mi = new JMenuItem("New Project") );
            mi.addActionListener(app_frame);

            file_menu.add ( mi = new JMenuItem("Exit") );
            mi.addActionListener(app_frame);

            menu_bar.add ( file_menu );

          JMenu view_menu = new JMenu("View");

            view_menu.add ( mi = new JMenuItem("2 Image") );
            mi.addActionListener(app_frame);

            view_menu.add ( mi = new JMenuItem("4 Image") );
            mi.addActionListener(app_frame);

            menu_bar.add ( view_menu );

        app_frame.setJMenuBar ( menu_bar );
        app_frame.pack();
        app_frame.setSize ( w, h );
        app_frame.setVisible ( true );

			}
		} );
	}

}
