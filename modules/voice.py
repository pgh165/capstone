"""
TTS(음성 출력) 모듈

졸음 경보와 LLM 코칭 메시지를 음성으로 출력한다.
- 비차단 큐 기반 — 메인 루프를 절대 멈추지 않음
- priority=True 시 대기 중인 메시지를 비우고 즉시 삽입
- 엔진: espeak-ng(오프라인) / edge-tts(온라인, 더 자연스러운 음질)
"""

import queue
import subprocess
import threading
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

_SENTINEL = object()


class Voice:
    def __init__(self):
        self.enabled = getattr(config, "TTS_ENABLED", True)
        self.engine  = getattr(config, "TTS_ENGINE",  "espeak-ng")

        self._q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)

        if self.enabled:
            self._thread.start()
            print(f"[voice] TTS 활성화 (engine={self.engine})")
        else:
            print("[voice] TTS 비활성화")

    # ──────────────────────────────────────────────────────────────
    #  공개 API
    # ──────────────────────────────────────────────────────────────
    def speak(self, text: str, priority: bool = False):
        """text를 음성으로 출력한다.

        Args:
            text:     읽을 문자열.
            priority: True 면 대기 중인 발화를 모두 버리고 앞에 삽입한다.
        """
        if not self.enabled or not text or not text.strip():
            return
        if priority:
            self._drain()
        self._q.put(text.strip())

    def stop(self):
        """대기 큐를 비우고 워커 스레드를 종료한다."""
        self._drain()
        self._q.put(_SENTINEL)

    # ──────────────────────────────────────────────────────────────
    #  내부
    # ──────────────────────────────────────────────────────────────
    def _drain(self):
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    def _worker(self):
        while True:
            item = self._q.get()
            if item is _SENTINEL:
                break
            try:
                self._synthesize(item)
            except Exception as e:
                print(f"[voice] 발화 오류: {e}")

    def _synthesize(self, text: str):
        if self.engine == "espeak-ng":
            self._espeak(text)
        elif self.engine == "edge-tts":
            self._edge_tts(text)
        else:
            print(f"[voice] 알 수 없는 엔진: {self.engine}")

    # ── espeak-ng ─────────────────────────────────────────────────
    def _espeak(self, text: str):
        lang  = getattr(config, "TTS_VOICE", "ko")
        rate  = str(getattr(config, "TTS_RATE",  150))
        pitch = str(getattr(config, "TTS_PITCH", 50))
        try:
            subprocess.run(
                ["espeak-ng", "-v", lang, "-s", rate, "-p", pitch, text],
                timeout=30,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            print("[voice] espeak-ng 없음 → sudo apt install espeak-ng")
            self.enabled = False
        except subprocess.TimeoutExpired:
            pass

    # ── edge-tts ──────────────────────────────────────────────────
    def _edge_tts(self, text: str):
        try:
            import edge_tts
            import asyncio
            import tempfile

            voice = getattr(config, "TTS_EDGE_VOICE", "ko-KR-InJoonNeural")
            rate  = getattr(config, "TTS_EDGE_RATE",  "+0%")

            async def _gen():
                comm = edge_tts.Communicate(text, voice, rate=rate)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    path = f.name
                await comm.save(path)
                return path

            path = asyncio.run(_gen())
            self._play_audio(path)
            os.unlink(path)

        except ImportError:
            print("[voice] edge-tts 없음 → pip install edge-tts")
            self.enabled = False
        except Exception as e:
            print(f"[voice] edge-tts 오류: {e}")

    def _play_audio(self, path: str):
        """MP3 파일을 재생한다. mpg123 → ffplay 순서로 시도."""
        for cmd in (["mpg123", "-q", path], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]):
            try:
                subprocess.run(cmd, timeout=60)
                return
            except FileNotFoundError:
                continue
        print("[voice] 오디오 플레이어 없음 (mpg123 또는 ffplay 필요)")
