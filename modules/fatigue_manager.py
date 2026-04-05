"""
피로도 관리 모듈

연속 작업 시간, 졸음 감지 빈도, 환경 스트레스를 추적하여
누적 피로도를 산출하고 피로 해소 가이드 종류를 추천한다.
선형 보간으로 부드러운 점수 전환을 구현한다.
"""

import sys
import os
import time
from collections import deque

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


class FatigueManager:
    """누적 피로도를 추적하고 관리하는 클래스."""

    def __init__(self):
        # 연속 작업 시간 추적
        self._work_start_time = time.time()

        # 최근 30분 졸음 감지 기록 (타임스탬프)
        self._drowsiness_events = deque()
        self._drowsiness_window = 30 * 60  # 30분 (초)
        self._last_drowsy_event_time = 0  # 이벤트 중복 방지 (최소 5초 간격)

        # 환경 스트레스 추적 (각 조건이 처음 충족된 시각)
        self._co2_stress_start = None    # CO2 >= 1000ppm 시작 시각
        self._temp_stress_start = None   # 온도 >= 26C 시작 시각
        self._humid_stress_start = None  # 습도 >= 70% 시작 시각

        # 환경 스트레스 지속시간 임계값 (초)
        self._env_stress_duration = config.ENV_STRESS_DURATION  # 10분

        # 피로도 가중치
        self._w_work = config.F1_WORK
        self._w_freq = config.F2_DROWSY
        self._w_env = config.F3_ENV

        # 현재 피로도 점수 캐시
        self._fatigue_score = 0.0

        # 자연 회복 추적
        self._last_normal_time = None  # 정상 상태 시작 시각
        self._natural_recovery_interval = 60  # 정상 60초 지속 시 회복 시작
        self._natural_recovery_rate = 2.0  # 초당 감소량 (60초마다 2점)
        self._last_recovery_tick = 0

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

        # 졸음이 감지된 경우 (주의 이상) 이벤트 기록 (최소 5초 간격)
        if alert_level >= 1 and (now - self._last_drowsy_event_time) >= 5.0:
            self._drowsiness_events.append(now)
            self._last_drowsy_event_time = now

        # 30분 윈도우 밖의 오래된 이벤트 제거
        while (
            self._drowsiness_events
            and (now - self._drowsiness_events[0]) > self._drowsiness_window
        ):
            self._drowsiness_events.popleft()

        # 환경 스트레스 타이머 갱신
        self._update_env_stress(env_data, now)

        # 자연 회복 처리 (정상 상태 지속 시 피로도 자연 감소)
        self._update_natural_recovery(alert_level, now)

        # 피로도 점수 계산 (선형 보간)
        work_score = self._calc_work_score(now)
        freq_score = self._calc_freq_score()
        env_stress_score = self._calc_env_stress_score(now)

        new_score = (
            self._w_work * work_score
            + self._w_freq * freq_score
            + self._w_env * env_stress_score
        )
        new_score = round(min(max(new_score, 0), 100), 1)

        # 피로도는 올라갈 수 있고, 정상 상태에서는 천천히 내려감
        if new_score > self._fatigue_score:
            # 피로 증가: 바로 반영
            self._fatigue_score = new_score
        elif self._last_normal_time is not None:
            # 정상 상태 지속 중: 자연 감소 적용
            normal_duration = now - self._last_normal_time
            if normal_duration >= self._natural_recovery_interval:
                # 60초 이상 정상이면 회복 시작
                if now - self._last_recovery_tick >= self._natural_recovery_interval:
                    self._fatigue_score = max(self._fatigue_score - self._natural_recovery_rate, new_score)
                    self._fatigue_score = round(max(self._fatigue_score, 0), 1)
                    self._last_recovery_tick = now

    # ──────────────────────────────────────────────────────────────
    #  연속 작업 시간 점수 (선형 보간)
    # ──────────────────────────────────────────────────────────────
    def _calc_work_score(self, now):
        """연속 작업 시간(분)에 따른 점수를 반환한다 (선형 보간)."""
        work_minutes = (now - self._work_start_time) / 60.0
        return _lerp_score(work_minutes, [
            (0, 0), (30, 0), (60, 20), (90, 50), (120, 80), (150, 100),
        ])

    def get_continuous_work_minutes(self):
        """현재 연속 작업 시간을 분 단위로 반환한다."""
        return round((time.time() - self._work_start_time) / 60.0, 1)

    # ──────────────────────────────────────────────────────────────
    #  졸음 빈도 점수 (선형 보간)
    # ──────────────────────────────────────────────────────────────
    def _calc_freq_score(self):
        """최근 30분 졸음 감지 횟수에 따른 점수를 반환한다 (선형 보간)."""
        count = len(self._drowsiness_events)
        return _lerp_score(count, [
            (0, 0), (3, 10), (5, 20), (10, 40),
            (15, 50), (20, 65), (30, 80), (40, 100),
        ])

    # ──────────────────────────────────────────────────────────────
    #  자연 회복 (정상 상태 지속 시)
    # ──────────────────────────────────────────────────────────────
    def _update_natural_recovery(self, alert_level, now):
        """정상 상태(alert_level == 0)가 지속되면 자연 회복을 추적한다."""
        if alert_level == 0:
            if self._last_normal_time is None:
                self._last_normal_time = now
                self._last_recovery_tick = now
        else:
            # 졸음 감지되면 자연 회복 타이머 리셋
            self._last_normal_time = None

    def get_drowsy_count_30min(self):
        """최근 30분간 졸음 감지 횟수를 반환한다."""
        return len(self._drowsiness_events)

    # ──────────────────────────────────────────────────────────────
    #  환경 스트레스 점수 (지속시간 비례 선형 보간)
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
        """환경 스트레스 점수를 산출한다 (지속시간 비례 선형 보간, 최대 100).

        임계값 도달 전에도 지속시간에 비례하여 점수가 서서히 오른다.
        """
        score = 0
        threshold = self._env_stress_duration

        # CO2 스트레스 (최대 +50)
        if self._co2_stress_start is not None:
            duration = now - self._co2_stress_start
            score += _lerp_score(duration, [
                (0, 0), (threshold * 0.5, 10), (threshold, 40), (threshold * 2, 50),
            ])

        # 온도 스트레스 (최대 +35)
        if self._temp_stress_start is not None:
            duration = now - self._temp_stress_start
            score += _lerp_score(duration, [
                (0, 0), (threshold * 0.5, 8), (threshold, 30), (threshold * 2, 35),
            ])

        # 습도 스트레스 (최대 +25)
        if self._humid_stress_start is not None:
            duration = now - self._humid_stress_start
            score += _lerp_score(duration, [
                (0, 0), (threshold * 0.5, 5), (threshold, 20), (threshold * 2, 25),
            ])

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
        # 회복 시 작업 타이머도 리셋하여 재충전 효과
        self.reset_work_timer()
        # 졸음 이벤트도 일부 제거 (오래된 것부터)
        remove_count = min(len(self._drowsiness_events), 10)
        for _ in range(remove_count):
            if self._drowsiness_events:
                self._drowsiness_events.popleft()
        print(f"[fatigue] 피로 회복 적용: -{amount}점 → 현재 {self._fatigue_score}점")

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
