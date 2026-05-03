# VideoNative

[![GitHub Release](https://img.shields.io/github/v/release/novfensec/videonative?style=flat-square&color=blue)](https://github.com/novfensec/videonative/releases)
[![License](https://img.shields.io/github/license/novfensec/videonative?style=flat-square&color=green)](LICENSE)
[![Build Status](https://img.shields.io/github/actions/workflow/status/novfensec/videonative/buildozer_action.yml?style=flat-square)](https://github.com/novfensec/videonative/actions)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square&logo=python)](https://www.python.org/)

High-performance video rendering in Python powered by C++, FFmpeg, and miniaudio.

## Overview

**VideoNative** is a lightweight, low-level Python extension designed for efficient video and audio decoding. By leveraging native C++ bindings, it bridges high-performance media frameworks directly into Python applications.

### Core Dependencies
* [FFmpeg](https://ffmpeg.org/) - Industry-standard library for video decoding and scaling.
* [miniaudio](https://miniaud.io/) - Single-file audio playback and management library.

#### Runtime requirements
* [Numpy](https://numpy.org/)

---

> [!TIP]
> Looking for a complete implementation? Check out the **[CarbonPlayer](https://github.com/novfensec/CarbonPlayer)** repository for a full-fledged video player example built using this library.

## Financial Support
[![Donate via](https://img.shields.io/badge/Donate%20via-Wise-9FE870?style=for-the-badge&logo=wise&labelColor=163300)](https://wise.com/pay/business/kartavyashukla)

[![Donate via PayPal](https://img.shields.io/badge/Donate%20via-PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.me/KARTAVYASHUKLA)

## Build and Install Instructions

Select your operating system below for step-by-step setup instructions.

### Windows

#### 1. Prerequisites
Install the necessary C++ build tools and CMake using Windows Package Manager (`winget`):

```powershell
# Install Visual C++ Build Tools
winget install Microsoft.VisualStudio.BuildTools

# Install CMake
winget install Kitware.CMake
```

#### 2. Install FFmpeg Shared Libraries
Download and extract the required FFmpeg master builds:

```powershell
cd "$env:USERPROFILE\Downloads"
wget https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip -OutFile ffmpeg.zip
Expand-Archive -Path ffmpeg.zip -DestinationPath . -Force
Rename-Item -Path "ffmpeg-master-latest-win64-gpl-shared" -NewName "ffmpeg"
```

#### 3. Installation

**Option A: Direct installation via pip**
```bash
pip install https://github.com/Novfensec/VideoNative/archive/main.zip --no-cache
```

**Option B: Build the extension locally**
```bash
pip install -e .

# OR using CMake directly
mkdir build
cd build
cmake ..
cmake --build . --config Release
```

### Linux

#### 1. Prerequisites
Install the necessary development headers and media libraries:

```bash
sudo apt update
sudo apt install build-essential pkg-config ffmpeg libavcodec-dev libavformat-dev libavutil-dev libswscale-dev libswresample-dev
pip install ninja cmake
```

#### 2. Installation

**Option A: Direct installation via pip**
```bash
pip install https://github.com/Novfensec/VideoNative/archive/main.zip --no-cache
```

**Option B: Build the extension locally**
```bash
pip install -e .

# OR using CMake directly
mkdir build
cd build
cmake ..
make
```

### Android

#### Using the `python-for-android` Toolchain

To use **VideoNative** within Android environments, configure your `buildozer.spec` to use the appropriate fork and branch containing Android-specific patches:

1. Add `ffmpeg`, `videonative` and `numpy` to your application requirements:
   ```ini
   requirements = python3, kivy, ffmpeg, videonative, numpy
   ```

2. To follow the latest development configure the toolchain source or you can proceed with `p4a.branch=develop` and skip this configuration:
   ```ini
   p4a.fork = novfensec
   p4a.branch = videonative
   ```

## License

This project is licensed under the [MIT License](LICENSE). Please review the license files of the upstream dependencies [FFmpeg](https://ffmpeg.org/legal.html) and [miniaudio](https://miniaud.io/) for their respective licensing terms.
