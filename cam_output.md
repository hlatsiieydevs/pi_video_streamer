# Camera Network Visibility and Stream Access

The **Basic Video Streamer (BVS)** is designed to flawlessly emulate a commercial IP Security Camera on your local network. It supports seamless auto-discovery and dynamic stream allocation for any number of physically connected hardware cameras.

## 1. How the System Makes Itself Visible

To ensure seamless integration with Video Management Systems (VMS), custom agents, and Network Video Recorders (NVR) like `tk_analytics_edge`, the system implements a lightweight **ONVIF Profile S** emulation layer. 

Here is exactly how the system announces its presence on the network:

* **WS-Discovery (UDP Multicast)**:
  As soon as the BVS server boots, it spins up a background UDP Multicast service binding to `239.255.255.250` on port `3702`. Whenever an NVR or VMS sends out an ONVIF `<Probe>` request to discover cameras on the local subnet, the Pi instantly replies with a `<ProbeMatch>` XML packet.
  This match includes the Raspberry Pi's actual physical MAC address and points the client to the device's main control address.

* **ONVIF SOAP Endpoints**:
  Once discovered, the VMS talks to standard ONVIF HTTP SOAP services hosted directly on the Pi's main port (5000):
  - **Device Service** (`/onvif/device_service`): Responds to `GetDeviceInformation` requests with the hardware's Manufacturer, Model, Firmware Version, and physical MAC address (used for licensing and uniquely identifying the camera).
  - **Media Service** (`/onvif/media_service`): Responds to `GetProfiles` and `GetStreamUri`. When the NVR asks for the video feed, the system automatically redirects the NVR to the correct local RTSP endpoint.

---

## 2. Accessing Video Streams (Multi-Camera Architecture)

The system features **Dynamic Hardware Auto-Detection**. When it boots, it scans the hardware for available CSI and USB capture interfaces natively using `libcamera`. 

Whether you plug in 1 camera or 16 cameras, the system dynamically spins up independent hardware capture pipelines and assigns a sequential integer ID (`0`, `1`, `2`, etc.) to each detected sensor.

### Available Endpoints for Each Camera

You can access the video streams for *any* detected camera simultaneously by simply changing the `<id>` parameter in the URL path. 

For example, if your Raspberry Pi's IP address is `10.0.0.5` and you have two cameras physically attached, they will map out as follows:

#### 🟢 RTSP Feeds (High-Performance, H.264/H.265)
RTSP is the primary protocol. It is served on port `8554` and importantly includes microsecond UNIX timestamps embedded directly in the RTP packet headers for analytics alignment.
* **Camera 0:** `rtsp://10.0.0.5:8554/stream1`
* **Camera 1:** `rtsp://10.0.0.5:8554/stream2`
* **Camera N:** `rtsp://10.0.0.5:8554/stream<N+1>`

#### 🟡 HTTP MJPEG Previews (Web / Browser)
A fallback Motion JPEG stream is available on port `5000`. This is ideal for simple browser viewing, debugging, or web integrations without needing WebRTC or an RTSP demuxer.
* **Camera 0:** `http://10.0.0.5:5000/video_feed/0`
* **Camera 1:** `http://10.0.0.5:5000/video_feed/1`
* **Camera N:** `http://10.0.0.5:5000/video_feed/<N>`

#### 🔵 REST API Telemetry & Control
You can programmatically query the status, resolution, and exact UNIX synchronization telemetry (or issue commands to change crop/rotation) of any specific camera using its ID via the REST API on port `5000`:
* **Camera 0 Status:** `GET http://10.0.0.5:5000/api/camera/0/status`
* **Camera 1 Status:** `GET http://10.0.0.5:5000/api/camera/1/status`
* **Camera N Status:** `GET http://10.0.0.5:5000/api/camera/<N>/status`
