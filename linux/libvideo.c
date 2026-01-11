// libvideo.c
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libswscale/swscale.h>
#include <libavutil/imgutils.h>

// Structure to hold video reader context
typedef struct {
    AVFormatContext *fmt_ctx;
    AVCodecContext  *codec_ctx;
    AVFrame         *frame;
    AVFrame         *rgb_frame;
    struct SwsContext *sws_ctx;
    int video_stream_index;
    uint8_t *rgb_buffer;
    int width, height;
} VideoReader;

extern "C" {

    // Open a video file and prepare for reading frames
    VideoReader* vr_open(const char *filename) {

        VideoReader *vr = av_mallocz(sizeof(VideoReader));
        if (avformat_open_input(&vr->fmt_ctx, filename, NULL, NULL) < 0) return NULL;
        if (avformat_find_stream_info(vr->fmt_ctx, NULL) < 0) return NULL;

        vr->video_stream_index = av_find_best_stream(vr->fmt_ctx, AVMEDIA_TYPE_VIDEO, -1, -1, NULL, 0);
        AVStream *video_stream = vr->fmt_ctx->streams[vr->video_stream_index];
        const AVCodec *codec = avcodec_find_decoder(video_stream->codecpar->codec_id);

        vr->codec_ctx = avcodec_alloc_context3(codec);
        avcodec_parameters_to_context(vr->codec_ctx, video_stream->codecpar);
        avcodec_open2(vr->codec_ctx, codec, NULL);

        vr->frame = av_frame_alloc();
        vr->rgb_frame = av_frame_alloc();

        vr->width = vr->codec_ctx->width;
        vr->height = vr->codec_ctx->height;

        int num_bytes = av_image_get_buffer_size(AV_PIX_FMT_RGB24, vr->width, vr->height, 1);
        vr->rgb_buffer = (uint8_t *)av_malloc(num_bytes);
        av_image_fill_arrays(vr->rgb_frame->data, vr->rgb_frame->linesize,
                            vr->rgb_buffer, AV_PIX_FMT_RGB24,
                            vr->width, vr->height, 1);

        vr->sws_ctx = sws_getContext(vr->width, vr->height, vr->codec_ctx->pix_fmt,
                                    vr->width, vr->height, AV_PIX_FMT_RGB24,
                                    SWS_BILINEAR, NULL, NULL, NULL);

        return vr;
    }

    // Read the next frame and convert it to RGB format
    int vr_read_frame(VideoReader *vr) {
        AVPacket packet;
        while (av_read_frame(vr->fmt_ctx, &packet) >= 0) {
            if (packet.stream_index == vr->video_stream_index) {
                if (avcodec_send_packet(vr->codec_ctx, &packet) == 0) {
                    if (avcodec_receive_frame(vr->codec_ctx, vr->frame) == 0) {
                        sws_scale(vr->sws_ctx,
                                (const uint8_t * const *)vr->frame->data,
                                vr->frame->linesize,
                                0, vr->height,
                                vr->rgb_frame->data,
                                vr->rgb_frame->linesize);
                        av_packet_unref(&packet);
                        return 1;
                    }
                }
            }
            av_packet_unref(&packet);
        }
        return 0;
    }

    // Get pointer to RGB buffer
    uint8_t* vr_get_rgb(VideoReader *vr) {
        return vr->rgb_buffer;
    }

    // Get video width
    int vr_get_width(VideoReader *vr) {
        return vr->width;
    }

    // Get video height
    int vr_get_height(VideoReader *vr) {
        return vr->height;
    }

    // Close the video reader and free resources
    void vr_close(VideoReader *vr) {
        sws_freeContext(vr->sws_ctx);
        av_free(vr->rgb_buffer);
        av_frame_free(&vr->frame);
        av_frame_free(&vr->rgb_frame);
        avcodec_free_context(&vr->codec_ctx);
        avformat_close_input(&vr->fmt_ctx);
        av_free(vr);
    }

    // Get frames per second of the video
    double vr_get_fps(VideoReader *vr) {
        AVRational fr = vr->fmt_ctx->streams[vr->video_stream_index]->avg_frame_rate;
        return av_q2d(fr);
    }

}