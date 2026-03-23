"""
AIoT 기반 졸음 및 집중력 저하 방지 시스템
메인 실행 파일

실행: python main.py
종료: 'q' 키 또는 Ctrl+C
"""

import sys
import time
import os

# Windows 환경 한글 출력 설정
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import cv2
import numpy as np

import config
from modules.camera import Camera
from modules.face_detector import FaceDetector
from modules.drowsiness import calculate_ear, calculate_mar, DrowsinessTracker
from modules.head_pose import HeadPoseEstimator
from modules.env_sensor import EnvironmentSensor
from modules.judge import DrowsinessJudge
from modules.fatigue_manager import FatigueManager
from modules.recovery_guide import RecoveryGuide
from modules.alert import AlertController
from modules.db_writer import DBWriter


def draw_info(frame, data):
    """프레임에 상태 정보 오버레이"""
    h, w = frame.shape[:2]
    overlay = frame.copy()

    # 반투명 배경
    cv2.rectangle(overlay, (0, 0), (320, 200), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # 텍스트 정보
    y = 20
    line_height = 22
    color = (255, 255, 255)
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.5

    lines = [
        f"EAR: {data.get('ear', 0):.3f}  MAR: {data.get('mar', 0):.3f}",
        f"Head: P={data.get('pitch', 0):.1f} Y={data.get('yaw', 0):.1f}",
        f"Drowsiness: {data.get('drowsiness_score', 0)} (L{data.get('alert_level', 0)})",
        f"Fatigue: {data.get('fatigue_score', 0)} ({data.get('fatigue_level', '-')})",
        f"CO2: {data.get('co2', 0)}ppm  T: {data.get('temp', 0)}C  H: {data.get('humid', 0)}%",
        f"Env Score: {data.get('env_score', 0)}",
        f"Work: {data.get('work_min', 0)}min  Drowsy: {data.get('drowsy_count', 0)}",
    ]

    for line in lines:
        cv2.putText(frame, line, (10, y), font, scale, color, 1)
        y += line_height

    # 경고 단계 표시 (우측 상단)
    alert_level = data.get('alert_level', 0)
    alert_colors = {
        0: ((0, 200, 0), "NORMAL"),
        1: ((0, 200, 200), "CAUTION"),
        2: ((0, 100, 255), "WARNING"),
        3: ((0, 0, 255), "DANGER"),
    }
    color_bgr, label = alert_colors.get(alert_level, ((200, 200, 200), "UNKNOWN"))
    cv2.putText(frame, label, (w - 150, 30), font, 0.7, color_bgr, 2)

    return frame


def main():
    print("=" * 60)
    print("  AIoT 기반 졸음 및 집중력 저하 방지 시스템")
    print(f"  모드: {'데스크탑 (웹캠)' if config.IS_DESKTOP else '라즈베리파이'}")
    print("=" * 60)

    # 모듈 초기화
    camera = Camera()
    face_detector = FaceDetector()
    drowsiness_tracker = DrowsinessTracker()
    head_pose_estimator = HeadPoseEstimator()
    env_sensor = EnvironmentSensor()
    judge = DrowsinessJudge()
    fatigue_manager = FatigueManager()
    recovery_guide = RecoveryGuide()
    alert_controller = AlertController()
    db_writer = DBWriter()

    print("[main] 모든 모듈 초기화 완료")
    print("[main] 'q' 키를 눌러 종료")
    print()

    last_db_save = time.time()
    last_fatigue_log = time.time()
    frame_count = 0

    try:
        while True:
            # 1. 프레임 캡처
            ret, frame = camera.read_frame()
            if not ret or frame is None:
                print("[main] 프레임 캡처 실패")
                time.sleep(0.1)
                continue

            frame_count += 1
            current_time = time.time()

            # 기본 데이터 초기화
            ear_value = 0.0
            mar_value = 0.0
            pitch, yaw, roll = 0.0, 0.0, 0.0
            ear_score = 0
            mar_score = 0
            head_score = 0

            # 2. 얼굴 검출
            landmarks = face_detector.detect(frame)

            if landmarks is None:
                # 얼굴 미검출
                if face_detector.is_no_face_alert():
                    alert_controller.set_alert_level(3)
            else:
                # 3. EAR 계산 (눈 감김)
                left_eye, right_eye = face_detector.get_eye_landmarks(landmarks, frame.shape)
                ear_left = calculate_ear(left_eye)
                ear_right = calculate_ear(right_eye)
                ear_value = (ear_left + ear_right) / 2.0

                drowsiness_tracker.update_ear(ear_value)
                ear_score = drowsiness_tracker.get_ear_score()

                # 4. MAR 계산 (하품)
                mouth = face_detector.get_mouth_landmarks(landmarks, frame.shape)
                mar_value = calculate_mar(mouth)

                drowsiness_tracker.update_mar(mar_value)
                mar_score = drowsiness_tracker.get_mar_score()

                # 5. Head Pose 추정
                face_points = face_detector.get_head_pose_points(landmarks, frame.shape)
                pitch, yaw, roll = head_pose_estimator.estimate(face_points, frame.shape)
                head_score = head_pose_estimator.get_head_score(pitch, yaw, roll)

                # 랜드마크 그리기 (디버깅용)
                frame = face_detector.draw_landmarks(frame, landmarks)

            # 6. 환경 센서 읽기
            env_data = env_sensor.read_all()
            env_score = judge.calculate_env_score(
                env_data['co2'],
                env_data['temperature'],
                env_data['humidity']
            )

            # 7. 종합 졸음 점수 산출
            drowsiness_score = judge.calculate_drowsiness_score(
                ear_score, mar_score, head_score, env_score
            )
            alert_level = judge.get_alert_level(drowsiness_score)

            # 얼굴 미검출 경고가 아닌 경우에만 졸음 기반 경고
            if landmarks is not None or not face_detector.is_no_face_alert():
                alert_controller.set_alert_level(alert_level)

            # 8. 피로도 업데이트
            fatigue_manager.update(drowsiness_score, alert_level, env_data)
            fatigue_status = fatigue_manager.get_status()

            # 9. 피로 해소 가이드 제공
            fatigue_level = fatigue_manager.get_fatigue_level()
            if fatigue_level != "good":
                guide_types = fatigue_manager.get_recommended_guide()
                if guide_types:
                    # 5분에 한 번만 가이드 출력 (콘솔 스팸 방지)
                    if not hasattr(main, '_last_guide_time') or \
                       current_time - main._last_guide_time > 300:
                        recovery_guide.display_guides_for_level(fatigue_level)
                        main._last_guide_time = current_time

            # 10. DB 저장 (주기적)
            if current_time - last_db_save >= config.DB_SAVE_INTERVAL:
                detection_data = {
                    "ear_value": round(ear_value, 4),
                    "mar_value": round(mar_value, 4),
                    "head_pitch": round(pitch, 2),
                    "head_yaw": round(yaw, 2),
                    "drowsiness_score": int(drowsiness_score),
                    "alert_level": alert_level,
                    "co2_ppm": env_data['co2'],
                    "temperature": env_data['temperature'],
                    "humidity": env_data['humidity'],
                    "env_score": int(env_score),
                }
                db_writer.save_detection(detection_data)

                # 피로도 로그 (30초마다)
                if current_time - last_fatigue_log >= 30:
                    fatigue_data = {
                        "fatigue_score": int(fatigue_status['fatigue_score']),
                        "continuous_work_min": int(fatigue_status['continuous_work_min']),
                        "drowsy_count_30min": fatigue_status['drowsy_count_30min'],
                        "env_stress_score": int(fatigue_status['env_stress_score']),
                        "fatigue_level": fatigue_status['fatigue_level'],
                    }
                    db_writer.save_fatigue(fatigue_data)
                    last_fatigue_log = current_time

                last_db_save = current_time

            # 11. 화면 표시
            display_data = {
                'ear': ear_value,
                'mar': mar_value,
                'pitch': pitch,
                'yaw': yaw,
                'drowsiness_score': int(drowsiness_score),
                'alert_level': alert_level,
                'fatigue_score': int(fatigue_status['fatigue_score']),
                'fatigue_level': fatigue_status['fatigue_level'],
                'co2': env_data['co2'],
                'temp': env_data['temperature'],
                'humid': env_data['humidity'],
                'env_score': int(env_score),
                'work_min': int(fatigue_status['continuous_work_min']),
                'drowsy_count': fatigue_status['drowsy_count_30min'],
            }
            frame = draw_info(frame, display_data)

            cv2.imshow('Drowsiness Detection', frame)

            # 종료 키
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # 'q' 또는 ESC
                print("\n[main] 종료 요청")
                break

    except KeyboardInterrupt:
        print("\n[main] Ctrl+C 감지 - 종료")

    finally:
        # 리소스 해제
        print("[main] 리소스 해제 중...")
        camera.release()
        face_detector.release()
        env_sensor.cleanup()
        alert_controller.cleanup()
        db_writer.close()
        cv2.destroyAllWindows()
        print("[main] 시스템 종료 완료")


if __name__ == '__main__':
    main()
