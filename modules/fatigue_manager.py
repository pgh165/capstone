"""
피로도 관리 모듈

연속 작업 시간, 졸음 감지 빈도를 추적하여
누적 피로도를 산출하고 피로 해소 가이드 종류를 추천한다.
선형 보간으로 부드러운 점수 전환을 구현한다.
"""

import sys
import os
import time
from bisect import bisect_right
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


def _lerp_score(value, bp_x, bp_y):
    """구간별 선형 보간으로 점수를 산출한다 (bisect 이진 탐색)."""
    if value <= bp_x[0]:
        return bp_y[0]
    if value >= bp_x[-1]:
        return bp_y[-1]
    i = bisect_right(bp_x, value) - 1
    x0, x1 = bp_x[i], bp_x[i + 1]
    t = (value - x0) / (x1 - x0)
    return bp_y[i] + t * (bp_y[i + 1] - bp_y[i])


class FatigueManager:
    """누적 피로도를 추적하고 관리하는 클래스."""

    # 사전 계산된 breakpoint 상수 (x값, y값 분리 → bisect 이진 탐색용)
    _WORK_BP_X = (0, 30, 60, 90, 120, 150)
    _WORK_BP_Y = (0, 0, 20, 50, 80, 100)

    _FREQ_BP_X = (0, 3, 5, 10, 15, 20, 30, 40)
    _FREQ_BP_Y = (0, 10, 20, 40, 50, 65, 80, 100)

    def __init__(self):
        # 연속 작업 시간 추적
        self._work_start_time = time.time()

        # 최근 30분 졸음 감지 기록 (타임스탬프)
        self._drowsiness_events = deque()
        self._drowsiness_window = 30 * 60  # 30분 (초)
        self._last_drowsy_event_time = 0  # 이벤트 중복 방지 (최소 30초 간격)

        # 피로도 가중치
        self._w_work = config.F1_WORK
        self._w_freq = config.F2_DROWSY

        # 현재 피로도 점수 캐시
        self._fatigue_score = 0.0

        # 자연 회복 추적
        self._last_normal_time = None  # 정상 상태 시작 시각
        self._natural_recovery_interval = 60  # 정상 60초 지속 시 회복 시작
        self._natural_recovery_rate = 2.0  # 초당 감소량 (60초마다 2점)
        self._last_recovery_tick = 0

        # work_score 캐싱 (분 단위로만 변하므로 1초마다 갱신)
        self._work_score_cache = 0.0
        self._work_score_last_update = 0.0

    # ──────────────────────────────────────────────────────────────
    #  메인 업데이트 (매 사이클 호출)
    # ──────────────────────────────────────────────────────────────
    def update(self, drowsiness_score, alert_level):
        """매 감지 사이클마다 호출하여 피로도를 갱신한다.

        Args:
            drowsiness_score (float): 현재 졸음 점수 (0-100).
            alert_level (int): 현재 경고 단계 (0-3).
        """
        now = time.time()

        # 졸음이 감지된 경우 (경고 이상) 이벤트 기록 (최소 30초 간격)
        if alert_level >= 2 and (now - self._last_drowsy_event_time) >= 30.0:
            self._drowsiness_events.append(now)
            self._last_drowsy_event_time = now

        # 30분 윈도우 밖의 오래된 이벤트 제거
        while (
            self._drowsiness_events
            and (now - self._drowsiness_events[0]) > self._drowsiness_window
        ):
            self._drowsiness_events.popleft()

        # 자연 회복 처리 (정상 상태 지속 시 피로도 자연 감소)
        self._update_natural_recovery(alert_level, now)

        # 피로도 점수 계산 (선형 보간)
        work_score = self._calc_work_score(now)
        freq_score = self._calc_freq_score()

        new_score = (
            self._w_work * work_score
            + self._w_freq * freq_score
        )
        new_score = round(min(max(new_score, 0), 100), 1)

        # 피로도는 올라갈 수 있고, 정상 상태에서는 천천히 내려감
        if new_score > self._fatigue_score:
            self._fatigue_score = new_score
        elif self._last_normal_time is not None:
            normal_duration = now - self._last_normal_time
            if normal_duration >= self._natural_recovery_interval:
                if now - self._last_recovery_tick >= self._natural_recovery_interval:
                    self._fatigue_score = max(self._fatigue_score - self._natural_recovery_rate, new_score)
                    self._fatigue_score = round(max(self._fatigue_score, 0), 1)
                    self._last_recovery_tick = now

    # ──────────────────────────────────────────────────────────────
    #  연속 작업 시간 점수 (선형 보간)
    # ──────────────────────────────────────────────────────────────
    def _calc_work_score(self, now):
        """연속 작업 시간(분)에 따른 점수를 반환한다 (1초 캐싱)."""
        if now - self._work_score_last_update >= 1.0:
            work_minutes = (now - self._work_start_time) / 60.0
            self._work_score_cache = _lerp_score(
                work_minutes, self._WORK_BP_X, self._WORK_BP_Y,
            )
            self._work_score_last_update = now
        return self._work_score_cache

    def get_continuous_work_minutes(self):
        """현재 연속 작업 시간을 분 단위로 반환한다."""
        return round((time.time() - self._work_start_time) / 60.0, 1)

    # ──────────────────────────────────────────────────────────────
    #  졸음 빈도 점수 (선형 보간)
    # ──────────────────────────────────────────────────────────────
    def _calc_freq_score(self):
        """최근 30분 졸음 감지 횟수에 따른 점수를 반환한다 (선형 보간)."""
        count = len(self._drowsiness_events)
        return _lerp_score(count, self._FREQ_BP_X, self._FREQ_BP_Y)

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
            self._last_normal_time = None

    def get_drowsy_count_30min(self):
        """최근 30분간 졸음 감지 횟수를 반환한다."""
        return len(self._drowsiness_events)

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

    # 단계별 기본 가이드 + 원인별 추가 가이드
    _GUIDE_MAP = {
        "caution": {
            "base": ["eye_rest", "ventilation"],
            "work": ["posture_correction", "hydration"],
            "drowsy": ["face_wash", "breathing"],
        },
        "warning": {
            "base": ["stretching", "eye_rest", "ventilation"],
            "work": ["walk", "hydration", "posture_correction"],
            "drowsy": ["face_wash", "breathing", "caffeine"],
        },
        "danger": {
            "base": ["rest_break", "stretching", "eye_rest", "ventilation"],
            "work": ["walk", "hydration"],
            "drowsy": ["face_wash", "caffeine", "breathing"],
        },
    }

    def get_dominant_cause(self):
        """피로의 주된 원인을 반환한다.

        Returns:
            str: "work" (연속 작업), "drowsy" (졸음 빈도)
        """
        now = time.time()
        scores = {
            "work": self._calc_work_score(now),
            "drowsy": self._calc_freq_score(),
        }
        return max(scores, key=scores.get)

    def get_recommended_guide(self):
        """피로 단계와 주된 원인에 따른 추천 가이드 유형 리스트를 반환한다.

        Returns:
            list[str]: 추천 가이드 유형 목록.
        """
        level = self.get_fatigue_level()
        if level == "good":
            return []

        dominant = self.get_dominant_cause()
        mapping = self._GUIDE_MAP[level]
        base_guides = list(mapping["base"])
        cause_guides = list(mapping[dominant])

        for g in cause_guides:
            if g not in base_guides:
                base_guides.append(g)
        return base_guides

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
        self.reset_work_timer()
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
        }
