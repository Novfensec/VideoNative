import os
from kivy.utils import platform
import threading
import queue

if platform == "win":
    os.add_dll_directory(
        os.path.join(os.path.expanduser("~"), "Downloads", "ffmpeg", "bin")
    )  # Replace with the path of your ffmpeg dll bin directory. Only for windows.

from carbonkivy.app import CarbonApp
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty, NumericProperty, ObjectProperty

import videonative

if platform not in ["android", "ios"]:
    Window.maximize()
Window.fullscreen = False

class VideoWidget(Image):

    filename = StringProperty()

    _running = BooleanProperty(False)

    was_running = BooleanProperty(False)

    _paused = BooleanProperty(False)

    current_pos = NumericProperty()

    duration = NumericProperty()

    current_pos_ratio = NumericProperty()

    buffering = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fps = 30.0
        self.frame_queue = queue.Queue(maxsize=3)
        self.read_thread = None
        self.decoder = None

    def on_filename(self, *args) -> None:
        if self.filename:
            self.open_video()

    def open_video(self, *args) -> None:
        threading.Thread(target=self._background_load, daemon=True).start()

    def _background_load(self):
        """THIS RUNS IN THE BACKGROUND: Heavy network & FFmpeg initialization."""
        try:
            temp_decoder = videonative.MediaDecoder(self.filename)
            temp_decoder.start()

            first_frame = temp_decoder.get_next_frame()

            if first_frame is None:
                raise RuntimeError("Failed to read the first frame of the video.")

            Clock.schedule_once(
                lambda dt: self._on_video_loaded(temp_decoder, first_frame), 0
            )

        except Exception as e:
            print(f"Video Load Error: {e}")

    def _on_video_loaded(self, loaded_decoder, first_frame) -> None:
        """THIS RUNS ON THE UI THREAD: Safely updates Kivy widgets."""
        self.decoder = loaded_decoder

        self.height_px, self.width_px, _ = first_frame.shape

        self.texture = Texture.create(
            size=(self.width_px, self.height_px), colorfmt="rgb"
        )
        self.texture.flip_vertical()

        self.texture.blit_buffer(
            first_frame.tobytes(), colorfmt="rgb", bufferfmt="ubyte"
        )
        self.canvas.ask_update()
        self.duration = self.decoder.get_duration()
        self.fps = self.decoder.get_fps()
        self.play()

    def _reader_loop(self):
        """THIS RUNS IN THE BACKGROUND: Reads NumPy frames and puts them in the queue."""
        while self._running and self.decoder:
            frame_arr = self.decoder.get_next_frame()

            if frame_arr is None:
                if self._running:
                    try:
                        self.frame_queue.put(None, timeout=0.1)
                    except queue.Full:
                        pass
                break

            while self._running:
                try:
                    self.frame_queue.put(frame_arr.tobytes(), timeout=0.1)
                    break
                except queue.Full:
                    continue

    def update_frame(self, dt) -> None:
        try:
            frame_bytes = self.frame_queue.get_nowait()

            if self.buffering:
                self.buffering = False

            if frame_bytes is None:
                self.current_pos = self.duration
                self.current_pos_ratio = 1.0
                self.pause()
                return

            self.texture.blit_buffer(
                frame_bytes,
                size=(self.width_px, self.height_px),
                colorfmt="rgb",
                bufferfmt="ubyte",
            )
            self.canvas.ask_update()
            self.current_pos = self.decoder.get_position()
            self.current_pos_ratio = self.current_pos / self.duration

        except queue.Empty:
            if self.decoder:
                self.buffering = self.decoder.is_buffering()

    def play(self, *args) -> None:
        if self._running:
            return

        if self.duration > 0 and self.current_pos >= self.duration - 0.2:
            self.seek(-self.current_pos)

        self._running = True
        self._paused = False

        if self.decoder:
            self.decoder.start()
            self.decoder.resume()

        self.read_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.read_thread.start()

        Clock.schedule_interval(self.update_frame, 1.0 / self.fps)

    def stop(self, *args) -> None:
        self._running = False
        self._paused = False
        Clock.unschedule(self.update_frame)

        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

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

        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=0.2)
            self.read_thread = None

    def seek(self, offset: float | int) -> None:
        if not self.decoder:
            return

        was_running = self._running
        new_pos = max(0.0, min(self.duration, self.current_pos + offset))

        self.current_pos = new_pos
        self.current_pos_ratio = self.current_pos / self.duration

        self._running = False
        Clock.unschedule(self.update_frame)

        if self.decoder:
            self.decoder.pause()

        self.decoder.seek(new_pos)

        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=1.0)
        self.read_thread = None

        if was_running:
            self.play()

    def on_buffering(self, *args) -> None:
        print("Buffering.....")

    def set_volume(self, volume: float) -> None:
        if self.decoder:
            clamped_vol = max(0.0, min(1.0, volume))
            self.decoder.set_volume(clamped_vol)

    def restart(self, url: str, *args) -> None:
        """Safely stops the current video, frees memory, and starts a new one."""
        self.buffering = True

        self.stop()
        self.decoder = None

        self.current_pos = 0.0
        self.current_pos_ratio = 0.0
        self.duration = 0.0

        self.texture = None
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
