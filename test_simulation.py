"""
졸음·피로 시뮬레이션 테스트
- AIJudge에 가짜 수치를 넣어 AI 판정 확인
- LLMCoach에 피로 컨텍스트를 넣어 코칭 메시지 + TTS 확인
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.ai_judge import AIJudge
from modules.llm_coach import LLMCoach
from modules.voice import Voice

# ── 시뮬레이션 시나리오 ──────────────────────────────────────
SCENARIOS = [
    {
        "name": "경고 단계 (눈 감김 + 하품)",
        "metrics": {
            "ear": 0.12,          # 눈 거의 감김
            "mar": 0.75,          # 하품 중
            "pitch": -18.0,       # 고개 숙임
            "yaw": 5.0,
            "ear_closed_sec": 3.5,
            "yawn_count": 4,
        },
        "fatigue_ctx": {
            "fatigue_level": "warning",
            "fatigue_score": 78,
            "dominant_cause": "drowsy",
            "guide_types": ["eye_rest", "stretch"],
            "work_min": 95,
            "drowsy_count": 8,
            "recovery_history_summary": "eye_rest=3/4, stretch=2/3",
        },
    },
    {
        "name": "위험 단계 (장시간 작업)",
        "metrics": {
            "ear": 0.10,
            "mar": 0.80,
            "pitch": -22.0,
            "yaw": 3.0,
            "ear_closed_sec": 5.0,
            "yawn_count": 7,
        },
        "fatigue_ctx": {
            "fatigue_level": "danger",
            "fatigue_score": 92,
            "dominant_cause": "work",
            "guide_types": ["walk", "hydration"],
            "work_min": 180,
            "drowsy_count": 15,
            "recovery_history_summary": "walk=1/2, hydration=2/2",
        },
    },
]

# ────────────────────────────────────────────────────────────

def run():
    voice = Voice()
    ai_judge = AIJudge()
    llm_coach = LLMCoach()

    for i, s in enumerate(SCENARIOS):
        print()
        print(f"{'='*60}")
        print(f"  시나리오 {i+1}: {s['name']}")
        print(f"{'='*60}")

        # 1. AI Judge 판정
        print("\n[1] AIJudge 판정 요청...")
        ai_judge._last_run = 0  # 쿨다운 초기화
        ai_judge._result = None
        ai_judge.request(s["metrics"])

        # 판정 결과 대기 (최대 60초) — 워커 완전 종료까지 기다림
        for _ in range(120):
            time.sleep(0.5)
            if ai_judge._worker and not ai_judge._worker.is_alive():
                break
        result = ai_judge.latest()
        if result:
            print(f"    졸음점수={result['drowsiness']}  Level={result['level']}")
        else:
            print("    [timeout] AI 판정 응답 없음")

        # 2. LLM Coach 코칭 메시지 (ai_judge 워커 종료 후 요청)
        print("\n[2] LLMCoach 코칭 요청...")
        llm_coach._last_request_time = 0  # 쿨다운 초기화
        submitted = llm_coach.request_coaching(s["fatigue_ctx"])
        print(f"    요청 제출 여부: {submitted}")

        # 코칭 결과 대기 (최대 120초)
        coaching_result = None
        for _ in range(240):
            time.sleep(0.5)
            coaching_result = llm_coach.poll_result()
            if coaching_result:
                break

        if coaching_result:
            llm_coach.display(coaching_result)
            text = coaching_result.get("text", "")
            if text:
                print("[3] TTS 발화 중...")
                voice.speak(text)
                # TTS 완료 대기
                time.sleep(len(text) * 0.1 + 3)
        else:
            print("    [timeout] 코칭 메시지 응답 없음")

        if i < len(SCENARIOS) - 1:
            print("\n다음 시나리오까지 5초 대기...")
            time.sleep(5)

    voice.stop()
    print("\n시뮬레이션 완료")


if __name__ == "__main__":
    run()
