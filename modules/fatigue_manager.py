"""
피로도 관리 모듈

연속 작업 시간, 졸음 감지 빈도, 환경 스트레스를 추적하여
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


class RecoverySession:
    """피로 회복 세션을 추적하고 생체 데이터로 효과를 검증한다.

    흐름: recovering(가이드 수행) → evaluating(생체 재측정) → done(결과 산출)
    """

    def __init__(self, guide_types, fatigue_before, drowsiness_before,
                 duration_sec):
        self.guide_types = guide_types
        self.fatigue_before = fatigue_before
        self.drowsiness_before = drowsiness_before
        self.duration_sec = duration_sec
        self.start_time = time.time()

        # 평가 단계 데이터
        self._eval_start_time = None
        self._eval_samples = []

        # recovering → evaluating → done
        self.phase = "recovering"

    def update(self, now, drowsiness_score, ear_value, mar_value):
        """매 프레임 호출. 현재 phase를 반환한다."""
        if self.phase == "recovering":
            if now - self.start_time >= self.duration_sec:
                self.phase = "evaluating"
                self._eval_start_time = now
                print("[recovery] 회복 시간 종료 — 효과 평가를 시작합니다.")
            return self.phase

        if self.phase == "evaluating":
            self._eval_samples.append({
                "drowsiness": drowsiness_score,
                "ear": ear_value,
                "mar": mar_value,
            })
            eval_elapsed = now - self._eval_start_time
            if (eval_elapsed >= config.RECOVERY_EVAL_DURATION
                    and len(self._eval_samples) >= config.RECOVERY_EVAL_MIN_SAMPLES):
                self.phase = "done"
            return self.phase

        return self.phase

    def get_result(self, fatigue_after):
        """회복 효과 평가 결과를 반환한다.

        Returns:
            dict: effective(bool), 각종 before/after 수치, 판정 사유.
        """
        if not self._eval_samples:
            return {
                "effective": False,
                "reason": "평가 데이터 없음",
                "guide_types": self.guide_types,
            }

        n = len(self._eval_samples)
        avg_drowsiness = sum(s["drowsiness"] for s in self._eval_samples) / n
        avg_ear = sum(s["ear"] for s in self._eval_samples) / n
        avg_mar = sum(s["mar"] for s in self._eval_samples) / n

        fatigue_drop = self.fatigue_before - fatigue_after
        drowsiness_drop = self.drowsiness_before - avg_drowsiness

        # 판정: 피로도 10점 이상 하락 OR 평균 졸음 점수 30 이하
        effective = (
            fatigue_drop >= config.RECOVERY_EFFECTIVE_FATIGUE_DROP
            or avg_drowsiness <= config.RECOVERY_EFFECTIVE_DROWSY_MAX
        )

        reasons = []
        if fatigue_drop >= config.RECOVERY_EFFECTIVE_FATIGUE_DROP:
            reasons.append(f"피로도 {fatigue_drop:.1f}점 감소")
        if avg_drowsiness <= config.RECOVERY_EFFECTIVE_DROWSY_MAX:
            reasons.append(f"졸음 점수 {avg_drowsiness:.1f}점으로 정상 범위")
        if not reasons:
            reasons.append(
                f"피로도 {fatigue_drop:.1f}점 변화, "
                f"졸음 점수 {avg_drowsiness:.1f}점으로 기준 미달"
            )

        return {
            "effective": effective,
            "reason": " / ".join(reasons),
            "guide_types": self.guide_types,
            "duration_sec": self.duration_sec,
            "fatigue_before": round(self.fatigue_before, 1),
            "fatigue_after": round(fatigue_after, 1),
            "fatigue_drop": round(fatigue_drop, 1),
            "drowsiness_before": round(self.drowsiness_before, 1),
            "drowsiness_after": round(avg_drowsiness, 1),
            "drowsiness_drop": round(drowsiness_drop, 1),
            "avg_ear": round(avg_ear, 4),
            "avg_mar": round(avg_mar, 4),
            "eval_samples": n,
        }


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
        self._last_drowsy_event_time = 0  # 이벤트 중복 방지 (최소 5초 간격)

        # 환경 스트레스 추적 (각 조건이 처음 충족된 시각)
        self._co2_stress_start = None    # CO2 >= 1000ppm 시작 시각
        self._temp_stress_start = None   # 온도 >= 26C 시작 시각
        self._humid_stress_start = None  # 습도 >= 70% 시작 시각

        # 환경 스트레스 지속시간 임계값 (초)
        th = config.ENV_STRESS_DURATION  # 10분
        self._env_stress_duration = th

        # 환경 스트레스 breakpoint 사전 계산 (threshold 곱셈 제거)
        th_half = th * 0.5
        th_double = th * 2.0
        self._co2_bp_x = (0, th_half, th, th_double)
        self._co2_bp_y = (0, 10, 40, 50)
        self._temp_bp_x = (0, th_half, th, th_double)
        self._temp_bp_y = (0, 8, 30, 35)
        self._humid_bp_x = (0, th_half, th, th_double)
        self._humid_bp_y = (0, 5, 20, 25)

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

        # work_score 캐싱 (분 단위로만 변하므로 1초마다 갱신)
        self._work_score_cache = 0.0
        self._work_score_last_update = 0.0

        # 회복 세션
        self._recovery_session = None

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

        # CO2 스트레스 (최대 +50)
        if self._co2_stress_start is not None:
            score += _lerp_score(
                now - self._co2_stress_start, self._co2_bp_x, self._co2_bp_y,
            )

        # 온도 스트레스 (최대 +35)
        if self._temp_stress_start is not None:
            score += _lerp_score(
                now - self._temp_stress_start, self._temp_bp_x, self._temp_bp_y,
            )

        # 습도 스트레스 (최대 +25)
        if self._humid_stress_start is not None:
            score += _lerp_score(
                now - self._humid_stress_start, self._humid_bp_x, self._humid_bp_y,
            )

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

    # 단계별 기본 가이드 + 원인별 추가 가이드
    _GUIDE_MAP = {
        "caution": {
            "base": ["eye_rest"],
            "work": ["posture_correction", "hydration"],
            "drowsy": ["face_wash", "breathing"],
            "env": ["ventilation"],
        },
        "warning": {
            "base": ["stretching", "eye_rest"],
            "work": ["walk", "hydration", "posture_correction"],
            "drowsy": ["face_wash", "breathing", "caffeine"],
            "env": ["ventilation", "breathing"],
        },
        "danger": {
            "base": ["rest_break", "stretching", "eye_rest"],
            "work": ["walk", "hydration"],
            "drowsy": ["face_wash", "caffeine", "breathing"],
            "env": ["ventilation", "walk"],
        },
    }

    def get_dominant_cause(self):
        """피로의 주된 원인을 반환한다.

        Returns:
            str: "work" (연속 작업), "drowsy" (졸음 빈도), "env" (환경 스트레스)
        """
        now = time.time()
        scores = {
            "work": self._calc_work_score(now),
            "drowsy": self._calc_freq_score(),
            "env": self._calc_env_stress_score(now),
        }
        return max(scores, key=scores.get)

    def get_recommended_guide(self):
        """피로 단계와 주된 원인에 따른 추천 가이드 유형 리스트를 반환한다.

        피로의 주된 원인(연속 작업/졸음 빈도/환경 스트레스)을 분석하여
        단계별 기본 가이드에 원인별 맞춤 가이드를 추가한다.

        Returns:
            list[str]: 추천 가이드 유형 목록.
        """
        level = self.get_fatigue_level()
        if level == "good":
            return []

        dominant = self.get_dominant_cause()
        mapping = self._GUIDE_MAP[level]

        guides = list(mapping["base"])
        for g in mapping[dominant]:
            if g not in guides:
                guides.append(g)
        return guides

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

    # ──────────────────────────────────────────────────────────────
    #  회복 세션 관리 (생체 데이터 기반 효과 검증)
    # ──────────────────────────────────────────────────────────────
    @property
    def has_active_recovery(self):
        """진행 중인 회복 세션이 있는지 반환한다."""
        return self._recovery_session is not None

    def start_recovery_session(self, guide_types, drowsiness_score,
                               duration_sec):
        """회복 세션을 시작한다.

        Args:
            guide_types (list[str]): 제공된 가이드 유형 목록.
            drowsiness_score (float): 세션 시작 시점의 졸음 점수.
            duration_sec (int): 회복 가이드 수행 시간 (초).
        """
        self._recovery_session = RecoverySession(
            guide_types=guide_types,
            fatigue_before=self._fatigue_score,
            drowsiness_before=drowsiness_score,
            duration_sec=duration_sec,
        )
        print(
            f"[recovery] 회복 세션 시작 "
            f"(피로도={self._fatigue_score}, "
            f"가이드={guide_types}, "
            f"소요={duration_sec}초)"
        )

    def update_recovery_session(self, drowsiness_score, ear_value, mar_value):
        """회복 세션 상태를 갱신한다. 매 프레임 호출.

        Returns:
            dict or None:
              - 진행 중: {"phase": "recovering"} 또는 {"phase": "evaluating"}
              - 완료: 효과 검증 결과 딕셔너리 (effective, reason, before/after 등)
              - 세션 없음: None
        """
        if self._recovery_session is None:
            return None

        now = time.time()
        phase = self._recovery_session.update(
            now, drowsiness_score, ear_value, mar_value,
        )

        if phase != "done":
            return {"phase": phase}

        # 평가 완료 — 결과 산출
        result = self._recovery_session.get_result(self._fatigue_score)

        if result["effective"]:
            self.apply_recovery()
            print(f"[recovery] 회복 효과 확인: {result['reason']}")
        else:
            print(f"[recovery] 회복 부족: {result['reason']}")

        self._recovery_session = None
        return result

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
