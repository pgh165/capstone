"""AlertController 경고 단계 수동 테스트"""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.alert import AlertController


def test_alert_levels():
    """모든 경고 단계를 순차적으로 테스트"""
    print("=" * 50)
    print("AlertController 경고 단계 테스트")
    print("=" * 50)

    alert = AlertController()

    levels = [
        (0, "정상", 2),
        (1, "주의", 2),
        (2, "경고", 3),
        (3, "위험", 3),
        (0, "정상으로 복귀", 2),
    ]

    for level, desc, duration in levels:
        print(f"\n테스트: Level {level} - {desc}")
        alert.set_alert_level(level)
        print(f"  {duration}초 유지...")
        time.sleep(duration)

    alert.cleanup()
    print("\n테스트 완료!")


if __name__ == '__main__':
    test_alert_levels()
