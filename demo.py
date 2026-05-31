"""
시연용 데모 실행 파일

실제 카메라로 동작하지만 경보가 빠르게 발동되도록 설정을 오버라이드합니다.
  - 눈 감김 감지: 2.0초 → 0.5초
  - EMA 반응 속도: 0.25 → 0.6 (4배 빠름)
  - 경보 임계값: 낮춰서 빠르게 단계 진입

실행: python demo.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 데모용 설정 오버라이드 (main 임포트 전에 적용) ──────────
import config
config.EAR_CONSEC_SECONDS = 0.5   # 원래 2.0 → 눈 0.5초만 감아도 감지
config.ALERT_LEVEL_0_MAX  = 10    # 원래 20  → 정상 구간 좁힘
config.ALERT_LEVEL_1_MAX  = 25    # 원래 45  → 주의 빠르게 발동
config.ALERT_LEVEL_2_MAX  = 40    # 원래 65  → 경고 빠르게 발동

from modules.judge import DrowsinessJudge
DrowsinessJudge._EMA_ALPHA = 0.6  # 원래 0.25 → 점수 반응 4배 빠름

# ── 데모 설정 안내 출력 ─────────────────────────────────────
print("=" * 60)
print("  [데모 모드] 빠른 경보 설정 적용됨")
print("  눈 감김 감지: 0.5초  |  EMA: 0.6  |  임계값 낮춤")
print("=" * 60)

# ── 실제 메인 실행 ──────────────────────────────────────────
from main import main
main()
