# Changelog - Basic Video Streamer

All notable changes to the **Basic Video Streamer** IP camera emulation service will be documented in this file.

---

## [1.5.0] - 2026-08-24

### Added
- **Microsecond UNIX Timestamp Frame Synchronization Telemetry (`app/camera_manager.py` & `app/rtsp_server.py`)**:
  - Attached microsecond-precision UNIX capture timestamps (`time.time()`) to every captured frame from both CSI cameras (`Camera 0` and `Camera 1`).
  - **RTSP 90 kHz Clock Sync**: Converted capture timestamps to 90 kHz RTP clock units (`(capture_unix * 90000) & 0xFFFFFFFF`) inside the RTP packet header for standard RTSP frame alignment in VLC, OpenCV, GStreamer, FFmpeg, and NVR receivers.
  - **HTTP Stream Header (`X-Timestamp`)**: Added `X-Timestamp: 1787573000.123456` response headers to HTTP MJPEG frame boundaries.
  - **REST API Telemetry**: Exposed `sync_telemetry` (`timestamp`, `timestamp_iso`, `frame_age_ms`) in `/api/cameras` and `/api/camera/<id>/status`.

---

## [1.4.1] - 2026-08-24

### Fixed
- **30 FPS Unblocked RTSP Streaming Loop (`app/rtsp_server.py`)**:
  - Added dedicated high-frequency background worker thread (`_stream_loop`) pushing RTP video packets continuously to VLC at **30 FPS (~33ms intervals)**.

---

## [1.4.0] - 2026-08-24

### Refactored & Optimized (Raspberry Pi 5 Optimization)
- **Default H.264 & MJPEG Streaming Pipeline (`app/camera_config.json` & `app/src/App.vue`)**:
  - Removed software H.265 (HEVC) encoder toggles to eliminate CPU thrashing, thermal throttling, and framerate drops on Raspberry Pi 5.

---

## [1.0.0] - 2026-08-24

### Added
- Initial release of **Basic Video Streamer** IP camera emulation service and Vue 3 mobile web dashboard.
