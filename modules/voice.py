"""
TTS(음성 출력) 모듈

졸음 경보와 LLM 코칭 메시지를 음성으로 출력한다.
- 비차단 큐 기반 — 메인 루프를 절대 멈추지 않음
- priority=True 시 대기 중인 메시지를 비우고 즉시 삽입
- 엔진: espeak-ng(오프라인) / edge-tts(온라인) / melo-tts(로컬 AI)
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
        self._speaking = threading.Event()  # 재생 중일 때 set
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

    def speak_and_wait(self, text: str):
        """text를 음성으로 출력하고 재생이 완전히 끝날 때까지 블로킹한다."""
        if not self.enabled or not text or not text.strip():
            return
        self._q.put(text.strip())
        # 큐가 비고 재생도 끝날 때까지 대기
        self._q.join()

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
                self._q.task_done()
                break
            try:
                self._synthesize(item)
            except Exception as e:
                print(f"[voice] 발화 오류: {e}")
            finally:
                self._q.task_done()

    def _synthesize(self, text: str):
        if self.engine == "espeak-ng":
            self._espeak(text)
        elif self.engine == "edge-tts":
            self._edge_tts(text)
        elif self.engine == "melo-tts":
            self._melo_tts(text)
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

    # ── MeloTTS ───────────────────────────────────────────────────
    def _melo_tts(self, text: str):
        try:
            import warnings
            warnings.filterwarnings('ignore')
            import tempfile
            from melo.api import TTS as MeloTTS

            # 모델은 처음 한 번만 로드 (재사용)
            if not hasattr(self, '_melo_model'):
                device = getattr(config, 'TTS_MELO_DEVICE', 'cpu')
                self._melo_model = MeloTTS(language='KR', device=device)
                self._melo_spk = self._melo_model.hps.data.spk2id['KR']

            speed = getattr(config, 'TTS_MELO_SPEED', 1.1)
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                path = f.name
            self._melo_model.tts_to_file(text, self._melo_spk, path, speed=speed)
            self._play_audio(path)
            os.unlink(path)

        except ImportError:
            print("[voice] melo-tts 없음 → pip install melotts")
            self.enabled = False
        except Exception as e:
            print(f"[voice] melo-tts 오류: {e}")

    def _play_audio(self, path: str):
        """오디오 파일을 재생한다. WSL2 환경에서는 PowerShell을 통해 Windows로 재생."""
        # WSL2: PowerShell SoundPlayer로 재생 (출력 장치가 Windows에 있음)
        try:
            win_path = subprocess.check_output(["wslpath", "-w", path], text=True).strip()
            result = subprocess.run(
                ["powershell.exe", "-c",
                 f"(New-Object Media.SoundPlayer '{win_path}').PlaySync()"],
                timeout=60,
            )
            if result.returncode == 0:
                return
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

        # 일반 Linux: mpg123 → ffplay 순서로 시도
        for cmd in (["mpg123", "-q", path], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]):
            try:
                subprocess.run(cmd, timeout=60)
                return
            except FileNotFoundError:
                continue
        print("[voice] 오디오 플레이어 없음 (mpg123 또는 ffplay 필요)")
