

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

#include <iostream>
#include <thread>
#include <mutex>
#include <queue>
#include <condition_variable>
#include <atomic>
#include <chrono>
#include <string>
#include <vector>
#include <algorithm>

// --- MINIAUDIO (Cross-Platform Audio) ---
#define MINIAUDIO_IMPLEMENTATION
#include "miniaudio.h"

extern "C"
{
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libswscale/swscale.h>
#include <libswresample/swresample.h>
#include <libavutil/imgutils.h>
}

namespace py = pybind11;

#define AUDIO_SAMPLE_RATE 44100
#define AUDIO_CHANNELS 2

class MediaDecoder
{
private:
    std::string source_url;
    std::atomic<bool> is_running{false};
    std::atomic<bool> is_paused{false};

    std::atomic<bool> is_buffering{true}; // Start in buffering state
    std::atomic<double> demuxed_video_time{0.0};
    const double HIGH_WATERMARK_SEC = 10.0;
    const double LOW_WATERMARK_SEC = 3.0;
    const double PREROLL_SEC = 3.0;

    // --- SEEK SYNCHRONIZATION ---
    std::atomic<bool> seek_requested{false};
    std::atomic<double> seek_pos_sec{0.0};
    std::mutex seek_mutex;
    std::condition_variable seek_cv;
    bool seek_completed = false;

    // --- A/V CLOCKS ---
    std::atomic<double> current_pts{0.0};
    std::atomic<double> audio_clock{0.0};
    std::atomic<bool> reset_audio_clock{false};

    AVFormatContext *fmt_ctx = nullptr;
    AVCodecContext *video_codec_ctx = nullptr;
    SwsContext *sws_ctx = nullptr;
    int video_stream_index = -1;
    int width = 0, height = 0;

    AVCodecContext *audio_codec_ctx = nullptr;
    SwrContext *swr_ctx = nullptr;
    int audio_stream_index = -1;

    ma_device audio_device;
    std::vector<uint8_t> pcm_buffer;
    std::mutex pcm_mutex;

    std::thread demux_thread;
    std::thread video_thread;
    std::thread audio_thread;

    std::mutex video_pkt_mutex;
    std::condition_variable video_pkt_cv;
    std::queue<AVPacket *> video_pkt_queue;

    std::mutex frame_mutex;
    std::condition_variable frame_cv;
    std::queue<AVFrame *> ready_frames;

    std::mutex audio_pkt_mutex;
    std::condition_variable audio_pkt_cv;
    std::queue<AVPacket *> audio_pkt_queue;

    std::mutex video_codec_mutex;
    std::mutex audio_codec_mutex;

    static void data_callback(ma_device *pDevice, void *pOutput, const void *pInput, ma_uint32 frameCount)
    {
        MediaDecoder *decoder = (MediaDecoder *)pDevice->pUserData;

        // Output silence if paused OR actively buffering (pre-rolling)
        if (!decoder || decoder->is_paused || decoder->is_buffering)
        {
            memset(pOutput, 0, frameCount * AUDIO_CHANNELS * sizeof(int16_t));
            return;
        }

        decoder->audio_clock.store(decoder->audio_clock.load() + ((double)frameCount / AUDIO_SAMPLE_RATE));
        uint32_t bytes_needed = frameCount * AUDIO_CHANNELS * sizeof(int16_t);

        std::lock_guard<std::mutex> lock(decoder->pcm_mutex);
        if (decoder->pcm_buffer.size() >= bytes_needed)
        {
            memcpy(pOutput, decoder->pcm_buffer.data(), bytes_needed);
            decoder->pcm_buffer.erase(decoder->pcm_buffer.begin(), decoder->pcm_buffer.begin() + bytes_needed);
        }
        else
        {
            memcpy(pOutput, decoder->pcm_buffer.data(), decoder->pcm_buffer.size());
            memset((uint8_t *)pOutput + decoder->pcm_buffer.size(), 0, bytes_needed - decoder->pcm_buffer.size());
            decoder->pcm_buffer.clear();
        }
    }

    void flush_queues()
    {
        std::lock_guard<std::mutex> v_lock(video_pkt_mutex);
        std::lock_guard<std::mutex> a_lock(audio_pkt_mutex);
        std::lock_guard<std::mutex> f_lock(frame_mutex);
        std::lock_guard<std::mutex> p_lock(pcm_mutex);
        std::lock_guard<std::mutex> vc_lock(video_codec_mutex);
        std::lock_guard<std::mutex> ac_lock(audio_codec_mutex);

        while (!video_pkt_queue.empty())
        {
            AVPacket *p = video_pkt_queue.front();
            av_packet_free(&p);
            video_pkt_queue.pop();
        }
        while (!audio_pkt_queue.empty())
        {
            AVPacket *p = audio_pkt_queue.front();
            av_packet_free(&p);
            audio_pkt_queue.pop();
        }
        while (!ready_frames.empty())
        {
            AVFrame *f = ready_frames.front();
            av_frame_free(&f);
            ready_frames.pop();
        }
        pcm_buffer.clear();

        if (video_codec_ctx)
            avcodec_flush_buffers(video_codec_ctx);
        if (audio_codec_ctx)
            avcodec_flush_buffers(audio_codec_ctx);

        // Reset time trackers to prevent false buffer health readings
        demuxed_video_time.store(seek_pos_sec.load());
        current_pts.store(seek_pos_sec.load());
    }

    void demux_worker()
    {
        AVPacket *packet = av_packet_alloc();
        while (is_running)
        {
            if (seek_requested)
            {
                // Seek the global file context so audio jumps too
                int64_t target_pts = (int64_t)(seek_pos_sec * AV_TIME_BASE);
                av_seek_frame(fmt_ctx, -1, target_pts, AVSEEK_FLAG_BACKWARD);

                flush_queues();

                {
                    std::lock_guard<std::mutex> lock(seek_mutex);
                    seek_requested = false;
                    seek_completed = true;
                }

                seek_cv.notify_all();
                frame_cv.notify_all();
                audio_pkt_cv.notify_all();
                continue;
            }

            // --- SMART BUFFER HEALTH CALCULATION ---
            double playback_time = current_pts.load();
            double demux_time = demuxed_video_time.load();
            double buffer_health_sec = std::max(0.0, demux_time - playback_time);

            // Pre-roll check: Are we buffering and have we gathered enough data to resume?
            if (is_buffering && buffer_health_sec >= PREROLL_SEC)
            {
                is_buffering = false;
                frame_cv.notify_all(); // Wake up Kivy frame requests
            }

            // High Watermark Check: Do we have 10+ seconds? Go to sleep until we drop to 3 seconds.
            if (!is_buffering && buffer_health_sec > HIGH_WATERMARK_SEC)
            {
                std::unique_lock<std::mutex> sleep_lock(seek_mutex);
                seek_cv.wait_for(sleep_lock, std::chrono::milliseconds(50), [this]
                                 { 
                    double health = std::max(0.0, demuxed_video_time.load() - current_pts.load());
                    return seek_requested.load() || !is_running.load() || health < LOW_WATERMARK_SEC; });
                continue;
            }

            if (av_read_frame(fmt_ctx, packet) >= 0)
            {
                if (packet->stream_index == video_stream_index)
                {
                    if (packet->pts != AV_NOPTS_VALUE)
                    {
                        demuxed_video_time.store(packet->pts * av_q2d(fmt_ctx->streams[video_stream_index]->time_base));
                    }

                    std::lock_guard<std::mutex> lock(video_pkt_mutex);
                    video_pkt_queue.push(av_packet_clone(packet));
                    video_pkt_cv.notify_one();
                }
                else if (packet->stream_index == audio_stream_index)
                {
                    std::lock_guard<std::mutex> lock(audio_pkt_mutex);
                    audio_pkt_queue.push(av_packet_clone(packet));
                    audio_pkt_cv.notify_one();
                }
            }
            else
            {
                // EOF Reached! Force resume if we were trying to pre-roll the end of the file.
                if (is_buffering)
                {
                    is_buffering = false;
                    frame_cv.notify_all();
                }

                if (!seek_requested)
                {
                    std::unique_lock<std::mutex> sleep_lock(seek_mutex);
                    seek_cv.wait_for(sleep_lock, std::chrono::milliseconds(100), [this]
                                     { return seek_requested.load() || !is_running; });
                }
            }
            av_packet_unref(packet);
        }
        av_packet_free(&packet);
    }

    void audio_worker()
    {
        AVFrame *frame = av_frame_alloc();
        while (is_running)
        {
            AVPacket *pkt = nullptr;
            {
                std::unique_lock<std::mutex> lock(audio_pkt_mutex);
                audio_pkt_cv.wait_for(lock, std::chrono::milliseconds(10),
                                      [this]
                                      { return !audio_pkt_queue.empty() || !is_running || seek_requested; });

                if (!is_running && audio_pkt_queue.empty())
                    break;
                if (audio_pkt_queue.empty() || seek_requested)
                    continue;

                pkt = audio_pkt_queue.front();
                audio_pkt_queue.pop();
            }

            if (seek_requested)
            {
                av_packet_free(&pkt);
                continue;
            }

            {
                std::lock_guard<std::mutex> ac_lock(audio_codec_mutex);
                if (avcodec_send_packet(audio_codec_ctx, pkt) == 0)
                {
                    while (avcodec_receive_frame(audio_codec_ctx, frame) == 0)
                    {
                        // Snap the master audio clock to the actual keyframe PTS FFmpeg landed on
                        if (reset_audio_clock && frame->best_effort_timestamp != AV_NOPTS_VALUE)
                        {
                            double actual_pts = frame->best_effort_timestamp * av_q2d(fmt_ctx->streams[audio_stream_index]->time_base);
                            audio_clock.store(actual_pts);
                            reset_audio_clock = false;
                        }

                        // Prevent decoding too far ahead in memory
                        while (pcm_buffer.size() > AUDIO_SAMPLE_RATE * 4 * HIGH_WATERMARK_SEC && is_running && !seek_requested)
                        {
                            std::this_thread::sleep_for(std::chrono::milliseconds(10));
                        }
                        if (seek_requested)
                            break;

                        int out_samples = swr_get_out_samples(swr_ctx, frame->nb_samples);
                        int out_size = out_samples * AUDIO_CHANNELS * sizeof(int16_t);

                        std::vector<uint8_t> temp_buf(out_size);
                        uint8_t *out_ptr = temp_buf.data();

                        int converted = swr_convert(swr_ctx, &out_ptr, out_samples,
                                                    (const uint8_t **)frame->data, frame->nb_samples);

                        if (converted > 0)
                        {
                            std::lock_guard<std::mutex> lock(pcm_mutex);
                            pcm_buffer.insert(pcm_buffer.end(), temp_buf.begin(), temp_buf.begin() + (converted * AUDIO_CHANNELS * sizeof(int16_t)));
                        }
                    }
                }
            }
            av_packet_free(&pkt);
        }
        av_frame_free(&frame);
    }

    void video_worker()
    {
        AVFrame *frame = av_frame_alloc();
        while (is_running)
        {
            AVPacket *pkt = nullptr;
            {
                std::unique_lock<std::mutex> lock(video_pkt_mutex);
                video_pkt_cv.wait_for(lock, std::chrono::milliseconds(10),
                                      [this]
                                      { return !video_pkt_queue.empty() || !is_running || seek_requested; });

                if (!is_running && video_pkt_queue.empty())
                    break;
                if (video_pkt_queue.empty() || seek_requested)
                    continue;

                pkt = video_pkt_queue.front();
                video_pkt_queue.pop();
            }

            if (seek_requested)
            {
                av_packet_free(&pkt);
                continue;
            }

            {
                std::lock_guard<std::mutex> vc_lock(video_codec_mutex);
                if (avcodec_send_packet(video_codec_ctx, pkt) == 0)
                {
                    while (avcodec_receive_frame(video_codec_ctx, frame) == 0)
                    {
                        if (seek_requested)
                            break;

                        AVFrame *rgb_frame = av_frame_alloc();
                        rgb_frame->format = AV_PIX_FMT_RGB24;
                        rgb_frame->width = width;
                        rgb_frame->height = height;

                        rgb_frame->pts = frame->best_effort_timestamp;

                        av_frame_get_buffer(rgb_frame, 1);
                        sws_scale(sws_ctx, (const uint8_t *const *)frame->data, frame->linesize,
                                  0, height, rgb_frame->data, rgb_frame->linesize);

                        std::lock_guard<std::mutex> lock(frame_mutex);
                        ready_frames.push(rgb_frame);
                        frame_cv.notify_one();
                    }
                }
            }
            av_packet_free(&pkt);
        }
        av_frame_free(&frame);
    }

public:
    MediaDecoder(const std::string &url) : source_url(url)
    {
        avformat_network_init();
        AVDictionary *opts = nullptr;
        av_dict_set(&opts, "buffer_size", "10240000", 0);
        av_dict_set(&opts, "reconnect", "1", 0);
        av_dict_set(&opts, "reconnect_streamed", "1", 0);
        av_dict_set(&opts, "reconnect_delay_max", "5", 0);
        av_dict_set(&opts, "timeout", "10000000", 0);
        av_dict_set(&opts, "rtsp_transport", "tcp", 0);

        av_dict_set(&opts, "user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", 0);

        av_dict_set(&opts, "headers", "Accept: */*\r\n", 0);

        if (avformat_open_input(&fmt_ctx, url.c_str(), nullptr, &opts) < 0)
        {
            av_dict_free(&opts);
            throw std::runtime_error("FFmpeg failed to open video file: " + url);
        }
        av_dict_free(&opts);

        if (avformat_find_stream_info(fmt_ctx, nullptr) < 0)
        {
            throw std::runtime_error("FFmpeg failed to find stream info.");
        }

        video_stream_index = av_find_best_stream(fmt_ctx, AVMEDIA_TYPE_VIDEO, -1, -1, nullptr, 0);
        if (video_stream_index >= 0)
        {
            const AVCodec *codec = avcodec_find_decoder(fmt_ctx->streams[video_stream_index]->codecpar->codec_id);
            video_codec_ctx = avcodec_alloc_context3(codec);
            avcodec_parameters_to_context(video_codec_ctx, fmt_ctx->streams[video_stream_index]->codecpar);
            avcodec_open2(video_codec_ctx, codec, nullptr);
            width = video_codec_ctx->width;
            height = video_codec_ctx->height;
            sws_ctx = sws_getContext(width, height, video_codec_ctx->pix_fmt, width, height, AV_PIX_FMT_RGB24, SWS_BILINEAR, nullptr, nullptr, nullptr);
        }

        audio_stream_index = av_find_best_stream(fmt_ctx, AVMEDIA_TYPE_AUDIO, -1, -1, nullptr, 0);
        if (audio_stream_index >= 0)
        {
            const AVCodec *acodec = avcodec_find_decoder(fmt_ctx->streams[audio_stream_index]->codecpar->codec_id);
            audio_codec_ctx = avcodec_alloc_context3(acodec);
            avcodec_parameters_to_context(audio_codec_ctx, fmt_ctx->streams[audio_stream_index]->codecpar);
            avcodec_open2(audio_codec_ctx, acodec, nullptr);

            AVChannelLayout out_ch_layout;
            av_channel_layout_default(&out_ch_layout, AUDIO_CHANNELS);
            swr_alloc_set_opts2(&swr_ctx, &out_ch_layout, AV_SAMPLE_FMT_S16, AUDIO_SAMPLE_RATE,
                                &fmt_ctx->streams[audio_stream_index]->codecpar->ch_layout,
                                (enum AVSampleFormat)fmt_ctx->streams[audio_stream_index]->codecpar->format,
                                fmt_ctx->streams[audio_stream_index]->codecpar->sample_rate, 0, nullptr);
            swr_init(swr_ctx);

            ma_device_config deviceConfig = ma_device_config_init(ma_device_type_playback);
            deviceConfig.playback.format = ma_format_s16;
            deviceConfig.playback.channels = AUDIO_CHANNELS;
            deviceConfig.sampleRate = AUDIO_SAMPLE_RATE;
            deviceConfig.dataCallback = data_callback;
            deviceConfig.pUserData = this;

            ma_device_init(NULL, &deviceConfig, &audio_device);
        }
    }

    ~MediaDecoder() { stop(); }

    void start()
    {
        if (is_running)
            return;
        is_running = true;

        demux_thread = std::thread(&MediaDecoder::demux_worker, this);
        if (video_stream_index >= 0)
            video_thread = std::thread(&MediaDecoder::video_worker, this);
        if (audio_stream_index >= 0)
        {
            audio_thread = std::thread(&MediaDecoder::audio_worker, this);
            ma_device_start(&audio_device);
        }
    }

    void stop()
    {
        is_running = false;
        is_paused = true;

        video_pkt_cv.notify_all();
        audio_pkt_cv.notify_all();
        frame_cv.notify_all();
        seek_cv.notify_all();

        if (demux_thread.joinable())
            demux_thread.join();
        if (video_thread.joinable())
            video_thread.join();
        if (audio_thread.joinable())
        {
            if (ma_device_get_state(&audio_device) == ma_device_state_started)
            {
                ma_device_stop(&audio_device);
            }
            ma_device_uninit(&audio_device);
            audio_thread.join();
        }
    }

    double get_fps()
    {
        if (video_stream_index < 0)
            return 30.0;
        AVRational fr = fmt_ctx->streams[video_stream_index]->avg_frame_rate;
        return (fr.num && fr.den) ? av_q2d(fr) : 30.0;
    }

    double get_duration()
    {
        if (!fmt_ctx)
            return 0.0;
        return (double)fmt_ctx->duration / AV_TIME_BASE;
    }

    double get_position()
    {
        return current_pts.load();
    }

    void seek(double time_sec)
    {
        seek_pos_sec = std::max(0.0, time_sec);

        std::unique_lock<std::mutex> lock(seek_mutex);

        is_buffering = true;
        seek_requested = true;
        seek_completed = false;

        seek_cv.notify_all();
        seek_cv.wait(lock, [this]
                     { return seek_completed || !is_running; });

        // Tell the audio worker to intercept the true PTS of the post-seek frame
        reset_audio_clock = true;
    }

    void pause()
    {
        is_paused = true;
        if (audio_stream_index >= 0)
        {
            ma_device_stop(&audio_device);
        }
    }

    void resume()
    {
        is_paused = false;
        if (audio_stream_index >= 0)
        {
            if (ma_device_get_state(&audio_device) != ma_device_state_started)
            {
                ma_device_start(&audio_device);
            }
        }
    }

    void set_volume(float volume)
    {
        if (audio_stream_index >= 0)
        {
            ma_device_set_master_volume(&audio_device, std::max(0.0f, volume));
        }
    }

    float get_volume()
    {
        float vol = 1.0f;
        if (audio_stream_index >= 0)
        {
            ma_device_get_master_volume(&audio_device, &vol);
        }
        return vol;
    }

    py::object get_next_frame()
    {
        AVFrame *rgb_frame = nullptr;

        while (true)
        {
            py::gil_scoped_release release;
            std::unique_lock<std::mutex> lock(frame_mutex);

            // Block Python completely if we are in the buffering state.
            frame_cv.wait(lock, [this]
                          { return (!ready_frames.empty() && !seek_requested && !is_buffering) || !is_running; });

            if (!is_running && ready_frames.empty())
                return py::none();
            if (seek_requested)
                return py::none();

            rgb_frame = ready_frames.front();

            double frame_time = 0.0;
            if (rgb_frame->pts != AV_NOPTS_VALUE && video_stream_index >= 0)
            {
                frame_time = rgb_frame->pts * av_q2d(fmt_ctx->streams[video_stream_index]->time_base);
            }

            if (audio_stream_index >= 0 && frame_time > 0.0)
            {
                double current_audio_time = audio_clock.load();

                if (frame_time > current_audio_time + 0.01)
                {
                    lock.unlock();
                    std::this_thread::sleep_for(std::chrono::milliseconds(2));
                    continue;
                }

                if (frame_time < current_audio_time - 0.1)
                {
                    ready_frames.pop();
                    av_frame_free(&rgb_frame);
                    continue;
                }
            }

            ready_frames.pop();
            break;
        }

        if (rgb_frame->pts != AV_NOPTS_VALUE && video_stream_index >= 0)
        {
            current_pts = rgb_frame->pts * av_q2d(fmt_ctx->streams[video_stream_index]->time_base);
        }

        uint8_t *ptr = rgb_frame->data[0];
        size_t stride = rgb_frame->linesize[0];

        py::capsule free_when_done(rgb_frame, [](void *f)
                                   {
            AVFrame* frame = reinterpret_cast<AVFrame*>(f);
            av_frame_free(&frame); });

        return py::array_t<uint8_t>(
            {height, width, 3},
            {stride, (size_t)3, (size_t)1},
            ptr,
            free_when_done);
    }
};

PYBIND11_MODULE(videonative, m)
{
    py::class_<MediaDecoder>(m, "MediaDecoder")
        .def(py::init<const std::string &>())
        .def("start", &MediaDecoder::start)
        .def("stop", &MediaDecoder::stop)
        .def("get_next_frame", &MediaDecoder::get_next_frame)
        .def("get_fps", &MediaDecoder::get_fps)
        .def("get_duration", &MediaDecoder::get_duration)
        .def("get_position", &MediaDecoder::get_position)
        .def("seek", &MediaDecoder::seek)
        .def("pause", &MediaDecoder::pause)
        .def("resume", &MediaDecoder::resume)
        .def("set_volume", &MediaDecoder::set_volume)
        .def("get_volume", &MediaDecoder::get_volume);
}