"""
MJPEG 브릿지 서버 (Windows 호스트 전용)

WSL에서 usbipd로 웹캠 isoc 스트림이 깨지는 문제를 우회하기 위해,
Windows에서 카메라를 직접 점유한 뒤 HTTP/MJPEG으로 송출한다.

사용:
    python tools/mjpeg_server.py

WSL에서 수신:
    cv2.VideoCapture("http://<windows-host-ip>:8080/video")

종료: Ctrl+C
"""

import os
import threading
import time
import cv2
from flask import Flask, Response

CAMERA_INDEX = int(os.environ.get("MJPEG_CAMERA_INDEX", "0"))
WIDTH = int(os.environ.get("MJPEG_WIDTH", "640"))
HEIGHT = int(os.environ.get("MJPEG_HEIGHT", "480"))
FPS = int(os.environ.get("MJPEG_FPS", "30"))
JPEG_QUALITY = int(os.environ.get("MJPEG_QUALITY", "80"))
PORT = int(os.environ.get("MJPEG_PORT", "8080"))

app = Flask(__name__)

_lock = threading.Lock()
_cap = None
_latest_jpeg = None
_latest_ts = 0.0


def _open_camera():
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"카메라 인덱스 {CAMERA_INDEX} 열기 실패")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)
    print(f"[mjpeg] 카메라 열림: index={CAMERA_INDEX} {WIDTH}x{HEIGHT}@{FPS}fps")
    return cap


def _capture_loop():
    global _cap, _latest_jpeg, _latest_ts
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    fail_count = 0
    while True:
        try:
            if _cap is None or not _cap.isOpened():
                _cap = _open_camera()
            ret, frame = _cap.read()
            if not ret:
                fail_count += 1
                if fail_count > 30:
                    print("[mjpeg] 연속 캡처 실패 - 재오픈")
                    _cap.release()
                    _cap = None
                    fail_count = 0
                time.sleep(0.05)
                continue
            fail_count = 0
            ok, buf = cv2.imencode(".jpg", frame, encode_param)
            if not ok:
                continue
            with _lock:
                _latest_jpeg = buf.tobytes()
                _latest_ts = time.time()
        except Exception as e:
            print(f"[mjpeg] 캡처 루프 오류: {e}")
            if _cap is not None:
                _cap.release()
                _cap = None
            time.sleep(1.0)


def _frame_generator():
    boundary = b"--frame"
    last_sent = 0.0
    min_interval = 1.0 / max(FPS, 1)
    while True:
        with _lock:
            jpeg = _latest_jpeg
            ts = _latest_ts
        now = time.time()
        if jpeg is None or ts == last_sent:
            time.sleep(min_interval / 2)
            continue
        if now - last_sent < min_interval:
            time.sleep(min_interval - (now - last_sent))
        last_sent = ts
        yield (
            boundary
            + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(jpeg)).encode()
            + b"\r\n\r\n"
            + jpeg
            + b"\r\n"
        )


@app.route("/")
def index():
    return (
        '<html><body style="margin:0;background:#111">'
        '<img src="/video" style="width:100%"/>'
        "</body></html>"
    )


@app.route("/video")
def video():
    return Response(
        _frame_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/healthz")
def healthz():
    age = time.time() - _latest_ts if _latest_ts else None
    return {
        "alive": _latest_jpeg is not None,
        "frame_age_sec": age,
        "camera_index": CAMERA_INDEX,
        "resolution": [WIDTH, HEIGHT],
        "fps": FPS,
    }


if __name__ == "__main__":
    t = threading.Thread(target=_capture_loop, daemon=True)
    t.start()
    print(f"[mjpeg] http://0.0.0.0:{PORT}/video 송출 시작")
    app.run(host="0.0.0.0", port=PORT, threaded=True, debug=False)
