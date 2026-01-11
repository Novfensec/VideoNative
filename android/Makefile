# Android NDK setup
NDK := /path/to/android-ndk
TOOLCHAIN := $(NDK)/toolchains/llvm/prebuilt/linux-x86_64
API := 34
CC := $(TOOLCHAIN)/bin/aarch64-linux-android$(API)-clang

# Paths to FFmpeg headers and libs (adjust to your build output)
FFMPEG_INCLUDE := $(PWD)/include
FFMPEG_LIB := $(PWD)/lib

# Compiler and linker flags
CFLAGS := -fPIC -O2 -Wall -I$(FFMPEG_INCLUDE)
LDFLAGS := -shared -L$(FFMPEG_LIB) \
           -lavcodec -lavformat -lavutil -lswresample -lswscale

# Sources and output
SRC := libvideo.c
OBJ := $(SRC:.c=.o)
OUT := libvideo.so

# Default target
all: $(OUT)

# Rule to build .so
$(OUT): $(OBJ)
	$(CC) -o $@ $^ $(LDFLAGS)

# Rule to build .o files
%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# Clean
clean:
	rm -f $(OBJ) $(OUT)