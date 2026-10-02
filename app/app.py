import os
import sys
import json
from flask import Flask, Response, jsonify, send_from_directory, request
from camera_manager import camera_manager
from rtsp_server import rtsp_manager

app = Flask(__name__, static_folder='dist', static_url_path='')

@app.route('/')
def index():
    """Serves the built frontend Vue app or API instructions"""
    if os.path.exists(os.path.join(app.static_folder, 'index.html')):
        resp = send_from_directory(app.static_folder, 'index.html')
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return resp
    return jsonify({
        "service": "Basic Video Streamer - RPi IP Camera Emulation Service",
        "status": "RUNNING",
        "api_endpoints": {
            "all_cameras": "/api/cameras",
            "camera_status": "/api/camera/<cam_id>/status",
            "camera_config": "POST /api/camera/<cam_id>/config",
            "rtsp_info": "/api/camera/<cam_id>/rtsp_url",
            "video_feed": "/video_feed/<cam_id>"
        },
        "instructions": "Build Vue 3 frontend using 'npm run build' or run Vite dev server on port 5173"
    })

@app.route('/video_feed/<int:cam_id>')
def video_feed(cam_id):
    """Multipart HTTP MJPEG stream preview endpoint for specified camera ID"""
    cam = camera_manager.get_camera(cam_id)
    if not cam:
        return jsonify({"error": f"Camera {cam_id} not found"}), 404

    return Response(
        camera_manager.generate_mjpeg_stream(cam_id),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/api/cameras')
def api_all_cameras():
    """Returns list of status and metadata for all available cameras"""
    return jsonify({
        "status": "OK",
        "count": len(camera_manager.cameras),
        "cameras": camera_manager.get_all_status()
    })

@app.route('/api/camera/<int:cam_id>/status')
def api_camera_status(cam_id):
    """Returns telemetry status, encoding parameters and hardware info for camera ID"""
    cam = camera_manager.get_camera(cam_id)
    if not cam:
        return jsonify({"error": f"Camera {cam_id} not found"}), 404
    return jsonify(cam.get_status())

@app.route('/api/camera/<int:cam_id>/config', methods=['POST'])
def api_camera_config(cam_id):
    """Dynamically reconfigures encoding, presets, parameters or hardware settings"""
    cam = camera_manager.get_camera(cam_id)
    if not cam:
        return jsonify({"error": f"Camera {cam_id} not found"}), 404

    data = request.json or {}
    updated_status = cam.set_config(data)
    return jsonify({
        "success": True,
        "message": f"Camera {cam_id} reconfigured successfully",
        "camera": updated_status
    })

@app.route('/api/camera/<int:cam_id>/rtsp_url')
def api_camera_rtsp_url(cam_id):
    """Returns RTSP URL and streaming configuration details"""
    cam = camera_manager.get_camera(cam_id)
    if not cam:
        return jsonify({"error": f"Camera {cam_id} not found"}), 404

    rtsp_url = rtsp_manager.get_rtsp_url(cam_id)
    return jsonify({
        "camera_id": cam_id,
        "rtsp_url": rtsp_url,
        "codec": cam.codec,
        "resolution": f"{cam.width}x{cam.height}",
        "fps": cam.target_fps if cam.fps_enabled else 30,
        "bitrate": cam.bitrate_name if cam.bitrate_enabled else "OFF",
        "protocol": cam.protocol
    })

if __name__ == '__main__':
    # Start RTSP service
    rtsp_manager.start_server()
    print("==========================================================")
    print(" BASIC VIDEO STREAMER: Raspberry Pi IP Camera Emulator   ")
    print(" Server running on http://0.0.0.0:5000                   ")
    print("==========================================================")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
