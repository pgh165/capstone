"""
종합 졸음 판단 모듈

EAR, MAR, Head Pose, 환경 점수를 가중 합산하여
최종 졸음 점수와 경고 단계를 산출한다.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class DrowsinessJudge:
    """영상 분석 결과와 환경 데이터를 종합하여 졸음 점수를 판단하는 클래스."""

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

    # ──────────────────────────────────────────────────────────────
    #  환경 점수 산출
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
        """CO2 농도를 점수로 변환한다.

        400~800ppm -> 0, 800~1000 -> 30, 1000~1500 -> 60, 1500+ -> 100
        """
        if co2 is None or co2 < 0:
            return 0
        if co2 <= 800:
            return 0
        elif co2 <= 1000:
            return 30
        elif co2 <= 1500:
            return 60
        else:
            return 100

    @staticmethod
    def _score_temperature(temp):
        """온도를 점수로 변환한다.

        18~24C -> 0, 24~26 -> 40, 26~28 -> 70, 28+ -> 100
        """
        if temp is None:
            return 0
        if temp <= 24:
            return 0
        elif temp <= 26:
            return 40
        elif temp <= 28:
            return 70
        else:
            return 100

    @staticmethod
    def _score_humidity(humidity):
        """습도를 점수로 변환한다.

        40~60%RH -> 0, 60~70 -> 40, 70+ -> 80
        """
        if humidity is None:
            return 0
        if humidity <= 60:
            return 0
        elif humidity <= 70:
            return 40
        else:
            return 80

    # ──────────────────────────────────────────────────────────────
    #  종합 졸음 점수 산출
    # ──────────────────────────────────────────────────────────────
    def calculate_drowsiness_score(self, ear_score, mar_score, head_score, env_score):
        """각 항목의 점수(0-100)를 가중 합산하여 최종 졸음 점수를 산출한다.

        Args:
            ear_score (float): EAR 기반 눈 감김 점수 (0-100).
            mar_score (float): MAR 기반 하품 점수 (0-100).
            head_score (float): Head Pose 기반 고개 기울기 점수 (0-100).
            env_score (float): 환경 점수 (0-100).

        Returns:
            float: 종합 졸음 점수 (0-100).
        """
        score = (
            self.w_ear * ear_score
            + self.w_mar * mar_score
            + self.w_head * head_score
            + self.w_env * env_score
        )
        return round(min(max(score, 0), 100), 1)

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
