"""피로도 관리 모듈 단위 테스트"""

import unittest
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from modules.fatigue_manager import FatigueManager


class TestFatigueManager(unittest.TestCase):
    """FatigueManager 클래스 테스트"""

    def setUp(self):
        self.fm = FatigueManager()

    def test_initial_state(self):
        """초기 상태 - 피로도 0, 단계 good"""
        self.assertEqual(self.fm.fatigue_score, 0)
        self.assertEqual(self.fm.get_fatigue_level(), "good")

    def test_update_with_normal_data(self):
        """정상 데이터 업데이트 - 피로도 낮음"""
        env = {"co2": 500, "temperature": 22, "humidity": 50}
        self.fm.update(drowsiness_score=10, alert_level=0, env_data=env)
        self.assertLessEqual(self.fm.fatigue_score, config.FATIGUE_GOOD_MAX)

    def test_drowsiness_events_increase_fatigue(self):
        """졸음 감지가 쌓이면 피로도 증가"""
        env = {"co2": 500, "temperature": 22, "humidity": 50}
        # alert_level >= 1 이벤트를 여러 번 발생
        for _ in range(6):
            self.fm.update(drowsiness_score=70, alert_level=2, env_data=env)
        self.assertGreater(self.fm.fatigue_score, 0)

    def test_fatigue_level_transitions(self):
        """피로 단계가 점수에 따라 전환"""
        self.fm._fatigue_score = 0
        self.assertEqual(self.fm.get_fatigue_level(), "good")

        self.fm._fatigue_score = 50
        self.assertEqual(self.fm.get_fatigue_level(), "caution")

        self.fm._fatigue_score = 75
        self.assertEqual(self.fm.get_fatigue_level(), "warning")

        self.fm._fatigue_score = 90
        self.assertEqual(self.fm.get_fatigue_level(), "danger")

    def test_apply_recovery(self):
        """피로 해소 적용"""
        self.fm._fatigue_score = 60
        self.fm.apply_recovery(30)
        self.assertEqual(self.fm.fatigue_score, 30)

    def test_apply_recovery_no_negative(self):
        """피로 해소 시 0 미만으로 내려가지 않음"""
        self.fm._fatigue_score = 10
        self.fm.apply_recovery(30)
        self.assertEqual(self.fm.fatigue_score, 0)

    def test_reset_work_timer(self):
        """작업 타이머 리셋"""
        self.fm.reset_work_timer()
        minutes = self.fm.get_continuous_work_minutes()
        self.assertLess(minutes, 1)

    def test_recommended_guide_good(self):
        """양호 상태 - 가이드 없음"""
        self.fm._fatigue_score = 10
        guides = self.fm.get_recommended_guide()
        self.assertEqual(guides, [])

    def test_recommended_guide_caution(self):
        """주의 상태 - 눈 휴식 + 환기"""
        self.fm._fatigue_score = 50
        guides = self.fm.get_recommended_guide()
        self.assertIn("eye_rest", guides)
        self.assertIn("ventilation", guides)

    def test_recommended_guide_danger(self):
        """위험 상태 - 모든 가이드"""
        self.fm._fatigue_score = 90
        guides = self.fm.get_recommended_guide()
        self.assertIn("rest_break", guides)
        self.assertGreater(len(guides), 3)

    def test_get_status(self):
        """상태 딕셔너리 반환"""
        status = self.fm.get_status()
        self.assertIn("fatigue_score", status)
        self.assertIn("fatigue_level", status)
        self.assertIn("continuous_work_min", status)
        self.assertIn("drowsy_count_30min", status)
        self.assertIn("env_stress_score", status)


if __name__ == '__main__':
    unittest.main()
