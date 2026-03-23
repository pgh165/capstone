"""EAR (Eye Aspect Ratio) 알고리즘 단위 테스트"""

import unittest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from modules.drowsiness import calculate_ear


class TestEAR(unittest.TestCase):
    """EAR 계산 함수 테스트"""

    def test_open_eye(self):
        """눈이 떠진 상태 - EAR이 임계값(0.2) 이상"""
        # P1(좌), P2(상1), P3(상2), P4(우), P5(하2), P6(하1)
        eye = np.array([
            [0, 0],    # P1 - 좌측 끝
            [1, 1],    # P2 - 상단1
            [2, 1],    # P3 - 상단2
            [3, 0],    # P4 - 우측 끝
            [2, -1],   # P5 - 하단2
            [1, -1],   # P6 - 하단1
        ], dtype=np.float64)
        ear = calculate_ear(eye)
        self.assertGreater(ear, 0.2, "열린 눈의 EAR은 0.2보다 커야 함")

    def test_closed_eye(self):
        """눈이 감긴 상태 - EAR이 임계값(0.2) 미만"""
        eye = np.array([
            [0, 0],      # P1
            [1, 0.05],   # P2 - 거의 가로선
            [2, 0.05],   # P3
            [3, 0],      # P4
            [2, -0.05],  # P5
            [1, -0.05],  # P6
        ], dtype=np.float64)
        ear = calculate_ear(eye)
        self.assertLess(ear, 0.2, "감긴 눈의 EAR은 0.2보다 작아야 함")

    def test_symmetric_eye(self):
        """대칭적인 눈 - 일관된 EAR 값"""
        eye = np.array([
            [0, 0],
            [1, 0.5],
            [2, 0.5],
            [3, 0],
            [2, -0.5],
            [1, -0.5],
        ], dtype=np.float64)
        ear = calculate_ear(eye)
        self.assertAlmostEqual(ear, 1.0 / 3.0, places=2)

    def test_zero_horizontal(self):
        """가로 거리가 0인 경우 0 반환"""
        eye = np.array([
            [1, 0], [1, 1], [1, 1],
            [1, 0], [1, -1], [1, -1],
        ], dtype=np.float64)
        ear = calculate_ear(eye)
        self.assertEqual(ear, 0.0)

    def test_ear_returns_float(self):
        """EAR은 항상 float 반환"""
        eye = np.array([
            [0, 0], [1, 1], [2, 1],
            [3, 0], [2, -1], [1, -1],
        ], dtype=np.float64)
        ear = calculate_ear(eye)
        self.assertIsInstance(ear, float)


if __name__ == '__main__':
    unittest.main()
