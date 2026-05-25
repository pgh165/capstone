"""
AI 개인 맞춤형 포모도로 타이머

현재 피로도·졸음 점수를 기반으로 작업 인터벌과 휴식 시간을 동적으로 조정한다.
- 피로·졸음이 낮으면 인터벌 연장 (최대 40분)
- 피로·졸음이 높으면 인터벌 단축 (최소 10분)
- 위험 수준 감지 시 즉시 휴식 전환
- 4사이클마다 긴 휴식 (15분)
"""

import time
import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class PomodoroTimer:
    """AI 기반 동적 포모도로 타이머."""

    IDLE    = "idle"
    WORKING = "working"
    BREAK   = "break"

    # 긴 휴식 트리거: N사이클 완료마다
    _LONG_BREAK_CYCLE = config.POMODORO_LONG_BREAK_CYCLE

    # 비상 중단 연속 발생 방지 쿨다운 (초)
    _EMERGENCY_COOLDOWN = 120

    def __init__(self):
        self.state = self.IDLE
        self.cycle = 0                  # 완료된 사이클 수

        self._work_start  = None
        self._break_start = None
        self._planned_work_sec  = config.POMODORO_BASE_WORK_MIN * 60
        self._planned_break_sec = config.POMODORO_BASE_BREAK_MIN * 60

        self._last_emergency = 0.0

        # 개인화 학습 데이터
        self._personal_base_min = None     # Step 4: DB 학습 기반 개인 기준 인터벌
        self._hourly_pattern = {}          # Step 3: {hour: avg_fatigue}

    # ──────────────────────────────────────────────────────────────
    #  공개 API
    # ──────────────────────────────────────────────────────────────
    def start(self, fatigue_score: float = 0, drowsiness_score: float = 0) -> dict:
        """작업 상태로 진입한다. 다음 인터벌을 AI 점수로 계산한다.

        Returns:
            dict: {"event": "work_start", "planned_min": int, "cycle": int}
        """
        work_min = self._calc_work_interval(fatigue_score, drowsiness_score)
        self._planned_work_sec = work_min * 60
        self._work_start = time.time()
        self.state = self.WORKING

        print(
            f"[pomodoro] 🍅 작업 시작 — {work_min}분 "
            f"(피로={fatigue_score:.0f}, 졸음={drowsiness_score:.0f}, "
            f"사이클={self.cycle + 1})"
        )
        return {"event": "work_start", "planned_min": work_min, "cycle": self.cycle + 1}

    def update(self, fatigue_score: float, drowsiness_score: float,
               alert_level: int) -> dict | None:
        """작업 중 매 프레임 호출. 휴식이 필요하면 이벤트를 반환한다.

        Returns:
            dict | None:
                {"event": "break_needed", "reason": str, "forced": bool}
        """
        if self.state != self.WORKING:
            return None

        now = time.time()
        elapsed = now - self._work_start

        # 비상 중단: 위험 경보 (alert_level == 3)
        if alert_level >= 3:
            if now - self._last_emergency >= self._EMERGENCY_COOLDOWN:
                self._last_emergency = now
                print("[pomodoro] ⚠️ 위험 수준 감지 — 즉시 휴식 전환")
                return {"event": "break_needed", "reason": "emergency", "forced": True}

        # 계획된 작업 시간 완료
        if elapsed >= self._planned_work_sec:
            print(f"[pomodoro] ✅ 작업 완료 ({elapsed / 60:.1f}분 경과)")
            return {"event": "break_needed", "reason": "interval_done", "forced": False}

        return None

    def start_break(self, fatigue_level: str, fatigue_score: float,
                    drowsiness_score: float) -> dict:
        """휴식 상태로 전환한다.

        Returns:
            dict: {"event": "break_start", "break_min": int, "cycle": int, ...}
        """
        break_min = self._calc_break_duration(fatigue_level, self.cycle)
        self._planned_break_sec = break_min * 60
        self._break_start = time.time()
        self.state = self.BREAK

        work_elapsed = (self._break_start - self._work_start) if self._work_start else 0

        print(
            f"[pomodoro] 💤 휴식 시작 — {break_min}분 "
            f"(피로={fatigue_level}, 사이클={self.cycle + 1})"
        )
        return {
            "event": "break_start",
            "break_min": break_min,
            "fatigue_level": fatigue_level,
            "work_elapsed_min": round(work_elapsed / 60, 1),
            "cycle": self.cycle + 1,
        }

    def update_break(self) -> dict | None:
        """휴식 중 매 프레임 호출. 완료 시 이벤트를 반환한다.

        Returns:
            dict | None: {"event": "break_done", "cycle": int}
        """
        if self.state != self.BREAK:
            return None

        elapsed = time.time() - self._break_start
        if elapsed >= self._planned_break_sec:
            self.cycle += 1
            print(f"[pomodoro] 🔔 휴식 완료 — {self.cycle}번째 사이클 종료")
            return {"event": "break_done", "cycle": self.cycle}

        return None

    def get_status(self) -> dict:
        """현재 타이머 상태 딕셔너리를 반환한다."""
        now = time.time()
        if self.state == self.WORKING and self._work_start:
            elapsed   = now - self._work_start
            remaining = max(0.0, self._planned_work_sec - elapsed)
            return {
                "state":         self.WORKING,
                "cycle":         self.cycle + 1,
                "elapsed_min":   round(elapsed / 60, 1),
                "remaining_min": round(remaining / 60, 1),
                "planned_min":   round(self._planned_work_sec / 60),
            }
        if self.state == self.BREAK and self._break_start:
            elapsed   = now - self._break_start
            remaining = max(0.0, self._planned_break_sec - elapsed)
            return {
                "state":         self.BREAK,
                "cycle":         self.cycle + 1,
                "elapsed_min":   round(elapsed / 60, 1),
                "remaining_min": round(remaining / 60, 1),
                "planned_min":   round(self._planned_break_sec / 60),
            }
        return {"state": self.IDLE, "cycle": self.cycle}

    def set_hourly_pattern(self, pattern: dict):
        """시간대별 평균 피로도 패턴을 설정한다.

        Args:
            pattern: {hour(int): avg_fatigue(float), ...}
        """
        self._hourly_pattern = pattern
        print(f"[pomodoro] 시간대별 피로 패턴 로드 ({len(pattern)}개 시간대)")

    def set_personal_base_min(self, minutes: int):
        """DB 학습 기반 개인 최적 작업 인터벌 기준을 설정한다."""
        clamped = max(config.POMODORO_MIN_WORK_MIN,
                      min(config.POMODORO_MAX_WORK_MIN, minutes))
        self._personal_base_min = clamped
        print(
            f"[pomodoro] 개인 최적 작업 시간 설정: {clamped}분 "
            f"(학습된 원본: {minutes}분)"
        )

    # ──────────────────────────────────────────────────────────────
    #  동적 계산 (AI 판단 기반)
    # ──────────────────────────────────────────────────────────────
    def _calc_work_interval(self, fatigue_score: float,
                            drowsiness_score: float) -> int:
        """피로도·졸음 점수로 다음 작업 인터벌(분)을 계산한다.

        피로/졸음이 낮을수록 인터벌 연장, 높을수록 단축.
        """
        # Step 4: 개인 학습 기준값 우선, 없으면 config 기본값
        base = self._personal_base_min if self._personal_base_min is not None \
               else config.POMODORO_BASE_WORK_MIN

        # 피로도 보정
        if fatigue_score <= 30:
            fatigue_adj = +10
        elif fatigue_score <= 50:
            fatigue_adj = +5
        elif fatigue_score <= 75:
            fatigue_adj = 0
        elif fatigue_score <= 88:
            fatigue_adj = -8
        else:
            fatigue_adj = -15

        # 졸음 점수 보정
        if drowsiness_score <= 20:
            drowsy_adj = +5
        elif drowsiness_score <= 40:
            drowsy_adj = 0
        elif drowsiness_score <= 70:
            drowsy_adj = -5
        else:
            drowsy_adj = -10

        # Step 3: 현재 시간대의 과거 피로 패턴 보정
        hour = datetime.datetime.now().hour
        hour_fatigue = self._hourly_pattern.get(hour)
        if hour_fatigue is not None:
            if hour_fatigue >= 75:
                time_adj = -5
            elif hour_fatigue >= 50:
                time_adj = -3
            else:
                time_adj = 0
        else:
            time_adj = 0

        result = base + fatigue_adj + drowsy_adj + time_adj
        return max(config.POMODORO_MIN_WORK_MIN,
                   min(config.POMODORO_MAX_WORK_MIN, result))

    def _calc_break_duration(self, fatigue_level: str, cycle: int) -> int:
        """피로 단계와 사이클 수로 휴식 시간(분)을 계산한다.

        4사이클마다 긴 휴식(15분)을 부여한다.
        """
        if cycle > 0 and (cycle + 1) % self._LONG_BREAK_CYCLE == 0:
            return config.POMODORO_LONG_BREAK_MIN

        return {
            "good":    config.POMODORO_BASE_BREAK_MIN,
            "caution": 8,
            "warning": 15,
            "danger":  30,
        }.get(fatigue_level, config.POMODORO_BASE_BREAK_MIN)
