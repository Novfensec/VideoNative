# VideoNative

A way of rendering video in kivy.

[![Donate via](https://img.shields.io/badge/Donate%20via-Wise-9FE870?style=for-the-badge&logo=wise&labelColor=163300)](https://wise.com/pay/business/kartavyashukla)

[![Donate via PayPal](https://img.shields.io/badge/Donate%20via-PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.me/KARTAVYASHUKLA)

## Build Instructions

### Windows
Install visual cpp build tools for building on windows.
```
winget install Microsoft.VisualStudio.BuildTools
```

[Install FFmpeg from https://gyan.dev](https://www.gyan.dev/ffmpeg/builds/)

```
winget install Gyan.FFmpeg.Shared
```

Copy all files under `ffmpegdirectory/bin` folder to `./bin/windows`.

Steps to build the dll (Windows):

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

Move the compiled `libvideo.so` to bin/linux folder.
