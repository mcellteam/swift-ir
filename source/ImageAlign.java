/* This Class provides zooming and panning for subclasses. */

import javax.swing.*;
import java.awt.*;
import java.awt.event.*;
import java.util.*;


class ImagePane extends ZoomPanLib {

	public void paint_frame (Graphics g) {
	  if (recalculate) {
      // set_scale_to_fit ( -100, 100, -100, 100, getSize().width, getSize().height );
	    recalculate = false;
	  }
	  fill_background(g);
    for (int r=0; r<10; r++) {
  		g.setColor ( new Color ( 255*(r&0x04)/4, 255*(r&0x02)/2, 255*(r&0x01) ) );
		  g.drawLine (  x_to_pxi(-r),  y_to_pyi(-r),  x_to_pxi(-r),  y_to_pyi(r) );
		  g.drawLine (  x_to_pxi(-r),  y_to_pyi(r),   x_to_pxi(r),   y_to_pyi(r) );
		  g.drawLine (  x_to_pxi(r),   y_to_pyi(r),   x_to_pxi(r),   y_to_pyi(-r) );
		  g.drawLine (  x_to_pxi(r),   y_to_pyi(-r),  x_to_pxi(-r),  y_to_pyi(-r) );
		}
	}

}

class ImagePaneFrame extends JFrame implements ActionListener, WindowListener {
  ImagePaneFrame ( String title ) {
    super(title);
    this.addWindowListener(this);
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
    System.out.println ( "ActionPerformed got \"" + cmd + "\" from " + action_source );
    if (cmd.equalsIgnoreCase("Exit")) {
      exit_as_needed();
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

	static int w=800, h=600;

	public static void main ( String[] args ) {
		System.out.println ( "Use the mouse wheel to zoom, and drag to pan." );
		javax.swing.SwingUtilities.invokeLater ( new Runnable() {
			public void run() {
			  ImagePaneFrame app_frame = new ImagePaneFrame("ImageAlign");
				app_frame.setDefaultCloseOperation(ImagePaneFrame.DO_NOTHING_ON_CLOSE);
				
				ImagePane zp_top = new ImagePane();
				zp_top.setBackground ( new Color (0,0,0) );
				zp_top.addMouseListener ( zp_top );
				zp_top.addMouseWheelListener ( zp_top );
				zp_top.addMouseMotionListener ( zp_top );

				ImagePane zp_bot = new ImagePane();
				zp_bot.lock_x(true);
				zp_bot.lock_y(true);
				zp_bot.setBackground ( new Color (64,64,64) );
				zp_bot.addMouseListener ( zp_bot );
				zp_bot.addMouseWheelListener ( zp_bot );
				zp_bot.addMouseMotionListener ( zp_bot );

				JSplitPane split_pane = new JSplitPane(JSplitPane.VERTICAL_SPLIT, true, zp_top, zp_bot );
				split_pane.setResizeWeight ( 0.8 );

				app_frame.add ( split_pane );
				app_frame.pack();
				app_frame.setSize ( w, h );
				app_frame.setVisible ( true );

        JMenuBar menu_bar = new JMenuBar();
          JMenuItem mi;

          JMenu file_menu = new JMenu("File");

            file_menu.add ( mi = new JMenuItem("New Project") );
            mi.addActionListener(app_frame);

            file_menu.add ( mi = new JMenuItem("Exit") );
            mi.addActionListener(app_frame);

            menu_bar.add ( file_menu );

        app_frame.setJMenuBar ( menu_bar );
        //app_frame.update_control_panel();
        //app_frame.center_current_image();

			}
		} );
	}

}
