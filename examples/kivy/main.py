import os
from kivy.utils import platform
import threading
import queue

if platform == "win":
    # Replace with the path of your ffmpeg dll bin directory. Only for windows.
    os.add_dll_directory(
        os.path.join(os.path.expanduser("~"), "Downloads", "ffmpeg", "bin")
    )  

from carbonkivy.app import CarbonApp
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.graphics import RenderContext, BindTexture, Rectangle, Color
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty, NumericProperty, ColorProperty

import videonative

if platform not in ["android", "ios"]:
    Window.maximize()
Window.fullscreen = False

NV12_SHADER = """$HEADER$
uniform sampler2D tex_uv;
uniform vec4 bg_color;
uniform float video_ready;

void main(void) {
    if (video_ready < 0.5) {
        gl_FragColor = frag_color * bg_color;
    } else {
        float y = texture2D(texture0, tex_coord0).r;
        float u = texture2D(tex_uv, tex_coord0).r - 0.5;
        float v = texture2D(tex_uv, tex_coord0).a - 0.5;
        
        float r = y + 1.402 * v;
        float g = y - 0.344136 * u - 0.714136 * v;
        float b = y + 1.772 * u;
        
        gl_FragColor = frag_color * vec4(r, g, b, 1.0);
    }
}
"""

class VideoWidget(Widget):
    filename = StringProperty()
    initial_color = ColorProperty([0.0, 0.0, 0.0, 1.0])
    _running = BooleanProperty(False)
    _paused = BooleanProperty(False)
    current_pos = NumericProperty(0.0)
    duration = NumericProperty(0.0)
    current_pos_ratio = NumericProperty(0.0)
    buffering = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fps = 30.0
        self.frame_queue = queue.Queue(maxsize=3)
        self.read_thread = None
        self.decoder = None
        self._seek_lock = threading.Lock()
        
        self.width_px = 0
        self.height_px = 0
        self.tex_y = None
        self.tex_uv = None
        
        self.canvas = RenderContext(use_parent_modelview=True, use_parent_projection=True)
        self.canvas.shader.fs = NV12_SHADER
        
        with self.canvas:
            Color(1, 1, 1, 1)
            self.bind_uv = BindTexture(index=1)
            self.rect = Rectangle(size=self.size, pos=self.pos)
            
        self.canvas['tex_uv'] = 1
        self.canvas['video_ready'] = 0.0
        self.canvas['bg_color'] = list(self.initial_color)
        
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        if not self.width_px or not self.height_px:
            self.rect.pos = self.pos
            self.rect.size = self.size
            return

        widget_w, widget_h = self.size
        if widget_h == 0 or widget_w == 0:
            return

        video_ratio = self.width_px / self.height_px
        widget_ratio = widget_w / widget_h

        if widget_ratio > video_ratio:
            fit_h = widget_h
            fit_w = fit_h * video_ratio
        else:
            fit_w = widget_w
            fit_h = fit_w / video_ratio

        pos_x = self.x + (widget_w - fit_w) / 2.0
        pos_y = self.y + (widget_h - fit_h) / 2.0

        self.rect.size = (fit_w, fit_h)
        self.rect.pos = (pos_x, pos_y)

    def on_initial_color(self, instance, value):
        if self.canvas:
            self.canvas['bg_color'] = value

    def on_filename(self, *args) -> None:
        if self.filename:
            self.open_video()

    def open_video(self, *args) -> None:
        self.buffering = True
        threading.Thread(target=self._background_load, daemon=True).start()

    def _background_load(self):
        """THIS RUNS IN THE BACKGROUND: Heavy network & FFmpeg initialization."""
        try:
            temp_decoder = videonative.MediaDecoder(self.filename)
            temp_decoder.enable_gpu()
            temp_decoder.start()

            first_frame_data = temp_decoder.get_next_frame()

            if first_frame_data is None:
                raise RuntimeError("Failed to read the first frame of the video.")

            Clock.schedule_once(
                lambda dt: self._on_video_loaded(temp_decoder, first_frame_data), 0
            )

        except Exception as e:
            print(f"Video Load Error: {e}")
            Clock.schedule_once(lambda dt: setattr(self, 'buffering', False), 0)

    def _on_video_loaded(self, loaded_decoder, first_frame_data) -> None:
        """THIS RUNS ON THE UI THREAD: Safely updates Kivy widgets."""
        self.decoder = loaded_decoder
        y_bytes, uv_bytes, self.width_px, self.height_px = first_frame_data

        self.tex_y = Texture.create(size=(self.width_px, self.height_px), colorfmt='luminance')
        self.tex_y.flip_vertical()
        
        self.tex_uv = Texture.create(size=(self.width_px // 2, self.height_px // 2), colorfmt='luminance_alpha')
        self.tex_uv.flip_vertical()
        
        self.tex_y.blit_buffer(y_bytes, colorfmt='luminance', bufferfmt='ubyte')
        self.tex_uv.blit_buffer(uv_bytes, colorfmt='luminance_alpha', bufferfmt='ubyte')

        self.rect.texture = self.tex_y
        self.bind_uv.texture = self.tex_uv
        
        self.canvas['video_ready'] = 1.0
        self.canvas.ask_update()
        self._update_rect()
        
        self.duration = self.decoder.get_duration()
        self.fps = self.decoder.get_fps()
        self.buffering = False
        self.play()

    def _reader_loop(self):
        """THIS RUNS IN THE BACKGROUND: Reads frames and serializes them."""
        while self._running and self.decoder:
            frame_data = self.decoder.get_next_frame()

            if frame_data is None:
                if self._running:
                    try:
                        self.frame_queue.put(None, timeout=0.1)
                    except queue.Full:
                        pass
                break

            y_bytes, uv_bytes, _, _ = frame_data

            while self._running:
                try:
                    self.frame_queue.put((y_bytes, uv_bytes), timeout=0.1)
                    break
                except queue.Full:
                    continue

    def update_frame(self, dt) -> None:
        try:
            frame_data = self.frame_queue.get_nowait()

            if self.buffering:
                self.buffering = False

            if frame_data is None:
                self.current_pos = self.duration
                self.current_pos_ratio = 1.0
                self.pause()
                return

            y_bytes, uv_bytes = frame_data

            self.tex_y.blit_buffer(y_bytes, colorfmt='luminance', bufferfmt='ubyte')
            self.tex_uv.blit_buffer(uv_bytes, colorfmt='luminance_alpha', bufferfmt='ubyte')
            
            self.canvas.ask_update()
            self.current_pos = self.decoder.get_position()
            
            if self.duration > 0:
                self.current_pos_ratio = self.current_pos / self.duration

        except queue.Empty:
            if self.decoder:
                self.buffering = self.decoder.is_buffering()

    def play(self, *args) -> None:
        if self._running or not self.decoder:
            return

        if self.duration > 0 and self.current_pos >= self.duration - 0.2:
            self.seek(-self.current_pos)

        self._running = True
        self._paused = False

        self.decoder.start()
        self.decoder.resume()

        self.read_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.read_thread.start()

        Clock.schedule_interval(self.update_frame, 1.0 / (self.fps + 5))

    def stop(self, *args) -> None:
        self._running = False
        self._paused = False
        Clock.unschedule(self.update_frame)

        self._clear_queue()

        if self.decoder:
            self.decoder.stop()

        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=1.0)
        self.read_thread = None

    def pause(self, *args) -> None:
        self._running = False
        self._paused = True

        if self.decoder:
            self.decoder.pause()

        Clock.unschedule(self.update_frame)
        self._clear_queue()

        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=0.2)
        self.read_thread = None

    def seek(self, offset: float | int) -> None:
        if not self.decoder:
            return

        new_pos = max(0.0, min(self.duration, self.current_pos + offset))
        
        self.current_pos = new_pos
        if self.duration > 0:
            self.current_pos_ratio = self.current_pos / self.duration
            
        self.buffering = True
        was_running = self._running
        
        self._running = False
        Clock.unschedule(self.update_frame)
        if self.decoder:
            self.decoder.pause()

        threading.Thread(target=self._background_seek, args=(new_pos, was_running), daemon=True).start()

    def _background_seek(self, new_pos, was_running):
        with self._seek_lock:
            self.decoder.seek(new_pos)
            self._clear_queue()
            Clock.schedule_once(lambda dt: self._post_seek_resume(was_running), 0)

    def _post_seek_resume(self, was_running):
        self.buffering = False
        if was_running:
            self.play()
        else:
            frame_data = self.decoder.get_next_frame()
            if frame_data is not None:
                y_bytes, uv_bytes, _, _ = frame_data
                self.tex_y.blit_buffer(y_bytes, colorfmt='luminance', bufferfmt='ubyte')
                self.tex_uv.blit_buffer(uv_bytes, colorfmt='luminance_alpha', bufferfmt='ubyte')
                self.canvas.ask_update()

    def _clear_queue(self):
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

    def set_volume(self, volume: float) -> None:
        if self.decoder:
            clamped_vol = max(0.0, min(1.0, volume))
            self.decoder.set_volume(clamped_vol)

    def restart(self, url: str, *args) -> None:
        self.buffering = True
        self.stop()
        self.decoder = None

        self.current_pos = 0.0
        self.current_pos_ratio = 0.0
        self.duration = 0.0
        
        self.tex_y = None
        self.tex_uv = None
        self.rect.texture = None
        self.bind_uv.texture = None
        self.canvas['video_ready'] = 0.0
        self.canvas.ask_update()

        if self.filename == url:
            self.open_video()
        else:
            self.filename = url


class VideoApp(CarbonApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.bind(on_key_down=self._on_key_down)

    def build(self):
        return Builder.load_file(os.path.join(self.directory, "main.kv"))

    def _on_key_down(self, window, key, scancode, codepoint, modifiers):
        if key == 292: # F11
            self.maximize()
        return True

    def maximize(self, *args) -> None:
        Window.fullscreen = not Window.fullscreen


if __name__ == "__main__":
    VideoApp().run()
