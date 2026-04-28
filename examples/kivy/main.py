import os
from kivy.utils import platform
import threading
import queue
import numpy as np

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
from kivy.properties import StringProperty, BooleanProperty

import videonative

if platform not in ["android", "ios"]:
    Window.maximize()
Window.fullscreen = False

class VideoWidget(Image):
    filename = StringProperty()
    _running = BooleanProperty(False)
    _paused = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fps = 30.0
        self.frame_queue = queue.Queue(maxsize=3)
        self.read_thread = None
        self.decoder = None

    def on_filename(self, *args) -> None:
        if self.filename:
            Clock.schedule_once(self.open_video, 1)

    def open_video(self, *args) -> None:
        self.decoder = videonative.MediaDecoder(self.filename)
        self.decoder.start()

        first_frame = self.decoder.get_next_frame()
        if first_frame is None:
            raise RuntimeError("Failed to read the first frame of the video.")

        self.height_px, self.width_px, _ = first_frame.shape

        self.texture = Texture.create(
            size=(self.width_px, self.height_px), colorfmt="rgb"
        )
        self.texture.flip_vertical()

        self.texture.blit_buffer(
            first_frame.tobytes(), colorfmt="rgb", bufferfmt="ubyte"
        )
        self.canvas.ask_update()

        self.fps = self.decoder.get_fps()
        self.play()

    def _reader_loop(self):
        """THIS RUNS IN THE BACKGROUND: Reads NumPy frames and puts them in the queue."""
        while self._running and self.decoder:
            frame_arr = self.decoder.get_next_frame()

            if frame_arr is None:
                # CRITICAL FIX: Only treat None as EOF if we didn't deliberately pause/seek
                if self._running:
                    self.frame_queue.put(None)
                break

            self.frame_queue.put(frame_arr.tobytes())

    def update_frame(self, dt) -> None:
        """THIS RUNS ON THE UI THREAD: Grabs bytes from the queue and draws them."""
        try:
            frame_bytes = self.frame_queue.get_nowait()

            if frame_bytes is None:
                self.pause()
                self.decoder.stop()
                return

            self.texture.blit_buffer(
                frame_bytes,
                size=(self.width_px, self.height_px),
                colorfmt="rgb",
                bufferfmt="ubyte",
            )
            self.canvas.ask_update()

        except queue.Empty:
            # Safe to pass here! The UI just freezes on the last frame while C++ is pre-rolling!
            pass

    def play(self, *args) -> None:
        if self._running:
            return

        self._running = True

        if self.decoder:
            self.decoder.start()
            self.decoder.resume()

        self.read_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.read_thread.start()

        Clock.schedule_interval(self.update_frame, 1.0 / self.fps)

    def stop(self, *args) -> None:
        self._running = False
        Clock.unschedule(self.update_frame)

        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=0.5)

        if self.decoder:
            self.decoder.stop()

    def pause(self, *args) -> None:
        # CRITICAL FIX: Set running to False instantly to lock out the reader thread
        self._running = False 
        
        if self.decoder:
            self.decoder.pause()
            
        Clock.unschedule(self.update_frame)

        # Clear the queue to unblock the thread if it's stuck trying to put()
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
                
        # Lowered timeout. C++ yields instantly now, so we don't need to freeze the UI for a full second
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=0.2)
            self.read_thread = None

    def seek(self, offset: float | int) -> None:
        if not self.decoder:
            return
            
        was_running = self._running
        current_pos = self.decoder.get_position()
        
        if was_running:
            self.pause() 

        new_pos = max(0.0, current_pos + offset)
        self.decoder.seek(new_pos)

        if was_running:
            self.play()

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
