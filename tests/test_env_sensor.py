"""환경 점수 산출 단위 테스트"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.judge import DrowsinessJudge


class TestEnvironmentScore(unittest.TestCase):
    """DrowsinessJudge의 환경 점수 산출 테스트"""

    def setUp(self):
        self.judge = DrowsinessJudge()

    # ── CO₂ 점수 테스트 ──
    def test_co2_comfortable(self):
        """CO₂ 400~800ppm → 0점"""
        self.assertEqual(self.judge._score_co2(500), 0)
        self.assertEqual(self.judge._score_co2(800), 0)

    def test_co2_moderate(self):
        """CO₂ 1000ppm → 30점 (breakpoint)"""
        self.assertEqual(self.judge._score_co2(1000), 30)

    def test_co2_bad(self):
        """CO₂ 1500ppm → 60점 (breakpoint)"""
        self.assertEqual(self.judge._score_co2(1500), 60)

    def test_co2_very_bad(self):
        """CO₂ 1500ppm 이상 → 100점"""
        self.assertEqual(self.judge._score_co2(2000), 100)

    def test_co2_none(self):
        """CO₂ None → 0점"""
        self.assertEqual(self.judge._score_co2(None), 0)

    # ── 온도 점수 테스트 ──
    def test_temp_comfortable(self):
        """18~24°C → 0점"""
        self.assertEqual(self.judge._score_temperature(22), 0)

    def test_temp_slightly_high(self):
        """26°C → 40점 (breakpoint)"""
        self.assertEqual(self.judge._score_temperature(26), 40)

    def test_temp_drowsy(self):
        """28°C → 70점 (breakpoint)"""
        self.assertEqual(self.judge._score_temperature(28), 70)

    def test_temp_very_high(self):
        """28°C 이상 → 100점"""
        self.assertEqual(self.judge._score_temperature(30), 100)

    # ── 습도 점수 테스트 ──
    def test_humidity_comfortable(self):
        """40~60%RH → 0점"""
        self.assertEqual(self.judge._score_humidity(50), 0)

    def test_humidity_slightly_high(self):
        """70%RH → 40점 (breakpoint)"""
        self.assertEqual(self.judge._score_humidity(70), 40)

    def test_humidity_uncomfortable(self):
        """80%RH → 80점 (breakpoint)"""
        self.assertEqual(self.judge._score_humidity(80), 80)

    # ── 종합 환경 점수 테스트 ──
    def test_env_score_all_comfortable(self):
        """쾌적한 환경 → 점수 0"""
        score = self.judge.calculate_env_score(500, 22, 50)
        self.assertEqual(score, 0)

    def test_env_score_all_bad(self):
        """모든 환경 나쁨 → 높은 점수"""
        score = self.judge.calculate_env_score(2000, 30, 80)
        self.assertGreater(score, 80)

    def test_env_score_range(self):
        """환경 점수는 0~100 범위"""
        for co2 in [400, 800, 1000, 1500, 2000]:
            for temp in [20, 25, 27, 30]:
                for humid in [50, 65, 75]:
                    score = self.judge.calculate_env_score(co2, temp, humid)
                    self.assertGreaterEqual(score, 0)
                    self.assertLessEqual(score, 100)


if __name__ == '__main__':
    unittest.main()
