"""
고개 기울기 추정 모듈
- solvePnP를 이용한 Head Pose Estimation
- Pitch (고개 숙임), Yaw (좌우 회전), Roll (기울임) 추정
- 이전 프레임 결과를 초기값으로 활용하여 수렴 가속
"""

import numpy as np
import cv2
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _lerp_score(value, breakpoints):
    """구간별 선형 보간으로 점수를 산출한다."""
    if value <= breakpoints[0][0]:
        return breakpoints[0][1]
    if value >= breakpoints[-1][0]:
        return breakpoints[-1][1]
    for i in range(len(breakpoints) - 1):
        x0, y0 = breakpoints[i]
        x1, y1 = breakpoints[i + 1]
        if value <= x1:
            t = (value - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return breakpoints[-1][1]


class HeadPoseEstimator:
    def __init__(self):
        # 3D 모델 포인트 (일반적인 얼굴 비율 기준)
        self.model_points = np.array([
            (0.0, 0.0, 0.0),         # 코 끝
            (0.0, -330.0, -65.0),     # 턱
            (-225.0, 170.0, -135.0),  # 왼쪽 눈 끝
            (225.0, 170.0, -135.0),   # 오른쪽 눈 끝
            (-150.0, -150.0, -125.0), # 왼쪽 입 끝
            (150.0, -150.0, -125.0)   # 오른쪽 입 끝
        ], dtype=np.float64)

        self.camera_matrix = None
        self.dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        # 이전 프레임의 회전/이동 벡터 (초기값 재활용)
        self._prev_rvec = None
        self._prev_tvec = None

    def _get_camera_matrix(self, frame_shape):
        """카메라 내부 파라미터 행렬 생성"""
        h, w = frame_shape[:2]
        focal_length = w
        center = (w / 2, h / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float64)
        return camera_matrix

    def estimate(self, face_points, frame_shape):
        """
        Head Pose 추정
        face_points: 6개 2D 포인트 (nose, chin, left_eye, right_eye, left_mouth, right_mouth)
        frame_shape: 프레임 크기

        Returns: (pitch, yaw, roll) 각도 (도 단위)
        """
        if self.camera_matrix is None:
            self.camera_matrix = self._get_camera_matrix(frame_shape)

        image_points = face_points.reshape(-1, 2)

        # 이전 프레임 결과를 초기값으로 활용 → 수렴 속도 향상
        if self._prev_rvec is not None:
            success, rotation_vector, translation_vector = cv2.solvePnP(
                self.model_points,
                image_points,
                self.camera_matrix,
                self.dist_coeffs,
                rvec=self._prev_rvec.copy(),
                tvec=self._prev_tvec.copy(),
                useExtrinsicGuess=True,
                flags=cv2.SOLVEPNP_ITERATIVE
            )
        else:
            success, rotation_vector, translation_vector = cv2.solvePnP(
                self.model_points,
                image_points,
                self.camera_matrix,
                self.dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE
            )

        if not success:
            return 0.0, 0.0, 0.0

        # 다음 프레임의 초기값으로 저장
        self._prev_rvec = rotation_vector
        self._prev_tvec = translation_vector

        # 회전 벡터 → 회전 행렬 → 오일러 각도
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        proj_matrix = np.hstack((rotation_matrix, translation_vector))
        euler_angles = cv2.decomposeProjectionMatrix(proj_matrix)[6]

        pitch = euler_angles[0][0]  # 고개 숙임 (-, 아래로)
        yaw = euler_angles[1][0]    # 좌우 회전
        roll = euler_angles[2][0]   # 좌우 기울임

        return pitch, yaw, roll

    def get_head_score(self, pitch, yaw, roll):
        """
        Head Pose 기반 졸음 점수 산출 (0~100, 연속 보간)
        - pitch < 0: 고개 숙임 → 높은 점수
        - |yaw| 큼: 고개 돌림 → 중간 점수
        - |roll| 큼: 고개 기울임 → 중간 점수
        """
        # Pitch 점수 (고개 숙임이 가장 중요)
        pitch_score = _lerp_score(-pitch, [
            (0, 0), (10, 10), (15, 25), (20, 40),
            (30, 60), (45, 80), (60, 100),
        ])

        # Yaw 점수 (좌우 돌림)
        yaw_score = _lerp_score(abs(yaw), [
            (0, 0), (20, 5), (30, 15), (45, 25), (60, 35),
        ])

        # Roll 점수 (좌우 기울임)
        roll_score = _lerp_score(abs(roll), [
            (0, 0), (10, 5), (20, 15), (30, 25), (45, 35),
        ])

        return min(100, pitch_score + yaw_score + roll_score)
