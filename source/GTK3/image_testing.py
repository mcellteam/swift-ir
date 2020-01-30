
title = "Drawing Area Python3 GTK3"
description = """
GtkDrawingArea is a blank area where you can draw custom displays
of various kinds.

This demo has two drawing areas. The checkerboard area shows
how you can just draw something; all you have to do is write
a signal handler for expose_event, as shown here.

The "scribble" area is a bit more advanced, and shows how to handle
events such as button presses and mouse motion. Click the mouse
and drag in the scribble area to draw squiggles. Resize the window
to clear the area.
"""

import gi
gi.require_version ( 'Gtk', '3.0')
import cairo

from gi.repository import Gtk, Gdk


class DrawingAreaApp:
    def __init__(self):
        self.surface = None

        self.some_image = Gtk.Image.new_from_file ( "S2best.JPG" )
        pb = self.some_image.get_pixbuf()
        print ( "Small image is of type " + str(type(pb) ) )
        self.some_image = Gtk.Image.new_from_file ( "Tile_r1-c1_LM9R5CA1series_017.tif" )
        pb = self.some_image.get_pixbuf()
        print ( "Large image is of type " + str(type(pb) ) )
        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

        window = Gtk.Window()
        window.set_title(title)
        window.connect('destroy', lambda x: Gtk.main_quit())
        window.set_border_width(8)

        vbox = Gtk.VBox(homogeneous=False, spacing=8)
        window.add(vbox)

        # create checkerboard area
        label = Gtk.Label()
        label.set_markup('<u>Checkerboard pattern</u>')
        vbox.pack_start(label, False, False, 0)

        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.IN)
        vbox.pack_start(frame, True, True, 0)

        da = Gtk.DrawingArea()
        da.set_size_request(600, 200)
        frame.add(da)
        da.connect('draw', self.checkerboard_draw_event)

        # create scribble area
        label = Gtk.Label()
        label.set_markup('<u>Scribble area</u>')
        vbox.pack_start(label, False, False, 0)

        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.IN)
        vbox.pack_start(frame, True, True, 0)

        da = Gtk.DrawingArea()
        da.set_size_request(600, 200)
        frame.add(da)
        da.connect('draw', self.scribble_draw_event)
        da.connect('configure-event', self.scribble_configure_event)

        # event signals
        da.connect('motion-notify-event', self.scribble_motion_notify_event)
        da.connect('button-press-event', self.scribble_button_press_event)

        # Ask to receive events the drawing area doesn't normally
        # subscribe to
        da.set_events(da.get_events() |
                      Gdk.EventMask.LEAVE_NOTIFY_MASK |
                      Gdk.EventMask.BUTTON_PRESS_MASK |
                      Gdk.EventMask.POINTER_MOTION_MASK |
                      Gdk.EventMask.POINTER_MOTION_HINT_MASK)

        window.show_all()

    def checkerboard_draw_event(self, da, cairo_ctx):

        # At the start of a draw handler, a clip region has been set on
        # the Cairo context, and the contents have been cleared to the
        # widget's background color. The docs for
        # gdk_window_begin_paint_region() give more details on how this
        # works.
        check_size = 10
        spacing = 2

        xcount = 0
        i = spacing
        width = da.get_allocated_width()
        height = da.get_allocated_height()

        while i < width:
            j = spacing
            ycount = xcount % 2  # start with even/odd depending on row
            while j < height:
                if ycount % 2:
                    cairo_ctx.set_source_rgb(0.45777, 0, 0.45777)
                else:
                    cairo_ctx.set_source_rgb(1, 1, 1)
                # If we're outside the clip this will do nothing.
                cairo_ctx.rectangle(i, j,
                                    check_size,
                                    check_size)
                cairo_ctx.fill()

                j += check_size + spacing
                ycount += 1

            i += check_size + spacing
            xcount += 1

        return True

    def scribble_draw_event(self, da, cairo_ctx):

        cairo_ctx.set_source_surface(self.surface, 0, 0)
        cairo_ctx.paint()

        return False

    def draw_brush(self, widget, x, y):
        update_rect = Gdk.Rectangle()
        update_rect.x = x - 3
        update_rect.y = y - 3
        update_rect.width = 6
        update_rect.height = 6

        # paint to the surface where we store our state
        cairo_ctx = cairo.Context(self.surface)

        Gdk.cairo_rectangle(cairo_ctx, update_rect)
        cairo_ctx.fill()

        widget.get_window().invalidate_rect(update_rect, False)

    def scribble_configure_event(self, da, event):

        allocation = da.get_allocation()
        self.surface = da.get_window().create_similar_surface(cairo.CONTENT_COLOR,
                                                              allocation.width,
                                                              allocation.height)

        cairo_ctx = cairo.Context(self.surface)
        cairo_ctx.set_source_rgb(1, 1, 1)
        cairo_ctx.paint()

        return True

    def scribble_motion_notify_event(self, da, event):
        if self.surface is None:  # paranoia check, in case we haven't gotten a configure event
            return False

        # This call is very important; it requests the next motion event.
        # If you don't call gdk_window_get_pointer() you'll only get
        # a single motion event. The reason is that we specified
        # GDK_POINTER_MOTION_HINT_MASK to gtk_widget_set_events().
        # If we hadn't specified that, we could just use event->x, event->y
        # as the pointer location. But we'd also get deluged in events.
        # By requesting the next event as we handle the current one,
        # we avoid getting a huge number of events faster than we
        # can cope.

        (window, x, y, state) = event.window.get_pointer()

        if state & Gdk.ModifierType.BUTTON1_MASK:
            self.draw_brush(da, x, y)

        return True

    def scribble_button_press_event(self, da, event):
        if self.surface is None:  # paranoia check, in case we haven't gotten a configure event
            return False

        if event.button == 1:
            self.draw_brush(da, event.x, event.y)
        if event.button != 1:
            print ( "Not button 1" )
            __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

        return True


def main(demoapp=None):
    DrawingAreaApp()
    Gtk.main()


if __name__ == '__main__':
    main()



'''
static gboolean
button_press_callback (GtkWidget      *event_box,
                       GdkEventButton *event,
                       gpointer        data)
{
  g_print ("Event box clicked at coordinates %f,%f\n",
           event->x, event->y);

  // Returning TRUE means we handled the event, so the signal
  // emission should be stopped (don’t call any further callbacks
  // that may be connected). Return FALSE to continue invoking callbacks.
  return TRUE;
}

static GtkWidget*
create_image (void)
{
  GtkWidget *image;
  GtkWidget *event_box;

  image = gtk_image_new_from_file ("myfile.png");

  event_box = gtk_event_box_new ();

  gtk_container_add (GTK_CONTAINER (event_box), image);

  g_signal_connect (G_OBJECT (event_box),
                    "button_press_event",
                    G_CALLBACK (button_press_callback),
                    image);

  return image;
}
'''
