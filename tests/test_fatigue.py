"""피로도 관리 모듈 단위 테스트"""

import unittest
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from modules.fatigue_manager import FatigueManager, RecoverySession, RecoveryProfile


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
        """주의 상태 - 기본(eye_rest) + 원인별 맞춤 가이드"""
        self.fm._fatigue_score = 50
        guides = self.fm.get_recommended_guide()
        # 기본 가이드는 항상 포함
        self.assertIn("eye_rest", guides)
        # 원인별 가이드가 추가됨 (work/drowsy/env 중 하나)
        self.assertGreater(len(guides), 1)

    def test_recommended_guide_danger(self):
        """위험 상태 - 기본(rest_break, stretching, eye_rest) + 원인별 가이드"""
        self.fm._fatigue_score = 90
        guides = self.fm.get_recommended_guide()
        self.assertIn("rest_break", guides)
        self.assertIn("stretching", guides)
        self.assertIn("eye_rest", guides)
        # 기본 3개 + 원인별 최소 2개
        self.assertGreaterEqual(len(guides), 5)

    def test_dominant_cause_work(self):
        """연속 작업이 주 원인일 때 work 반환"""
        # 작업 시작 시간을 2시간 전으로 설정
        self.fm._work_start_time = time.time() - 7200
        cause = self.fm.get_dominant_cause()
        self.assertEqual(cause, "work")

    def test_dominant_cause_drowsy(self):
        """졸음 빈도가 주 원인일 때 drowsy 반환"""
        now = time.time()
        # 30분 내 졸음 이벤트 15개 추가
        for i in range(15):
            self.fm._drowsiness_events.append(now - i * 10)
        cause = self.fm.get_dominant_cause()
        self.assertEqual(cause, "drowsy")

    def test_dominant_cause_env(self):
        """환경 스트레스가 주 원인일 때 env 반환"""
        # CO2 스트레스가 20분(1200초) 전부터 지속
        self.fm._co2_stress_start = time.time() - 1200
        cause = self.fm.get_dominant_cause()
        self.assertEqual(cause, "env")

    def test_guide_includes_cause_specific(self):
        """원인별 맞춤 가이드가 포함되는지 확인"""
        self.fm._fatigue_score = 75  # warning 단계
        # 졸음이 주 원인이 되도록 설정
        now = time.time()
        for i in range(20):
            self.fm._drowsiness_events.append(now - i * 10)
        guides = self.fm.get_recommended_guide()
        # drowsy 원인 → face_wash, breathing, caffeine 중 포함
        self.assertTrue(
            any(g in guides for g in ["face_wash", "breathing", "caffeine"]),
        )

    def test_get_status(self):
        """상태 딕셔너리 반환"""
        status = self.fm.get_status()
        self.assertIn("fatigue_score", status)
        self.assertIn("fatigue_level", status)
        self.assertIn("continuous_work_min", status)
        self.assertIn("drowsy_count_30min", status)
        self.assertIn("env_stress_score", status)


class TestRecoverySession(unittest.TestCase):
    """RecoverySession 회복 효과 검증 테스트"""

    def test_session_phase_flow(self):
        """recovering → evaluating → done 단계 전환"""
        session = RecoverySession(
            guide_types=["eye_rest"],
            fatigue_before=60,
            drowsiness_before=50,
            duration_sec=0,  # 즉시 평가 시작
        )
        now = time.time()
        # 즉시 evaluating으로 전환
        phase = session.update(now + 0.1, 20, 0.3, 0.2)
        self.assertEqual(phase, "evaluating")

        # 평가 샘플 충분히 수집
        for i in range(config.RECOVERY_EVAL_MIN_SAMPLES):
            session.update(
                now + config.RECOVERY_EVAL_DURATION + 1 + i * 0.1,
                20, 0.3, 0.2,
            )
        self.assertEqual(session.phase, "done")

    def test_effective_recovery_low_drowsiness(self):
        """졸음 점수가 기준 이하면 회복 성공"""
        session = RecoverySession(
            guide_types=["eye_rest"],
            fatigue_before=60,
            drowsiness_before=50,
            duration_sec=0,
        )
        now = time.time()
        # evaluating 진입
        session.update(now + 0.1, 20, 0.3, 0.2)
        # 충분한 샘플 수집 (졸음 점수 20 = 기준 30 이하)
        for i in range(config.RECOVERY_EVAL_MIN_SAMPLES):
            session.update(
                now + config.RECOVERY_EVAL_DURATION + 1 + i * 0.1,
                20, 0.3, 0.2,
            )
        result = session.get_result(fatigue_after=55)
        self.assertTrue(result["effective"])

    def test_effective_recovery_fatigue_drop(self):
        """피로도가 충분히 하락하면 회복 성공"""
        session = RecoverySession(
            guide_types=["rest_break"],
            fatigue_before=70,
            drowsiness_before=60,
            duration_sec=0,
        )
        now = time.time()
        session.update(now + 0.1, 50, 0.25, 0.3)
        for i in range(config.RECOVERY_EVAL_MIN_SAMPLES):
            session.update(
                now + config.RECOVERY_EVAL_DURATION + 1 + i * 0.1,
                50, 0.25, 0.3,
            )
        # 피로도 70 → 55 (15점 하락 ≥ 10점 기준)
        result = session.get_result(fatigue_after=55)
        self.assertTrue(result["effective"])
        self.assertGreaterEqual(result["fatigue_drop"], 10)

    def test_ineffective_recovery(self):
        """졸음 점수 높고 피로도 하락 부족 → 회복 실패"""
        session = RecoverySession(
            guide_types=["breathing"],
            fatigue_before=60,
            drowsiness_before=55,
            duration_sec=0,
        )
        now = time.time()
        session.update(now + 0.1, 50, 0.2, 0.3)
        for i in range(config.RECOVERY_EVAL_MIN_SAMPLES):
            session.update(
                now + config.RECOVERY_EVAL_DURATION + 1 + i * 0.1,
                50, 0.2, 0.3,
            )
        # 피로도 60 → 58 (2점 하락 < 10), 졸음 50 > 30
        result = session.get_result(fatigue_after=58)
        self.assertFalse(result["effective"])

    def test_result_contains_metrics(self):
        """결과 딕셔너리에 필수 필드가 포함되는지 확인"""
        session = RecoverySession(
            guide_types=["eye_rest", "hydration"],
            fatigue_before=50,
            drowsiness_before=40,
            duration_sec=0,
        )
        now = time.time()
        session.update(now + 0.1, 15, 0.3, 0.1)
        for i in range(config.RECOVERY_EVAL_MIN_SAMPLES):
            session.update(
                now + config.RECOVERY_EVAL_DURATION + 1 + i * 0.1,
                15, 0.3, 0.1,
            )
        result = session.get_result(fatigue_after=40)
        for key in ("effective", "reason", "fatigue_before", "fatigue_after",
                     "fatigue_drop", "drowsiness_before", "drowsiness_after",
                     "drowsiness_drop", "avg_ear", "avg_mar", "eval_samples",
                     "guide_types", "duration_sec"):
            self.assertIn(key, result)


class TestFatigueManagerRecovery(unittest.TestCase):
    """FatigueManager 회복 세션 관리 테스트"""

    def setUp(self):
        self.fm = FatigueManager()

    def test_no_active_recovery_initially(self):
        """초기 상태에서 회복 세션 없음"""
        self.assertFalse(self.fm.has_active_recovery)

    def test_start_recovery_session(self):
        """회복 세션 시작"""
        self.fm._fatigue_score = 60
        self.fm.start_recovery_session(["eye_rest"], 50, 60)
        self.assertTrue(self.fm.has_active_recovery)

    def test_update_recovery_returns_phase(self):
        """세션 진행 중 phase 반환"""
        self.fm._fatigue_score = 60
        self.fm.start_recovery_session(["eye_rest"], 50, 9999)
        result = self.fm.update_recovery_session(40, 0.3, 0.2)
        self.assertIsNotNone(result)
        self.assertEqual(result["phase"], "recovering")

    def test_no_session_returns_none(self):
        """세션 없을 때 None 반환"""
        result = self.fm.update_recovery_session(30, 0.3, 0.2)
        self.assertIsNone(result)

    def test_completed_session_clears(self):
        """완료된 세션은 자동 정리됨"""
        self.fm._fatigue_score = 60
        self.fm.start_recovery_session(["eye_rest"], 50, 0)
        now = time.time()
        # 평가 단계까지 진행
        self.fm.update_recovery_session(20, 0.3, 0.2)
        # 충분한 샘플 수집을 위해 시간 조작
        session = self.fm._recovery_session
        session._eval_start_time = now - config.RECOVERY_EVAL_DURATION - 1
        for _ in range(config.RECOVERY_EVAL_MIN_SAMPLES - 1):
            session._eval_samples.append({"drowsiness": 20, "ear": 0.3, "mar": 0.2})
        result = self.fm.update_recovery_session(20, 0.3, 0.2)
        self.assertIn("effective", result)
        self.assertFalse(self.fm.has_active_recovery)


class TestRecoveryProfile(unittest.TestCase):
    """RecoveryProfile 개인화 테스트"""

    def _make_history(self, guide_type, effective_count, total_count):
        """테스트용 회복 이력을 생성한다."""
        records = []
        for i in range(total_count):
            records.append({
                "guide_type": guide_type,
                "effective": 1 if i < effective_count else 0,
            })
        return records

    def test_success_rate_calculation(self):
        """성공률 계산 확인"""
        profile = RecoveryProfile()
        # eye_rest: 4/5 = 0.8
        history = self._make_history("eye_rest", 4, 5)
        profile.load_from_history(history)
        rate = profile.get_success_rate("eye_rest")
        self.assertAlmostEqual(rate, 0.8)

    def test_insufficient_data_returns_none(self):
        """데이터 부족 시 None 반환"""
        profile = RecoveryProfile()
        history = self._make_history("eye_rest", 1, 2)
        profile.load_from_history(history)
        self.assertIsNone(profile.get_success_rate("eye_rest"))

    def test_rank_guides_sorts_by_effectiveness(self):
        """효과순 정렬 확인"""
        profile = RecoveryProfile()
        # breathing: 90% 성공, hydration: 40% 성공
        history = (
            self._make_history("breathing", 9, 10)
            + self._make_history("hydration", 2, 5)
        )
        profile.load_from_history(history)
        result = profile.rank_guides(["eye_rest"], ["hydration", "breathing"])
        # breathing(90%)이 hydration(40%)보다 앞에 위치
        self.assertEqual(result[0], "eye_rest")  # base 유지
        bi = result.index("breathing")
        hi = result.index("hydration")
        self.assertLess(bi, hi)

    def test_rank_guides_excludes_low_effectiveness(self):
        """성공률 30% 미만 가이드 제외"""
        profile = RecoveryProfile()
        # caffeine: 1/5 = 20% → 제외 대상
        history = self._make_history("caffeine", 1, 5)
        profile.load_from_history(history)
        result = profile.rank_guides(["eye_rest"], ["caffeine", "breathing"])
        self.assertNotIn("caffeine", result)

    def test_rank_guides_adds_bonus_high_rate(self):
        """성공률 70% 이상 가이드 보너스 추천"""
        profile = RecoveryProfile()
        # walk: 80% 성공 (원래 추천 목록에 없어도 추가)
        history = self._make_history("walk", 4, 5)
        profile.load_from_history(history)
        result = profile.rank_guides(["eye_rest"], ["breathing"])
        self.assertIn("walk", result)

    def test_comma_separated_guide_types(self):
        """쉼표 구분된 guide_type 파싱"""
        profile = RecoveryProfile()
        history = [
            {"guide_type": "eye_rest,breathing", "effective": 1},
            {"guide_type": "eye_rest,breathing", "effective": 1},
            {"guide_type": "eye_rest,breathing", "effective": 1},
        ]
        profile.load_from_history(history)
        self.assertAlmostEqual(profile.get_success_rate("eye_rest"), 1.0)
        self.assertAlmostEqual(profile.get_success_rate("breathing"), 1.0)

    def test_has_data(self):
        """데이터 충분 여부 판별"""
        profile = RecoveryProfile()
        self.assertFalse(profile.has_data)
        history = self._make_history("eye_rest", 3, 3)
        profile.load_from_history(history)
        self.assertTrue(profile.has_data)


class TestFatigueManagerPersonalization(unittest.TestCase):
    """FatigueManager 개인화 가이드 추천 테스트"""

    def setUp(self):
        self.fm = FatigueManager()

    def _make_history(self, guide_type, effective_count, total_count):
        records = []
        for i in range(total_count):
            records.append({
                "guide_type": guide_type,
                "effective": 1 if i < effective_count else 0,
            })
        return records

    def test_personalized_guide_prefers_effective(self):
        """개인화 시 효과 높은 가이드 우선 추천"""
        self.fm._fatigue_score = 75  # warning 단계
        # breathing이 가장 효과적이도록 이력 설정
        history = (
            self._make_history("breathing", 9, 10)  # 90%
            + self._make_history("face_wash", 2, 5)  # 40%
        )
        self.fm.load_recovery_profile(history)
        guides = self.fm.get_recommended_guide()
        # breathing이 face_wash보다 앞에 있어야 함
        if "breathing" in guides and "face_wash" in guides:
            self.assertLess(
                guides.index("breathing"),
                guides.index("face_wash"),
            )

    def test_default_guide_without_profile(self):
        """프로필 없으면 기본 순서 유지"""
        self.fm._fatigue_score = 50  # caution 단계
        guides = self.fm.get_recommended_guide()
        self.assertIn("eye_rest", guides)
        self.assertGreater(len(guides), 1)


if __name__ == '__main__':
    unittest.main()
