"""
피로도 관리 모듈

연속 작업 시간, 졸음 감지 빈도, 환경 스트레스를 추적하여
누적 피로도를 산출하고 피로 해소 가이드 종류를 추천한다.
"""

import sys
import os
import time
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class FatigueManager:
    """누적 피로도를 추적하고 관리하는 클래스."""

    def __init__(self):
        # 연속 작업 시간 추적
        self._work_start_time = time.time()

        # 최근 30분 졸음 감지 기록 (타임스탬프)
        self._drowsiness_events = deque()
        self._drowsiness_window = 30 * 60  # 30분 (초)

        # 환경 스트레스 추적 (각 조건이 처음 충족된 시각)
        self._co2_stress_start = None    # CO2 >= 1000ppm 시작 시각
        self._temp_stress_start = None   # 온도 >= 26C 시작 시각
        self._humid_stress_start = None  # 습도 >= 70% 시작 시각

        # 환경 스트레스 지속 시간 임계값 (초)
        self._env_stress_duration = config.ENV_STRESS_DURATION  # 10분

        # 피로도 가중치
        self._w_work = config.F1_WORK
        self._w_freq = config.F2_DROWSY
        self._w_env = config.F3_ENV

        # 현재 피로도 점수 캐시
        self._fatigue_score = 0.0

    # ──────────────────────────────────────────────────────────────
    #  메인 업데이트 (매 사이클 호출)
    # ──────────────────────────────────────────────────────────────
    def update(self, drowsiness_score, alert_level, env_data):
        """매 감지 사이클마다 호출하여 피로도를 갱신한다.

        Args:
            drowsiness_score (float): 현재 졸음 점수 (0-100).
            alert_level (int): 현재 경고 단계 (0-3).
            env_data (dict): {"co2": int, "temperature": float, "humidity": float}
        """
        now = time.time()

        # 졸음이 감지된 경우 (주의 이상) 이벤트 기록
        if alert_level >= 1:
            self._drowsiness_events.append(now)

        # 30분 윈도우 밖의 오래된 이벤트 제거
        while (
            self._drowsiness_events
            and (now - self._drowsiness_events[0]) > self._drowsiness_window
        ):
            self._drowsiness_events.popleft()

        # 환경 스트레스 타이머 갱신
        self._update_env_stress(env_data, now)

        # 피로도 점수 계산
        work_score = self._calc_work_score(now)
        freq_score = self._calc_freq_score()
        env_stress_score = self._calc_env_stress_score(now)

        self._fatigue_score = (
            self._w_work * work_score
            + self._w_freq * freq_score
            + self._w_env * env_stress_score
        )
        self._fatigue_score = round(min(max(self._fatigue_score, 0), 100), 1)

    # ──────────────────────────────────────────────────────────────
    #  연속 작업 시간 점수
    # ──────────────────────────────────────────────────────────────
    def _calc_work_score(self, now):
        """연속 작업 시간(분)에 따른 점수를 반환한다.

        0-30분 -> 0, 30-60 -> 20, 60-90 -> 50, 90-120 -> 80, 120+ -> 100
        """
        work_minutes = (now - self._work_start_time) / 60.0
        if work_minutes <= 30:
            return 0
        elif work_minutes <= 60:
            return 20
        elif work_minutes <= 90:
            return 50
        elif work_minutes <= 120:
            return 80
        else:
            return 100

    def get_continuous_work_minutes(self):
        """현재 연속 작업 시간을 분 단위로 반환한다."""
        return round((time.time() - self._work_start_time) / 60.0, 1)

    # ──────────────────────────────────────────────────────────────
    #  졸음 빈도 점수
    # ──────────────────────────────────────────────────────────────
    def _calc_freq_score(self):
        """최근 30분 졸음 감지 횟수에 따른 점수를 반환한다.

        0회 -> 0, 1-2 -> 30, 3-5 -> 60, 6+ -> 100
        """
        count = len(self._drowsiness_events)
        if count == 0:
            return 0
        elif count <= 2:
            return 30
        elif count <= 5:
            return 60
        else:
            return 100

    def get_drowsy_count_30min(self):
        """최근 30분간 졸음 감지 횟수를 반환한다."""
        return len(self._drowsiness_events)

    # ──────────────────────────────────────────────────────────────
    #  환경 스트레스 점수
    # ──────────────────────────────────────────────────────────────
    def _update_env_stress(self, env_data, now):
        """환경 데이터를 기반으로 스트레스 타이머를 갱신한다."""
        co2 = env_data.get("co2", 0) or 0
        temp = env_data.get("temperature", 0) or 0
        humidity = env_data.get("humidity", 0) or 0

        # CO2 스트레스 타이머
        if co2 >= config.CO2_WARNING_PPM:
            if self._co2_stress_start is None:
                self._co2_stress_start = now
        else:
            self._co2_stress_start = None

        # 온도 스트레스 타이머
        if temp >= config.TEMP_WARNING_C:
            if self._temp_stress_start is None:
                self._temp_stress_start = now
        else:
            self._temp_stress_start = None

        # 습도 스트레스 타이머
        if humidity >= config.HUMID_WARNING_PCT:
            if self._humid_stress_start is None:
                self._humid_stress_start = now
        else:
            self._humid_stress_start = None

    def _calc_env_stress_score(self, now):
        """환경 스트레스 점수를 산출한다 (합산, 최대 100).

        CO2 >= 1000ppm이 10분 이상 지속 -> +40
        온도 >= 26C가 10분 이상 지속 -> +30
        습도 >= 70%가 10분 이상 지속 -> +20
        """
        score = 0

        if (
            self._co2_stress_start is not None
            and (now - self._co2_stress_start) >= self._env_stress_duration
        ):
            score += 40

        if (
            self._temp_stress_start is not None
            and (now - self._temp_stress_start) >= self._env_stress_duration
        ):
            score += 30

        if (
            self._humid_stress_start is not None
            and (now - self._humid_stress_start) >= self._env_stress_duration
        ):
            score += 20

        return min(score, 100)

    def get_env_stress_score(self):
        """현재 환경 스트레스 점수를 반환한다."""
        return self._calc_env_stress_score(time.time())

    # ──────────────────────────────────────────────────────────────
    #  피로 단계 및 가이드 추천
    # ──────────────────────────────────────────────────────────────
    @property
    def fatigue_score(self):
        """현재 피로도 점수를 반환한다."""
        return self._fatigue_score

    def get_fatigue_level(self):
        """피로도 점수에 따른 피로 단계 문자열을 반환한다.

        Returns:
            str: "good", "caution", "warning", "danger"
        """
        score = self._fatigue_score
        if score <= config.FATIGUE_GOOD_MAX:
            return "good"
        elif score <= config.FATIGUE_CAUTION_MAX:
            return "caution"
        elif score <= config.FATIGUE_WARNING_MAX:
            return "warning"
        else:
            return "danger"

    def get_recommended_guide(self):
        """현재 피로 단계에 따른 추천 가이드 유형 리스트를 반환한다.

        Returns:
            list[str]: 추천 가이드 유형 목록.
              - "caution" -> ["eye_rest", "ventilation"]
              - "warning" -> ["stretching", "breathing", "ventilation"]
              - "danger"  -> ["rest_break", "stretching", "breathing", "ventilation", "eye_rest"]
        """
        level = self.get_fatigue_level()

        if level == "caution":
            return ["eye_rest", "ventilation"]
        elif level == "warning":
            return ["stretching", "breathing", "ventilation"]
        elif level == "danger":
            return ["rest_break", "stretching", "breathing", "ventilation", "eye_rest"]
        else:
            return []

    # ──────────────────────────────────────────────────────────────
    #  피로 회복 및 리셋
    # ──────────────────────────────────────────────────────────────
    def apply_recovery(self, amount=None):
        """피로도 점수를 감소시킨다 (부분 리셋).

        Args:
            amount (int, optional): 감소시킬 점수. 기본값은 config.RECOVERY_REDUCTION (30).
        """
        if amount is None:
            amount = config.RECOVERY_REDUCTION
        self._fatigue_score = max(self._fatigue_score - amount, 0)
        self._fatigue_score = round(self._fatigue_score, 1)

    def reset_work_timer(self):
        """연속 작업 시간 타이머를 리셋한다."""
        self._work_start_time = time.time()

    def get_status(self):
        """피로 관리 상태를 딕셔너리로 반환한다."""
        return {
            "fatigue_score": self._fatigue_score,
            "fatigue_level": self.get_fatigue_level(),
            "continuous_work_min": self.get_continuous_work_minutes(),
            "drowsy_count_30min": self.get_drowsy_count_30min(),
            "env_stress_score": self.get_env_stress_score(),
        }
