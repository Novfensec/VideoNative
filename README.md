# VideoNative

Rendering videos in python.

Thanks to ffmpeg and miniaudio contributors.
miniaudio: https://miniaud.io/
ffmpeg: https://ffmpeg.org/

## Build and Install Instructions

### Windows

- Install visual cpp build tools for building on windows.
    ```powershell
    winget install Microsoft.VisualStudio.BuildTools
    ```

- Download FFmpeg:
    ```powershell
    cd "$env:USERPROFILE\Downloads"
    wget https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip -OutFile ffmpeg.zip
    Expand-Archive -Path ffmpeg.zip -DestinationPath . -Force
    Rename-Item -Path "ffmpeg-master-latest-win64-gpl-shared" -NewName "ffmpeg"
    ```

- Install via pip:
    ```bash
    pip install https://github.com/Novfensec/VideoNative/archive/main.zip --no-cache
    ```

OR

- Build the `videonative` extension:
    ```bash
    pip install build
    python -m build
    ```
    OR
    ```bash
    mkdir build
    cd build
    cmake ..
    cmake --build . --config Release
    ```

### Linux

- Install ffmpeg and build-essential.
    ```bash
    sudo apt install build-essential pkg-config ffmpeg libavcodec-dev libavformat-dev libavutil-dev libswscale-dev libswresample-dev
    ```

- Install via pip:
    ```bash
    pip install https://github.com/Novfensec/VideoNative/archive/main.zip --no-cache
    ```

OR

- Build the `videonative` extension:
    ```bash
    pip install build
    python -m build
    ```
    OR
    ```bash
    mkdir build
    cd build
    cmake ..
    make
    ```

### Android

#### Using python-for-android toolchain

- Add `ffmpeg` and `videonative` as requirements in buildozer.spec.
- Use `p4a.fork = novfensec` and `p4a.branch = videonative` to build for android with buildozer.
