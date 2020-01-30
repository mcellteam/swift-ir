import wx
import sys

# This working example of the use of OpenGL in the wxPython context
# was assembled in August 2012 from the GLCanvas.py file found in
# the wxPython docs-demo package, plus components of that package's
# run-time environment.

# Note that dragging the mouse rotates the view of the 3D cube or cone.

# Code was updated in 2019 to replace the missing cone function with
#  a list of triangles (with normals).

# Changes were made in WxWidgets_Py3_Win10_FF_Test_001 Virtual Machine

try:
    from wx import glcanvas
    haveGLCanvas = True
except ImportError:
    haveGLCanvas = False

try:
    # The Python OpenGL package can be found at
    # http://PyOpenGL.sourceforge.net/
    from OpenGL.GL import *
    from OpenGL.GLUT import *
    haveOpenGL = True
except ImportError:
    haveOpenGL = False

#----------------------------------------------------------------------

buttonDefs = {
    wx.NewIdRef(count=1) : ('CubeCanvas',      'Cube'),
    wx.NewIdRef(count=1) : ('ConeCanvas',      'Cone'),
    }

class ButtonPanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add((20, 30))
        keys = buttonDefs.keys()
        # keys.sort()
        for k in keys:
            text = buttonDefs[k][1]
            btn = wx.Button(self, k, text)
            box.Add(btn, 0, wx.ALIGN_CENTER|wx.ALL, 15)
            self.Bind(wx.EVT_BUTTON, self.OnButton, btn)

        # With this enabled, you see how you can put a GLCanvas on the wx.Panel
        if 1:
            c = CubeCanvas(self)
            c.SetMinSize((200, 200))
            box.Add(c, 0, wx.ALIGN_CENTER|wx.ALL, 15)

        self.SetAutoLayout(True)
        self.SetSizer(box)

    def OnButton(self, evt):
        if not haveGLCanvas:
            dlg = wx.MessageDialog(self,
                                   'The GLCanvas class has not been included with this build of wxPython!',
                                   'Sorry', wx.OK | wx.ICON_WARNING)
            dlg.ShowModal()
            dlg.Destroy()

        elif not haveOpenGL:
            dlg = wx.MessageDialog(self,
                                   'The OpenGL package was not found.  You can get it at\n'
                                   'http://PyOpenGL.sourceforge.net/',
                                   'Sorry', wx.OK | wx.ICON_WARNING)
            dlg.ShowModal()
            dlg.Destroy()

        else:
            canvasClassName = buttonDefs[evt.GetId()][0]
            canvasClass = eval(canvasClassName)
            cx = 0
            if canvasClassName == 'ConeCanvas': cx = 400
            frame = wx.Frame(None, -1, canvasClassName, size=(400,400), pos=(cx,400))
            canvasClass(frame) # CubeCanvas(frame) or ConeCanvas(frame); frame passed to MyCanvasBase
            frame.Show(True)

class MyCanvasBase(glcanvas.GLCanvas):
    def __init__(self, parent):
        glcanvas.GLCanvas.__init__(self, parent, -1)
        self.init = False
        self.context = glcanvas.GLContext(self)
        
        # initial mouse position
        self.lastx = self.x = 30
        self.lasty = self.y = 30
        self.size = None
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnMouseUp)
        self.Bind(wx.EVT_MOTION, self.OnMouseMotion)

    def OnEraseBackground(self, event):
        pass # Do nothing, to avoid flashing on MSW.

    def OnSize(self, event):
        wx.CallAfter(self.DoSetViewport)
        event.Skip()

    def DoSetViewport(self):
        size = self.size = self.GetClientSize()
        self.SetCurrent(self.context)
        glViewport(0, 0, size.width, size.height)
        
    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        self.SetCurrent(self.context)
        if not self.init:
            self.InitGL()
            self.init = True
        self.OnDraw()

    def OnMouseDown(self, evt):
        self.CaptureMouse()
        self.x, self.y = self.lastx, self.lasty = evt.GetPosition()

    def OnMouseUp(self, evt):
        self.ReleaseMouse()

    def OnMouseMotion(self, evt):
        if evt.Dragging() and evt.LeftIsDown():
            self.lastx, self.lasty = self.x, self.y
            self.x, self.y = evt.GetPosition()
            self.Refresh(False)

class CubeCanvas(MyCanvasBase):
    def InitGL(self):
        # set viewing projection
        glMatrixMode(GL_PROJECTION)
        glFrustum(-0.5, 0.5, -0.5, 0.5, 1.0, 3.0)

        # position viewer
        glMatrixMode(GL_MODELVIEW)
        glTranslatef(0.0, 0.0, -2.0)

        # position object
        glRotatef(self.y, 1.0, 0.0, 0.0)
        glRotatef(self.x, 0.0, 1.0, 0.0)

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)

    def OnDraw(self):
        # clear color and depth buffers
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # draw six faces of a cube
        glBegin(GL_QUADS)
        glNormal3f( 0.0, 0.0, 1.0)
        glVertex3f( 0.5, 0.5, 0.5)
        glVertex3f(-0.5, 0.5, 0.5)
        glVertex3f(-0.5,-0.5, 0.5)
        glVertex3f( 0.5,-0.5, 0.5)

        glNormal3f( 0.0, 0.0,-1.0)
        glVertex3f(-0.5,-0.5,-0.5)
        glVertex3f(-0.5, 0.5,-0.5)
        glVertex3f( 0.5, 0.5,-0.5)
        glVertex3f( 0.5,-0.5,-0.5)

        glNormal3f( 0.0, 1.0, 0.0)
        glVertex3f( 0.5, 0.5, 0.5)
        glVertex3f( 0.5, 0.5,-0.5)
        glVertex3f(-0.5, 0.5,-0.5)
        glVertex3f(-0.5, 0.5, 0.5)

        glNormal3f( 0.0,-1.0, 0.0)
        glVertex3f(-0.5,-0.5,-0.5)
        glVertex3f( 0.5,-0.5,-0.5)
        glVertex3f( 0.5,-0.5, 0.5)
        glVertex3f(-0.5,-0.5, 0.5)

        glNormal3f( 1.0, 0.0, 0.0)
        glVertex3f( 0.5, 0.5, 0.5)
        glVertex3f( 0.5,-0.5, 0.5)
        glVertex3f( 0.5,-0.5,-0.5)
        glVertex3f( 0.5, 0.5,-0.5)

        glNormal3f(-1.0, 0.0, 0.0)
        glVertex3f(-0.5,-0.5,-0.5)
        glVertex3f(-0.5,-0.5, 0.5)
        glVertex3f(-0.5, 0.5, 0.5)
        glVertex3f(-0.5, 0.5,-0.5)
        glEnd()

        if self.size is None:
            self.size = self.GetClientSize()
        w, h = self.size
        w = max(w, 1.0)
        h = max(h, 1.0)
        xScale = 180.0 / w
        yScale = 180.0 / h
        glRotatef((self.y - self.lasty) * yScale, 1.0, 0.0, 0.0);
        glRotatef((self.x - self.lastx) * xScale, 0.0, 1.0, 0.0);

        self.SwapBuffers()

class ConeCanvas(MyCanvasBase):
    def InitGL( self ):
        glMatrixMode(GL_PROJECTION)
        # camera frustrum setup
        glFrustum(-0.5, 0.5, -0.5, 0.5, 1.0, 3.0)
        glMaterial(GL_FRONT, GL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
        glMaterial(GL_FRONT, GL_DIFFUSE, [0.5, 1.0, 0.5, 1.0])
        glMaterial(GL_FRONT, GL_SPECULAR, [1.0, 0.0, 1.0, 1.0])
        glMaterial(GL_FRONT, GL_SHININESS, 50.0)
        glLight(GL_LIGHT0, GL_AMBIENT, [0.0, 1.0, 0.0, 1.0])
        glLight(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
        glLight(GL_LIGHT0, GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])
        glLight(GL_LIGHT0, GL_POSITION, [1.0, 1.0, 1.0, 0.0])
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.9, 1.0, 0.9, 1.0])
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glDepthFunc(GL_LESS)
        glEnable(GL_DEPTH_TEST)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        # position viewer
        glMatrixMode(GL_MODELVIEW)
        # position viewer
        glTranslatef(0.0, 0.0, -2.0);
        #glutInit(sys.argv)

    def OnDraw(self):
        # clear color and depth buffers
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        pts = [
          [0,0.005,-0.005],[0.001913,0.004619,-0.005],[0.003536,0.003536,-0.005],[0.004619,0.001913,-0.005],[0.005,0,-0.005],
          [0.004619,-0.001913,-0.005],[0.003536,-0.003536,-0.005],[0.001913,-0.004619,-0.005],[0,-0.005,-0.005],
          [-0.001913,-0.004619,-0.005],[-0.003536,-0.003536,-0.005],[-0.004619,-0.001913,-0.005],[-0.005,0,-0.005],
          [-0.004619,0.001913,-0.005],[-0.003536,0.003536,-0.005],[-0.001913,0.004619,-0.005],[0,0,0.005],[0,0,-0.005] ]

        # scale the points up
        pt_scale = 100
        for p in pts:
          for pi in range(3):
            p[pi] = pt_scale * p[pi]

        fcs = [
          [1,0,16],[16,2,1],[16,3,2],[16,4,3],[16,5,4],[16,6,5],[16,7,6],[16,8,7],[16,9,8],[16,10,9],[16,11,10],
          [16,12,11],[16,13,12],[16,14,13],[16,15,14],[16,0,15],[17,0,1],[17,1,2],[17,2,3],[17,3,4],[17,4,5],[17,5,6],
          [17,6,7],[17,7,8],[17,8,9],[17,9,10],[17,10,11],[17,11,12],[17,12,13],[17,13,14],[17,14,15],[15,0,17] ]

        # draw faces of a cone as triangles
        glBegin(GL_TRIANGLES)
        for f in fcs:
          # Convenience assignments to help compute the normal for this face
          p0x = pts[f[0]][0]
          p0y = pts[f[0]][1]
          p0z = pts[f[0]][2]
          p1x = pts[f[1]][0]
          p1y = pts[f[1]][1]
          p1z = pts[f[1]][2]
          p2x = pts[f[2]][0]
          p2y = pts[f[2]][1]
          p2z = pts[f[2]][2]

          # Compute a and b vectors from p1 and p2 relative to p0
          a1 = p1x - p0x
          a2 = p1y - p0y
          a3 = p1z - p0z
          b1 = p2x - p0x
          b2 = p2y - p0y
          b3 = p2z - p0z

          # Use the cross product of a x b as the normal (known to be valid)
          glNormal3f( (a2*b3)-(a3*b2), (a3*b1)-(a1*b3), (a1*b2)-(a2*b1) )

          # Provide the verticies for the triangle itself
          glVertex3f(p0x, p0y, p0z)
          glVertex3f(p1x, p1y, p1z)
          glVertex3f(p2x, p2y, p2z)

          '''
          # This version would not have normals
          glVertex3f(pts[f[0]][0],pts[f[0]][1],pts[f[0]][2])
          glVertex3f(pts[f[1]][0],pts[f[1]][1],pts[f[1]][2])
          glVertex3f(pts[f[2]][0],pts[f[2]][1],pts[f[2]][2])
          '''
        glEnd()

        if self.size is None:
            self.size = self.GetClientSize()
        w, h = self.size
        w = max(w, 1.0)
        h = max(h, 1.0)
        xScale = 180.0 / w
        yScale = 180.0 / h
        glRotatef((self.y - self.lasty) * yScale, 1.0, 0.0, 0.0);
        glRotatef((self.x - self.lastx) * xScale, 0.0, 1.0, 0.0);

        self.SwapBuffers()


class OldConeCanvas(MyCanvasBase):
    def InitGL( self ):
        glMatrixMode(GL_PROJECTION)
        # camera frustrum setup
        glFrustum(-0.5, 0.5, -0.5, 0.5, 1.0, 3.0)
        glMaterial(GL_FRONT, GL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
        glMaterial(GL_FRONT, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])
        glMaterial(GL_FRONT, GL_SPECULAR, [1.0, 0.0, 1.0, 1.0])
        glMaterial(GL_FRONT, GL_SHININESS, 50.0)
        glLight(GL_LIGHT0, GL_AMBIENT, [0.0, 1.0, 0.0, 1.0])
        glLight(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
        glLight(GL_LIGHT0, GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])
        glLight(GL_LIGHT0, GL_POSITION, [1.0, 1.0, 1.0, 0.0])
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glDepthFunc(GL_LESS)
        glEnable(GL_DEPTH_TEST)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        # position viewer
        glMatrixMode(GL_MODELVIEW)
        # position viewer
        glTranslatef(0.0, 0.0, -2.0);
        #
        #glutInit(sys.argv)


    def OnDraw(self):
        # clear color and depth buffers
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        # use a fresh transformation matrix
        glPushMatrix()
        # position object
        #glTranslate(0.0, 0.0, -2.0)
        glRotate(30.0, 1.0, 0.0, 0.0)
        glRotate(30.0, 0.0, 1.0, 0.0)

        glTranslate(0, -1, 0)
        glRotate(250, 1, 0, 0)
        glutSolidCone(0.5, 1, 30, 5)
        glPopMatrix()
        glRotatef((self.y - self.lasty), 0.0, 0.0, 1.0);
        glRotatef((self.x - self.lastx), 1.0, 0.0, 0.0);
        # push into visible buffer
        self.SwapBuffers()


#----------------------------------------------------------------------
class RunDemoApp(wx.App):
    def __init__(self):
        wx.App.__init__(self, redirect=False)

    def OnInit(self):
        frame = wx.Frame(None, -1, "RunDemo: ", pos=(0,0),
                        style=wx.DEFAULT_FRAME_STYLE, name="run a sample")
        #frame.CreateStatusBar()

        menuBar = wx.MenuBar()
        menu = wx.Menu()
        item = menu.Append(wx.ID_EXIT, "E&xit\tCtrl-Q", "Exit demo")
        self.Bind(wx.EVT_MENU, self.OnExitApp, item)
        menuBar.Append(menu, "&File")
        
        frame.SetMenuBar(menuBar)
        frame.Show(True)
        frame.Bind(wx.EVT_CLOSE, self.OnCloseFrame)

        win = runTest(frame)

        # set the frame to a good size for showing the two buttons
        frame.SetSize((200,400))
        win.SetFocus()
        self.window = win
        frect = frame.GetRect()

        self.SetTopWindow(frame)
        self.frame = frame
        return True
        
    def OnExitApp(self, evt):
        self.frame.Close(True)

    def OnCloseFrame(self, evt):
        if hasattr(self, "window") and hasattr(self.window, "ShutdownDemo"):
            self.window.ShutdownDemo()
        evt.Skip()

def runTest(frame):
    win = ButtonPanel(frame)
    return win

#__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
app = RunDemoApp()
app.MainLoop()
