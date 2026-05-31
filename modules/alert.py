"""
경고 출력 제어 모듈

졸음 경고 단계에 따라 콘솔 출력과 TTS 음성 경보를 출력한다.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class AlertController:
    LEVEL_LABELS = {
        0: "정상",
        1: "주의 — 졸음 감지",
        2: "경고 — 졸음 수준 높음",
        3: "위험 — 즉시 휴식 필요",
    }

    # 히스테리시스: 레벨 하강 시 적용되는 낮은 임계값 (진동 방지)
    # 예) 레벨1로 올라가려면 >20 필요, 레벨0으로 내려오려면 <13 필요
    _DOWN_THRESHOLDS = {
        1: 13,  # 레벨1→0: 13 미만이어야 복귀
        2: 33,  # 레벨2→1: 33 미만이어야 복귀
        3: 53,  # 레벨3→2: 53 미만이어야 복귀
    }

    def __init__(self, voice=None):
        self._voice = voice
        self._current_level = -1
        self._call_name = ""   # "지호야, " 형태로 저장

    def set_user_name(self, name: str):
        """main.py에서 프로필 로드 후 호출. 경보 문구에 이름 삽입."""
        if not name:
            self._call_name = ""
            return
        first_name = name[1:] if len(name) >= 2 else name
        self._call_name = first_name + "님, "

    def update(self, score: float, level: int):
        """점수와 판정 레벨을 받아 히스테리시스를 적용한 후 경고를 발생시킨다."""
        effective_level = level

        if level < self._current_level:
            threshold = self._DOWN_THRESHOLDS.get(self._current_level, 0)
            if score >= threshold:
                effective_level = self._current_level

        if effective_level == self._current_level:
            return
        self._current_level = effective_level

        label = self.LEVEL_LABELS.get(effective_level, f"알 수 없는 단계 ({effective_level})")
        print(f"[ALERT] Level {effective_level}: {label}")

        if self._voice and effective_level > 0:
            phrase = config.ALERT_PHRASES.get(effective_level, "")
            if phrase:
                self._voice.speak(self._call_name + phrase, priority=True)

    def set_alert_level(self, level: int):
        """하위 호환용. 점수 없이 레벨만 받는 경우 히스테리시스 미적용."""
        if level == self._current_level:
            return
        self._current_level = level
        label = self.LEVEL_LABELS.get(level, f"알 수 없는 단계 ({level})")
        print(f"[ALERT] Level {level}: {label}")
        if self._voice and level > 0:
            phrase = config.ALERT_PHRASES.get(level, "")
            if phrase:
                self._voice.speak(self._call_name + phrase, priority=True)

    def cleanup(self):
        pass
