"""
카메라 캡처 모듈
- 데스크탑/WSL: ffmpeg subprocess로 V4L2 MJPEG 캡처 (pip OpenCV는 V4L2 미포함)
- 라즈베리파이: Pi Camera V2
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

        if source is None:
            source = config.CAMERA_INDEX

        if config.IS_DESKTOP:
            if isinstance(source, int):
                self._open_ffmpeg(source)
            else:
                # HTTP 스트림 (레거시 호환)
                self.cap = cv2.VideoCapture(source)
                print(f"[Camera] 원격 스트림 사용: {source}")
                self._proc = None
        else:
            try:
                from picamera2 import Picamera2
                self.cap = Picamera2()
                camera_config = self.cap.create_preview_configuration(
                    main={"size": (config.CAMERA_WIDTH, config.CAMERA_HEIGHT),
                          "format": "RGB888"}
                )
                self.cap.configure(camera_config)
                self.cap.start()
            except ImportError:
                print("[Camera] picamera2를 사용할 수 없습니다. 웹캠으로 전환합니다.")
                self._open_ffmpeg(source if isinstance(source, int) else 0)
                config.IS_DESKTOP = True

    def _open_ffmpeg(self, index: int):
        """ffmpeg subprocess로 /dev/videoN을 열어 raw BGR 프레임을 stdout으로 받는다."""
        device = f"/dev/video{index}"
        w, h, fps = config.CAMERA_WIDTH, config.CAMERA_HEIGHT, config.CAMERA_FPS
        cmd = [
            "ffmpeg", "-loglevel", "quiet",
            "-f", "v4l2",
            "-input_format", "mjpeg",
            "-video_size", f"{w}x{h}",
            "-framerate", str(fps),
            "-i", device,
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "pipe:1",
        ]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._frame_size = w * h * 3
        self._width = w
        self._height = h
        self.cap = None
        print(f"[Camera] ffmpeg subprocess로 열기: {device} ({w}x{h}@{fps}fps)")
        # 워밍업 프레임을 백그라운드 스레드에서 미리 소비
        self._warmup_event = threading.Event()
        threading.Thread(target=self._warmup, daemon=True).start()

    def _warmup(self):
        for _ in range(5):
            self._proc.stdout.read(self._frame_size)
        self._warmup_event.set()

    def read_frame(self):
        """프레임 읽기. (success, frame) 반환"""
        if self._proc is not None:
            self._warmup_event.wait()  # 워밍업 완료 대기
            raw = self._proc.stdout.read(self._frame_size)
            if len(raw) != self._frame_size:
                return False, None
            frame = np.frombuffer(raw, dtype=np.uint8).reshape((self._height, self._width, 3))
            return True, frame.copy()
        elif config.IS_DESKTOP:
            ret, frame = self.cap.read()
            return ret, frame
        else:
            try:
                frame = self.cap.capture_array()
                return True, frame
            except Exception as e:
                print(f"[Camera] 프레임 캡처 오류: {e}")
                return False, None

    def release(self):
        """카메라 리소스 해제"""
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait()
        elif config.IS_DESKTOP and self.cap is not None:
            self.cap.release()
        else:
            try:
                self.cap.stop()
            except Exception:
                pass
        print("[Camera] 카메라 해제 완료")
