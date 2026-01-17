# Makefile for building libvideo.dll with MSVC cl

FFMPEG_INC="your/ffmpeg/dir/ffmpeg-8.0.1-full_build-shared\include"
FFMPEG_LIB="your/ffmpeg/dir/ffmpeg-8.0.1-full_build-shared\lib"

# Compiler and linker flags
CFLAGS=/LD /I $(FFMPEG_INC)
LDFLAGS=/LIBPATH:$(FFMPEG_LIB) avformat.lib avcodec.lib avutil.lib swscale.lib swresample.lib

# Target
TARGET=libvideo.dll
OBJS=libvideo.obj

all: $(TARGET)

$(TARGET): libvideo.c
	cl $(CFLAGS) libvideo.c /link $(LDFLAGS) /OUT:$(TARGET) /IMPLIB:libvideo.lib

clean:
	del $(OBJS) $(TARGET) libvideo.lib libvideo.exp