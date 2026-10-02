# Basic Video Streamer (BVS) Refactor Prompt

Hello Agent,

You are tasked with refactoring the **Basic Video Streamer (BVS)** pipeline on a Raspberry Pi. Currently, the BVS system is successfully streaming RTSP video, but the video feed format is fundamentally incompatible with strict hardware-accelerated clients like `tk_analytics_edge`.

Please implement the following two critical fixes to the BVS camera pipeline:

## 1. Fix the Colorspace/Pixel Format Encoding
**The Issue:** The RTSP H.264 stream currently has inverted red and blue channels (red cars look blue, green plants look teal). This indicates that the raw sensor data is being fed into the hardware H.264 encoder as `BGR` (or `RGB`) instead of the standard `YUV420p` or `NV12` format. While tolerant software decoders like VLC will display this stream (with the wrong colors), strict hardware decoders (like OpenCV's `hwaccel;auto` with FFmpeg) will silently fail to decode this non-standard format and output completely black/empty frames.
**The Fix:** You must ensure that `libcamera` (or the underlying capture pipeline) converts the raw sensor data to standard `YUV420` (or `NV12`) *before* it gets piped into the hardware H.264 encoder.

## 2. Apply a 180-Degree Orientation Fix
**The Issue:** The physical Raspberry Pi camera unit is mounted upside down. As a result, the live feed is currently inverted.
**The Fix:** Apply a 180-degree rotation (or simultaneous `hflip` and `vflip` arguments) to the `libcamera` or `picamera2` initialization configuration. This will correct the orientation at the source so clients do not have to flip the feed computationally.

### Success Criteria:
When connected via a strict RTSP client (like `tk_analytics_edge` or OpenCV with `hwaccel=auto`), the stream should display:
1. Right-side up.
2. With accurate real-world colors.
3. Without dropping into a black screen due to hardware decoding failure.
