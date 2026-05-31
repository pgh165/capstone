"""
종합 졸음 판단 모듈

EAR, MAR, Head Pose 점수를 가중 합산하여
최종 졸음 점수와 경고 단계를 산출한다.
EMA(지수이동평균) 스무딩으로 점수 플리커링을 방지한다.
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class DrowsinessJudge:
    """영상 분석 결과를 종합하여 졸음 점수를 판단하는 클래스."""

    # EMA 스무딩 계수 (0에 가까울수록 부드러움, 1이면 스무딩 없음)
    _EMA_ALPHA = 0.25

    # 지속 고개 떨굼 감지 임계값
    _HEAD_DROOP_THRESHOLD = 60   # head_score 이 이상이면 "떨굼 중"으로 판정
    _HEAD_DROOP_ONSET_SEC = 5    # 이 시간 이후부터 보너스 시작
    _HEAD_DROOP_BONUS_PER_SEC = 2.5  # 초당 추가 raw 점수
    _HEAD_DROOP_BONUS_MAX = 45   # 보너스 상한

    def __init__(self):
        self.w_ear = config.W1_EAR
        self.w_mar = config.W2_MAR
        self.w_head = config.W3_HEAD
        self._ema_score = None
        self._head_droop_start: float | None = None  # 고개 떨굼 시작 시각

    def calculate_drowsiness_score(self, ear_score, mar_score, head_score):
        """각 항목의 점수(0-100)를 가중 합산 후 EMA 스무딩하여 최종 점수를 산출한다.

        Args:
            ear_score (float): EAR 기반 눈 감김 점수 (0-100).
            mar_score (float): MAR 기반 하품 점수 (0-100).
            head_score (float): Head Pose 기반 고개 기울기 점수 (0-100).

        Returns:
            float: 종합 졸음 점수 (0-100), EMA 스무딩 적용.
        """
        raw_score = (
            self.w_ear * ear_score
            + self.w_mar * mar_score
            + self.w_head * head_score
        )

        # 지속 고개 떨굼 보너스: HEAD_DROOP_THRESHOLD 이상이 지속될수록 점수 증가
        now = time.time()
        if head_score >= self._HEAD_DROOP_THRESHOLD:
            if self._head_droop_start is None:
                self._head_droop_start = now
            droop_duration = now - self._head_droop_start
            if droop_duration > self._HEAD_DROOP_ONSET_SEC:
                bonus = min(
                    self._HEAD_DROOP_BONUS_MAX,
                    (droop_duration - self._HEAD_DROOP_ONSET_SEC) * self._HEAD_DROOP_BONUS_PER_SEC,
                )
                raw_score = min(100, raw_score + bonus)
        else:
            self._head_droop_start = None

        raw_score = min(max(raw_score, 0), 100)

        # 1.5승 변환: 제곱보다 이른 주의 감지, 선형보다 오경보 억제 (x^1.5 / 10)
        raw_score = (raw_score ** 1.5) / 10

        if self._ema_score is None:
            self._ema_score = raw_score
        else:
            self._ema_score = (
                self._EMA_ALPHA * raw_score
                + (1 - self._EMA_ALPHA) * self._ema_score
            )

        return round(self._ema_score, 1)

    def get_alert_level(self, score):
        """졸음 점수에 따른 경고 단계를 반환한다.

        Returns:
            int: 0(정상), 1(주의), 2(경고), 3(위험).
        """
        if score <= config.ALERT_LEVEL_0_MAX:
            return 0
        elif score <= config.ALERT_LEVEL_1_MAX:
            return 1
        elif score <= config.ALERT_LEVEL_2_MAX:
            return 2
        else:
            return 3

    @staticmethod
    def get_alert_label(level):
        """경고 단계 숫자를 한글 라벨로 변환한다."""
        labels = {0: "정상", 1: "주의", 2: "경고", 3: "위험"}
        return labels.get(level, "알 수 없음")
