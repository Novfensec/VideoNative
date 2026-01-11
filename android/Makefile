NDK := /path/to/android/ndk
TOOLCHAIN := $(NDK)/toolchains/llvm/prebuilt/linux-x86_64
API := 34
CC := $(TOOLCHAIN)/bin/aarch64-linux-android$(API)-clang
CXX := $(TOOLCHAIN)/bin/aarch64-linux-android$(API)-clang++
CFLAGS := -fPIC -O2 -Wall
LDFLAGS := -shared

SRC := libvideo.c
OUT := libvideo.so

all: $(OUT)

$(OUT): $(SRC)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f $(OUT)
