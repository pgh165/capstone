"""
카메라 캡처 모듈
- CAMERA_URL이 설정되면 HTTP 스트림(MJPEG 브릿지 등)으로 캡처
- 없으면 ffmpeg subprocess로 로컬 V4L2 장치를 직접 캡처 (pip OpenCV는 V4L2 미포함)
"""

import cv2
import sys
import os
import subprocess
import threading
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class Camera:
    def __init__(self, source=None):
        self._proc = None
        self._warmup_event = None

        if source is None:
            url = (getattr(config, "CAMERA_URL", "") or "").strip()
            source = url if url else config.CAMERA_INDEX

        if isinstance(source, str) and source.startswith("http"):
            self.cap = cv2.VideoCapture(source)
            print(f"[Camera] 원격 스트림 사용: {source}")
            if not self.cap.isOpened():
                raise RuntimeError(f"[Camera] 스트림을 열 수 없습니다: {source}")
        else:
            index = source if isinstance(source, int) else config.CAMERA_INDEX
            self._open_ffmpeg(index)
            self.cap = None

    def _open_ffmpeg(self, index: int):
        device = f"/dev/video{index}"
        w, h, fps = config.CAMERA_WIDTH, config.CAMERA_HEIGHT, config.CAMERA_FPS
        cmd = [
            "ffmpeg", "-loglevel", "quiet",
            "-f", "v4l2", "-input_format", "mjpeg",
            "-video_size", f"{w}x{h}", "-framerate", str(fps),
            "-i", device,
            "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1",
        ]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._frame_size = w * h * 3
        self._width = w
        self._height = h
        self._warmup_event = threading.Event()
        threading.Thread(target=self._warmup, daemon=True).start()
        print(f"[Camera] ffmpeg subprocess로 열기: {device} ({w}x{h}@{fps}fps)")

    def _warmup(self):
        for _ in range(5):
            self._proc.stdout.read(self._frame_size)
        self._warmup_event.set()

    def read_frame(self):
        if self._proc is not None:
            self._warmup_event.wait()
            raw = self._proc.stdout.read(self._frame_size)
            if len(raw) != self._frame_size:
                return False, None
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((self._height, self._width, 3))
            return True, frame.copy()
        else:
            ret, frame = self.cap.read()
            return ret, frame

    def release(self):
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait()
        elif self.cap is not None:
            self.cap.release()
        print("[Camera] 카메라 해제 완료")
