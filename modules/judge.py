"""
종합 졸음 판단 모듈

EAR, MAR, Head Pose, 환경 점수를 가중 합산하여
최종 졸음 점수와 경고 단계를 산출한다.
EMA(지수이동평균) 스무딩으로 점수 플리커링을 방지한다.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
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


class DrowsinessJudge:
    """영상 분석 결과와 환경 데이터를 종합하여 졸음 점수를 판단하는 클래스."""

    # EMA 스무딩 계수 (0에 가까울수록 부드러움, 1이면 스무딩 없음)
    _EMA_ALPHA = 0.3

    def __init__(self):
        # 환경 점수 가중치
        self.w_co2 = config.E1_CO2
        self.w_temp = config.E2_TEMP
        self.w_humidity = config.E3_HUMID

        # 졸음 점수 가중치
        self.w_ear = config.W1_EAR
        self.w_mar = config.W2_MAR
        self.w_head = config.W3_HEAD
        self.w_env = config.W4_ENV

        # EMA 스무딩 상태
        self._ema_score = None

    # ──────────────────────────────────────────────────────────────
    #  환경 점수 산출 (선형 보간)
    # ──────────────────────────────────────────────────────────────
    def calculate_env_score(self, co2, temperature, humidity):
        """CO2, 온도, 습도로부터 환경 점수(0-100)를 산출한다.

        Args:
            co2 (int): CO2 농도 (ppm).
            temperature (float): 온도 (C).
            humidity (float): 습도 (%RH).

        Returns:
            float: 환경 점수 (0-100).
        """
        co2_score = self._score_co2(co2)
        temp_score = self._score_temperature(temperature)
        humidity_score = self._score_humidity(humidity)

        env_score = (
            self.w_co2 * co2_score
            + self.w_temp * temp_score
            + self.w_humidity * humidity_score
        )
        return round(min(max(env_score, 0), 100), 1)

    @staticmethod
    def _score_co2(co2):
        """CO2 농도를 점수로 변환한다 (선형 보간)."""
        if co2 is None or co2 < 0:
            return 0
        return _lerp_score(co2, [
            (0, 0), (800, 0), (1000, 30), (1500, 60), (2000, 100),
        ])

    @staticmethod
    def _score_temperature(temp):
        """온도를 점수로 변환한다 (선형 보간)."""
        if temp is None:
            return 0
        return _lerp_score(temp, [
            (18, 0), (24, 0), (26, 40), (28, 70), (30, 100),
        ])

    @staticmethod
    def _score_humidity(humidity):
        """습도를 점수로 변환한다 (선형 보간)."""
        if humidity is None:
            return 0
        return _lerp_score(humidity, [
            (40, 0), (60, 0), (70, 40), (80, 80), (90, 100),
        ])

    # ──────────────────────────────────────────────────────────────
    #  종합 졸음 점수 산출 (EMA 스무딩 적용)
    # ──────────────────────────────────────────────────────────────
    def calculate_drowsiness_score(self, ear_score, mar_score, head_score, env_score):
        """각 항목의 점수(0-100)를 가중 합산 후 EMA 스무딩하여 최종 점수를 산출한다.

        Args:
            ear_score (float): EAR 기반 눈 감김 점수 (0-100).
            mar_score (float): MAR 기반 하품 점수 (0-100).
            head_score (float): Head Pose 기반 고개 기울기 점수 (0-100).
            env_score (float): 환경 점수 (0-100).

        Returns:
            float: 종합 졸음 점수 (0-100), EMA 스무딩 적용.
        """
        raw_score = (
            self.w_ear * ear_score
            + self.w_mar * mar_score
            + self.w_head * head_score
            + self.w_env * env_score
        )
        raw_score = min(max(raw_score, 0), 100)

        # EMA 스무딩: 급격한 점수 변동 완화
        if self._ema_score is None:
            self._ema_score = raw_score
        else:
            self._ema_score = (
                self._EMA_ALPHA * raw_score
                + (1 - self._EMA_ALPHA) * self._ema_score
            )

        return round(self._ema_score, 1)

    # ──────────────────────────────────────────────────────────────
    #  경고 단계 판정
    # ──────────────────────────────────────────────────────────────
    def get_alert_level(self, score):
        """졸음 점수에 따른 경고 단계를 반환한다.

        Args:
            score (float): 종합 졸음 점수 (0-100).

        Returns:
            int: 0(정상), 1(주의), 2(경고), 3(위험).
        """
        if score <= config.ALERT_LEVEL_0_MAX:
            return 0  # 정상
        elif score <= config.ALERT_LEVEL_1_MAX:
            return 1  # 주의
        elif score <= config.ALERT_LEVEL_2_MAX:
            return 2  # 경고
        else:
            return 3  # 위험

    @staticmethod
    def get_alert_label(level):
        """경고 단계 숫자를 한글 라벨로 변환한다."""
        labels = {0: "정상", 1: "주의", 2: "경고", 3: "위험"}
        return labels.get(level, "알 수 없음")
