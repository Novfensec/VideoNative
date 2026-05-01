cmake_minimum_required(VERSION 3.15)
project(videonative LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(PYBIND11_FINDPYTHON ON)
find_package(pybind11 CONFIG REQUIRED)

find_package(Threads REQUIRED)

if(WIN32)
    set(DEFAULT_FFMPEG_DIR "$ENV{USERPROFILE}/Downloads/ffmpeg")
    set(FFMPEG_DIR "${DEFAULT_FFMPEG_DIR}" CACHE PATH "Path to FFmpeg root directory.")

    set(FFMPEG_INCLUDE_DIRS "${FFMPEG_DIR}/include")
    set(FFMPEG_LIB_DIR "${FFMPEG_DIR}/lib")

    add_compile_definitions(NOMINMAX)
elseif(ANDROID)
    set(FFMPEG_INCLUDE_DIRS "${ANDROID_FFMPEG_INCLUDE}")
    set(FFMPEG_LIB_DIR "${ANDROID_FFMPEG_LIB}")
else()
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(FFMPEG REQUIRED IMPORTED_TARGET 
        libavformat 
        libavcodec 
        libavutil 
        libswscale 
        libswresample
    )
endif()

pybind11_add_module(videonative src/media_decoder.cpp)

target_include_directories(videonative PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}/src/include
)

if(WIN32 OR ANDROID)
    target_include_directories(videonative PRIVATE ${FFMPEG_INCLUDE_DIRS})
    target_link_directories(videonative PRIVATE ${FFMPEG_LIB_DIR})
    target_link_libraries(videonative PRIVATE
        avformat
        avcodec
        avutil
        swscale
        swresample
    )
else()
    target_link_libraries(videonative PRIVATE 
        PkgConfig::FFMPEG
        Threads::Threads
    )
endif()

if(CMAKE_CXX_COMPILER_ID MATCHES "MSVC")
    target_compile_options(videonative PRIVATE /O2)
else()
    target_compile_options(videonative PRIVATE -O3)
endif()

install(TARGETS videonative DESTINATION .)
