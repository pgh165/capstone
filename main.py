"""
AI 기반 학습 피로 관리 시스템
메인 실행 파일

실행: python main.py
종료: 'q' 키 또는 Ctrl+C
"""

import sys
import time
import os
import select

# 헤드리스 모드 감지 (SSH 등 디스플레이 없는 환경)
HEADLESS = 'DISPLAY' not in os.environ and sys.platform != 'win32'
if HEADLESS:
    os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
    print('[system] 헤드리스 모드 (GUI 없음, q+Enter 또는 Ctrl+C로 종료)')


def _stdin_has_quit():
    """HEADLESS 모드에서 stdin을 비차단으로 확인해 q 입력 시 True 반환."""
    try:
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if ready:
            line = sys.stdin.readline()
            if line and line.strip().lower() in ('q', 'quit', 'exit'):
                return True
    except (ValueError, OSError):
        # stdin이 없거나(daemon 등) 오류 시 무시
        pass
    return False

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
from modules.calibration import EARCalibrator
from modules.head_pose import HeadPoseEstimator
from modules.judge import DrowsinessJudge
from modules.fatigue_manager import FatigueManager
from modules.recovery_guide import RecoveryGuide
from modules.llm_coach import LLMCoach
from modules.alert import AlertController
from modules.db_writer import DBWriter
from modules.voice import Voice
from modules.ai_judge import AIJudge
from modules.pomodoro import PomodoroTimer


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

    pomo = data.get('pomo_status', {})
    pomo_state = pomo.get('state', 'idle')
    if pomo_state == 'working':
        pomo_str = (f"Pomo: Work {pomo.get('elapsed_min',0):.0f}/"
                    f"{pomo.get('planned_min',0)}min (C{pomo.get('cycle',1)})")
    elif pomo_state == 'break':
        pomo_str = (f"Pomo: BREAK {pomo.get('remaining_min',0):.0f}min left")
    else:
        pomo_str = "Pomo: --"

    lines = [
        f"EAR: {data.get('ear', 0):.3f}  MAR: {data.get('mar', 0):.3f}",
        f"Head: P={data.get('pitch', 0):.1f} Y={data.get('yaw', 0):.1f}",
        f"Drowsiness: {data.get('drowsiness_score', 0)} (L{data.get('alert_level', 0)})",
        f"Fatigue: {data.get('fatigue_score', 0)} ({data.get('fatigue_level', '-')})",
        pomo_str,
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
    print("  AI 개인 맞춤형 포모도로 타이머")
    print(f"  모드: WSL 웹캠 직접 캡처")
    print("=" * 60)

    # 모듈 초기화
    camera = Camera()
    face_detector = FaceDetector()
    drowsiness_tracker = DrowsinessTracker()
    head_pose_estimator = HeadPoseEstimator()
    judge = DrowsinessJudge()
    fatigue_manager = FatigueManager()
    calibrator = EARCalibrator()
    recovery_guide = RecoveryGuide()
    voice = Voice()
    llm_coach = LLMCoach()
    ai_judge = AIJudge()
    alert_controller = AlertController(voice=voice)
    db_writer = DBWriter()
    pomodoro = PomodoroTimer()

    print("[main] 모든 모듈 초기화 완료")

    # Step 3: 시간대별 피로 패턴 로드
    hourly_pattern = db_writer.get_hourly_fatigue_pattern()
    if hourly_pattern:
        pomodoro.set_hourly_pattern({int(r["hour"]): float(r["avg_fatigue"]) for r in hourly_pattern})

    # Step 4: DB 기반 개인 최적 작업 인터벌 로드
    optimal = db_writer.get_optimal_work_interval()
    if optimal and optimal.get("cnt", 0) >= 5:
        # 피로 진입 전 평균 시간의 85%를 목표 인터벌로 설정
        target_min = max(10, int(optimal["avg_min"] * 0.85))
        pomodoro.set_personal_base_min(target_min)

    print("[main] 'q' 키를 눌러 종료")
    print()

    last_db_save = time.time()
    last_fatigue_log = time.time()
    last_status_write = time.time()
    frame_count = 0
    drowsiness_score = 0.0   # 첫 프레임 rule_score 참조 전 초기화
    _last_head_score = 0     # 얼굴 미검출 시 직전 head_score 유지용

    # 실시간 상태 공유 파일 경로 (Docker 볼륨 마운트 경로와 일치)
    STATUS_FILE = os.path.join(config.BASE_DIR, "data", "realtime_status.json")
    CMD_FILE    = os.path.join(config.BASE_DIR, "data", "cmd.json")

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
            head_score = _last_head_score  # 얼굴 미검출 시 직전 값 유지

            # 2. 얼굴 검출
            landmarks = face_detector.detect(frame)

            if landmarks is None:
                # 얼굴 미검출 — AI 판정 결과도 무효화
                ai_judge.reset()
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
                _last_head_score = head_score  # 다음 프레임 미검출 대비 저장

                # 랜드마크 그리기 (디버깅용)
                frame = face_detector.draw_landmarks(frame, landmarks)

                # 캘리브레이션 (세션 초반 30초)
                if not calibrator.done:
                    calibrator.update(ear_value, mar_value)
                    if calibrator.done:
                        drowsiness_tracker.set_thresholds(
                            calibrator.ear_threshold,
                            calibrator.mar_threshold,
                        )

                # AI 판정 요청 (비동기, 5초 주기) — 규칙 기반 점수를 앵커로 전달
                ai_judge.request({
                    "ear": ear_value,
                    "mar": mar_value,
                    "pitch": pitch,
                    "yaw": yaw,
                    "ear_closed_sec": drowsiness_tracker.get_ear_closed_seconds(),
                    "yawn_count": drowsiness_tracker.get_yawn_count(),
                }, rule_score=drowsiness_score)

            # 6. 종합 졸음 점수 산출 (얼굴 미검출 시 이전 점수 유지)
            if landmarks is not None:
                drowsiness_score = judge.calculate_drowsiness_score(
                    ear_score, mar_score, head_score
                )
            alert_level = judge.get_alert_level(drowsiness_score)

            # 7-1. AI 판정 결과 반영 (편차 30점 초과 시 절반만 반영)
            ai_result = ai_judge.latest()
            if ai_result:
                ai_score = float(ai_result["drowsiness"])
                if abs(ai_score - drowsiness_score) > 30:
                    # 규칙 기반과 너무 큰 차이 → 중간값으로 완화
                    drowsiness_score = round((drowsiness_score + ai_score) / 2, 1)
                else:
                    drowsiness_score = ai_score
                alert_level = judge.get_alert_level(drowsiness_score)

            # 얼굴 미검출 경고가 아닌 경우에만 졸음 기반 경고 (히스테리시스 적용)
            if landmarks is not None or not face_detector.is_no_face_alert():
                alert_controller.update(drowsiness_score, alert_level)

            # 8. 피로도 업데이트
            fatigue_manager.update(drowsiness_score, alert_level)
            fatigue_status = fatigue_manager.get_status()

            fatigue_level = fatigue_manager.get_fatigue_level()

            # 9. 포모도로 타이머 (AI 개인 맞춤형)
            # ── 최초 얼굴 감지 시 타이머 자동 시작
            if landmarks is not None and pomodoro.state == pomodoro.IDLE:
                start_ev = pomodoro.start(
                    fatigue_status['fatigue_score'], drowsiness_score
                )
                voice.speak(
                    f"포모도로 시작. {start_ev['planned_min']}분 집중해볼까요?"
                )

            # ── 작업 중: 휴식 필요 여부 확인
            if pomodoro.state == pomodoro.WORKING:
                pomo_ev = pomodoro.update(
                    fatigue_status['fatigue_score'], drowsiness_score, alert_level
                )
                if pomo_ev and pomo_ev['event'] == 'break_needed':
                    dominant_cause = fatigue_manager.get_dominant_cause()
                    guide_level = fatigue_level if fatigue_level != "good" else "caution"
                    guide_types = (fatigue_manager.get_recommended_guide()
                                   or ["eye_rest"])

                    # 가이드 콘솔 출력
                    recovery_guide.display_guides_for_level(
                        guide_level, guide_types, dominant_cause,
                    )

                    # 포모도로 휴식 전환
                    break_ev = pomodoro.start_break(
                        fatigue_level,
                        fatigue_status['fatigue_score'],
                        drowsiness_score,
                    )

                    # TTS 안내
                    forced = pomo_ev.get('forced', False)
                    tts_msg = (
                        f"{'위험 수준! ' if forced else ''}"
                        f"휴식 시간입니다. {break_ev['break_min']}분 쉬어갑니다."
                    )
                    voice.speak(tts_msg)

                    # LLM 개인화 코칭 요청
                    llm_coach.request_coaching({
                        "fatigue_level": fatigue_level,
                        "fatigue_score": fatigue_status['fatigue_score'],
                        "dominant_cause": dominant_cause,
                        "guide_types": guide_types,
                        "work_min": fatigue_status['continuous_work_min'],
                        "drowsy_count": fatigue_status['drowsy_count_30min'],
                        "recovery_history_summary": "",
                    })

                    # 피로 회복 적용
                    fatigue_manager.apply_recovery()

            # ── 휴식 중: 완료 감지
            elif pomodoro.state == pomodoro.BREAK:
                done_ev = pomodoro.update_break()
                if done_ev:
                    next_ev = pomodoro.start(
                        fatigue_status['fatigue_score'], drowsiness_score
                    )
                    voice.speak(
                        f"휴식 끝! {done_ev['cycle']}번째 사이클 완료. "
                        f"다음 작업은 {next_ev['planned_min']}분입니다."
                    )

            # 9-1. 커맨드 파일 폴링 (대시보드 → main.py 제어)
            try:
                if os.path.exists(CMD_FILE):
                    import json as _json2
                    with open(CMD_FILE) as _cf:
                        _cmd = _json2.load(_cf)
                    os.remove(CMD_FILE)
                    if _cmd.get("cmd") == "pomo_reset":
                        pomodoro.reset()
                        fatigue_manager.apply_recovery(
                            amount=fatigue_manager.fatigue_score  # 피로도 완전 초기화
                        )
                        judge._ema_score = None  # 졸음 EMA 초기화
                        drowsiness_score = 0.0
                        voice.speak("포모도로 타이머를 초기화했습니다.")
            except Exception:
                pass

            # 9-2. LLM 코칭 결과 폴링 (비동기 응답 도착 시 출력)
            llm_result = llm_coach.poll_result()
            if llm_result:
                llm_coach.display(llm_result)
                voice.speak(llm_result.get("text", ""))

            # 9-2. 실시간 상태 파일 갱신 (1초마다)
            if current_time - last_status_write >= 1.0:
                try:
                    import json as _json
                    _status = {
                        "ts": current_time,
                        "drowsiness_score": int(drowsiness_score),
                        "alert_level": alert_level,
                        "fatigue_score": int(fatigue_status["fatigue_score"]),
                        "fatigue_level": fatigue_status["fatigue_level"],
                        "perclos": round(drowsiness_tracker.get_perclos(), 1),
                        "yawn_count": drowsiness_tracker.get_yawn_count(),
                        "ear": round(ear_value, 3),
                        "mar": round(mar_value, 3),
                        "pitch": round(pitch, 1),
                        "yaw": round(yaw, 1),
                        "face_detected": landmarks is not None,
                        "pomo": pomodoro.get_status(),
                    }
                    with open(STATUS_FILE, "w") as _f:
                        _json.dump(_status, _f)
                    last_status_write = current_time
                except Exception:
                    pass

            # 10. DB 저장 (주기적)
            if current_time - last_db_save >= config.DB_SAVE_INTERVAL:
                detection_data = {
                    "ear_value": round(ear_value, 4),
                    "mar_value": round(mar_value, 4),
                    "head_pitch": round(pitch, 2),
                    "head_yaw": round(yaw, 2),
                    "drowsiness_score": int(drowsiness_score),
                    "alert_level": alert_level,
                }
                db_writer.save_detection(detection_data)

                # 피로도 로그 (30초마다)
                if current_time - last_fatigue_log >= 30:
                    fatigue_data = {
                        "fatigue_score": int(fatigue_status['fatigue_score']),
                        "continuous_work_min": int(fatigue_status['continuous_work_min']),
                        "drowsy_count_30min": fatigue_status['drowsy_count_30min'],
                        "fatigue_level": fatigue_status['fatigue_level'],
                    }
                    db_writer.save_fatigue(fatigue_data)
                    last_fatigue_log = current_time

                last_db_save = current_time

            # 11. 화면 표시
            pomo_status = pomodoro.get_status()
            display_data = {
                'ear': ear_value,
                'mar': mar_value,
                'pitch': pitch,
                'yaw': yaw,
                'drowsiness_score': int(drowsiness_score),
                'alert_level': alert_level,
                'fatigue_score': int(fatigue_status['fatigue_score']),
                'fatigue_level': fatigue_status['fatigue_level'],
                'pomo_status': pomo_status,
            }

            if HEADLESS:
                # 헤드리스: 콘솔에 상태 출력 (5초마다)
                if frame_count % (config.CAMERA_FPS * 5) == 0:
                    level_names = {0: '정상', 1: '주의', 2: '경고', 3: '위험'}
                    pomo_st = pomo_status.get('state', 'idle')
                    if pomo_st == 'working':
                        pomo_info = (f"작업 {pomo_status.get('elapsed_min',0):.0f}/"
                                     f"{pomo_status.get('planned_min',0)}분"
                                     f"(C{pomo_status.get('cycle',1)})")
                    elif pomo_st == 'break':
                        pomo_info = f"휴식 {pomo_status.get('remaining_min',0):.0f}분 남음"
                    else:
                        pomo_info = "대기"
                    print(f"[{time.strftime('%H:%M:%S')}] "
                          f"졸음={int(drowsiness_score)}(L{alert_level}-{level_names.get(alert_level,'?')}) "
                          f"피로={int(fatigue_status['fatigue_score'])}({fatigue_status['fatigue_level']}) "
                          f"🍅{pomo_info}")
                # stdin에서 q 입력 감지
                if _stdin_has_quit():
                    print("\n[main] 종료 요청 (stdin)")
                    break
                time.sleep(0.03)  # CPU 부하 방지
            else:
                # GUI 모드: 화면에 정보 오버레이
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
        # 실시간 상태 파일 삭제 (대시보드에 "연결 끊김" 표시)
        try:
            if os.path.exists(STATUS_FILE):
                os.remove(STATUS_FILE)
        except Exception:
            pass

        # 리소스 해제
        print("[main] 리소스 해제 중...")
        voice.stop()
        camera.release()
        face_detector.release()
        alert_controller.cleanup()
        db_writer.close()
        if not HEADLESS:
            cv2.destroyAllWindows()
        print("[main] 시스템 종료 완료")


if __name__ == '__main__':
    main()
