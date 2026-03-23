"""GPIO 경고 출력 테스트

데스크탑에서는 콘솔 출력으로 동작을 확인한다.
라즈베리파이에서는 실제 LED/부저를 테스트한다.
"""

import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from modules.alert import AlertController


def test_alert_levels():
    """모든 경고 단계를 순차적으로 테스트"""
    print("=" * 50)
    print("GPIO 경고 출력 테스트")
    print(f"모드: {'데스크탑 (콘솔)' if config.IS_DESKTOP else '라즈베리파이 (GPIO)'}")
    print("=" * 50)

    alert = AlertController()

    levels = [
        (0, "정상 (녹색 LED)", 2),
        (1, "주의 (황색 LED + 짧은 알림음)", 2),
        (2, "경고 (적색 LED + 연속 부저)", 3),
        (3, "위험 (적색 점멸 + 강한 부저)", 3),
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
