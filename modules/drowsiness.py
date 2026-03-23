"""
졸음 감지 모듈
- EAR (Eye Aspect Ratio) 계산
- MAR (Mouth Aspect Ratio) 계산
- 졸음 상태 추적
"""

import time
import numpy as np
from collections import deque
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def calculate_ear(eye_landmarks):
    """
    EAR (Eye Aspect Ratio) 계산
    EAR = (|P2 - P6| + |P3 - P5|) / (2 × |P1 - P4|)

    eye_landmarks: 6개 포인트 [P1, P2, P3, P4, P5, P6]
      P1, P4: 눈의 좌우 끝점 (가로)
      P2, P3: 눈의 상단 점 (세로)
      P5, P6: 눈의 하단 점 (세로)
    """
    p1, p2, p3, p4, p5, p6 = eye_landmarks

    # 세로 거리
    vertical_1 = np.linalg.norm(p2 - p6)
    vertical_2 = np.linalg.norm(p3 - p5)

    # 가로 거리
    horizontal = np.linalg.norm(p1 - p4)

    if horizontal == 0:
        return 0.0

    ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
    return ear


def calculate_mar(mouth_landmarks):
    """
    MAR (Mouth Aspect Ratio) 계산
    입의 벌어진 정도를 측정하여 하품 감지

    mouth_landmarks: 12개 포인트
      [0]=61, [1]=37, [2]=0, [3]=267, [4]=270, [5]=291,
      [6]=405, [7]=314, [8]=17, [9]=84, [10]=181, [11]=78
    """
    # 세로 거리 (입의 상하 열림)
    vertical_1 = np.linalg.norm(mouth_landmarks[1] - mouth_landmarks[9])   # 37-84
    vertical_2 = np.linalg.norm(mouth_landmarks[2] - mouth_landmarks[8])   # 0-17
    vertical_3 = np.linalg.norm(mouth_landmarks[3] - mouth_landmarks[7])   # 267-314

    # 가로 거리 (입의 좌우 폭)
    horizontal = np.linalg.norm(mouth_landmarks[0] - mouth_landmarks[5])   # 61-291

    if horizontal == 0:
        return 0.0

    mar = (vertical_1 + vertical_2 + vertical_3) / (2.0 * horizontal)
    return mar


class DrowsinessTracker:
    """졸음 상태 추적 클래스"""

    def __init__(self):
        # 눈 감김 추적
        self.eye_closed = False
        self.eye_close_start = None
        self.eye_close_duration = 0.0
        self.current_ear = 0.0

        # 하품 추적 (슬라이딩 윈도우)
        self.yawn_timestamps = deque()
        self.is_yawning = False
        self.current_mar = 0.0

        # 점수
        self.ear_score = 0
        self.mar_score = 0

    def update_ear(self, ear_value):
        """EAR 값 업데이트 및 눈 감김 추적"""
        self.current_ear = ear_value

        if ear_value < config.EAR_THRESHOLD:
            # 눈 감김
            if not self.eye_closed:
                self.eye_closed = True
                self.eye_close_start = time.time()
            self.eye_close_duration = time.time() - self.eye_close_start
        else:
            # 눈 뜸
            self.eye_closed = False
            self.eye_close_start = None
            self.eye_close_duration = 0.0

        self._update_ear_score()

    def update_mar(self, mar_value):
        """MAR 값 업데이트 및 하품 추적"""
        self.current_mar = mar_value
        current_time = time.time()

        if mar_value > config.MAR_THRESHOLD:
            if not self.is_yawning:
                self.is_yawning = True
                self.yawn_timestamps.append(current_time)
        else:
            self.is_yawning = False

        # 슬라이딩 윈도우: 3분 이전 하품 제거
        while (self.yawn_timestamps and
               current_time - self.yawn_timestamps[0] > config.YAWN_WINDOW_SECONDS):
            self.yawn_timestamps.popleft()

        self._update_mar_score()

    def _update_ear_score(self):
        """EAR 기반 졸음 점수 산출 (0~100)"""
        if not self.eye_closed:
            # 눈이 떠져 있을 때 - EAR 값에 따라 경미한 점수
            if self.current_ear < 0.25:
                self.ear_score = 20  # 눈이 약간 감긴 상태
            else:
                self.ear_score = 0
            return

        # 눈 감김 지속 시간에 따른 점수
        if self.eye_close_duration < 0.5:
            self.ear_score = 20
        elif self.eye_close_duration < 1.0:
            self.ear_score = 40
        elif self.eye_close_duration < config.EAR_CONSEC_SECONDS:
            self.ear_score = 60
        elif self.eye_close_duration < 3.0:
            self.ear_score = 80
        else:
            self.ear_score = 100

    def _update_mar_score(self):
        """MAR 기반 졸음 점수 산출 (0~100)"""
        yawn_count = len(self.yawn_timestamps)

        if yawn_count == 0:
            self.mar_score = 0
        elif yawn_count < 2:
            self.mar_score = 20
        elif yawn_count < config.YAWN_COUNT_THRESHOLD:
            self.mar_score = 40
        elif yawn_count < 5:
            self.mar_score = 70
        else:
            self.mar_score = 100

        # 현재 하품 중이면 추가 점수
        if self.is_yawning:
            self.mar_score = min(100, self.mar_score + 20)

    def get_ear_score(self):
        """현재 EAR 점수 반환 (0~100)"""
        return self.ear_score

    def get_mar_score(self):
        """현재 MAR 점수 반환 (0~100)"""
        return self.mar_score

    def get_yawn_count(self):
        """3분 내 하품 횟수"""
        return len(self.yawn_timestamps)

    def is_drowsy_by_ear(self):
        """EAR 기준 졸음 판정 (2초 이상 연속 눈 감김)"""
        return self.eye_closed and self.eye_close_duration >= config.EAR_CONSEC_SECONDS

    def is_drowsy_by_mar(self):
        """MAR 기준 졸음 전조 (3분 내 3회 이상 하품)"""
        return len(self.yawn_timestamps) >= config.YAWN_COUNT_THRESHOLD
