"""
로컬 LLM 코치 모듈 (Ollama HTTP API 연동)

피로 상태·원인·환경·회복 이력을 기반으로 개인화된 졸음 관리 조언을 생성한다.
- 백그라운드 스레드로 실행되어 메인 감지 루프를 차단하지 않음
- Ollama 서버 미가동 시 자동으로 비활성화 (기존 정적 가이드 fallback)
- 쿨다운으로 동일한 조언 반복 방지
"""

import sys
import os
import json
import time
import threading
from urllib import request as urlreq
from urllib.error import URLError, HTTPError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


CAUSE_LABELS = {
    "work": "장시간 연속 작업",
    "drowsy": "졸음 빈번 감지",
    "env": "환경 스트레스(CO2/온도/습도)",
}

LEVEL_LABELS = {
    "caution": "주의",
    "warning": "경고",
    "danger": "위험",
}

SYSTEM_PROMPT = (
    "당신은 사용자의 졸음과 피로를 실시간으로 관리하는 헬스 코치입니다. "
    "얼굴 감지(EAR/MAR), 연속 작업 시간, 환경 센서(CO2/온도/습도), "
    "과거 회복 이력을 참고해서 한국어로 간결하고 친근하게 조언합니다. "
    "답변 규칙: (1) 4~6문장, (2) 마크다운이나 번호 목록 금지, "
    "(3) 사용자를 '님'으로 부르고 공감 먼저, 행동 제안 뒤에 제시, "
    "(4) 현재 상황의 주된 원인을 짚고 즉시 할 수 있는 구체적 행동을 1~2개 제안."
)


class LLMCoach:
    """Ollama 로컬 LLM을 비동기로 호출하는 코치 클라이언트."""

    def __init__(self):
        self.enabled = config.LLM_ENABLED
        self.host = config.LLM_HOST.rstrip("/")
        self.model = config.LLM_MODEL
        self.timeout = config.LLM_TIMEOUT
        self.cooldown = config.LLM_COOLDOWN

        self._last_request_time = 0.0
        self._worker = None            # 현재 실행 중인 스레드
        self._pending_result = None    # 스레드가 완료되면 채워짐
        self._lock = threading.Lock()
        self._available = None         # None=미확인, True/False=확인됨

        if self.enabled:
            # 지연 초기화 — 서버 체크는 첫 호출 시
            print(f"[llm_coach] LLM 코치 활성화 (model={self.model})")
        else:
            print("[llm_coach] LLM 코치 비활성화 (config.LLM_ENABLED=False)")

    # ──────────────────────────────────────────────────────────────
    #  서버 가용성 체크
    # ──────────────────────────────────────────────────────────────
    def _check_available(self):
        """Ollama 서버 가용 여부를 확인한다 (1회만 수행)."""
        if self._available is not None:
            return self._available
        try:
            req = urlreq.Request(f"{self.host}/api/tags")
            with urlreq.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                self._available = True
                # 모델 존재 여부 체크 (태그 정확히 일치하지 않아도 경고만)
                if not any(self.model in m for m in models):
                    print(
                        f"[llm_coach] 경고: '{self.model}' 모델이 설치되어 있지 않을 수 있음. "
                        f"설치된 모델: {models}"
                    )
                else:
                    print("[llm_coach] Ollama 서버 연결 확인")
        except (URLError, HTTPError, OSError, json.JSONDecodeError) as e:
            self._available = False
            print(f"[llm_coach] Ollama 서버 접속 불가 — LLM 코칭 비활성화 ({e})")
        return self._available

    # ──────────────────────────────────────────────────────────────
    #  프롬프트 구성
    # ──────────────────────────────────────────────────────────────
    def _build_prompt(self, context):
        """사용자 상태 컨텍스트로부터 LLM 프롬프트를 구성한다."""
        level = context.get("fatigue_level", "caution")
        cause = context.get("dominant_cause", "work")
        level_label = LEVEL_LABELS.get(level, level)
        cause_label = CAUSE_LABELS.get(cause, cause)

        guide_names = context.get("guide_types") or []
        guide_str = ", ".join(guide_names) if guide_names else "(없음)"

        env = context.get("env", {})
        history = context.get("recovery_history_summary", "")

        lines = [
            f"현재 피로 단계: {level_label} (점수 {context.get('fatigue_score', 0):.0f}/100)",
            f"주된 피로 원인: {cause_label}",
            f"연속 작업 시간: {context.get('work_min', 0):.0f}분",
            f"최근 30분 졸음 감지 횟수: {context.get('drowsy_count', 0)}회",
            f"CO2: {env.get('co2', 0)}ppm, 온도: {env.get('temp', 0)}°C, "
            f"습도: {env.get('humid', 0)}%",
            f"현재 권장 가이드: {guide_str}",
        ]
        if history:
            lines.append(f"과거 회복 효과 이력 요약: {history}")

        context_block = "\n".join(lines)
        return (
            f"{context_block}\n\n"
            f"위 상황에 맞는 개인화된 졸음 관리 조언을 작성해 주세요."
        )

    # ──────────────────────────────────────────────────────────────
    #  LLM 호출 (동기, 내부용)
    # ──────────────────────────────────────────────────────────────
    def _call_ollama(self, prompt):
        """Ollama /api/generate 엔드포인트를 호출해 응답 문자열을 반환."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": 0.6,
                "num_predict": config.LLM_MAX_TOKENS,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urlreq.Request(
            f"{self.host}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urlreq.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("response", "").strip()

    # ──────────────────────────────────────────────────────────────
    #  워커 스레드
    # ──────────────────────────────────────────────────────────────
    def _worker_fn(self, prompt, context):
        try:
            text = self._call_ollama(prompt)
        except (URLError, HTTPError, OSError) as e:
            text = ""
            print(f"[llm_coach] LLM 호출 실패: {e}")
        except json.JSONDecodeError as e:
            text = ""
            print(f"[llm_coach] 응답 파싱 실패: {e}")

        with self._lock:
            self._pending_result = {
                "text": text,
                "context": context,
                "finished_at": time.time(),
            }

    # ──────────────────────────────────────────────────────────────
    #  공개 API
    # ──────────────────────────────────────────────────────────────
    def request_coaching(self, context):
        """코칭을 비동기로 요청한다.

        Args:
            context (dict): 피로 상태·원인·환경·이력 정보.

        Returns:
            bool: 요청이 큐에 실제로 제출됐는지 여부.
        """
        if not self.enabled:
            return False
        if not self._check_available():
            return False

        now = time.time()
        if now - self._last_request_time < self.cooldown:
            return False
        if self._worker is not None and self._worker.is_alive():
            return False  # 이전 요청이 아직 진행 중

        prompt = self._build_prompt(context)
        self._last_request_time = now
        self._pending_result = None
        self._worker = threading.Thread(
            target=self._worker_fn,
            args=(prompt, context),
            daemon=True,
        )
        self._worker.start()
        return True

    def poll_result(self):
        """완료된 코칭 결과가 있으면 반환하고, 없으면 None.

        반환 후에는 내부 상태가 초기화되어 같은 결과를 두 번 반환하지 않는다.
        """
        with self._lock:
            if self._pending_result is None:
                return None
            result = self._pending_result
            self._pending_result = None
            return result

    def display(self, result):
        """코칭 결과를 콘솔에 보기 좋게 출력한다."""
        text = (result or {}).get("text", "").strip()
        if not text:
            return
        print()
        print("┌" + "─" * 58 + "┐")
        print("│  AI 졸음 관리 코치" + " " * 40 + "│")
        print("├" + "─" * 58 + "┤")
        for line in text.splitlines():
            # 긴 줄은 56자마다 나눠 출력
            while len(line) > 56:
                print(f"│ {line[:56]:<57}│")
                line = line[56:]
            print(f"│ {line:<57}│")
        print("└" + "─" * 58 + "┘")
        print()
