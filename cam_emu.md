# Raspberry Pi Security Camera Emulation Guidelines

This document outlines the key features implemented by the **Basic Video Streamer (BVS)** project to emulate a standard IP Security Camera using a Raspberry Pi. Another agent can use these guidelines to understand how to interact with, ingest from, or configure the emulated camera feed.

## Key Emulation Features (Based on BVS)

### 1. RTSP Streaming (Real-Time Streaming Protocol)
Standard commercial security cameras stream compressed video over RTSP.
- **RTSP Endpoints:** The Pi exposes standard RTSP streams at `rtsp://<pi-ip>:8554/stream1`.
- **Hardware Encoding:** Video is compressed using H.264 (AVC) or H.265 (HEVC) encoding, which is essential for low latency, high-quality IP camera emulation.
- **Multi-Protocol Support:** In addition to RTSP, the system provides HTTP MJPEG (`http://<pi-ip>:5000/video_feed/0`), HLS, RTMP, and WebRTC to support various NVRs and web clients.

### 2. Microsecond UNIX Timestamping (Crucial for VMS/Analytics Sync)
To synchronize multiple cameras or accurately correlate video frames with real-world analytics events, the stream carries highly precise capture timestamps.
- **RTP Headers (RTSP):** The RTSP stream carries 90 kHz UNIX-derived timestamps (`(capture_unix * 90000) & 0xFFFFFFFF`) directly in the RTP packet headers.
- **HTTP MJPEG Headers:** For HTTP fallback streams, individual frames include an `X-Timestamp: <unix_epoch>` multipart boundary header.

### 3. Open REST API & Telemetry
### 3. Open REST API & Telemetry (and ONVIF Wrapper)
While BVS provides a modern REST API (e.g., `GET /api/camera/0/status` on port 5000) for telemetry and control, **`tk_analytics_edge` requires ONVIF for auto-discovery in the setup wizard.**
- **Requirement for the Emulation Agent:** You must build a lightweight ONVIF Profile S wrapper around BVS.
- **WS-Discovery:** The Pi must broadcast WS-Discovery packets on port 3702 so the `tk_analytics_edge` backend's `discover_cameras` function can find it on the subnet.
- **Device & Media Service:** The ONVIF wrapper must answer `GetDeviceInformation` (returning dummy MAC/firmware) and `GetStreamUri` (returning the BVS RTSP URL).

---

## Agent Integration Guide

If you are an agent or service attempting to ingest video or extract telemetry from this emulated Pi camera, follow these integration patterns:

### 1. Connecting to the Video Feed
- **For Analytics/Computer Vision:** Use the RTSP stream (`rtsp://<pi-ip>:8554/live/cam0`).
- **For Web Dashboard Previews:** Use the HTTP MJPEG stream (`http://<pi-ip>:5000/video_feed/0`).

### 2. Extracting Exact Frame Timestamps
Standard OpenCV `VideoCapture` abstracts away the RTSP RTP timestamps. If you need absolute synchronization across multiple cameras:
- **Use PyAV (`av`)**:
  ```python
  import av
  container = av.open("rtsp://<pi-ip>:8554/live/cam0")
  for packet in container.demux(video=0):
      if packet.pts is not None:
          exact_unix_time = packet.pts / 90000.0
  ```
- **Use MJPEG with Requests**: Parse the `X-Timestamp:` header from the HTTP multipart stream.

### 3. Verifying Camera Status
Before attempting to decode streams, you can fetch hardware telemetry and active config:
```bash
curl -s http://<pi-ip>:5000/api/camera/0/status
```
This payload will confirm if the camera is `enabled`, its `fps.actual`, and its `sync_telemetry`.
