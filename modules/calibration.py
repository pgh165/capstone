"""
개인 EAR/MAR 기준값 캘리브레이션 모듈

세션 시작 후 30초간 정상 상태의 EAR/MAR을 측정하여
사용자 개인 얼굴 구조에 맞는 임계값을 자동 산출한다.
"""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class EARCalibrator:
    """세션 초반 개인 EAR/MAR 기준값을 자동 측정하는 클래스."""

    DURATION = 30         # 캘리브레이션 수집 시간 (초)

    # 수집 시 명백한 이상값 제외 기준
    EAR_OPEN_MIN = 0.12   # 눈 감김 값(blink) 제외
    MAR_YAWN_MAX = 0.45   # 하품 중 값 제외

    # 개인 임계값 계산 비율
    EAR_FACTOR = 0.75     # 기준 EAR의 75% → 눈 감김 판정
    MAR_FACTOR = 3.0      # 기준 MAR의 3.0배 → 하품 판정

    # 안전 범위 클램프
    EAR_MIN, EAR_MAX = 0.10, 0.25
    MAR_MIN, MAR_MAX = 0.65, 0.90

    def __init__(self):
        self._ear_samples = []
        self._mar_samples = []
        self._start_time = None
        self._last_log_time = 0.0

        self.done = False
        self.ear_threshold = config.EAR_THRESHOLD
        self.mar_threshold = config.MAR_THRESHOLD

    def update(self, ear: float, mar: float):
        """매 프레임(얼굴 감지 시) 호출. 완료 후에는 즉시 반환한다."""
        if self.done:
            return

        now = time.time()
        if self._start_time is None:
            self._start_time = now
            print(
                f"[calibration] 개인 기준값 측정 시작 — "
                f"{self.DURATION}초간 정면을 바라봐 주세요."
            )

        elapsed = now - self._start_time
        if elapsed < self.DURATION:
            # 이상값 제외 후 샘플 수집
            if ear > self.EAR_OPEN_MIN:
                self._ear_samples.append(ear)
            if mar < self.MAR_YAWN_MAX:
                self._mar_samples.append(mar)

            # 10초마다 진행 상황 출력
            if now - self._last_log_time >= 10.0:
                remaining = int(self.DURATION - elapsed)
                print(f"[calibration] 측정 중... {remaining}초 남음")
                self._last_log_time = now
        else:
            self._finalize()

    @property
    def progress(self) -> int:
        """캘리브레이션 진행률 (0~100)."""
        if self._start_time is None:
            return 0
        return min(100, int((time.time() - self._start_time) / self.DURATION * 100))

    def _finalize(self):
        """수집된 샘플로 개인 임계값을 산출한다."""
        if self._ear_samples:
            avg_ear = sum(self._ear_samples) / len(self._ear_samples)
            personal_ear = round(avg_ear * self.EAR_FACTOR, 3)
            self.ear_threshold = max(self.EAR_MIN, min(self.EAR_MAX, personal_ear))

        if self._mar_samples:
            avg_mar = sum(self._mar_samples) / len(self._mar_samples)
            personal_mar = round(avg_mar * self.MAR_FACTOR, 3)
            self.mar_threshold = max(self.MAR_MIN, min(self.MAR_MAX, personal_mar))

        self.done = True
        print(
            f"[calibration] 완료 — "
            f"EAR: {self.ear_threshold:.3f} (기본: {config.EAR_THRESHOLD}) / "
            f"MAR: {self.mar_threshold:.3f} (기본: {config.MAR_THRESHOLD}) "
            f"[샘플: EAR {len(self._ear_samples)}개, MAR {len(self._mar_samples)}개]"
        )
