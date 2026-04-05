"""
환경 센서 모듈 - MH-Z19B (CO2) + DHT22 (온습도)

데스크탑 모드에서는 더미 데이터를 반환하고,
라즈베리파이 모드에서는 UART와 GPIO를 통해 실제 센서값을 읽는다.
"""

import sys
import os
import time

# 프로젝트 루트를 sys.path에 추가하여 config 임포트 가능하게 함
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class EnvironmentSensor:
    """CO2 (MH-Z19B) 및 온습도 (DHT22) 센서를 관리하는 클래스."""

    # MH-Z19B 읽기 명령 (9바이트 고정 프로토콜)
    MHZ19_READ_CMD = bytes([0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79])

    # 센서 데이터 캐싱 간격 (초) - 환경 데이터는 느리게 변하므로 매 프레임 읽을 필요 없음
    _CACHE_INTERVAL = 5.0

    def __init__(self):
        self._serial = None
        self._dht_sensor = None
        self._dht_pin = config.GPIO_DHT

        # read_all 캐시
        self._cache = None
        self._cache_time = 0

        if not config.IS_DESKTOP:
            self._init_hardware()

    def _init_hardware(self):
        """라즈베리파이 환경에서 시리얼 포트와 DHT 센서를 초기화한다."""
        # MH-Z19B UART 초기화
        try:
            import serial
            self._serial = serial.Serial(
                port="/dev/ttyAMA0",
                baudrate=config.CO2_BAUD_RATE if hasattr(config, "CO2_BAUD_RATE") else 9600,
                timeout=1.0,
            )
            print("[env_sensor] MH-Z19B UART 초기화 완료")
        except Exception as e:
            print(f"[env_sensor] MH-Z19B 초기화 실패: {e}")
            self._serial = None

        # DHT22 라이브러리 로드
        try:
            import Adafruit_DHT
            self._dht_sensor = Adafruit_DHT.DHT22
            print("[env_sensor] DHT22 초기화 완료")
        except ImportError:
            print("[env_sensor] Adafruit_DHT 라이브러리를 찾을 수 없습니다.")
            self._dht_sensor = None

    # ──────────────────────────────────────────────────────────────
    #  CO2 읽기
    # ──────────────────────────────────────────────────────────────
    def read_co2(self):
        """CO2 농도를 ppm 단위로 반환한다.

        Returns:
            int: CO2 ppm 값. 읽기 실패 시 -1.
        """
        if config.IS_DESKTOP:
            return config.DUMMY_CO2

        if self._serial is None:
            return -1

        try:
            # 버퍼 비우기
            self._serial.flushInput()
            self._serial.write(self.MHZ19_READ_CMD)
            response = self._serial.read(9)

            if len(response) == 9 and response[0] == 0xFF and response[1] == 0x86:
                # 체크섬 검증
                checksum = (~(sum(response[1:8]) & 0xFF) + 1) & 0xFF
                if checksum == response[8]:
                    co2 = response[2] * 256 + response[3]
                    return co2
                else:
                    print("[env_sensor] CO2 체크섬 오류")
                    return -1
            else:
                print("[env_sensor] CO2 응답 형식 오류")
                return -1
        except Exception as e:
            print(f"[env_sensor] CO2 읽기 실패: {e}")
            return -1

    # ──────────────────────────────────────────────────────────────
    #  온습도 읽기
    # ──────────────────────────────────────────────────────────────
    def read_temperature_humidity(self):
        """온도(C)와 습도(%RH)를 튜플로 반환한다.

        Returns:
            tuple: (temperature, humidity). 읽기 실패 시 (None, None).
        """
        if config.IS_DESKTOP:
            return (config.DUMMY_TEMPERATURE, config.DUMMY_HUMIDITY)

        if self._dht_sensor is None:
            return (None, None)

        try:
            import Adafruit_DHT
            humidity, temperature = Adafruit_DHT.read_retry(
                self._dht_sensor, self._dht_pin
            )
            if humidity is not None and temperature is not None:
                return (round(temperature, 1), round(humidity, 1))
            else:
                print("[env_sensor] DHT22 읽기 실패 (None)")
                return (None, None)
        except Exception as e:
            print(f"[env_sensor] DHT22 읽기 오류: {e}")
            return (None, None)

    # ──────────────────────────────────────────────────────────────
    #  전체 센서 데이터 읽기
    # ──────────────────────────────────────────────────────────────
    def read_all(self):
        """CO2, 온도, 습도를 한 번에 읽어 딕셔너리로 반환한다.

        캐시된 데이터가 _CACHE_INTERVAL 이내이면 캐시를 반환하여
        불필요한 센서 I/O를 줄인다.

        Returns:
            dict: {"co2": int, "temperature": float, "humidity": float}
        """
        now = time.time()
        if self._cache is not None and (now - self._cache_time) < self._CACHE_INTERVAL:
            return self._cache

        co2 = self.read_co2()
        temperature, humidity = self.read_temperature_humidity()
        self._cache = {
            "co2": co2,
            "temperature": temperature,
            "humidity": humidity,
        }
        self._cache_time = now
        return self._cache

    def cleanup(self):
        """시리얼 포트를 닫는다."""
        if self._serial is not None:
            try:
                self._serial.close()
                print("[env_sensor] 시리얼 포트 닫기 완료")
            except Exception:
                pass
