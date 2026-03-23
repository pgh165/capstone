"""
고개 기울기 추정 모듈
- solvePnP를 이용한 Head Pose Estimation
- Pitch (고개 숙임), Yaw (좌우 회전), Roll (기울임) 추정
"""

import numpy as np
import cv2
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


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

        success, rotation_vector, translation_vector = cv2.solvePnP(
            self.model_points,
            image_points,
            self.camera_matrix,
            self.dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if not success:
            return 0.0, 0.0, 0.0

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
        Head Pose 기반 졸음 점수 산출 (0~100)
        - pitch < -15: 고개 숙임 → 높은 점수
        - |yaw| > 30: 고개 돌림 → 중간 점수
        - |roll| > 20: 고개 기울임 → 중간 점수
        """
        score = 0

        # Pitch 점수 (고개 숙임이 가장 중요)
        if pitch < -30:
            score += 60
        elif pitch < -20:
            score += 45
        elif pitch < -15:
            score += 30
        elif pitch < -10:
            score += 15

        # Yaw 점수 (좌우 돌림)
        abs_yaw = abs(yaw)
        if abs_yaw > 45:
            score += 25
        elif abs_yaw > 30:
            score += 15
        elif abs_yaw > 20:
            score += 5

        # Roll 점수 (좌우 기울임)
        abs_roll = abs(roll)
        if abs_roll > 30:
            score += 25
        elif abs_roll > 20:
            score += 15
        elif abs_roll > 10:
            score += 5

        return min(100, score)
