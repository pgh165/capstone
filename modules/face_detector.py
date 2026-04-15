"""
얼굴 랜드마크 검출 모듈
- MediaPipe FaceLandmarker Tasks API (478개 랜드마크)
- 얼굴 미검출 추적
"""

import time
import cv2
import mediapipe as mp
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode


class FaceDetector:
    def __init__(self):
        # 모델 파일 경로 (한글 경로 문제 우회: 바이트로 읽어서 전달)
        model_path = os.path.join(config.BASE_DIR, 'models', 'face_landmarker.task')

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"[FaceDetector] 모델 파일을 찾을 수 없습니다: {model_path}\n"
                "다운로드: https://storage.googleapis.com/mediapipe-models/"
                "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
            )

        # 한글 경로 문제 우회: 모델을 바이트로 읽어서 전달
        with open(model_path, 'rb') as f:
            model_data = f.read()

        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=model_data),
            running_mode=VisionRunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self.landmarker = FaceLandmarker.create_from_options(options)
        # MediaPipe VIDEO 모드는 단조 증가 타임스탬프 필요. 실제 시간 기반으로 추적.
        self._start_time = time.time()
        self._last_timestamp_ms = -1

        # 얼굴 미검출 추적
        self.no_face_start_time = None
        self.no_face_duration = 0.0

        # 마지막 감지된 랜드마크 (내부 리스트 형태)
        self._last_landmarks = None

    def detect(self, frame):
        """
        얼굴 랜드마크 검출
        Returns: landmarks 리스트 (NormalizedLandmark) 또는 None
        """
        # BGR → RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # 실제 경과 시간(ms). 단조 증가 보장 (같거나 작으면 +1)
        ts = int((time.time() - self._start_time) * 1000)
        if ts <= self._last_timestamp_ms:
            ts = self._last_timestamp_ms + 1
        self._last_timestamp_ms = ts
        result = self.landmarker.detect_for_video(mp_image, ts)

        if result.face_landmarks and len(result.face_landmarks) > 0:
            self.no_face_start_time = None
            self.no_face_duration = 0.0
            self._last_landmarks = result.face_landmarks[0]
            return self._last_landmarks
        else:
            # 얼굴 미검출 시간 추적
            if self.no_face_start_time is None:
                self.no_face_start_time = time.time()
            self.no_face_duration = time.time() - self.no_face_start_time
            self._last_landmarks = None
            return None

    def is_no_face_alert(self):
        """얼굴 미검출이 임계값을 초과했는지 확인"""
        return self.no_face_duration >= config.NO_FACE_ALERT_SECONDS

    def get_no_face_duration(self):
        """현재 얼굴 미검출 지속시간 반환"""
        return self.no_face_duration

    def get_eye_landmarks(self, landmarks, frame_shape):
        """좌우 눈 랜드마크 좌표 반환"""
        h, w = frame_shape[:2]
        left_eye = []
        for idx in config.LEFT_EYE_IDX:
            lm = landmarks[idx]
            left_eye.append([lm.x * w, lm.y * h])

        right_eye = []
        for idx in config.RIGHT_EYE_IDX:
            lm = landmarks[idx]
            right_eye.append([lm.x * w, lm.y * h])

        return np.array(left_eye), np.array(right_eye)

    def get_mouth_landmarks(self, landmarks, frame_shape):
        """입 랜드마크 좌표 반환"""
        h, w = frame_shape[:2]
        mouth = []
        for idx in config.MOUTH_IDX:
            lm = landmarks[idx]
            mouth.append([lm.x * w, lm.y * h])
        return np.array(mouth)

    def get_head_pose_points(self, landmarks, frame_shape):
        """Head Pose 추정용 6개 주요 포인트 반환"""
        h, w = frame_shape[:2]
        indices = [
            config.NOSE_TIP_IDX,
            config.CHIN_IDX,
            config.LEFT_EYE_CORNER_IDX,
            config.RIGHT_EYE_CORNER_IDX,
            config.LEFT_MOUTH_IDX,
            config.RIGHT_MOUTH_IDX
        ]
        points = []
        for idx in indices:
            lm = landmarks[idx]
            points.append([lm.x * w, lm.y * h])
        return np.array(points, dtype=np.float64)

    def draw_landmarks(self, frame, landmarks):
        """프레임에 랜드마크 그리기 (디버깅용)"""
        if landmarks is None:
            return frame

        h, w = frame.shape[:2]

        # 눈 그리기
        for idx in config.LEFT_EYE_IDX + config.RIGHT_EYE_IDX:
            lm = landmarks[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)

        # 입 그리기
        for idx in config.MOUTH_IDX:
            lm = landmarks[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (x, y), 2, (0, 0, 255), -1)

        return frame

    def release(self):
        """리소스 해제"""
        self.landmarker.close()
