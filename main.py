import os
import ctypes
from kivy.app import App
from kivy.utils import platform
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.window import Window

Window.maximize()

if platform == "win":
    lib = ctypes.CDLL(os.path.abspath(os.path.join(os.path.dirname(__file__), "bin", "windows", "libvideo.dll")))
elif platform == "linux":
    lib = ctypes.CDLL(os.path.abspath(os.path.join(os.path.dirname(__file__), "bin", "linux", "libvideo.so")))

lib.vr_open.argtypes = [ctypes.c_char_p]
lib.vr_open.restype = ctypes.c_void_p
lib.vr_read_frame.argtypes = [ctypes.c_void_p]
lib.vr_read_frame.restype = ctypes.c_int
lib.vr_get_rgb.argtypes = [ctypes.c_void_p]
lib.vr_get_rgb.restype = ctypes.POINTER(ctypes.c_uint8)
lib.vr_get_width.argtypes = [ctypes.c_void_p]
lib.vr_get_width.restype = ctypes.c_int
lib.vr_get_height.argtypes = [ctypes.c_void_p]
lib.vr_get_height.restype = ctypes.c_int
lib.vr_close.argtypes = [ctypes.c_void_p]
lib.vr_close.restype = None
lib.vr_get_fps.argtypes = [ctypes.c_void_p]
lib.vr_get_fps.restype = ctypes.c_double


class VideoWidget(Image):
    def __init__(self, filename, **kwargs):
        super().__init__(**kwargs)
        self.vr = lib.vr_open(filename.encode('utf-8'))
        if not self.vr:
            raise RuntimeError("Failed to open video")

        self.width_px = lib.vr_get_width(self.vr)
        self.height_px = lib.vr_get_height(self.vr)

        self.texture = Texture.create(size=(self.width_px, self.height_px), colorfmt='rgb')
        self.texture.mag_filter = 'linear'
        self.texture.min_filter = 'linear'
        self.texture.flip_vertical()

        fps = lib.vr_get_fps(self.vr)
        Clock.schedule_interval(self.update_frame, 1.0 / fps)

    def update_frame(self, dt):
        if lib.vr_read_frame(self.vr):
            buf_ptr = lib.vr_get_rgb(self.vr)
            size = self.width_px * self.height_px * 3
            buf = ctypes.string_at(buf_ptr, size)

            self.texture.blit_buffer(buf,
                                    size=(self.width_px, self.height_px),
                                    colorfmt='rgb',
                                    bufferfmt='ubyte')
            self.canvas.ask_update()
        else:
            Clock.unschedule(self.update_frame)
            lib.vr_close(self.vr)

class VideoApp(App):
    def build(self):
        return VideoWidget("sample.mp4")

if __name__ == "__main__":
    VideoApp().run()