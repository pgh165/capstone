"""
개인 EAR/MAR 기준값 캘리브레이션 모듈

세션 시작 후 30초간 정상 상태의 EAR/MAR을 측정하여
사용자 개인 얼굴 구조에 맞는 임계값을 자동 산출한다.

측정 결과는 data/calibration.json에 저장되어 다음 실행 시 재사용한다.
저장 데이터가 EXPIRY_DAYS 이내이면 측정을 건너뛴다.
"""

import time
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

_DEFAULT_SAVE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "calibration.json"
)


class EARCalibrator:
    """세션 초반 개인 EAR/MAR 기준값을 자동 측정하는 클래스.

    저장된 캘리브레이션 데이터가 있으면 즉시 로드하고,
    없거나 만료됐으면 30초 측정 후 저장한다.
    """

    DURATION    = 30          # 캘리브레이션 수집 시간 (초)
    EXPIRY_DAYS = 30          # 저장 데이터 유효 기간 (일)

    # 수집 시 명백한 이상값 제외 기준
    EAR_OPEN_MIN = 0.12       # 눈 감김 값(blink) 제외
    MAR_YAWN_MAX = 0.45       # 하품 중 값 제외

    # 개인 임계값 계산 비율
    EAR_FACTOR = 0.75         # 기준 EAR의 75% → 눈 감김 판정
    MAR_FACTOR = 3.0          # 기준 MAR의 3.0배 → 하품 판정

    # 안전 범위 클램프
    EAR_MIN, EAR_MAX = 0.10, 0.25
    MAR_MIN, MAR_MAX = 0.65, 0.90

    def __init__(self, save_path: str = _DEFAULT_SAVE_PATH):
        self._save_path = save_path
        self._ear_samples = []
        self._mar_samples = []
        self._start_time = None
        self._last_log_time = 0.0

        self.done = False
        self.ear_threshold = config.EAR_THRESHOLD
        self.mar_threshold = config.MAR_THRESHOLD

        # 저장된 데이터가 있으면 즉시 로드
        self._try_load()

    # ──────────────────────────────────────────────
    #  저장 / 로드
    # ──────────────────────────────────────────────
    def _try_load(self):
        """저장 파일이 있고 유효 기간 내이면 로드하여 측정을 건너뛴다."""
        if not os.path.exists(self._save_path):
            return

        try:
            with open(self._save_path, encoding="utf-8") as f:
                data = json.load(f)

            saved_at = data.get("saved_at", 0)
            age_days = (time.time() - saved_at) / 86400
            if age_days > self.EXPIRY_DAYS:
                print(
                    f"[calibration] 저장 데이터 만료 ({age_days:.0f}일 경과) "
                    f"— 재측정합니다."
                )
                return

            self.ear_threshold = float(data["ear_threshold"])
            self.mar_threshold = float(data["mar_threshold"])
            self.done = True
            print(
                f"[calibration] 저장된 개인 기준값 로드 "
                f"(측정일: {_fmt_age(age_days)}) — "
                f"EAR: {self.ear_threshold:.3f} / MAR: {self.mar_threshold:.3f}"
            )
        except Exception as e:
            print(f"[calibration] 저장 데이터 로드 실패 ({e}) — 재측정합니다.")

    def save(self):
        """현재 임계값을 파일에 저장한다."""
        try:
            os.makedirs(os.path.dirname(self._save_path), exist_ok=True)
            payload = {
                "ear_threshold": round(self.ear_threshold, 4),
                "mar_threshold": round(self.mar_threshold, 4),
                "saved_at":      time.time(),
                "ear_samples":   len(self._ear_samples),
                "mar_samples":   len(self._mar_samples),
            }
            with open(self._save_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            print(f"[calibration] 개인 기준값 저장 완료 → {self._save_path}")
        except Exception as e:
            print(f"[calibration] 저장 실패: {e}")

    def reset(self):
        """저장 파일을 삭제하고 재측정 상태로 초기화한다."""
        if os.path.exists(self._save_path):
            try:
                os.remove(self._save_path)
            except Exception:
                pass
        self._ear_samples = []
        self._mar_samples = []
        self._start_time = None
        self._last_log_time = 0.0
        self.done = False
        self.ear_threshold = config.EAR_THRESHOLD
        self.mar_threshold = config.MAR_THRESHOLD
        print("[calibration] 리셋 — 다음 얼굴 감지 시 재측정을 시작합니다.")

    # ──────────────────────────────────────────────
    #  측정 루프
    # ──────────────────────────────────────────────
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
        """수집된 샘플로 개인 임계값을 산출하고 파일에 저장한다."""
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
        self.save()


def _fmt_age(days: float) -> str:
    if days < 1:
        return f"{int(days * 24)}시간 전"
    return f"{int(days)}일 전"
