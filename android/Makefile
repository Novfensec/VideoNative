# Path to your Android NDK
NDK_PATH := /path/to/android-ndk

# Target ABI and platform
ABI := arm64-v8a
API := 34

# Toolchain
TOOLCHAIN := $(NDK_PATH)/toolchains/llvm/prebuilt/linux-x86_64
CC := $(TOOLCHAIN)/bin/aarch64-linux-android$(API)-clang
CXX := $(TOOLCHAIN)/bin/aarch64-linux-android$(API)-clang++

# FFmpeg include and libs (prebuilt for Android)
FFMPEG_INCLUDE := /path/to/ffmpeg/include
FFMPEG_LIB := /path/to/ffmpeg/libs/$(ABI)

# Output
OUT_DIR := build/$(ABI)
OUT_LIB := $(OUT_DIR)/libvideo.so

# Sources
SRC := libvideo.c

# Flags
CFLAGS := -I$(FFMPEG_INCLUDE) -fPIC
LDFLAGS := -L$(FFMPEG_LIB) -lavformat -lavcodec -lavutil -lswscale -llog

all: $(OUT_LIB)

$(OUT_LIB): $(SRC)
	mkdir -p $(OUT_DIR)
	$(CC) $(CFLAGS) -shared -o $@ $^ $(LDFLAGS)

clean:
	rm -rf build