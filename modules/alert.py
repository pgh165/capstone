"""
GPIO 경고 출력 제어 모듈

졸음 경고 단계에 따라 RGB LED와 부저를 제어한다.
데스크탑 모드에서는 콘솔 출력으로 대체한다.
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class AlertController:
    """경고 단계에 따라 LED/부저를 제어하는 클래스."""

    # 경고 단계 라벨
    LEVEL_LABELS = {
        0: "정상 (녹색 LED)",
        1: "주의 (황색 LED + 짧은 알림음)",
        2: "경고 (적색 LED + 연속 부저)",
        3: "위험 (적색 LED 점멸 + 강한 연속 부저)",
    }

    def __init__(self):
        self._current_level = -1
        self._gpio_initialized = False
        self._buzzer_pwm = None
        self._blink_thread = None
        self._blink_running = False

        if not config.IS_DESKTOP:
            self._init_gpio()

    def _init_gpio(self):
        """라즈베리파이 GPIO를 초기화한다."""
        try:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # LED 핀 출력 설정
            GPIO.setup(config.GPIO_LED_RED, GPIO.OUT)
            GPIO.setup(config.GPIO_LED_GREEN, GPIO.OUT)
            GPIO.setup(config.GPIO_LED_BLUE, GPIO.OUT)

            # 부저 PWM 설정
            GPIO.setup(config.GPIO_BUZZER, GPIO.OUT)
            self._buzzer_pwm = GPIO.PWM(config.GPIO_BUZZER, 1000)  # 1kHz

            # 초기 상태: 모든 LED OFF
            GPIO.output(config.GPIO_LED_RED, GPIO.LOW)
            GPIO.output(config.GPIO_LED_GREEN, GPIO.LOW)
            GPIO.output(config.GPIO_LED_BLUE, GPIO.LOW)

            self._gpio_initialized = True
            print("[alert] GPIO 초기화 완료")
        except ImportError:
            print("[alert] RPi.GPIO 라이브러리를 찾을 수 없습니다.")
        except Exception as e:
            print(f"[alert] GPIO 초기화 실패: {e}")

    # ──────────────────────────────────────────────────────────────
    #  LED 제어 (내부)
    # ──────────────────────────────────────────────────────────────
    def _set_led(self, red, green, blue):
        """RGB LED 상태를 설정한다 (RPi 전용)."""
        if not self._gpio_initialized:
            return
        try:
            import RPi.GPIO as GPIO
            GPIO.output(config.GPIO_LED_RED, GPIO.HIGH if red else GPIO.LOW)
            GPIO.output(config.GPIO_LED_GREEN, GPIO.HIGH if green else GPIO.LOW)
            GPIO.output(config.GPIO_LED_BLUE, GPIO.HIGH if blue else GPIO.LOW)
        except Exception:
            pass

    def _all_led_off(self):
        """모든 LED를 끈다."""
        self._set_led(False, False, False)

    # ──────────────────────────────────────────────────────────────
    #  부저 제어 (내부)
    # ──────────────────────────────────────────────────────────────
    def _buzzer_on(self, frequency=1000, duty=50):
        """부저를 켠다."""
        if self._buzzer_pwm is not None:
            try:
                self._buzzer_pwm.ChangeFrequency(frequency)
                self._buzzer_pwm.start(duty)
            except Exception:
                pass

    def _buzzer_off(self):
        """부저를 끈다."""
        if self._buzzer_pwm is not None:
            try:
                self._buzzer_pwm.stop()
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────
    #  LED 점멸 스레드 (3단계용)
    # ──────────────────────────────────────────────────────────────
    def _stop_blink(self):
        """점멸 스레드를 중지한다."""
        self._blink_running = False
        if self._blink_thread is not None:
            self._blink_thread.join(timeout=1.0)
            self._blink_thread = None

    def _start_blink(self):
        """적색 LED 점멸 스레드를 시작한다."""
        self._stop_blink()
        self._blink_running = True
        self._blink_thread = threading.Thread(target=self._blink_loop, daemon=True)
        self._blink_thread.start()

    def _blink_loop(self):
        """적색 LED를 0.3초 간격으로 점멸한다."""
        while self._blink_running:
            self._set_led(True, False, False)
            time.sleep(0.3)
            if not self._blink_running:
                break
            self._set_led(False, False, False)
            time.sleep(0.3)

    # ──────────────────────────────────────────────────────────────
    #  경고 단계 설정 (메인 인터페이스)
    # ──────────────────────────────────────────────────────────────
    def set_alert_level(self, level):
        """경고 단계를 설정하고 LED/부저를 제어한다.

        Args:
            level (int): 0(정상), 1(주의), 2(경고), 3(위험).
        """
        # 같은 단계면 중복 처리하지 않음
        if level == self._current_level:
            return

        self._current_level = level

        if config.IS_DESKTOP:
            self._set_alert_desktop(level)
        else:
            self._set_alert_gpio(level)

    def _set_alert_desktop(self, level):
        """데스크탑 모드: 콘솔에 경고 상태를 출력한다."""
        label = self.LEVEL_LABELS.get(level, f"알 수 없는 단계 ({level})")

        if level == 0:
            print(f"[ALERT] Level 0: {label}")
        elif level == 1:
            print(f"[ALERT] Level 1: {label}")
        elif level == 2:
            print(f"[ALERT] Level 2: {label}")
        elif level == 3:
            print(f"[ALERT] Level 3: {label}")

    def _set_alert_gpio(self, level):
        """라즈베리파이 모드: GPIO로 LED/부저를 제어한다."""
        # 이전 상태 정리
        self._stop_blink()
        self._buzzer_off()
        self._all_led_off()

        if level == 0:
            # 정상: 녹색 LED, 부저 없음
            self._set_led(False, True, False)

        elif level == 1:
            # 주의: 황색 LED (적+녹), 짧은 비프
            self._set_led(True, True, False)
            self._short_beep()

        elif level == 2:
            # 경고: 적색 LED, 연속 부저
            self._set_led(True, False, False)
            self._buzzer_on(frequency=1000, duty=50)

        elif level == 3:
            # 위험: 적색 LED 점멸, 강한 연속 부저
            self._start_blink()
            self._buzzer_on(frequency=2000, duty=80)

    def _short_beep(self, duration=0.2):
        """짧은 비프음을 낸다 (별도 스레드에서 실행하여 메인 루프 블로킹 방지)."""
        def _beep():
            self._buzzer_on(frequency=1000, duty=50)
            time.sleep(duration)
            self._buzzer_off()
        threading.Thread(target=_beep, daemon=True).start()

    # ──────────────────────────────────────────────────────────────
    #  정리
    # ──────────────────────────────────────────────────────────────
    def cleanup(self):
        """GPIO 자원을 해제한다."""
        self._stop_blink()
        self._buzzer_off()

        if self._gpio_initialized:
            try:
                import RPi.GPIO as GPIO
                self._all_led_off()
                GPIO.cleanup()
                print("[alert] GPIO 정리 완료")
            except Exception:
                pass

        self._gpio_initialized = False
        self._current_level = -1
