from __future__ import division
import numpy as np
from vispy.util.transforms import perspective, translate, rotate
from vispy.gloo import (Program, VertexBuffer, IndexBuffer, Texture2D, clear,
                        FrameBuffer)
from vispy.util.transforms import perspective, translate, xrotate, yrotate
from vispy.util.transforms import zrotate
from vispy.util.logs import set_log_level

from vispy import gloo
from vispy import app

from ..OpenGL.utils import Logger
from ..OpenGL.shaders import Distorter
from ..OpenGL.drawing import Drawable, Context
from .drawables import Example, Target, Map, Button, Brain, Toast, Battery
from .environments import Terrain
from .globals import State, Paths

import argparse

parser = argparse.ArgumentParser(description='Display the VisAR augmented reality.')
parser.add_argument('-d', '--draw_terrain', dest='draw_terrain', action='store_true',
                   default=False,
                   help='Draw simulated terrain')
parser.add_argument('-na', '--no_audio', dest='no_audio', action='store_true',
                   default=False,
                   help='Disable audio')
parser.add_argument('-f', '--fullscreen', dest='full', action='store_true',
                    default=False,
                    help='Launch visar program in Fullscreen mode')
parser.add_argument('-n', '--no_distort', dest='no_distort', action='store_true',
                   default=False,
                   help='Skip applying the distortion (For debugging)')
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                    default=False,
                    help='Verbose output')
parser.add_argument('-b', '--debug', dest='debug', action='store_true',
                    default=False,
                    help='Vispy debug output')
parser.add_argument('--npbrain', dest='brain', action='store_true',
                    default=False,
                    help='Use a demo brain')


args = parser.parse_args()

# Presets
FPS = 60 # Maximum FPS (how often needs_update is checked)

class Renderer(app.Canvas): # Canvas is a GUI object
    def __init__(self, size=(1980, 1020)):    

        app.Canvas.__init__(self, keys='interactive')
        self.size = size 
        
        # Create a rendering context (A render list)
        Logger.set_verbosity('log')
        renders = [
            # Target((738585.65, -5498364.10, 3136365.42), color=(0.2, 0.8, 0.4)),
            # Target((0.0, 10.0, 0.0), color=(0.2, 0.8, 0.4)),
            # Target((10.0, 10.0, 0.0), color=(0.2, 0.8, 0.4)),

        ]

        # fault tolerant map initialization
        self.map_ob = Map()
        UI_elements = [
            self.map_ob,
            #Toast(self),
            Button('Toggle Map', self, position=1),
            Button('Make Call', self, position=3),
            Button('End Call', self, position=2),
            Button('Start Voice', self, position=4),
            Button('Stop Voice', self, position=5),
            Battery(),
        ]

        #fault tolerant map initialization
        #try:    
        #    self.map_ob = Map()
        #    UI_elements.append(map_ob)
        #except: 
        #    self.map_ob = None
        #    Logger.warn("Failed to Initialize the map")        
        self.hide_map = False

        self.view = np.eye(4)
        self.Render_List = Context(*renders)
        if args.brain:
            self.Render_List.append(Brain())
        if args.draw_terrain:
            terrain = Terrain()
            self.Render_List.append(terrain)

        if args.verbose:
            set_log_level(True)
            Logger.set_verbosity('log')
        else:
            set_log_level('error')
            Logger.set_verbosity('warn')
        if args.debug:
            set_log_level('debug')

        self.projection = perspective(30.0, 1920 / float(1080), 2.0, 10.0)
        self.Render_List.set_projection(self.projection)
        self.Render_List.set_view(self.view)

        self.UI_elements = Context(*UI_elements)
        self.UI_elements.set_projection(self.projection)

        # Create the distorter
        self.Distorter = Distorter(self.size, no_distort=args.no_distort)

        # Set an update timer to run every FPS
        self.interval = 1 / FPS
        self._timer = app.Timer('auto', connect=self.on_timer, start=True)
  
    def on_timer(self, event):
        if State.shutdown_flag: self.close() # shutdown if signaled
       
        '''
        if not State.hide_map == self.hide_map:
            if State.hide_map and self.map_ob is not None:
                self.Render_List.remove(map_ob)
            elif not State.hide_map and self.map_ob is not None:
                self.Render_List.remove(map_ob)
            
            self.hide_map = State.hide_map
        '''
        
        # Update and draw
        self.Render_List.set_view(State.orientation_matrix)

        Target.do_update(State.targets, self.Render_List, self.projection) # update the targets
        self.Render_List.update()
        self.UI_elements.update()
        self.update()

    def on_resize(self, event):
        width, height = event.size
        gloo.set_viewport(0, 0, width, height)
        self.Render_List.on_resize()
    
    def on_draw(self, event):
        # Draw each drawable using the distorter
        gloo.set_viewport(0, 0, *self.size)
        self.Distorter.draw(self.Render_List, self.UI_elements)

    def on_key_press(self, event):
        """Controls -
        a(A) - move left
        d(D) - move right
        w(W) - move up
        s(S) - move down
        x/X - rotate about x-axis cw/anti-cw
        y/Y - rotate about y-axis cw/anti-cw
        z/Z - rotate about z-axis cw/anti-cw
        space - reset view
        p(P) - print current view
        i(I) - zoom in
        o(O) - zoom out
        """
        self.translate = [0, 0, 0]
        self.rotate = [0, 0, 0]

        # print event.text
        if(event.text == 'p' or event.text == 'P'):
            print(self.view)
        # '''
        elif(event.text == 'd' or event.text == 'D'):
            self.translate[0] = 0.3
        elif(event.text == 'a' or event.text == 'A'):
            self.translate[0] = -0.3
        elif(event.text == 'w' or event.text == 'W'):
            self.translate[1] = 0.3
        elif(event.text == 's' or event.text == 'S'):
            self.translate[1] = -0.3
        elif(event.text == 'o' or event.text == 'O'):
            self.translate[2] = 0.3
        elif(event.text == 'i' or event.text == 'I'):
            self.translate[2] = -0.3
        elif(event.text == 'x'):
            self.rotate = [1, 0, 0]
        elif(event.text == 'X'):
            self.rotate = [-1, 0, 0]
        elif(event.text == 'y'):
            self.rotate = [0, 1, 0]
        elif(event.text == 'Y'):
            self.rotate = [0, -1, 0]
        elif(event.text == 'z'):
            self.rotate = [0, 0, 1]
        elif(event.text == 'Z'):
            self.rotate = [0, 0, -1]
        # '''
        elif(event.text == 'B'):
            State.shutdown_flag = True
        elif(event.text == ' ' or event.key == 'Space'):
            State.make_call()
            return
            # '''
            default_view = np.array(
            [[0.8, 0.2, -0.48, 0],
             [-0.5, 0.3, -0.78, 0],
             [-0.01, 0.9, -0.3, 0],
             [-4.5, -21.5, -7.4, 1]],
             dtype=np.float32
            )

            self.view = default_view
            # '''
        elif(event.text == '['):
            State.button_up()
        elif(event.text == ']'):
            State.button_down()
        elif event.key == 'Up':
            State.button_up()
        elif event.key == 'Down':
            State.button_down()
        elif event.key == 'Enter':
            State.press_enter()
        # elif event.key is not None and event.text is not None:
        #     Logger.warn('Unrecognized key', event.text, event.key)

        # '''
        # translate(self.view, -self.translate[0], -self.translate[1],
        #           -self.translate[2])
        # xrotate(self.view, self.rotate[0])
        # yrotate(self.view, self.rotate[1])
        # zrotate(self.view, self.rotate[2])
        
        # self.Render_List.translate(-self.translate[0], -self.translate[1], -self.translate[2])
        # State.set_orientation_matrix(self.view)
        # '''
    
def main():
    if(args.no_audio): 
        State.do_init(audio=False) # initialize the state objects/threads
    else:
        State.do_init(audio=True) # initialize the state objects/threads
    app.use_app(backend_name='PyGlet')
    c = Renderer()
    c.show()
    if(args.full): c.fullscreen = True # fullscreen mode
    c.app.run()
    State.destroy()

    Logger.warn('Exiting VisAR')

if __name__ == '__main__':
    main()
