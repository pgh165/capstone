"""
카메라 캡처 모듈
- 데스크탑: OpenCV VideoCapture (웹캠)
- 라즈베리파이: Pi Camera V2
"""

import cv2
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class Camera:
    def __init__(self, source=None):
        if source is None:
            url = getattr(config, "CAMERA_URL", "") or ""
            source = url.strip() if url.strip() else config.CAMERA_INDEX

        if config.IS_DESKTOP:
            self.cap = cv2.VideoCapture(source)
            if isinstance(source, int):
                # 로컬 웹캠일 때만 해상도/FPS 강제 (HTTP MJPEG는 송출측 설정을 따름)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
                self.cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
            else:
                print(f"[Camera] 원격 스트림 사용: {source}")
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
                self.cap = cv2.VideoCapture(source)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
                config.IS_DESKTOP = True

    def read_frame(self):
        """프레임 읽기. (success, frame) 반환"""
        if config.IS_DESKTOP:
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
        if config.IS_DESKTOP:
            if self.cap is not None:
                self.cap.release()
        else:
            try:
                self.cap.stop()
            except Exception:
                pass
        print("[Camera] 카메라 해제 완료")
