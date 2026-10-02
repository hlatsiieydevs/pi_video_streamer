import sys
import os
import glob
import logging

# Configure path for Picamera2 if available
for p in ['/usr/lib/python3/dist-packages', '/usr/local/lib/python3/dist-packages']:
    if p not in sys.path:
        sys.path.append(p)

def check_connected_cameras():
    cameras_found = []
    
    # 1. Try Picamera2 hardware probe
    try:
        from picamera2 import Picamera2
        picam_list = Picamera2.cameras()
        for idx, dev in enumerate(picam_list):
            model = dev.get("Model", f"CSI Camera {idx}")
            cameras_found.append({
                "id": idx,
                "type": "CSI (Picamera2)",
                "model": model
            })
    except Exception as e:
        pass

    # 2. Fallback to /dev/video* devices if Picamera2 returned none
    if not cameras_found:
        video_devs = glob.glob("/dev/video*")
        # Filter primary capture devices
        for dev_path in sorted(video_devs):
            dev_num = dev_path.replace("/dev/video", "")
            if dev_num.isdigit() and int(dev_num) % 2 == 0:
                cameras_found.append({
                    "id": int(dev_num),
                    "type": "V4L2 / USB Device",
                    "model": f"Video Device ({dev_path})"
                })

    count = len(cameras_found)
    print("==========================================================")
    print("                CAMERA HARDWARE PROBE CHECK               ")
    print("==========================================================")

    if count > 0:
        print(f"[✓] SUCCESS: Found {count} camera device(s) connected:")
        for cam in cameras_found:
            print(f"    - Camera ID {cam['id']}: {cam['model']} [{cam['type']}]")
        print("==========================================================")
        sys.exit(0)
    else:
        print(f"[✗] ERROR: 0 cameras detected on this system!")
        print("    Reason: No CSI or V4L2 video devices were found under /dev/video* or libcamera.")
        print("    Terminating startup sequence.")
        print("==========================================================")
        sys.exit(1)

if __name__ == "__main__":
    check_connected_cameras()
