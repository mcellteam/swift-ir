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

class ImagePaneFrame extends JFrame {
  ImagePaneFrame ( String title ) {
    super(title);
  }
}

public class ImageAlign {

	static int w=800, h=600;

	public static void main ( String[] args ) {
		System.out.println ( "Use the mouse wheel to zoom, and drag to pan." );
		javax.swing.SwingUtilities.invokeLater ( new Runnable() {
			public void run() {
			  ImagePaneFrame f = new ImagePaneFrame("ImageAlign");
				f.setDefaultCloseOperation ( ImagePaneFrame.EXIT_ON_CLOSE );
				
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

				f.add ( split_pane );
				f.pack();
				f.setSize ( w, h );
				f.setVisible ( true );
			}
		} );
	}

}
