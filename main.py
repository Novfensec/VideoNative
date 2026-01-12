import os
import ctypes
from carbonkivy.app import CarbonApp
from kivy.utils import platform
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty

Window.maximize()
Window.fullscreen = False

if platform == "win":
    lib = ctypes.CDLL(os.path.abspath(os.path.join(os.path.dirname(__file__), "bin", "windows", "libvideo.dll")))
elif platform == "linux":
    lib = ctypes.CDLL(os.path.abspath(os.path.join(os.path.dirname(__file__), "bin", "linux", "libvideo.so")))
elif platform == "android":
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    mActivity = PythonActivity.mActivity
    libs_dir = mActivity.getApplicationInfo().nativeLibraryDir
    lib = ctypes.CDLL(os.path.join(libs_dir, "libvideo.so"))

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
lib.vr_get_pts.argtypes = [ctypes.c_void_p]
lib.vr_get_pts.restype = ctypes.c_double
lib.vr_seek_forward.argtypes = [ctypes.c_void_p, ctypes.c_double]
lib.vr_seek_forward.restype  = ctypes.c_int
lib.vr_seek_backward.argtypes = [ctypes.c_void_p, ctypes.c_double]
lib.vr_seek_backward.restype  = ctypes.c_int


class VideoWidget(Image):

    filename = StringProperty()

    _running = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fps = 30.0

    def on_filename(self, *args) -> None:
        if self.filename:
            self.open_video()

    def open_video(self, *args) -> None:
        self.vr = lib.vr_open(self.filename.encode('utf-8'))
        if not self.vr:
            raise RuntimeError("Failed to open video")

        self.width_px = lib.vr_get_width(self.vr)
        self.height_px = lib.vr_get_height(self.vr)

        self.texture = Texture.create(size=(self.width_px, self.height_px), colorfmt='rgb')
        self.texture.flip_vertical()

        self.fps = lib.vr_get_fps(self.vr)
        self.play(self.fps)

    def update_frame(self, dt):
        if lib.vr_read_frame(self.vr):
            buf_ptr = lib.vr_get_rgb(self.vr)
            size = self.width_px * self.height_px * 3
            # buf = ctypes.string_at(buf_ptr, size)
            buf = memoryview((ctypes.c_ubyte * size).from_address(ctypes.cast(buf_ptr, ctypes.c_void_p).value))
            self.texture.blit_buffer(buf,
                                    size=(self.width_px, self.height_px),
                                    colorfmt='rgb',
                                    bufferfmt='ubyte')
            self.canvas.ask_update()
        else:
            self.stop()

    def play(self, *args)-> None:
        try:
            lib.vr_read_frame(self.vr)
        except:
            self.open_video()
            return
        Clock.schedule_interval(self.update_frame, 1.0 / self.fps)
        self._running = True

    def stop(self, *args) -> None:
        Clock.unschedule(self.update_frame)
        self._running = False
        lib.vr_close(self.vr)

    def pause(self, *args) -> None:
        Clock.unschedule(self.update_frame)
        self._running = False

    def seek(self, direction: str, offset: float | int) -> None:
        try:
            lib.vr_read_frame(self.vr)
        except:
            self.open_video()
            return
        current_time = lib.vr_get_pts(self.vr)
        if direction == "forward":
            new_time = current_time + offset
            lib.vr_seek_forward(self.vr, new_time)
        else:
            new_time = current_time - offset
            lib.vr_seek_backward(self.vr, new_time)




class VideoApp(CarbonApp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.bind(on_key_down=self._on_key_down)

    def build(self):
        return Builder.load_file(os.path.join(self.directory, "main.kv"))

        # return VideoWidget(os.path.join(self.directory, "sample4k.mp4"))
    def _on_key_down(self, window, key, scancode, codepoint, modifiers):
        # F11 key has keycode 293 on most systems
        print(key)
        if key == 292:  
            self.maximize()
        return True

    def maximize(self, *args) -> None:
        if Window.fullscreen:
            Window.fullscreen = False
        else:
            Window.fullscreen = True

if __name__ == "__main__":
    VideoApp().run()