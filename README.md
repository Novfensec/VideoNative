# VideoNative

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
