# Basic Video Streamer - RPi IP Camera Emulation Service

![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-5%20%2F%204-red?style=for-the-badge&logo=raspberrypi)
![Vue 3](https://img.shields.io/badge/Vue.js-3.5-green?style=for-the-badge&logo=vuedotjs)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)
![RTSP](https://img.shields.io/badge/RTSP-H.264%20%2F%20H.265-orange?style=for-the-badge)

**Basic Video Streamer** is an IP camera emulation solution for Raspberry Pi. It captures raw camera video feeds and streams them using H.264 (AVC) or H.265 (HEVC) encoding over RTSP and other standard IP camera protocols. It exposes open REST API endpoints for each connected camera on the local network and includes a mobile-friendly web dashboard for real-time monitoring and dynamic parameter control.

---

## 🌟 Key Features

* **IP Camera Emulation & RTSP Streaming**:
  * Dual-codec support: Selectable **H.264 (AVC)** and **H.265 (HEVC)** hardware/software compression.
  * Dedicated RTSP endpoints dynamically generated for each connected camera (e.g., `rtsp://<pi-ip>:8554/live/cam<id>`).
  * Multiple streaming protocols: **RTSP**, **HLS**, **HTTP MJPEG**, **RTMP**, and **WebRTC**.
* **Microsecond UNIX Timestamp Frame Synchronization**:
  * Every frame captured from CSI hardware is stamped with high-precision microsecond UNIX epoch time (`time.time()`).
  * RTSP RTP headers carry 90 kHz UNIX-derived timestamps (`(capture_unix * 90000) & 0xFFFFFFFF`) for multi-camera frame alignment in VLC, OpenCV, PyAV, GStreamer, FFmpeg, and NVRs.
  * HTTP MJPEG streams contain `X-Timestamp: 1787573000.123456` in multipart boundary headers.
* **Orientation Controls & Digital Cropping**:
  * **Camera Orientation & Flips**: Horizontal Mirror (`hflip`), Vertical Flip (`vflip`), and 180° rotation for upside-down physical camera mounting.
  * **Digital Cropping & ROI Zoom**: Togglable digital zoom presets (1.0x to 2.0x, Center 50%, Top-Half, Bottom-Half).
* **Open REST API Architecture**:
  * Unique API endpoints for each camera (`/api/camera/<cam_id>/status`, `/api/camera/<cam_id>/config`).
  * Full programmatic control over resolution, framerate, quality, bitrate, aspect ratio, orientation, and crop.
* **Dynamic Hardware Auto-Detection**:
  * Automatically detects physical cameras (up to 16+) using `libcamera` and dynamically creates independent streaming pipelines and API routes for each device.
* **ONVIF Profile S Emulation (Auto-Discovery)**:
  * Includes a built-in WS-Discovery UDP Multicast responder.
  * Implements ONVIF Device and Media SOAP services, broadcasting the actual Pi MAC address to allow instant auto-discovery by standard NVRs and VMS systems (like `tk_analytics_edge`).
* **Mobile-Optimized Responsive Web Interface**:
  1. **Live Camera Preview & Real-Time Metrics**:
     - Real-time preview stream with live metadata overlay (Bitrate, FPS, Codec, Resolution, Orientation, Crop, UNIX Timestamp).
  2. **Hardware Information Panel**:
     - Direct hardware diagnostic telemetry: Model, Sensor Size, Shutter Speed, Aperture, ISO, and Frame Sync UNIX timestamp.

---

## 📖 Integration Guide: Accessing Video Feeds & Frame UNIX Timestamps

This section details how external applications (Python, OpenCV, PyAV, Node.js, C++, FFmpeg, GStreamer, NVRs) can consume video streams and extract UNIX timestamps to align dual-camera frames.

### 1. Stream Network Endpoints

| Stream Type | Endpoint URL | Protocol / Format | Notes |
| :--- | :--- | :--- | :--- |
| **Camera <id> RTSP** | `rtsp://<pi-ip>:8554/live/cam<id>` | RTSP / RTP (H.264 / MJPEG) | Port 8554, 90 kHz UNIX RTP Timestamp in Header |
| **Camera <id> HTTP Preview** | `http://<pi-ip>:5000/video_feed/<id>` | HTTP Multipart MJPEG | Includes `X-Timestamp: 1787573000.123456` Header |


---

### 2. Python Integration Examples

#### Option A: PyAV (`av`) — Precise RTSP Packet UNIX Timestamp Extraction

```python
import av

# Connect to RTSP Stream for Camera 0
rtsp_url = "rtsp://10.0.0.5:8554/live/cam0"
container = av.open(rtsp_url)

for packet in container.demux(video=0):
    for frame in packet.decode():
        # Convert 90 kHz RTP timestamp back to exact UNIX Epoch Seconds
        if packet.pts is not None:
            frame_unix_timestamp = packet.pts / 90000.0
            print(f"Cam 0 Frame Received | Frame Time UNIX: {frame_unix_timestamp:.6f}")
        
        # Convert frame to numpy array for processing / OpenCV
        img_bgr = frame.to_ndarray(format="bgr24")
```

#### Option B: OpenCV (`cv2.VideoCapture`) — RTSP Video Stream Decoding

```python
import cv2

rtsp_url = "rtsp://10.0.0.5:8554/live/cam0"
cap = cv2.VideoCapture(rtsp_url)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    # Get frame timestamp in milliseconds relative to stream start
    msec = cap.get(cv2.CAP_PROP_POS_MSEC)
    cv2.imshow("Camera 0 RTSP", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

#### Option C: HTTP MJPEG Stream with `X-Timestamp` Header Extraction

```python
import requests

url = "http://10.0.0.5:5000/video_feed/0"
res = requests.get(url, stream=True)

for line in res.iter_lines():
    if line.startswith(b"X-Timestamp:"):
        unix_ts = float(line.split(b":")[1].strip())
        print(f"Cam 0 MJPEG Frame | UNIX Capture Timestamp: {unix_ts:.6f}")
```

---

### 3. REST API Telemetry Endpoint

External applications can poll camera status and frame sync metrics:

```bash
curl -s http://10.0.0.5:5000/api/camera/0/status | jq .
```

**JSON Response Payload**:

```json
{
  "id": 0,
  "name": "Camera 0 (CSI-0)",
  "enabled": true,
  "codec": "H.264",
  "protocol": "RTSP",
  "rtsp_url": "rtsp://10.0.0.5:8554/live/cam0",
  "sync_telemetry": {
    "timestamp": 1787573000.123456,
    "timestamp_iso": "2026-08-24T14:46:00.123456Z",
    "frame_age_ms": 12.4
  },
  "fps": {
    "value": 30,
    "actual": 30.0
  },
  "resolution": {
    "width": 1920,
    "height": 1080
  }
}
```

---

### 4. Command Line & Media Player Examples

* **VLC Media Player**:
  ```bash
  vlc rtsp://10.0.0.5:8554/live/cam0
  vlc rtsp://10.0.0.5:8554/live/cam1
  ```
* **FFmpeg Stream Ingestion**:
  ```bash
  ffmpeg -i rtsp://10.0.0.5:8554/live/cam0 -c copy output_cam0.mp4
  ```
* **GStreamer Pipeline**:
  ```bash
  gst-launch-1.0 rtspsrc location=rtsp://10.0.0.5:8554/live/cam0 ! rtph264depay ! avdec_h264 ! autovideosink
  ```

---

## 🚀 Quick Start & Installation

### 1. Initialization
An initialization script is provided to automatically install system dependencies (Node.js, Python 3, FFmpeg), set up the Python virtual environment, install package dependencies, and verify the setup.

```bash
chmod +x init_script.sh
./init_script.sh
```

### 2. Run the Application
Once initialized, start the application:

```bash
chmod +x start.sh
./start.sh
```

Web Interface: `http://<pi-ip-address>:5000` or `http://localhost:5000`

---

## 📄 License
MIT License &copy; 2026 Basic Video Streamer Project.
