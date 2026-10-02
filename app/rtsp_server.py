import os
import sys
import time
import socket
import threading
import random
import logging
import struct

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] RTSP Server: %(message)s')
logger = logging.getLogger("RTSPServer")

# Standard default 128-byte JPEG Quantization tables fallback
DEFAULT_LUMA_DQT = bytes([
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68,109,103, 77, 24, 35, 55, 64, 81,104,113, 92,
    49, 64, 78, 87,103,121,120,101, 72, 92, 95, 98,112,100,103, 99
])
DEFAULT_CHROMA_DQT = bytes([
    17, 18, 24, 47, 99, 99, 99, 99, 18, 21, 26, 66, 99, 99, 99, 99,
    24, 26, 56, 99, 99, 99, 99, 99, 47, 66, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99,
    99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99
])
DEFAULT_DQT = DEFAULT_LUMA_DQT + DEFAULT_CHROMA_DQT

class RTSPClientHandler(threading.Thread):
    """Handles an individual RTSP client session with high-precision UNIX-derived RTP timestamp sync"""
    def __init__(self, client_socket, client_address, server_manager):
        super().__init__(daemon=True)
        self.client_socket = client_socket
        self.client_address = client_address
        self.server_manager = server_manager
        self.session_id = str(random.randint(10000000, 99999999))
        self.cam_id = 0
        self.state = "INIT"  # INIT, READY, PLAYING
        self.is_running = True
        self.stream_thread = None
        self.seq_num = 0
        self.timestamp = 0

    def run(self):
        logger.info(f"RTSP Client connected from {self.client_address[0]}:{self.client_address[1]}")
        self.client_socket.settimeout(1.0)
        buffer = ""

        try:
            while self.is_running:
                try:
                    data = self.client_socket.recv(2048)
                    if not data:
                        break
                    
                    # Skip client interleaved data packets if any
                    if data[0] == 36:  # '$'
                        continue

                    buffer += data.decode('utf-8', errors='ignore')
                    while "\r\n\r\n" in buffer:
                        req_text, buffer = buffer.split("\r\n\r\n", 1)
                        self.handle_rtsp_request(req_text)
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.debug(f"RTSP client receiver note: {e}")
                    break
        finally:
            self.is_running = False
            self.state = "INIT"
            try:
                self.client_socket.close()
            except Exception:
                pass
            logger.info(f"RTSP Client disconnected: {self.client_address[0]}")

    def handle_rtsp_request(self, req_text):
        lines = req_text.strip().split("\r\n")
        if not lines or not lines[0]:
            return

        request_line = lines[0].split(" ")
        if len(request_line) < 3:
            return

        method, url, version = request_line[0], request_line[1], request_line[2]
        
        # Extract CSeq
        cseq = "1"
        for line in lines[1:]:
            if line.lower().startswith("cseq:"):
                cseq = line.split(":", 1)[1].strip()

        # Parse Camera ID from URL (e.g., rtsp://10.0.0.5:8554/stream1 -> cam_id=0)
        if "/stream" in url:
            try:
                stream_num = int(url.split("/stream")[1].split("/")[0].split("?")[0])
                self.cam_id = max(0, stream_num - 1)
            except ValueError:
                self.cam_id = 0
        else:
            self.cam_id = 0

        logger.info(f"RTSP Request: {method} {url} (CSeq: {cseq})")

        if method == "OPTIONS":
            resp = (
                f"RTSP/1.0 200 OK\r\n"
                f"CSeq: {cseq}\r\n"
                f"Public: OPTIONS, DESCRIBE, SETUP, TEARDOWN, PLAY, PAUSE\r\n"
                f"Server: RPi BasicVideoStreamer RTSP Server 1.0\r\n\r\n"
            )
            self.client_socket.sendall(resp.encode('utf-8'))

        elif method == "DESCRIBE":
            sdp_body = (
                f"v=0\r\n"
                f"o=- {int(time.time())} 1 IN IP4 {self.server_manager.host_ip}\r\n"
                f"s=Camera {self.cam_id} RTSP Stream\r\n"
                f"c=IN IP4 {self.server_manager.host_ip}\r\n"
                f"t=0 0\r\n"
                f"m=video 0 RTP/AVP 26\r\n"
                f"a=control:streamid=0\r\n"
                f"a=framerate:30\r\n"
            )
            resp = (
                f"RTSP/1.0 200 OK\r\n"
                f"CSeq: {cseq}\r\n"
                f"Content-Type: application/sdp\r\n"
                f"Content-Base: {url}/\r\n"
                f"Content-Length: {len(sdp_body)}\r\n\r\n"
                f"{sdp_body}"
            )
            self.client_socket.sendall(resp.encode('utf-8'))

        elif method == "SETUP":
            self.state = "READY"
            resp = (
                f"RTSP/1.0 200 OK\r\n"
                f"CSeq: {cseq}\r\n"
                f"Transport: RTP/AVP/TCP;interleaved=0-1\r\n"
                f"Session: {self.session_id};timeout=60\r\n\r\n"
            )
            self.client_socket.sendall(resp.encode('utf-8'))

        elif method == "PLAY":
            self.state = "PLAYING"
            resp = (
                f"RTSP/1.0 200 OK\r\n"
                f"CSeq: {cseq}\r\n"
                f"Session: {self.session_id}\r\n"
                f"RTP-Info: url={url}/streamid=0;seq=1;rtptime=0\r\n\r\n"
            )
            self.client_socket.sendall(resp.encode('utf-8'))

            # Launch high-speed 30 FPS streaming thread
            if not self.stream_thread or not self.stream_thread.is_alive():
                self.stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
                self.stream_thread.start()

        elif method == "TEARDOWN":
            self.state = "INIT"
            self.is_running = False
            resp = (
                f"RTSP/1.0 200 OK\r\n"
                f"CSeq: {cseq}\r\n"
                f"Session: {self.session_id}\r\n\r\n"
            )
            self.client_socket.sendall(resp.encode('utf-8'))

    def _stream_loop(self):
        """Dedicated high-frequency worker sending 30 FPS RTP video packets to client"""
        logger.info(f"Started 30 FPS streaming loop for client {self.client_address[0]}")
        while self.is_running and self.state == "PLAYING":
            start_time = time.time()
            
            # Send latest video frame
            self.send_next_rtp_frame()

            # Target rate pacing (30 FPS default)
            from camera_manager import camera_manager
            cam = camera_manager.get_camera(self.cam_id)
            fps = cam.target_fps if (cam and cam.fps_enabled) else 30

            elapsed = time.time() - start_time
            sleep_time = max(0.001, (1.0 / max(1, fps)) - elapsed)
            time.sleep(sleep_time)

    def parse_jpeg_stream(self, b):
        """Extracts DQT tables and scan payload from raw JPEG bytes for RFC 2435 payloading"""
        dqt = DEFAULT_DQT
        scan_offset = 0
        pos = 0

        while pos < len(b) - 1:
            if b[pos] == 0xFF:
                marker = b[pos + 1]
                if marker == 0xDB:  # DQT marker
                    length = (b[pos + 2] << 8) | b[pos + 3]
                    dqt_chunk = b[pos + 4:pos + 2 + length]
                    if len(dqt_chunk) >= 130:
                        dqt = dqt_chunk[1:65] + dqt_chunk[66:130]
                    elif len(dqt_chunk) >= 65:
                        dqt = dqt_chunk[1:65] * 2
                    pos += 2 + length
                    continue
                elif marker == 0xDA:  # SOS marker
                    length = (b[pos + 2] << 8) | b[pos + 3]
                    scan_offset = pos + 2 + length
                    break
            pos += 1

        scan_data = b[scan_offset:] if scan_offset > 0 else b
        return dqt, scan_data

    def send_next_rtp_frame(self):
        """Packetizes latest frame bytes with microsecond UNIX-derived 90 kHz RTP timestamp"""
        try:
            from camera_manager import camera_manager
            cam = camera_manager.get_camera(self.cam_id)
            if not cam or not cam.enabled:
                return

            res = cam.get_frame_bytes()
            if isinstance(res, tuple):
                jpeg_bytes, capture_unix = res
            else:
                jpeg_bytes, capture_unix = res, time.time()

            if not jpeg_bytes or len(jpeg_bytes) < 100:
                return

            dqt, scan_data = self.parse_jpeg_stream(jpeg_bytes)

            w_blocks = min(255, max(1, cam.width // 8))
            h_blocks = min(255, max(1, cam.height // 8))

            max_payload = 1380
            total_len = len(scan_data)
            offset = 0

            # Convert exact microsecond UNIX timestamp to 90 kHz RTP clock ticks (RTSP RFC 2435 / RFC 3550 standard)
            rtp_timestamp = int((capture_unix * 90000.0)) & 0xFFFFFFFF

            while offset < total_len and self.is_running and self.state == "PLAYING":
                chunk_size = min(max_payload, total_len - offset)
                is_last = (offset + chunk_size >= total_len)

                self.seq_num = (self.seq_num + 1) & 0xFFFF

                # 1. RTP Header (12 bytes) with 90 kHz UNIX-derived frame timestamp
                marker_pt = 0x9A if is_last else 0x1A  # PT 26 (JPEG), Marker bit on last chunk
                rtp_hdr = struct.pack("!BBHII", 0x80, marker_pt, self.seq_num, rtp_timestamp, 0x12345678)

                # 2. Main JPEG Header (8 bytes according to RFC 2435)
                off_b0 = (offset >> 16) & 0xFF
                off_b1 = (offset >> 8) & 0xFF
                off_b2 = offset & 0xFF
                jpeg_hdr = struct.pack("!BBBBBBBB", 0, off_b0, off_b1, off_b2, 1, 255, w_blocks, h_blocks)

                # 3. Quantization Table Header (132 bytes, attached only to first fragment offset == 0)
                q_table_hdr = b""
                if offset == 0 and dqt and len(dqt) == 128:
                    q_table_hdr = struct.pack("!BBH", 0, 0, 128) + dqt

                payload = rtp_hdr + jpeg_hdr + q_table_hdr + scan_data[offset:offset + chunk_size]

                # 4. RTSP Interleaved TCP Framing Header (4 bytes: '$', channel=0, 16-bit length)
                rtsp_interleaved_hdr = struct.pack("!BBH", 0x24, 0, len(payload))

                # Send interleaved packet over TCP
                self.client_socket.sendall(rtsp_interleaved_hdr + payload)

                offset += chunk_size

        except (socket.error, BrokenPipeError):
            self.is_running = False
            self.state = "INIT"
        except Exception as e:
            logger.debug(f"RTP packet send error: {e}")


class RTSPServerManager:
    """Manages multi-threaded RTSP TCP server listening on port 8554"""
    def __init__(self, port=8554):
        self.port = port
        self.active_streams = {}
        self.lock = threading.Lock()
        self.is_running = False
        self.server_socket = None
        self.listen_thread = None
        self.host_ip = self._detect_host_ip()

    def _detect_host_ip(self):
        """Detects primary local network IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start_server(self):
        """Starts RTSP TCP listener service on port 8554"""
        with self.lock:
            if self.is_running:
                return
            self.is_running = True
            
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind(("0.0.0.0", self.port))
                self.server_socket.listen(10)
                
                self.listen_thread = threading.Thread(target=self._listen_worker, daemon=True)
                self.listen_thread.start()
                logger.info(f"RTSP Server TCP Listener ACTIVE on rtsp://{self.host_ip}:{self.port}")
            except Exception as e:
                logger.error(f"Failed to start RTSP socket server on port {self.port}: {e}")

    def _listen_worker(self):
        """Background thread accepting client socket connections"""
        while self.is_running and self.server_socket:
            try:
                client_sock, client_addr = self.server_socket.accept()
                handler = RTSPClientHandler(client_sock, client_addr, self)
                handler.start()
            except Exception as e:
                if self.is_running:
                    logger.debug(f"RTSP accept loop exception: {e}")
                break

    def register_camera_stream(self, cam_id, codec="H.264", width=1920, height=1080, fps=30, bitrate="2048kbps"):
        """Registers or updates camera RTSP stream profile"""
        with self.lock:
            url = f"rtsp://{self.host_ip}:{self.port}/stream{cam_id + 1}"
            self.active_streams[cam_id] = {
                "cam_id": cam_id,
                "url": url,
                "codec": codec,
                "resolution": f"{width}x{height}",
                "fps": fps,
                "bitrate": bitrate,
                "status": "ACTIVE",
                "transport": "RTP/AVP/TCP",
                "active_clients": 1
            }
            logger.info(f"Registered RTSP Stream Cam {cam_id}: {url} [{codec}]")
            return url

    def get_rtsp_url(self, cam_id):
        """Returns the network RTSP URL for a camera ID"""
        with self.lock:
            stream = self.active_streams.get(cam_id)
            if stream:
                return stream["url"]
            return f"rtsp://{self.host_ip}:{self.port}/stream{cam_id + 1}"

    def stop_server(self):
        """Stops RTSP server service"""
        with self.lock:
            self.is_running = False
            if self.server_socket:
                try:
                    self.server_socket.close()
                except Exception:
                    pass
            logger.info("RTSP Server Service stopped.")

rtsp_manager = RTSPServerManager()
