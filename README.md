# VideoNative

A way of rendering video in kivy.

[![Donate via](https://img.shields.io/badge/Donate%20via-Wise-9FE870?style=for-the-badge&logo=wise&labelColor=163300)](https://wise.com/pay/business/kartavyashukla)

[![Donate via PayPal](https://img.shields.io/badge/Donate%20via-PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.me/KARTAVYASHUKLA)

## Build Instructions

### Windows
- Move to the `windows` directory.
    ```
    cd windows
    ```

- Install visual cpp build tools for building on windows.
    ```
    winget install Microsoft.VisualStudio.BuildTools
    ```

- [Install FFmpeg from https://gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
    ```
    winget install Gyan.FFmpeg.Shared
    ```

- Copy all files under `ffmpegdirectory/bin` folder to `./bin/windows`.

- Edit `Makefile` accordingly.

- Steps to build the dll (Windows):
    ```
    nmake clean
    nmake
    ```

After compiling move the `libvideo.dll` to `bin/windows` folder.

### Linux
- Move to `linux` directory.
    ```
    cd linux
    ```

- Install ffmpeg and other libs.
    ```
    sudo apt install ffmpeg libavcodec-dev libavformat-dev libavutil-dev libswscale-dev
    ```

- Build using make
    ```
    make clean
    make
    ```

After compiling move the `libvideo.so` to `bin/linux` folder.

### Android

#### Using [pythonforandroid](https://github.com/kivy/pythonforandroid) toolchain

- Add `videonative` and `ffmpeg` as requirements in buildozer.spec.
- Use `p4a.fork = novfensec` and `p4a.branch=videonative` to build for android.

#### Manually building from source

For building `libvideo.so` yourself compile the ffmpeg library for the android and make it available in path.
then move to `android` directory and run make.
```
cd android
make
```
