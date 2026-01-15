// libvideo.c
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libswscale/swscale.h>
#include <libavutil/imgutils.h>
#include <libswresample/swresample.h>

// Structure to hold video + audio reader context
typedef struct
{
    AVFormatContext *fmt_ctx;
    AVCodecContext *codec_ctx;
    AVFrame *frame;
    AVFrame *rgb_frame;
    struct SwsContext *sws_ctx;
    int video_stream_index;
    uint8_t *rgb_buffer;
    int width, height;

    AVCodecContext *audio_ctx;
    AVFrame *audio_frame;
    struct SwrContext *swr_ctx;
    int audio_stream_index;
    uint8_t *audio_buffer;
    int audio_buffer_size;
    int audio_sample_rate;
    int audio_channels;
} VideoReader;

// Open a video file and prepare for reading frames
__declspec(dllexport) VideoReader *vr_open(const char *filename)
{

    VideoReader *vr = av_mallocz(sizeof(VideoReader));
    if (avformat_open_input(&vr->fmt_ctx, filename, NULL, NULL) < 0)
        return NULL;
    if (avformat_find_stream_info(vr->fmt_ctx, NULL) < 0)
        return NULL;

    vr->video_stream_index = av_find_best_stream(vr->fmt_ctx, AVMEDIA_TYPE_VIDEO, -1, -1, NULL, 0);
    AVStream *video_stream = vr->fmt_ctx->streams[vr->video_stream_index];
    const AVCodec *codec = avcodec_find_decoder(video_stream->codecpar->codec_id);

    vr->audio_stream_index = av_find_best_stream(vr->fmt_ctx, AVMEDIA_TYPE_AUDIO, -1, -1, NULL, 0);
    AVStream *audio_stream = vr->fmt_ctx->streams[vr->audio_stream_index];
    const AVCodec *audio_codec = avcodec_find_decoder(audio_stream->codecpar->codec_id);

    vr->codec_ctx = avcodec_alloc_context3(codec);
    avcodec_parameters_to_context(vr->codec_ctx, video_stream->codecpar);
    avcodec_open2(vr->codec_ctx, codec, NULL);

    vr->audio_ctx = avcodec_alloc_context3(audio_codec);
    if (avcodec_parameters_to_context(vr->audio_ctx, audio_stream->codecpar) < 0)
        NULL;
    if (avcodec_open2(vr->audio_ctx, audio_codec, NULL) < 0)
        NULL;

    vr->frame = av_frame_alloc();
    vr->rgb_frame = av_frame_alloc();
    vr->audio_frame = av_frame_alloc();

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

    AVChannelLayout out_ch_layout;
    av_channel_layout_default(&out_ch_layout, 2);

    if (swr_alloc_set_opts2(
            &vr->swr_ctx,
            &out_ch_layout,
            AV_SAMPLE_FMT_S16,
            vr->audio_ctx->sample_rate,
            &vr->audio_ctx->ch_layout,
            vr->audio_ctx->sample_fmt,
            vr->audio_ctx->sample_rate,
            0, NULL) == 0)
    {
        swr_init(vr->swr_ctx);
    }
    return vr;
}

// Read the next frame and convert it to RGB format
__declspec(dllexport) int vr_read_frame(VideoReader *vr)
{
    AVPacket packet;
    while (av_read_frame(vr->fmt_ctx, &packet) >= 0)
    {
        if (packet.stream_index == vr->video_stream_index)
        {
            if (avcodec_send_packet(vr->codec_ctx, &packet) == 0)
            {
                if (avcodec_receive_frame(vr->codec_ctx, vr->frame) == 0)
                {
                    sws_scale(vr->sws_ctx,
                              (const uint8_t *const *)vr->frame->data,
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

//
__declspec(dllexport) int vr_read_audio(VideoReader *vr)
{
    AVPacket packet;
    while (av_read_frame(vr->fmt_ctx, &packet) >= 0)
    {
        if (packet.stream_index == vr->audio_stream_index)
        {
            if (avcodec_send_packet(vr->audio_ctx, &packet) == 0)
            {
                while (avcodec_receive_frame(vr->audio_ctx, vr->audio_frame) == 0)
                {
                    int nb_samples = vr->audio_frame->nb_samples;
                    int out_linesize;

                    if (vr->audio_buffer)
                        av_freep(&vr->audio_buffer);

                    av_samples_alloc(&vr->audio_buffer, &out_linesize,
                                     2, nb_samples, AV_SAMPLE_FMT_S16, 1);

                    int converted = swr_convert(vr->swr_ctx,
                                                &vr->audio_buffer, nb_samples,
                                                (const uint8_t **)vr->audio_frame->data,
                                                nb_samples);

                    vr->audio_buffer_size = av_samples_get_buffer_size(
                        &out_linesize,
                        2, converted,
                        AV_SAMPLE_FMT_S16, 1);

                    vr->audio_sample_rate = vr->audio_ctx->sample_rate;
                    vr->audio_channels = 2;

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
__declspec(dllexport) uint8_t *vr_get_rgb(VideoReader *vr)
{
    return vr->rgb_buffer;
}

// Get video width
__declspec(dllexport) int vr_get_width(VideoReader *vr)
{
    return vr->width;
}

// Get video height
__declspec(dllexport) int vr_get_height(VideoReader *vr)
{
    return vr->height;
}

// Get the duration of the video
__declspec(dllexport) int64_t vr_get_duration(VideoReader *vr)
{
    if (!vr || !vr->fmt_ctx)
        return -1;
    return vr->fmt_ctx->streams[vr->video_stream_index]->duration;
}

// Close the video reader and free resources
__declspec(dllexport) void vr_close(VideoReader *vr)
{
    sws_freeContext(vr->sws_ctx);
    av_free(vr->rgb_buffer);
    av_frame_free(&vr->frame);
    av_frame_free(&vr->rgb_frame);
    avcodec_free_context(&vr->codec_ctx);
    avformat_close_input(&vr->fmt_ctx);
    av_free(vr);
    swr_free(&vr->swr_ctx);
    av_freep(&vr->audio_buffer);
    av_frame_free(&vr->audio_frame);
    avcodec_free_context(&vr->audio_ctx);
}

// Get frames per second of the video
__declspec(dllexport) double vr_get_fps(VideoReader *vr)
{
    AVRational fr = vr->fmt_ctx->streams[vr->video_stream_index]->avg_frame_rate;
    return av_q2d(fr);
}

// Get current playback timestamp in seconds
__declspec(dllexport) double vr_get_pts(VideoReader *vr)
{
    if (!vr || !vr->frame)
        return 0.0;
    AVStream *stream = vr->fmt_ctx->streams[vr->video_stream_index];
    if (vr->frame->pts == AV_NOPTS_VALUE)
        return 0.0;
    return vr->frame->pts * av_q2d(stream->time_base);
}

// Seek forward by offset seconds
__declspec(dllexport) int vr_seek_forward(VideoReader *vr, double offset)
{
    if (!vr || !vr->fmt_ctx)
        return -1;

    double current = vr_get_pts(vr);

    double target = current + offset;
    AVStream *stream = vr->fmt_ctx->streams[vr->video_stream_index];
    int64_t ts = (int64_t)(target / av_q2d(stream->time_base));

    if (av_seek_frame(vr->fmt_ctx, vr->video_stream_index, ts, AVSEEK_FLAG_ANY) < 0)
        return -1;

    avcodec_flush_buffers(vr->codec_ctx);
    return 0;
}

// Seek backward by offset seconds
__declspec(dllexport) int vr_seek_backward(VideoReader *vr, double offset)
{
    if (!vr || !vr->fmt_ctx)
        return -1;

    double current = vr_get_pts(vr);

    double target = current - offset;
    if (target < 0.0)
        target = 0.0; // clamp at start

    AVStream *stream = vr->fmt_ctx->streams[vr->video_stream_index];
    int64_t ts = (int64_t)(target / av_q2d(stream->time_base));

    if (av_seek_frame(vr->fmt_ctx, vr->video_stream_index, ts, AVSEEK_FLAG_BACKWARD) < 0)
        return -1;

    avcodec_flush_buffers(vr->codec_ctx);
    return 0;
}

// Stop and seek to start or end of the video
// mode = 0 → go to start
// mode = 1 → go to end
__declspec(dllexport) int vr_stop(VideoReader *vr, int mode)
{
    if (!vr || !vr->fmt_ctx)
        return -1;

    int stream_index = vr->video_stream_index;
    int64_t ts;

    if (mode == 0)
    {
        ts = 0;
    }
    else
    {
        AVStream *stream = vr->fmt_ctx->streams[stream_index];
        int64_t duration = stream->duration;
        if (duration == AV_NOPTS_VALUE)
        {
            duration = vr->fmt_ctx->duration;
        }

        double fps = vr_get_fps(vr);
        if (fps <= 0.0)
            fps = 25.0;
        int64_t one_frame_ts = (int64_t)(stream->time_base.den / (fps * stream->time_base.num));

        ts = duration - one_frame_ts;
        if (ts < 0)
            ts = 0;
    }

    if (av_seek_frame(vr->fmt_ctx, stream_index, ts, AVSEEK_FLAG_BACKWARD) < 0)
    {
        return -1;
    }

    avcodec_flush_buffers(vr->codec_ctx);
    return 0;
}

__declspec(dllexport) uint8_t *vr_get_audio(VideoReader *vr)
{
    return vr->audio_buffer; // filled with PCM samples
}
__declspec(dllexport) int vr_get_audio_size(VideoReader *vr)
{
    return vr->audio_buffer_size; // number of bytes in buffer
}

// Get audio sample rate
__declspec(dllexport) int vr_get_sample_rate(VideoReader *vr)
{
    return vr->audio_sample_rate;
}
