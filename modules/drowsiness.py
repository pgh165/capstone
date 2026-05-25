"""
졸음 감지 모듈
- EAR (Eye Aspect Ratio) 계산
- MAR (Mouth Aspect Ratio) 계산
- PERCLOS (눈 감김 비율) 추적
- 졸음 상태 추적
"""

import time
import math
from collections import deque
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _lerp_score(value, breakpoints):
    """구간별 선형 보간으로 점수를 산출한다.

    Args:
        value: 입력값.
        breakpoints: [(입력값, 출력점수), ...] 오름차순 정렬된 튜플 리스트.

    Returns:
        float: 보간된 점수.
    """
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


def _dist2d(a, b):
    """2D 유클리드 거리 (np.linalg.norm 대비 경량화)."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


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
    vertical_1 = _dist2d(p2, p6)
    vertical_2 = _dist2d(p3, p5)

    # 가로 거리
    horizontal = _dist2d(p1, p4)

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
    vertical_1 = _dist2d(mouth_landmarks[1], mouth_landmarks[9])   # 37-84
    vertical_2 = _dist2d(mouth_landmarks[2], mouth_landmarks[8])   # 0-17
    vertical_3 = _dist2d(mouth_landmarks[3], mouth_landmarks[7])   # 267-314

    # 가로 거리 (입의 좌우 폭)
    horizontal = _dist2d(mouth_landmarks[0], mouth_landmarks[5])   # 61-291

    if horizontal == 0:
        return 0.0

    mar = (vertical_1 + vertical_2 + vertical_3) / (2.0 * horizontal)
    return mar


class DrowsinessTracker:
    """졸음 상태 추적 클래스"""

    # PERCLOS 점수 보간 구간: (60초 눈 감김 비율 %, 점수)
    # 정상 깜빡임(~6%) 오탐 방지를 위해 10% 이하는 0점
    _PERCLOS_BREAKPOINTS = [
        (0, 0), (10, 0), (20, 20), (30, 45),
        (45, 70), (55, 85), (65, 100),
    ]

    # MAR 점수 보간 구간: (하품 횟수, 점수)
    _MAR_BREAKPOINTS = [
        (0, 0), (1, 5), (2, 20), (3, 40), (5, 70), (7, 100),
    ]

    # PERCLOS 윈도우 (초)
    _PERCLOS_WINDOW = 60.0
    # PERCLOS 최소 유효 윈도우: 이 시간 미만이면 데이터 부족으로 0점 처리
    _PERCLOS_MIN_WINDOW = 20.0

    def __init__(self):
        # 개인 임계값 (캘리브레이션 후 set_thresholds()로 갱신)
        self._ear_threshold = config.EAR_THRESHOLD
        self._mar_threshold = config.MAR_THRESHOLD

        # 눈 감김 추적
        self.eye_closed = False
        self.eye_close_start = None
        self.eye_close_duration = 0.0
        self.current_ear = 0.0

        # 하품 추적 (슬라이딩 윈도우)
        self.yawn_timestamps = deque()
        self.is_yawning = False
        self.current_mar = 0.0
        self._mar_above_start = None   # MAR 임계값 초과 시작 시각
        self._YAWN_MIN_SEC = 0.8       # 하품으로 인정되는 최소 지속시간 (초)

        # PERCLOS 추적 (60초 윈도우 내 눈 감김 비율)
        self._eye_states = deque()  # (timestamp, is_closed)

        # 점수
        self.ear_score = 0
        self.mar_score = 0
        self.perclos = 0.0

    def set_thresholds(self, ear_threshold: float, mar_threshold: float):
        """캘리브레이션 결과로 개인 임계값을 갱신한다."""
        self._ear_threshold = ear_threshold
        self._mar_threshold = mar_threshold
        print(
            f"[drowsiness] 개인 임계값 적용 — "
            f"EAR: {ear_threshold:.3f}, MAR: {mar_threshold:.3f}"
        )

    def update_ear(self, ear_value):
        """EAR 값 업데이트 및 눈 감김 추적"""
        self.current_ear = ear_value
        now = time.time()
        is_closed = ear_value < self._ear_threshold

        # PERCLOS 기록 및 윈도우 관리
        self._eye_states.append((now, is_closed))
        while self._eye_states and (now - self._eye_states[0][0]) > self._PERCLOS_WINDOW:
            self._eye_states.popleft()

        # PERCLOS 계산 (윈도우 내 눈 감김 시간 비율)
        # 최소 10초 이상 데이터가 쌓여야 의미 있는 값으로 인정
        if len(self._eye_states) >= 2:
            closed_time = 0.0
            for i in range(1, len(self._eye_states)):
                if self._eye_states[i][1]:
                    closed_time += self._eye_states[i][0] - self._eye_states[i - 1][0]
            total_time = self._eye_states[-1][0] - self._eye_states[0][0]
            if total_time >= self._PERCLOS_MIN_WINDOW:
                self.perclos = closed_time / total_time * 100.0
            else:
                self.perclos = 0.0
        else:
            self.perclos = 0.0

        # 눈 감김 지속시간 추적
        if is_closed:
            if not self.eye_closed:
                self.eye_closed = True
                self.eye_close_start = now
            self.eye_close_duration = now - self.eye_close_start
        else:
            self.eye_closed = False
            self.eye_close_start = None
            self.eye_close_duration = 0.0

        self._update_ear_score()

    def update_mar(self, mar_value):
        """MAR 값 업데이트 및 하품 추적"""
        self.current_mar = mar_value
        current_time = time.time()

        if mar_value > self._mar_threshold:
            if self._mar_above_start is None:
                self._mar_above_start = current_time
            duration = current_time - self._mar_above_start
            if duration >= self._YAWN_MIN_SEC and not self.is_yawning:
                # 0.8초 이상 지속된 경우에만 하품으로 카운트
                self.is_yawning = True
                self.yawn_timestamps.append(current_time)
        else:
            self._mar_above_start = None
            self.is_yawning = False

        # 슬라이딩 윈도우: 3분 이전 하품 제거
        while (self.yawn_timestamps and
               current_time - self.yawn_timestamps[0] > config.YAWN_WINDOW_SECONDS):
            self.yawn_timestamps.popleft()

        self._update_mar_score()

    def _update_ear_score(self):
        """PERCLOS 기반 졸음 점수 산출 (최근 60초 눈 감김 비율)"""
        self.ear_score = _lerp_score(self.perclos, self._PERCLOS_BREAKPOINTS)

    def _update_mar_score(self):
        """MAR 기반 졸음 점수 산출 (연속 보간)"""
        yawn_count = len(self.yawn_timestamps)
        self.mar_score = _lerp_score(yawn_count, self._MAR_BREAKPOINTS)

        # 현재 하품 중이면 추가 점수
        if self.is_yawning:
            self.mar_score = min(100, self.mar_score + 20)

    def get_ear_score(self):
        """현재 EAR 점수 반환 (0~100)"""
        return self.ear_score

    def get_mar_score(self):
        """현재 MAR 점수 반환 (0~100)"""
        return self.mar_score

    def get_perclos(self):
        """최근 60초간 PERCLOS 값 (%) 반환"""
        return round(self.perclos, 1)

    def get_ear_closed_seconds(self):
        """현재 연속 눈 감김 지속 시간(초)"""
        return round(self.eye_close_duration, 2)

    def get_yawn_count(self):
        """3분 내 하품 횟수"""
        return len(self.yawn_timestamps)

    def is_drowsy_by_ear(self):
        """EAR 기준 졸음 판정 (2초 이상 연속 눈 감김)"""
        return self.eye_closed and self.eye_close_duration >= config.EAR_CONSEC_SECONDS

    def get_thresholds(self) -> dict:
        """현재 적용 중인 임계값을 반환한다."""
        return {"ear": self._ear_threshold, "mar": self._mar_threshold}

    def is_drowsy_by_mar(self):
        """MAR 기준 졸음 전조 (3분 내 3회 이상 하품)"""
        return len(self.yawn_timestamps) >= config.YAWN_COUNT_THRESHOLD
