# Compiler
CC = gcc

# Output library
TARGET = libvideo.so

# Sources
SRC = libvideo.c

# Flags
CFLAGS = -fPIC
LDFLAGS = -shared
PKGCONFIG = $(shell pkg-config --cflags --libs libavformat libavcodec libavutil libswscale)

# Default rule
all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ $(PKGCONFIG)

clean:
	rm -f $(TARGET)