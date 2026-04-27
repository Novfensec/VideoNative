# VideoNative

Rendering videos in python.

Thanks to ffmpeg and miniaudio contributors.
miniaudio: https://miniaud.io/
ffmpeg: https://ffmpeg.org/

[![Donate via](https://img.shields.io/badge/Donate%20via-Wise-9FE870?style=for-the-badge&logo=wise&labelColor=163300)](https://wise.com/pay/business/kartavyashukla)

[![Donate via PayPal](https://img.shields.io/badge/Donate%20via-PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.me/KARTAVYASHUKLA)

## Build Instructions

### Windows

- Install visual cpp build tools for building on windows.
    ```
    winget install Microsoft.VisualStudio.BuildTools
    ```

- [Download FFmpeg](https://github.com/BtbN/FFmpeg-Builds/releases/download/)

    > Powershell commands below

    ```powershell
    cd "$env:USERPROFILE\Downloads"

    wget https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip -OutFile ffmpeg.zip

    Expand-Archive -Path ffmpeg.zip -DestinationPath . -Force

    Rename-Item -Path "ffmpeg-master-latest-win64-gpl-shared" -NewName "ffmpeg"
    ```

- Build the `videonative` extension:
    ```
    pip install build
    python -m build
    ```
    OR
    ```
    mkdir build
    cd build

    cmake ..
    cmake --build . --config Release
    ```

### Linux

- Install ffmpeg and build-essential.
    ```
    sudo apt install build-essential pkg-config ffmpeg libavcodec-dev libavformat-dev libavutil-dev libswscale-dev libswresample-dev
    ```

- Build the `videonative` extension:
    ```
    pip install build
    python -m build
    ```
    OR
    ```
    mkdir build
    cd build

    cmake ..
    make
    ```

### Android

#### Using [pythonforandroid](https://github.com/kivy/pythonforandroid) toolchain

- Add `videonative` and `ffmpeg` as requirements in buildozer.spec.
- Use `p4a.fork = novfensec` and `p4a.branch=videonative` to build for android.
