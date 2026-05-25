"""
AI 기반 학습 피로 관리 시스템 - 동작 시연 데모

카메라 없이 시뮬레이션 데이터로 전체 파이프라인을 시연한다.
  정상 → 주의 → 경고 → 위험 → 포모도로 휴식 → 회복

실행: python demo.py
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from modules.judge import DrowsinessJudge
from modules.fatigue_manager import FatigueManager
from modules.alert import AlertController
from modules.voice import Voice
from modules.pomodoro import PomodoroTimer
from modules.llm_coach import LLMCoach

# ── ANSI 색상 ────────────────────────────────────────────────
GREEN  = "\033[32m"
YELLOW = "\033[33m"
ORANGE = "\033[91m"
RED    = "\033[31m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

LEVEL_COLOR = {0: GREEN, 1: YELLOW, 2: ORANGE, 3: RED}
LEVEL_NAME  = {0: "정상", 1: "주의", 2: "경고", 3: "위험"}

STATUS_FILE = os.path.join(config.BASE_DIR, "data", "realtime_status.json")


# ── 유틸 ─────────────────────────────────────────────────────
def write_status(drowsiness_score, alert_level, fatigue_score, fatigue_level,
                 ear=0.30, mar=0.20, pitch=0.0, yaw=0.0,
                 yawn_count=0, perclos=0.0, pomo=None):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump({
            "ts": time.time(),
            "drowsiness_score": int(drowsiness_score),
            "alert_level": alert_level,
            "fatigue_score": int(fatigue_score),
            "fatigue_level": fatigue_level,
            "perclos": round(perclos, 1),
            "yawn_count": yawn_count,
            "ear": round(ear, 3),
            "mar": round(mar, 3),
            "pitch": round(pitch, 1),
            "yaw": round(yaw, 1),
            "face_detected": True,
            "pomo": pomo or {"state": "idle"},
        }, f)


def banner(title, color=CYAN):
    print(f"\n{color}{BOLD}{'━' * 56}")
    print(f"  {title}")
    print(f"{'━' * 56}{RESET}")


def log_state(drowsiness_score, alert_level, fatigue_score, fatigue_level, pomo_status):
    color = LEVEL_COLOR[alert_level]
    pomo_st = pomo_status.get("state", "idle")
    if pomo_st == "working":
        pomo_str = f"작업 {pomo_status.get('elapsed_min', 0):.0f}/{pomo_status.get('planned_min', 25)}분"
    elif pomo_st == "break":
        pomo_str = f"휴식 {pomo_status.get('remaining_min', 0):.1f}분 남음"
    else:
        pomo_str = "대기 중"
    print(f"  {color}졸음 {drowsiness_score:5.1f}  "
          f"L{alert_level}-{LEVEL_NAME[alert_level]:<4}  "
          f"피로 {fatigue_score:5.1f} ({fatigue_level:<8})  "
          f"🍅 {pomo_str}{RESET}")


# ── 핵심: N프레임 시뮬레이션 ────────────────────────────────
def simulate(judge, fatigue_manager, alert_controller, pomodoro, llm_coach,
             *,
             ear_score, mar_score, head_score,       # 0~100 점수
             ear_val, mar_val, pitch, perclos,        # 대시보드용 원시 값
             yawn_count=0,
             duration_sec=8, fps=15,
             request_coaching=False):
    """지정 시간 동안 센서 데이터를 시뮬레이션한다."""
    frames = int(duration_sec * fps)
    last_print = time.time()
    coaching_sent = False

    for i in range(frames):
        drowsiness_score = judge.calculate_drowsiness_score(ear_score, mar_score, head_score)
        alert_level      = judge.get_alert_level(drowsiness_score)

        fatigue_manager.update(drowsiness_score, alert_level)
        fs = fatigue_manager.get_status()
        fatigue_score = fs["fatigue_score"]
        fatigue_level = fs["fatigue_level"]

        # 포모도로: 첫 프레임에서 자동 시작
        if pomodoro.state == pomodoro.IDLE:
            ev = pomodoro.start(fatigue_score, drowsiness_score)
            print(f"\n  [포모도로] 작업 시작 — {ev['planned_min']}분 집중")

        pomo_status = pomodoro.get_status()

        # 경보 (히스테리시스 적용)
        alert_controller.update(drowsiness_score, alert_level)

        # 대시보드 상태 파일 갱신
        write_status(drowsiness_score, alert_level, fatigue_score, fatigue_level,
                     ear=ear_val, mar=mar_val, pitch=pitch,
                     yawn_count=yawn_count, perclos=perclos, pomo=pomo_status)

        # LLM 코칭 요청 (1회)
        if request_coaching and not coaching_sent:
            llm_coach._last_request_time = 0
            llm_coach.request_coaching({
                "fatigue_level": fatigue_level,
                "fatigue_score": int(fatigue_score),
                "dominant_cause": fatigue_manager.get_dominant_cause(),
                "guide_types": fatigue_manager.get_recommended_guide() or ["eye_rest"],
                "work_min": int(fs["continuous_work_min"]),
                "drowsy_count": fs["drowsy_count_30min"],
                "recovery_history_summary": "",
            })
            coaching_sent = True
            print(f"  [LLM] 코칭 메시지 요청 전송 (응답 대기 중...)")

        # 1초마다 콘솔 출력
        now = time.time()
        if now - last_print >= 1.0:
            log_state(drowsiness_score, alert_level, fatigue_score, fatigue_level, pomo_status)
            last_print = now

        time.sleep(1 / fps)

    return drowsiness_score, alert_level, fatigue_manager.get_status()


# ── 메인 데모 ────────────────────────────────────────────────
def run():
    print(f"\n{BOLD}{CYAN}{'=' * 56}")
    print("  AI 기반 학습 피로 관리 시스템 — 동작 시연 데모")
    print(f"{'=' * 56}{RESET}")
    print(f"  대시보드: http://localhost:8000/realtime/\n")

    # 모듈 초기화
    judge            = DrowsinessJudge()
    fatigue_manager  = FatigueManager()
    voice            = Voice()
    alert_controller = AlertController(voice=voice)
    pomodoro         = PomodoroTimer()
    llm_coach        = LLMCoach()

    # ── Phase 1: 정상 ──────────────────────────────────────
    banner("Phase 1 / 정상  —  집중 작업 중", GREEN)
    print(f"  EAR 높음(눈 떠있음), 하품 없음, 고개 바른 자세")
    # EMA 초기화: 낮은 점수로 빠르게 수렴
    judge._ema_score = 8.0
    simulate(judge, fatigue_manager, alert_controller, pomodoro, llm_coach,
             ear_score=8,  mar_score=5,  head_score=5,
             ear_val=0.32, mar_val=0.15, pitch=-2.0, perclos=2.0,
             duration_sec=8)

    # ── Phase 2: 주의 ──────────────────────────────────────
    banner("Phase 2 / 주의  —  눈 깜박임 증가, 가벼운 하품", YELLOW)
    print(f"  EAR 감소, MAR 소폭 상승")
    # raw = 75*0.45 + 65*0.30 + 45*0.25 = 33.75+19.5+11.25 = 64.5 → (64.5²)/100 = 41.6 (주의)
    judge._ema_score = 42.0
    simulate(judge, fatigue_manager, alert_controller, pomodoro, llm_coach,
             ear_score=75, mar_score=65, head_score=45,
             ear_val=0.20, mar_val=0.45, pitch=-8.0, perclos=18.0,
             yawn_count=1, duration_sec=8)

    # ── Phase 3: 경고 ──────────────────────────────────────
    banner("Phase 3 / 경고  —  눈 자주 감김, 반복 하품", ORANGE)
    print(f"  EAR 임계값 이하, MAR 상승, 하품 횟수 증가")
    # raw = 100*0.45 + 85*0.30 + 70*0.25 = 45+25.5+17.5 = 88 → (88²)/100 = 77.4 (경고)
    judge._ema_score = 73.0
    simulate(judge, fatigue_manager, alert_controller, pomodoro, llm_coach,
             ear_score=100, mar_score=85, head_score=70,
             ear_val=0.14, mar_val=0.68, pitch=-15.0, perclos=42.0,
             yawn_count=3, duration_sec=8)

    # ── Phase 4: 위험 + LLM 코칭 요청 ─────────────────────
    banner("Phase 4 / 위험  —  장시간 눈 감김, 고개 숙임", RED)
    print(f"  PERCLOS 높음, 지속적 눈 감김 → LLM 코칭 요청")
    # raw = 100*0.45 + 95*0.30 + 90*0.25 = 45+28.5+22.5 = 96 → (96²)/100 = 92.2 (위험)
    judge._ema_score = 88.0
    simulate(judge, fatigue_manager, alert_controller, pomodoro, llm_coach,
             ear_score=100, mar_score=95, head_score=90,
             ear_val=0.09, mar_val=0.78, pitch=-22.0, perclos=65.0,
             yawn_count=6, duration_sec=10,
             request_coaching=True)

    # ── Phase 5: 포모도로 휴식 전환 ───────────────────────
    banner("Phase 5 / 포모도로 휴식  —  LLM 코칭 메시지 수신 대기", CYAN)
    pomodoro.start_break("warning", fatigue_manager.get_status()["fatigue_score"], 88.0)
    voice.speak("위험 수준 감지! 휴식 시간입니다. 5분 쉬어갑니다.")
    print(f"  [포모도로] 휴식 전환 완료")
    print(f"  LLM 응답 대기 중 (최대 60초)...\n")

    # LLM 응답 폴링 + 상태 파일 계속 갱신
    fs = fatigue_manager.get_status()
    judge._ema_score = 50.0   # 휴식 중 점수 서서히 감소 시뮬레이션
    for tick in range(120):
        drowsiness_score = judge.calculate_drowsiness_score(40, 30, 20)
        fs = fatigue_manager.get_status()
        write_status(drowsiness_score, 1, fs["fatigue_score"], fs["fatigue_level"],
                     ear=0.24, mar=0.25, pitch=-5.0, perclos=10.0,
                     pomo=pomodoro.get_status())

        result = llm_coach.poll_result()
        if result:
            print()
            llm_coach.display(result)
            text = result.get("text", "")
            if text:
                print("\n  [TTS] 코칭 메시지 음성 출력...")
                voice.speak(text)
                time.sleep(max(len(text) * 0.08, 5))
            break
        if tick % 10 == 0 and tick > 0:
            print(f"  ... {tick // 2}초 경과")
        time.sleep(0.5)
    else:
        print("  [LLM] 응답 없음 (서버 미응답 또는 비활성화)")

    # ── Phase 6: 회복 정상 복귀 ───────────────────────────
    banner("Phase 6 / 회복  —  정상 상태 복귀", GREEN)
    judge._ema_score = 15.0
    for _ in range(5):
        drowsiness_score = judge.calculate_drowsiness_score(10, 8, 5)
        fs = fatigue_manager.get_status()
        write_status(drowsiness_score, 0, fs["fatigue_score"], fs["fatigue_level"],
                     ear=0.31, mar=0.16, pitch=-1.0, perclos=3.0,
                     pomo=pomodoro.get_status())
        log_state(drowsiness_score, 0, fs["fatigue_score"], fs["fatigue_level"],
                  pomodoro.get_status())
        time.sleep(1)

    # ── 종료 ──────────────────────────────────────────────
    print(f"\n{BOLD}{GREEN}{'=' * 56}")
    print("  시연 완료")
    print(f"{'=' * 56}{RESET}\n")

    voice.stop()
    try:
        if os.path.exists(STATUS_FILE):
            os.remove(STATUS_FILE)
    except Exception:
        pass


if __name__ == "__main__":
    run()
