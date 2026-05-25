"""
AI 기반 졸음·피로도 판정 모듈

MediaPipe로 추출한 수치(EAR/MAR/고개)를 로컬 LLM에 전달하여
졸음 점수와 피로 레벨을 판정받는다.

- 백그라운드 스레드로 비동기 실행 (메인 루프 차단 없음)
- LLM 응답 오기 전까지는 규칙 기반 점수를 fallback으로 사용
- 응답은 JSON으로 강제: {"drowsiness": 0~100, "level": 0~3, "reason": "..."}
"""

import json
import re
import sys
import os
import threading
import time
from urllib import request as urlreq
from urllib.error import URLError, HTTPError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


SYSTEM_PROMPT = """\
당신은 졸음 감지 AI입니다. 사용자의 얼굴 분석 수치를 받아 졸음 점수를 판정합니다.

수치 설명:
- EAR: 눈 개방 비율. 정상 0.25~0.35, 0.20 이하면 눈 감김.
- MAR: 입 개방 비율. 0.6 이상이면 하품.
- pitch: 고개 상하 각도. |pitch| > 15이면 고개 숙임.
- yaw: 고개 좌우 각도. |yaw| > 20이면 고개 돌림.
- ear_closed_sec: 연속 눈 감김 지속 시간(초).
- yawn_count: 최근 3분 내 하품 횟수.
- rule_score: 규칙 기반 알고리즘이 계산한 현재 졸음 점수 (0~100). 이 값에서 ±25 이내로 판정하세요.

반드시 아래 JSON 형식으로만 답하세요. 다른 텍스트 없이 JSON만 출력하세요:
{"drowsiness": <0~100 정수>, "level": <0~3 정수>}

level 기준: 0=정상(0~40), 1=주의(41~70), 2=경고(71~85), 3=위험(86~100)
"""


class AIJudge:
    """LLM 기반 졸음·피로도 판정기."""

    INTERVAL = 5.0  # 판정 주기 (초)

    def __init__(self):
        self.enabled = config.LLM_ENABLED
        self.host = config.LLM_HOST.rstrip("/")
        self.model = config.LLM_MODEL
        self.timeout = config.LLM_TIMEOUT

        self._lock = threading.Lock()
        self._worker = None
        self._last_run = 0.0
        self._result = None      # 최신 AI 판정 결과
        self._available = None

        if self.enabled:
            print(f"[ai_judge] AI 판정 활성화 (model={self.model}, interval={self.INTERVAL}s)")
        else:
            print("[ai_judge] AI 판정 비활성화")

    # ──────────────────────────────────────────────────────────────
    #  공개 API
    # ──────────────────────────────────────────────────────────────
    def request(self, metrics: dict, rule_score: float = 0):
        """수치를 넘겨 비동기 판정을 요청한다. 주기가 안 됐으면 무시.

        Args:
            metrics: {
                "ear": float, "mar": float,
                "pitch": float, "yaw": float,
                "ear_closed_sec": float, "yawn_count": int
            }
            rule_score: 규칙 기반 알고리즘의 현재 졸음 점수 (앵커로 활용)
        """
        if not self.enabled:
            return
        now = time.time()
        if now - self._last_run < self.INTERVAL:
            return
        if self._worker and self._worker.is_alive():
            return

        self._last_run = now
        self._worker = threading.Thread(
            target=self._run, args=(dict(metrics), float(rule_score)), daemon=True
        )
        self._worker.start()

    def latest(self):
        """최신 AI 판정 결과를 반환한다. 아직 없으면 None.

        Returns:
            dict | None: {"drowsiness": int, "level": int}
        """
        with self._lock:
            return self._result

    def reset(self):
        """최신 판정 결과를 초기화한다 (얼굴 미검출 시 호출)."""
        with self._lock:
            self._result = None

    # ──────────────────────────────────────────────────────────────
    #  내부
    # ──────────────────────────────────────────────────────────────
    def _check_available(self):
        if self._available is not None:
            return self._available
        try:
            req = urlreq.Request(f"{self.host}/api/tags")
            with urlreq.urlopen(req, timeout=3) as resp:
                self._available = True
                print("[ai_judge] Ollama 서버 연결 확인")
        except Exception as e:
            self._available = False
            print(f"[ai_judge] Ollama 접속 불가 — AI 판정 비활성화 ({e})")
        return self._available

    def _build_prompt(self, m: dict, rule_score: float) -> str:
        return (
            f"EAR={m.get('ear', 0):.3f}, "
            f"MAR={m.get('mar', 0):.3f}, "
            f"pitch={m.get('pitch', 0):.1f}°, "
            f"yaw={m.get('yaw', 0):.1f}°, "
            f"눈 감김 지속={m.get('ear_closed_sec', 0):.1f}초, "
            f"하품 횟수={m.get('yawn_count', 0)}회, "
            f"rule_score={int(rule_score)}"
        )

    def _run(self, metrics: dict, rule_score: float):
        if not self._check_available():
            return

        prompt = self._build_prompt(metrics, rule_score)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": SYSTEM_PROMPT,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": 80,
                "repeat_penalty": 1.8,
            },
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urlreq.Request(
                f"{self.host}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urlreq.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                raw = body.get("response", "").strip()
                result = self._parse(raw)
                if result:
                    with self._lock:
                        self._result = result
                    print(
                        f"[ai_judge] 판정 완료 → "
                        f"졸음={result['drowsiness']} Level={result['level']}"
                    )
        except (URLError, HTTPError, OSError) as e:
            print(f"[ai_judge] 호출 실패: {e}")
        except Exception as e:
            print(f"[ai_judge] 오류: {e}")

    def _parse(self, raw: str) -> dict | None:
        """LLM 응답에서 JSON을 파싱한다. 잘린 JSON도 숫자 필드만 추출해 복구."""
        def _extract(text):
            obj = json.loads(text)
            drowsiness = int(obj.get("drowsiness", -1))
            level = int(obj.get("level", -1))
            if 0 <= drowsiness <= 100 and 0 <= level <= 3:
                return {"drowsiness": drowsiness, "level": level}
            return None

        try:
            return _extract(raw)
        except (json.JSONDecodeError, ValueError):
            pass

        # 잘린 JSON 복구: drowsiness, level 숫자만 정규식으로 추출
        try:
            d = re.search(r'"drowsiness"\s*:\s*(\d+)', raw)
            l = re.search(r'"level"\s*:\s*(\d+)', raw)
            if d and l:
                drowsiness = int(d.group(1))
                level = int(l.group(1))
                if 0 <= drowsiness <= 100 and 0 <= level <= 3:
                    return {"drowsiness": drowsiness, "level": level}
        except (AttributeError, ValueError):
            pass

        print(f"[ai_judge] JSON 파싱 실패: {raw[:120]}")
        return None
