"""
피로 해소 가이드 모듈

data/guides.json에서 가이드 데이터를 로드하여
피로 단계에 맞는 해소 가이드를 제공한다.
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class RecoveryGuide:
    """피로 해소 가이드 데이터를 관리하고 출력하는 클래스."""

    # 지원하는 가이드 유형
    VALID_TYPES = [
        "eye_rest", "stretching", "breathing", "ventilation", "rest_break",
        "face_wash", "hydration", "posture_correction", "caffeine", "walk",
    ]

    def __init__(self):
        self._guides = {}
        self._load_guides()

    def _load_guides(self):
        """data/guides.json 파일에서 가이드 데이터를 로드한다."""
        guides_path = config.GUIDES_JSON_PATH

        try:
            with open(guides_path, "r", encoding="utf-8") as f:
                self._guides = json.load(f)
            print(f"[recovery_guide] 가이드 데이터 로드 완료 ({len(self._guides)}개)")
        except FileNotFoundError:
            print(f"[recovery_guide] 가이드 파일을 찾을 수 없습니다: {guides_path}")
            self._guides = {}
        except json.JSONDecodeError as e:
            print(f"[recovery_guide] 가이드 JSON 파싱 오류: {e}")
            self._guides = {}

    # ──────────────────────────────────────────────────────────────
    #  가이드 조회
    # ──────────────────────────────────────────────────────────────
    def get_guide(self, guide_type):
        """특정 유형의 가이드 콘텐츠를 반환한다.

        Args:
            guide_type (str): 가이드 유형
                ("eye_rest", "stretching", "breathing", "ventilation", "rest_break")

        Returns:
            dict: 가이드 콘텐츠 딕셔너리. 없으면 None.
        """
        return self._guides.get(guide_type, None)

    def get_guides_for_level(self, fatigue_level, guide_types=None):
        """피로 단계에 따라 적절한 가이드 목록을 반환한다.

        Args:
            fatigue_level (str): "good", "caution", "warning", "danger"
            guide_types (list[str], optional): 직접 지정할 가이드 유형 목록.
                지정하면 fatigue_level 기반 기본 매핑 대신 이 목록을 사용한다.

        Returns:
            list[dict]: 해당 단계에 맞는 가이드 딕셔너리 목록.
        """
        if fatigue_level == "good":
            return []

        if guide_types is None:
            # 하위 호환: guide_types 미지정 시 기본 매핑 사용
            if fatigue_level == "caution":
                guide_types = ["eye_rest", "ventilation"]
            elif fatigue_level == "warning":
                guide_types = ["stretching", "breathing", "ventilation"]
            elif fatigue_level == "danger":
                guide_types = ["rest_break", "stretching", "breathing",
                               "ventilation", "eye_rest"]
            else:
                return []

        guides = []
        for t in guide_types:
            guide = self.get_guide(t)
            if guide is not None:
                guides.append(guide)
        return guides

    # ──────────────────────────────────────────────────────────────
    #  콘솔 출력
    # ──────────────────────────────────────────────────────────────
    def display_guide(self, guide):
        """가이드 내용을 콘솔에 출력한다.

        Args:
            guide (dict): 가이드 콘텐츠 딕셔너리.
        """
        if guide is None:
            print("[recovery_guide] 출력할 가이드가 없습니다.")
            return

        print()
        print("=" * 50)
        print(f"  {guide.get('title', '피로 해소 가이드')}")
        print("=" * 50)
        print(f"  {guide.get('description', '')}")
        print()

        steps = guide.get("steps", [])
        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step}")

        duration = guide.get("duration_sec", 0)
        if duration > 0:
            minutes = duration // 60
            seconds = duration % 60
            if minutes > 0:
                print(f"\n  예상 소요 시간: {minutes}분 {seconds}초")
            else:
                print(f"\n  예상 소요 시간: {seconds}초")
        print("=" * 50)
        print()

    def display_guides_for_level(self, fatigue_level, guide_types=None,
                                dominant_cause=None):
        """피로 단계에 맞는 모든 가이드를 순서대로 출력한다.

        Args:
            fatigue_level (str): "good", "caution", "warning", "danger"
            guide_types (list[str], optional): 직접 지정할 가이드 유형 목록.
            dominant_cause (str, optional): 주된 피로 원인
                ("work", "drowsy", "env")
        """
        guides = self.get_guides_for_level(fatigue_level, guide_types)
        if not guides:
            return

        level_labels = {
            "caution": "주의",
            "warning": "경고",
            "danger": "위험",
        }
        cause_labels = {
            "work": "장시간 연속 작업",
            "drowsy": "졸음 빈번 감지",
            "env": "환경 스트레스(CO2/온도/습도)",
        }
        label = level_labels.get(fatigue_level, fatigue_level)
        print(f"\n[피로 해소 가이드] 현재 피로 단계: {label}")
        if dominant_cause:
            cause_label = cause_labels.get(dominant_cause, dominant_cause)
            print(f"  주요 원인: {cause_label}")
        print(f"  총 {len(guides)}개의 맞춤 가이드를 제공합니다.\n")

        for guide in guides:
            self.display_guide(guide)
