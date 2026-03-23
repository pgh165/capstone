"""MAR (Mouth Aspect Ratio) 알고리즘 단위 테스트"""

import unittest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.drowsiness import calculate_mar


class TestMAR(unittest.TestCase):
    """MAR 계산 함수 테스트"""

    def _make_mouth(self, opening=0.0):
        """테스트용 입 랜드마크 생성 (12개 포인트)

        Args:
            opening: 입 벌림 정도 (0=닫힘, 1=크게 벌림)
        """
        return np.array([
            [0, 0],             # [0] 61 - 좌측 끝
            [1, opening],       # [1] 37 - 상단1
            [2, opening],       # [2] 0  - 상단2 (윗입술 중앙)
            [3, opening],       # [3] 267 - 상단3
            [4, 0],             # [4] 270
            [5, 0],             # [5] 291 - 우측 끝
            [4, -opening],      # [6] 405
            [3, -opening],      # [7] 314 - 하단3
            [2, -opening],      # [8] 17  - 하단2 (아랫입술 중앙)
            [1, -opening],      # [9] 84  - 하단1
            [0.5, 0],           # [10] 181
            [0.25, 0],          # [11] 78
        ], dtype=np.float64)

    def test_closed_mouth(self):
        """입 다문 상태 - MAR이 임계값(0.6) 미만"""
        mouth = self._make_mouth(opening=0.1)
        mar = calculate_mar(mouth)
        self.assertLess(mar, 0.6)

    def test_yawning(self):
        """하품 상태 - MAR이 임계값(0.6) 이상"""
        mouth = self._make_mouth(opening=2.0)
        mar = calculate_mar(mouth)
        self.assertGreater(mar, 0.6)

    def test_mar_returns_float(self):
        """MAR은 항상 float 반환"""
        mouth = self._make_mouth(opening=0.5)
        mar = calculate_mar(mouth)
        self.assertIsInstance(mar, float)

    def test_mar_non_negative(self):
        """MAR은 항상 0 이상"""
        mouth = self._make_mouth(opening=0.0)
        mar = calculate_mar(mouth)
        self.assertGreaterEqual(mar, 0.0)


if __name__ == '__main__':
    unittest.main()
