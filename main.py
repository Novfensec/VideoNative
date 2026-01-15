import os
import ctypes
import sounddevice as sd
import numpy as np
import threading
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
lib.vr_get_duration.argtypes = [ctypes.c_void_p]
lib.vr_get_duration.restype = ctypes.c_int64
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
lib.vr_stop.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.vr_stop.restype = ctypes.c_int
lib.vr_read_audio.argtypes = [ctypes.c_void_p]
lib.vr_read_audio.restype = ctypes.c_int
lib.vr_get_audio.argtypes = [ctypes.c_void_p]
lib.vr_get_audio.restype = ctypes.c_void_p
lib.vr_get_audio_size.argtypes = [ctypes.c_void_p]
lib.vr_get_audio_size.restype = ctypes.c_int
lib.vr_get_sample_rate.argtypes = [ctypes.c_void_p]
lib.vr_get_sample_rate.restype = ctypes.c_int

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
        self.audio_rate = lib.vr_get_sample_rate(self.vr)
        self.audio_channels = 2
        rate = lib.vr_get_sample_rate(self.vr)
        if rate <= 0 or rate not in (44100, 48000):
            rate = 44100
        self.audio_stream = sd.OutputStream(samplerate=rate, channels=2, dtype='int16')
        self.audio_stream.start()

        self.width_px = lib.vr_get_width(self.vr)
        self.height_px = lib.vr_get_height(self.vr)

        self.texture = Texture.create(size=(self.width_px, self.height_px), colorfmt='rgb')
        self.texture.flip_vertical()

        self.fps = lib.vr_get_fps(self.vr)
        self.play(self.fps)

    def update_frame(self, *args) -> None:
        if lib.vr_read_frame(self.vr) == 1:
            buf_ptr = lib.vr_get_rgb(self.vr)
            size = self.width_px * self.height_px * 3
            buf = memoryview((ctypes.c_ubyte * size).from_address(ctypes.cast(buf_ptr, ctypes.c_void_p).value))
            self.texture.blit_buffer(buf,
                                    size=(self.width_px, self.height_px),
                                    colorfmt='rgb',
                                    bufferfmt='ubyte')
            self.canvas.ask_update()
        else:
            self.pause()
            lib.vr_stop(self.vr, 0)

    def play_audio(self, *args) -> None:
        while lib.vr_read_audio(self.vr) == 1 and self._running:
            buf_ptr = lib.vr_get_audio(self.vr)
            size    = lib.vr_get_audio_size(self.vr)
            if buf_ptr and size > 0:
                array_type = ctypes.c_ubyte * size
                raw_array  = array_type.from_address(buf_ptr)
                buf        = memoryview(raw_array)
                samples = np.frombuffer(buf, dtype=np.int16)
                samples = samples.reshape(-1, 2)  # shape (frames, channels)
                self.audio_stream.write(samples)

    def play(self, *args)-> None:
        try:
            lib.vr_read_frame(self.vr)
        except:
            lib.vr_stop(self.vr, 0)
            self.open_video()
            return
        Clock.schedule_interval(self.update_frame, 1.0 / self.fps)
        self._running = True
        threading.Thread(target=self.play_audio, daemon=True).start()

    def stop(self, *args) -> None:
        Clock.unschedule(self.update_frame)
        self._running = False
        if self.vr:
            lib.vr_stop(self.vr, 1)
            self.update_frame()

    def pause(self, *args) -> None:
        Clock.unschedule(self.update_frame)
        self._running = False

    def seek(self, direction: str, offset: float | int) -> None:
        if direction == "forward":
            lib.vr_seek_forward(self.vr, offset)
        else:
            lib.vr_seek_backward(self.vr, offset)
        self.update_frame()


class VideoApp(CarbonApp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.bind(on_key_down=self._on_key_down)

    def build(self):
        return Builder.load_file(os.path.join(self.directory, "main.kv"))

    def _on_key_down(self, window, key, scancode, codepoint, modifiers):
        # F11 key has keycode 292 on most systems
        print(key)
        if key == 292:  
            self.maximize()
        return True

    def maximize(self, *args) -> None:
        if Window.fullscreen:
            Window.fullscreen = False
        else:
            Window.fullscreen = True

    def on_stop(self):
        if hasattr(self.root.ids.video_widget, 'audio_stream'):
            self.root.ids.video_widget.audio_stream.stop()
            self.root.ids.video_widget.audio_stream.close()
        lib.vr_close(self.root.ids.video_widget.vr)
        return super().on_stop()

if __name__ == "__main__":
    VideoApp().run()