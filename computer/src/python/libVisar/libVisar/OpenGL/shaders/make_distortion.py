import numpy as np
from vispy.geometry import create_cube
from vispy.util.transforms import perspective, translate, rotate, scale
from vispy.gloo import (Program, VertexBuffer, IndexBuffer, Texture2D, clear,
                        FrameBuffer)
from vispy import gloo

from ..rift_parameters import read_mesh_txt, parameters
from ..utils import Logger


class Mesh(object):
    ''' Expect
        ('pos', np.float32, 2),
        ('red_xy', np.float32, 2),
        ('green_xy', np.float32, 2),
        ('blue_xy', np.float32, 2),
        ('vignette', np.float32, 1),
    '''
    _i_buffers, _v_buffers = read_mesh_txt.read()

    _vert_shader = '''
    #version 120
    attribute vec2 pos;
    attribute vec2 red_xy;
    attribute vec2 green_xy;
    attribute vec2 blue_xy;
    attribute float vignette;
    
    varying vec2 oRed_xy;
    varying vec2 oGreen_xy;
    varying vec2 oBlue_xy;
    varying float oVignette;
    void main() {
        gl_Position = vec4(pos.xy, 0.5, 1.0);
        oRed_xy = red_xy;
        oRed_xy.y = 1 - oRed_xy.y;
        oGreen_xy = green_xy;
        oGreen_xy.y = 1 - oGreen_xy.y;
        oBlue_xy = blue_xy;
        oBlue_xy.y = 1 - oBlue_xy.y;
        
        // These corrections are not exact...there is quite a bit of texture clipping at the bottom...not sure why
        oRed_xy = vec2(oRed_xy.x + 1.2, oRed_xy.y + 0.13);
        oGreen_xy = vec2(oGreen_xy.x + 1.2, oGreen_xy.y + 0.13);
        oBlue_xy = vec2(oBlue_xy.x + 1.2, oBlue_xy.y + 0.13);

        // oRed_xy = vec2(oRed_xy.x + 1.2, oRed_xy.y + 0.13);
        // oGreen_xy = vec2(oGreen_xy.x + 1.2, oGreen_xy.y + 0.13);

        oVignette = vignette;

        // oRed_xy = red_xy;
        // oRed_xy.y = 1.0 - oRed_xy.y;
        // oGreen_xy = green_xy;
        // oGreen_xy.y = 1.0 - oGreen_xy.y;
        // oBlue_xy = blue_xy;
        // oBlue_xy.y = 1.0 - oBlue_xy.y;

    }
    '''

    _frag_shader = '''
    #version 120
    // -> Add capability for setting "enable-aberration, disable rift-projection"
    uniform sampler2D texture;
    varying vec2 oRed_xy;
    varying vec2 oGreen_xy;
    varying vec2 oBlue_xy;
    varying float oVignette;

    void main() {

        int test = 0;
        float tex_scale = 0.1;

        float r = 0.0;
        float g = 0.0;
        float b = 0.0;


        // (This is because the FPGA uses the top right pixel to calibrate for true black)
        if (((oRed_xy.x * tex_scale) > 0.22) || ((oRed_xy.y * tex_scale) > 0.24)) {
            gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        } else {
            r = texture2D(texture, (oRed_xy * tex_scale)).r;
            g = texture2D(texture, (oGreen_xy * tex_scale)).g;
            b = texture2D(texture, (oBlue_xy * tex_scale)).b;
            gl_FragColor = vec4(r, g, b, 1);
        }

        if (test == 1) {
            if ((tex_scale * oBlue_xy.x) < 0.0) {
                b = 0.9;
            }
            if ((tex_scale * oBlue_xy.x) > 1.0) {
                b = 0.2;
            }
            if ((tex_scale * oBlue_xy.y) > 1.0) {
                r = 0.9;
            }
            if ((tex_scale * oBlue_xy.y) < 0.0) {
                r = 0.2;
            }
            gl_FragColor = vec4(r, g, b, 1);
        }

        if (test == 2) {
            gl_FragColor = vec4(oRed_xy.x * tex_scale, oRed_xy.y * tex_scale, 1, 1);
        }

    }
    '''

    @classmethod
    def make_eye(self, texture, eye):
        '''make_eye (eye_texture, eye)
        Arguments:
            - eye_texture: The texture (bound to a framebuffer), that represents the view of the eye
            - eye: 'left' or 'right', the eye being rendered
        Todo:
            - Use vertex buffer instead of manually binding
        '''
        assert isinstance(texture, Texture2D), "texture not a texture 2D instance!"
        assert eye in ['left', 'right'], eye + " is not a valid eye (Should be left or right)"

        program = Program(self._vert_shader, self._frag_shader)

        i_buffer = self._i_buffers[eye + '_indices']
        _buffer = self._v_buffers[eye + '_buffer']

        Logger.log('Loading {} eye distortion mesh pos'.format(eye))
        program['pos'] = _buffer['pos']
        Logger.log('Loading {} eye distortion mesh red_xy'.format(eye))
        program['red_xy'] = _buffer['red_xy']
        Logger.log('Loading {} eye distortion mesh green_xy'.format(eye))
        program['green_xy'] = _buffer['green_xy']
        Logger.log('Loading {} eye distortion mesh blue_xy'.format(eye))
        program['blue_xy'] = _buffer['blue_xy']
        program['vignette'] = _buffer['vignette']
        program['texture'] = texture

        return program, IndexBuffer(i_buffer)


class Distorter(object):
    def __init__(self, size=(1600, 900), no_distort=False):
        '''Distorter object: Applies distortion to Contexts and drawables

        - size (X, Y): Size of monitor
        - distortion (Bool): Apply distortion or not?
        '''
        self.size = size
        self.left_eye_tex = gloo.Texture2D(shape=(4096, 4096) + (3,))
        self.right_eye_tex = gloo.Texture2D(shape=(4096, 4096) + (3,))
        
        self.left_eye = gloo.FrameBuffer(self.left_eye_tex, gloo.RenderBuffer(self.size))
        self.right_eye = gloo.FrameBuffer(self.right_eye_tex, gloo.RenderBuffer(self.size))

        self.left_eye_program, self.left_eye_indices = Mesh.make_eye(self.left_eye_tex, 'left')
        self.right_eye_program, self.right_eye_indices = Mesh.make_eye(self.right_eye_tex, 'right')

        self.IPD = 0.0647 # Interpupilary distance in m
        # Male: 64.7 mm
        # Female: 62.3 mm

        self.L_projection = parameters.projection_left.T
        self.R_projection = parameters.projection_right.T

        self.no_distort = no_distort
        if self.no_distort:
            self.projection = perspective(30.0, 1920 / float(1080), 2.0, 10.0)
            self.draw = self.draw_no_distortion
        else:

            self.draw = self.draw_distortion

    def draw_no_distortion(self, *Contexts):
        '''Distorter WITHOUT applying distortion or chromatic aberration corrections

        FOR DEBUG
        '''
        gloo.set_clear_color('black')
        gloo.set_state(depth_test=True)
        gloo.clear(color=True, depth=True)
        for context in Contexts:
            context.set_projection(self.L_projection)
            context.draw()

    def draw_distortion(self, *Contexts):
        '''Distorter.draw(list_of_drawables)
        Draw the drawables to the right and left-eye render buffers,
        then apply the distortion and display these buffers to the screen
        TODO:
        How can we globally handle view?
        Should we even bother trying to find the 'right' way to do this?
        '''
        gloo.set_clear_color('black')
        gloo.set_state(depth_test=True)

        with self.left_eye:
            gloo.clear(color=True, depth=True)
            for context in Contexts:
                context.translate(0, self.IPD / 2, 0)
                context.set_projection(self.L_projection)
                context.draw()

        with self.right_eye:
            gloo.clear(color=True, depth=True)
            for context in Contexts:
                context.translate(0, -self.IPD / 2, 0)
                context.set_projection(self.R_projection)
                context.draw()

        gloo.clear(color=True, depth=True)
        self.left_eye_program.draw('triangles', self.left_eye_indices)
        self.right_eye_program.draw('triangles', self.right_eye_indices)