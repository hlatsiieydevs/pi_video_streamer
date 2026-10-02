import os
import sys
import json
import time
import io
import math
import datetime
import threading
import logging
import numpy as np
import cv2
from rtsp_server import rtsp_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] CameraManager: %(message)s')
logger = logging.getLogger("CameraManager")

# Add system python path for Picamera2 if available
for p in ['/usr/lib/python3/dist-packages', '/usr/local/lib/python3/dist-packages']:
    if p not in sys.path:
        sys.path.append(p)

HAS_PICAMERA2 = False
try:
    from picamera2 import Picamera2
    HAS_PICAMERA2 = True
    logger.info("picamera2 module successfully imported.")
except ImportError as err:
    logger.warning(f"picamera2 import error: {err}. Using synthetic test pattern generator.")

RESOLUTION_MAP = {
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "480p": (854, 480),
    "360p": (640, 360),
    "240p": (426, 240)
}

QUALITY_MAP = {
    "Low": 50,
    "Medium": 75,
    "High": 85,
    "Ultra": 95
}

CROP_PRESETS = {
    "1.0x (Full)": {"zoom": 1.0, "x_offset": 0.0, "y_offset": 0.0},
    "1.2x Zoom": {"zoom": 1.2, "x_offset": 0.0, "y_offset": 0.0},
    "1.5x Zoom": {"zoom": 1.5, "x_offset": 0.0, "y_offset": 0.0},
    "2.0x Zoom": {"zoom": 2.0, "x_offset": 0.0, "y_offset": 0.0},
    "Center 50%": {"zoom": 2.0, "x_offset": 0.0, "y_offset": 0.0},
    "Top-Half": {"zoom": 2.0, "x_offset": 0.0, "y_offset": -0.5},
    "Bottom-Half": {"zoom": 2.0, "x_offset": 0.0, "y_offset": 0.5}
}

class CameraDevice:
    """Represents an IP-emulated Camera instance with UNIX timestamp frame metadata"""
    def __init__(self, config):
        self.camera_id = config["id"]
        self.name = config["name"]
        self.enabled = config.get("enabled", True)
        
        # Codec & Protocol
        self.codec = config.get("codec", "H.264")
        self.protocol = config.get("protocol", "RTSP")
        
        # Orientation & Flips
        orient_cfg = config.get("orientation", {})
        self.hflip = orient_cfg.get("hflip", False)
        self.vflip = orient_cfg.get("vflip", False)
        self.rotation = orient_cfg.get("rotation", 0)
        self.orient_presets = orient_cfg.get("presets", ["Normal (0°)", "180° (Upside Down)", "H-Flip", "V-Flip"])
        
        # Digital Cropping & Zoom
        crop_cfg = config.get("crop", {})
        self.crop_enabled = crop_cfg.get("enabled", False)
        self.crop_preset = crop_cfg.get("preset", "1.0x (Full)")
        self.crop_zoom = crop_cfg.get("zoom", 1.0)
        self.crop_x_offset = crop_cfg.get("x_offset", 0.0)
        self.crop_y_offset = crop_cfg.get("y_offset", 0.0)
        self.crop_presets = crop_cfg.get("presets", ["1.0x (Full)", "1.2x Zoom", "1.5x Zoom", "2.0x Zoom", "Center 50%", "Top-Half", "Bottom-Half"])

        # Camera Parameters: FPS
        fps_cfg = config.get("fps", {})
        self.fps_enabled = fps_cfg.get("enabled", True)
        self.target_fps = fps_cfg.get("value", 30)
        self.fps_presets = fps_cfg.get("presets", [15, 24, 30, 60])
        
        # Resolution
        res_cfg = config.get("resolution", {})
        self.res_enabled = res_cfg.get("enabled", True)
        self.resolution_name = res_cfg.get("value", "1080p")
        self.width = res_cfg.get("width", 1920)
        self.height = res_cfg.get("height", 1080)
        self.res_presets = res_cfg.get("presets", ["1080p", "720p", "480p", "360p"])
        
        # Quality
        qual_cfg = config.get("quality", {})
        self.quality_enabled = qual_cfg.get("enabled", True)
        self.quality_name = qual_cfg.get("value", "High")
        self.jpeg_quality = QUALITY_MAP.get(self.quality_name, 85)
        self.qual_presets = qual_cfg.get("presets", ["Medium", "High", "Ultra"])
        
        # Bitrate
        bit_cfg = config.get("bitrate", {})
        self.bitrate_enabled = bit_cfg.get("enabled", True)
        self.bitrate_name = bit_cfg.get("value", "2048kbps")
        self.bitrate_presets = bit_cfg.get("presets", ["1024kbps", "2048kbps", "4096kbps", "8192kbps"])
        
        # Aspect Ratio
        ar_cfg = config.get("aspect_ratio", {})
        self.ar_enabled = ar_cfg.get("enabled", True)
        self.aspect_ratio = ar_cfg.get("value", "16:9")
        self.ar_presets = ar_cfg.get("presets", ["4:3", "16:9", "21:9"])
        
        # Hardware specs
        hw_cfg = config.get("hardware", {})
        self.hardware_model = hw_cfg.get("model", f"RPi Camera Sensor {self.camera_id}")
        self.sensor_size = hw_cfg.get("sensor_size", "1/2.8\"")
        self.shutter_speed = hw_cfg.get("shutter_speed", "1/1000s")
        self.aperture = hw_cfg.get("aperture", "f/1.8")
        self.iso = hw_cfg.get("iso", 100)
        
        # Raw Frame Buffer & Lock (High-performance background capture)
        self.lock = threading.Lock()
        self.raw_frame = None
        self.last_capture_unix = time.time()
        self.raw_lock = threading.Lock()
        self.is_simulated = True
        self.is_running = True
        self.picam = None
        self.frame_count = 0
        self.start_time = time.time()
        self.actual_fps = 0.0
        self.last_frame_time = time.time()
        
        # Init hardware backend ONCE at native resolution & start capture worker thread
        self._init_backend()
        self.capture_thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.capture_thread.start()
        
        # Register RTSP stream
        self.update_rtsp_stream()

    def _init_backend(self):
        """Initializes Picamera2 hardware once at fixed 1920x1080 resolution"""
        if HAS_PICAMERA2:
            try:
                self.picam = Picamera2(self.camera_id)
                config = self.picam.create_preview_configuration(
                    main={"size": (1920, 1080), "format": "YUV420"}
                )
                try:
                    from picamera2 import Transform
                    config.transform = Transform(hflip=True, vflip=True)
                except Exception:
                    pass
                self.picam.configure(config)
                self.picam.start()
                self.is_simulated = False
                logger.info(f"Picamera2({self.camera_id}) initialized once at fixed 1920x1080 hardware capture resolution.")
                return
            except Exception as e:
                logger.warning(f"Picamera2({self.camera_id}) init error: {e}. Using synthetic simulator.")
                self.picam = None
                self.is_simulated = True
        
        self.is_simulated = True
        logger.info(f"Camera {self.camera_id} initialized in SIMULATION mode.")

    def _stop_backend(self):
        """Releases the camera hardware resources"""
        if not self.is_simulated and self.picam:
            try:
                self.picam.stop()
                self.picam.close()
            except Exception as e:
                logger.error(f"Picamera2 stop error: {e}")
            finally:
                self.picam = None
        with self.raw_lock:
            self.raw_frame = None
        logger.info(f"Camera {self.camera_id} hardware released.")

    def _capture_worker(self):
        """Background thread grabbing raw frames and recording microsecond UNIX capture timestamps"""
        while self.is_running:
            if not self.enabled:
                time.sleep(1)
                continue
                
            capture_unix = time.time()
            if not self.is_simulated and self.picam:
                try:
                    frame_yuv = self.picam.capture_array()
                    frame_bgr = cv2.cvtColor(frame_yuv, cv2.COLOR_YUV2BGR_I420)
                    with self.raw_lock:
                        self.raw_frame = frame_bgr
                        self.last_capture_unix = capture_unix
                except Exception as e:
                    logger.error(f"Picamera2 background frame grab error: {e}")
                    time.sleep(0.05)
            else:
                frame_bgr = self.generate_synthetic_frame(capture_unix)
                with self.raw_lock:
                    self.raw_frame = frame_bgr
                    self.last_capture_unix = capture_unix
                time.sleep(0.03)

    def update_rtsp_stream(self):
        """Updates RTSP server registration with current settings"""
        rtsp_manager.register_camera_stream(
            cam_id=self.camera_id,
            codec=self.codec,
            width=self.width,
            height=self.height,
            fps=self.target_fps if self.fps_enabled else 30,
            bitrate=self.bitrate_name if self.bitrate_enabled else "Auto"
        )

    def set_config(self, data):
        """Updates dynamic camera settings in memory"""
        with self.lock:
            if "enabled" in data:
                new_enabled = bool(data["enabled"])
                if new_enabled != self.enabled:
                    self.enabled = new_enabled
                    if self.enabled:
                        self._init_backend()
                    else:
                        self._stop_backend()
            
            if "codec" in data and data["codec"] in ["H.264", "H.265"]:
                self.codec = str(data["codec"])
                
            if "protocol" in data:
                self.protocol = str(data["protocol"])

            # Orientation Flips & Rotations
            if "hflip" in data:
                self.hflip = bool(data["hflip"])
            if "vflip" in data:
                self.vflip = bool(data["vflip"])
            if "rotation" in data:
                self.rotation = int(data["rotation"])
            if "orientation_mode" in data:
                mode = str(data["orientation_mode"])
                if mode == "Normal (0°)":
                    self.hflip, self.vflip, self.rotation = False, False, 0
                elif mode == "180° (Upside Down)":
                    self.hflip, self.vflip, self.rotation = True, True, 180
                elif mode == "H-Flip":
                    self.hflip, self.vflip, self.rotation = True, False, 0
                elif mode == "V-Flip":
                    self.hflip, self.vflip, self.rotation = False, True, 0

            # Digital Cropping & Zoom
            if "crop_enabled" in data:
                self.crop_enabled = bool(data["crop_enabled"])
            if "crop_preset" in data:
                self.crop_preset = str(data["crop_preset"])
                if self.crop_preset in CROP_PRESETS:
                    c = CROP_PRESETS[self.crop_preset]
                    self.crop_zoom = c["zoom"]
                    self.crop_x_offset = c["x_offset"]
                    self.crop_y_offset = c["y_offset"]

            # FPS
            if "fps_enabled" in data:
                self.fps_enabled = bool(data["fps_enabled"])
            if "fps" in data:
                self.target_fps = int(data["fps"])

            # Resolution
            if "res_enabled" in data:
                self.res_enabled = bool(data["res_enabled"])
            if "resolution" in data:
                res_val = str(data["resolution"])
                if res_val in RESOLUTION_MAP:
                    self.resolution_name = res_val
                    self.width, self.height = RESOLUTION_MAP[res_val]

            # Quality
            if "quality_enabled" in data:
                self.quality_enabled = bool(data["quality_enabled"])
            if "quality" in data:
                self.quality_name = str(data["quality"])
                self.jpeg_quality = QUALITY_MAP.get(self.quality_name, 85)

            # Bitrate
            if "bitrate_enabled" in data:
                self.bitrate_enabled = bool(data["bitrate_enabled"])
            if "bitrate" in data:
                self.bitrate_name = str(data["bitrate"])

            # Aspect Ratio
            if "ar_enabled" in data:
                self.ar_enabled = bool(data["ar_enabled"])
            if "aspect_ratio" in data:
                self.aspect_ratio = str(data["aspect_ratio"])

            self.update_rtsp_stream()
            return self.get_status()

    def get_processed_frame(self):
        """Software Post-Processing Pipeline: Raw Frame -> Crop -> Flip/Rotate -> Resize -> OSD"""
        with self.raw_lock:
            if self.raw_frame is None:
                return None, time.time()
            frame = self.raw_frame.copy()
            capture_unix = self.last_capture_unix

        h, w = frame.shape[:2]

        # 1. Digital Cropping / Zoom ROI
        if self.crop_enabled and self.crop_zoom > 1.0:
            crop_w = int(w / self.crop_zoom)
            crop_h = int(h / self.crop_zoom)
            
            start_x = int((w - crop_w) * 0.5 + self.crop_x_offset * (w - crop_w) * 0.5)
            start_y = int((h - crop_h) * 0.5 + self.crop_y_offset * (h - crop_h) * 0.5)
            
            start_x = max(0, min(w - crop_w, start_x))
            start_y = max(0, min(h - crop_h, start_y))
            
            frame = frame[start_y:start_y + crop_h, start_x:start_x + crop_w]

        # 2. Orientation Flips
        if self.hflip and self.vflip:
            frame = cv2.flip(frame, -1)  # 180° upside down
        elif self.hflip:
            frame = cv2.flip(frame, 1)   # Horizontal mirror
        elif self.vflip:
            frame = cv2.flip(frame, 0)   # Vertical flip

        # 3. Extra Degrees Rotation
        if self.rotation == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotation == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # 4. Post-processing Resolution Resize
        target_w, target_h = (self.width, self.height) if self.res_enabled else (w, h)
        if (frame.shape[1], frame.shape[0]) != (target_w, target_h):
            frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

        # 5. OSD Telemetry Badge
        cv2.putText(frame, f"CAM {self.camera_id} [{self.codec}] {target_w}x{target_h}", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

        return frame, capture_unix

    def generate_synthetic_frame(self, capture_unix=None):
        """Generates realistic synthetic video stream with test patterns & UNIX timestamp"""
        w, h = 1920, 1080
        img = np.zeros((h, w, 3), dtype=np.uint8)
        if capture_unix is None:
            capture_unix = time.time()

        t = capture_unix - self.start_time
        bg_r = int((math.sin(t * 0.5) * 0.5 + 0.5) * 40) + 15
        bg_g = int((math.cos(t * 0.7) * 0.5 + 0.5) * 50) + 20
        bg_b = int((math.sin(t * 0.3 + 1.0) * 0.5 + 0.5) * 70) + 30
        img[:, :] = (bg_b, bg_g, bg_r)

        grid_step = max(40, int(w / 16))
        for x in range(0, w, grid_step):
            cv2.line(img, (x, 0), (x, h), (45, 55, 65), 1)
        for y in range(0, h, grid_step):
            cv2.line(img, (0, y), (w, y), (45, 55, 65), 1)

        cx = int((math.sin(t * 1.5) * 0.35 + 0.5) * w)
        cy = int((math.cos(t * 1.2) * 0.35 + 0.5) * h)
        radius = int(min(w, h) * 0.08)
        
        cv2.circle(img, (cx, cy), radius + 4, (0, 215, 255), 2)
        cv2.circle(img, (cx, cy), radius, (255, 120, 0), -1)

        cv2.rectangle(img, (0, 0), (w, 60), (15, 23, 42), -1)
        cv2.line(img, (0, 60), (w, 60), (59, 130, 246), 2)

        title_text = f"CAM {self.camera_id}: {self.name} | [{self.codec}] RTSP STREAM"
        time_text = datetime.datetime.fromtimestamp(capture_unix, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cv2.putText(img, title_text, (20, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (241, 245, 249), 2, cv2.LINE_AA)
        cv2.putText(img, time_text, (w - 380, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (52, 211, 153), 2, cv2.LINE_AA)

        cv2.rectangle(img, (0, h - 45), (w, h), (15, 23, 42), -1)
        cv2.line(img, (0, h - 45), (w, h - 45), (59, 130, 246), 1)

        fps_val = self.target_fps if self.fps_enabled else 30
        res_str = f"{self.width}x{self.height}"
        bit_str = self.bitrate_name if self.bitrate_enabled else "OFF"
        osd_bottom = f"RES: {res_str} | FPS: {fps_val} | CODEC: {self.codec} | BITRATE: {bit_str} | TS: {capture_unix:.6f}"
        cv2.putText(img, osd_bottom, (20, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (203, 213, 225), 1, cv2.LINE_AA)

        return img

    def get_frame_bytes(self):
        """Returns tuple of (encoded_jpeg_bytes, capture_unix_timestamp)"""
        now = time.time()
        dt = now - self.last_frame_time
        if dt > 0:
            self.actual_fps = 0.9 * self.actual_fps + 0.1 * (1.0 / dt)
        self.last_frame_time = now
        self.frame_count += 1

        frame_bgr, capture_unix = self.get_processed_frame()
        if frame_bgr is None:
            capture_unix = time.time()
            frame_bgr = self.generate_synthetic_frame(capture_unix)

        q = self.jpeg_quality if self.quality_enabled else 85
        _, jpeg = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, q])
        return jpeg.tobytes(), capture_unix

    def get_status(self):
        """Returns camera metadata, settings, hardware details, and frame sync UNIX timestamp"""
        with self.lock:
            orient_mode = "Normal (0°)"
            if self.hflip and self.vflip:
                orient_mode = "180° (Upside Down)"
            elif self.hflip:
                orient_mode = "H-Flip"
            elif self.vflip:
                orient_mode = "V-Flip"

            now_unix = self.last_capture_unix
            iso_str = datetime.datetime.fromtimestamp(now_unix, tz=datetime.timezone.utc).isoformat()

            return {
                "id": self.camera_id,
                "name": self.name,
                "enabled": self.enabled,
                "codec": self.codec,
                "protocol": self.protocol,
                "rtsp_url": rtsp_manager.get_rtsp_url(self.camera_id),
                "sync_telemetry": {
                    "timestamp": round(now_unix, 6),
                    "timestamp_iso": iso_str,
                    "frame_age_ms": round((time.time() - now_unix) * 1000.0, 2)
                },
                "orientation": {
                    "hflip": self.hflip,
                    "vflip": self.vflip,
                    "rotation": self.rotation,
                    "mode": orient_mode,
                    "presets": self.orient_presets
                },
                "crop": {
                    "enabled": self.crop_enabled,
                    "preset": self.crop_preset,
                    "zoom": self.crop_zoom,
                    "x_offset": self.crop_x_offset,
                    "y_offset": self.crop_y_offset,
                    "presets": self.crop_presets
                },
                "fps": {
                    "enabled": self.fps_enabled,
                    "value": self.target_fps,
                    "actual": round(self.actual_fps, 1),
                    "presets": self.fps_presets
                },
                "resolution": {
                    "enabled": self.res_enabled,
                    "name": self.resolution_name,
                    "width": self.width,
                    "height": self.height,
                    "presets": self.res_presets
                },
                "quality": {
                    "enabled": self.quality_enabled,
                    "name": self.quality_name,
                    "jpeg_quality": self.jpeg_quality,
                    "presets": self.qual_presets
                },
                "bitrate": {
                    "enabled": self.bitrate_enabled,
                    "name": self.bitrate_name,
                    "presets": self.bitrate_presets
                },
                "aspect_ratio": {
                    "enabled": self.ar_enabled,
                    "name": self.aspect_ratio,
                    "presets": self.ar_presets
                },
                "hardware": {
                    "model": self.hardware_model,
                    "sensor_size": self.sensor_size,
                    "shutter_speed": self.shutter_speed,
                    "aperture": self.aperture,
                    "iso": self.iso,
                    "is_simulated": self.is_simulated
                }
            }


class CameraManager:
    """Global manager for all camera devices in the workspace"""
    def __init__(self, config_path="camera_config.json"):
        self.config_path = config_path
        self.cameras = {}
        self.load_cameras()

    def detect_cameras(self):
        """Dynamically probes for connected cameras via libcamera"""
        cameras_found = []
        import subprocess
        try:
            # Safely list cameras without acquiring them in Python
            output = subprocess.check_output(
                ["rpicam-hello", "--list-cameras"], 
                text=True, 
                stderr=subprocess.STDOUT, 
                timeout=5
            )
            for line in output.split('\n'):
                # Format is usually "0 : imx708 [4608x2592] (/base/...)"
                if line.strip().startswith(str(len(cameras_found)) + " :") or line.strip().startswith(str(len(cameras_found)) + ":"):
                    idx = len(cameras_found)
                    name_str = line.split(":", 1)[1].strip()
                    model_short = name_str.split(" ")[0]
                    cameras_found.append({
                        "id": idx,
                        "name": f"Camera {idx} ({model_short})",
                        "codec": "H.264",
                        "hardware": {"model": name_str, "is_simulated": False}
                    })
        except Exception as e:
            logger.warning(f"Failed to list cameras via rpicam-hello: {e}")
            
        return cameras_found

    def load_cameras(self):
        """Loads cameras by dynamically detecting hardware"""
        detected = self.detect_cameras()
        if not detected:
            logger.warning("No hardware cameras detected. System will wait for hardware to be connected.")
            
        saved_config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    for c in data.get("cameras", []):
                        saved_config[c["id"]] = c
            except Exception as e:
                logger.error(f"Error reading {self.config_path}: {e}")

        for cam_cfg in detected:
            cam_id = cam_cfg["id"]
            final_cfg = saved_config.get(cam_id, {}).copy()
            final_cfg.update(cam_cfg) # Overwrite hardware basics
            self.cameras[cam_id] = CameraDevice(final_cfg)

    def get_camera(self, cam_id):
        """Returns CameraDevice instance by ID"""
        return self.cameras.get(cam_id)

    def get_all_status(self):
        """Returns metrics and state for all registered cameras"""
        return [cam.get_status() for cam in self.cameras.values()]

    def generate_mjpeg_stream(self, cam_id):
        """Generator function for Flask HTTP MJPEG stream response with UNIX timestamp headers"""
        cam = self.get_camera(cam_id)
        if not cam:
            return

        while True:
            if not cam.enabled:
                time.sleep(1)
                continue

            res = cam.get_frame_bytes()
            if isinstance(res, tuple):
                frame_bytes, capture_unix = res
            else:
                frame_bytes, capture_unix = res, time.time()

            hdr = (
                f"--frame\r\n"
                f"Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(frame_bytes)}\r\n"
                f"X-Timestamp: {capture_unix:.6f}\r\n\r\n"
            ).encode('utf-8')

            yield (hdr + frame_bytes + b'\r\n')
            
            fps = cam.target_fps if cam.fps_enabled else 30
            sleep_time = max(0.01, 1.0 / max(1, fps))
            time.sleep(sleep_time)

camera_manager = CameraManager()
