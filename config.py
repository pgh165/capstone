"""
AIoT 기반 졸음 및 집중력 저하 방지 시스템 - 설정 파일
"""

# ──────────────────────────────────────────────
# 실행 모드 (데스크탑 개발 / 라즈베리파이)
# ──────────────────────────────────────────────
IS_DESKTOP = True  # True: 웹캠 + 더미 센서, False: Pi Camera + 실제 센서

# ──────────────────────────────────────────────
# 카메라 설정
# ──────────────────────────────────────────────
CAMERA_INDEX = 0          # 웹캠 인덱스 (데스크탑)
CAMERA_URL = ""           # 비어있지 않으면 인덱스 대신 MJPEG/RTSP URL 사용
                          # 예) "http://172.20.224.1:8080/video"  (Windows MJPEG 브릿지)
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# ──────────────────────────────────────────────
# EAR (Eye Aspect Ratio) 설정
# ──────────────────────────────────────────────
EAR_THRESHOLD = 0.2       # 이 값 미만이면 눈 감김 판정
EAR_CONSEC_SECONDS = 2.0  # 연속 눈 감김 지속시간 임계값 (초)

# ──────────────────────────────────────────────
# MAR (Mouth Aspect Ratio) 설정
# ──────────────────────────────────────────────
MAR_THRESHOLD = 0.6       # 이 값 이상이면 하품 판정
YAWN_COUNT_THRESHOLD = 3  # 3분 내 이 횟수 이상이면 졸음 전조
YAWN_WINDOW_SECONDS = 180 # 하품 카운트 윈도우 (초)

# ──────────────────────────────────────────────
# 졸음 점수 가중치
# ──────────────────────────────────────────────
W1_EAR = 0.35   # 눈 감김 (가장 직접적)
W2_MAR = 0.25   # 하품 빈도
W3_HEAD = 0.20  # 고개 기울기
W4_ENV = 0.20   # 환경 (CO₂ + 온도 + 습도)

# ──────────────────────────────────────────────
# 환경 점수 가중치
# ──────────────────────────────────────────────
E1_CO2 = 0.50   # CO₂ (졸음 유발 연관성 최고)
E2_TEMP = 0.30  # 온도
E3_HUMID = 0.20 # 습도

# ──────────────────────────────────────────────
# 피로도 가중치
# ──────────────────────────────────────────────
F1_WORK = 0.35    # 연속 작업 시간
F2_DROWSY = 0.40  # 졸음 감지 빈도 (가장 직접적)
F3_ENV = 0.25     # 환경 스트레스 누적

# ──────────────────────────────────────────────
# 경고 단계 (졸음 점수 기준)
# ──────────────────────────────────────────────
ALERT_LEVEL_0_MAX = 40   # 정상 (0~40)
ALERT_LEVEL_1_MAX = 70   # 주의 (41~70)
ALERT_LEVEL_2_MAX = 85   # 경고 (71~85)
# 86~100                 # 위험

# ──────────────────────────────────────────────
# 피로 단계
# ──────────────────────────────────────────────
FATIGUE_GOOD_MAX = 40       # 양호
FATIGUE_CAUTION_MAX = 70    # 주의
FATIGUE_WARNING_MAX = 85    # 경고
# 86~100                    # 위험

# ──────────────────────────────────────────────
# 얼굴 미검출 설정
# ──────────────────────────────────────────────
NO_FACE_ALERT_SECONDS = 5  # 얼굴 미검출 시 경고까지 시간 (초)

# ──────────────────────────────────────────────
# GPIO 핀 배치 (Raspberry Pi)
# ──────────────────────────────────────────────
GPIO_LED_RED = 17
GPIO_LED_GREEN = 27
GPIO_LED_BLUE = 22
GPIO_BUZZER = 18      # PWM
GPIO_DHT = 4
GPIO_UART_TX = 14
GPIO_UART_RX = 15

# ──────────────────────────────────────────────
# 환경 센서 임계값
# ──────────────────────────────────────────────
CO2_WARNING_PPM = 1000
CO2_DANGER_PPM = 1500
TEMP_WARNING_C = 26
TEMP_DANGER_C = 28
HUMID_WARNING_PCT = 70

# 환경 스트레스 지속시간 임계값 (초)
ENV_STRESS_DURATION = 600  # 10분

# ──────────────────────────────────────────────
# 데이터베이스 설정
# ──────────────────────────────────────────────
DB_HOST = 'localhost'
DB_USER = 'jiho'
DB_PASSWORD = 'qwer1234'
DB_NAME = 'jihodb'
DB_CHARSET = 'utf8mb4'

# ──────────────────────────────────────────────
# 데이터 저장 주기
# ──────────────────────────────────────────────
DB_SAVE_INTERVAL = 5   # 초 단위 (매 N초마다 DB에 저장)

# ──────────────────────────────────────────────
# 피로 회복 설정
# ──────────────────────────────────────────────
RECOVERY_REDUCTION = 30  # 피로 해소 시 감소 점수

# 회복 검증 설정
RECOVERY_EVAL_DURATION = 30   # 회복 후 평가 시간 (초)
RECOVERY_EVAL_MIN_SAMPLES = 10  # 최소 평가 샘플 수
RECOVERY_EFFECTIVE_DROWSY_MAX = 30  # 이 점수 이하면 회복 성공 (졸음 점수)
RECOVERY_EFFECTIVE_FATIGUE_DROP = 10  # 이 점수 이상 하락하면 회복 성공 (피로도)

# ──────────────────────────────────────────────
# MediaPipe Face Mesh 랜드마크 인덱스
# ──────────────────────────────────────────────
# 왼쪽 눈
LEFT_EYE_IDX = [362, 385, 387, 263, 373, 380]
# 오른쪽 눈
RIGHT_EYE_IDX = [33, 160, 158, 133, 153, 144]
# 입
MOUTH_IDX = [61, 37, 0, 267, 270, 291, 405, 314, 17, 84, 181, 78]
# Head Pose 추정용 주요 포인트
NOSE_TIP_IDX = 1
CHIN_IDX = 152
LEFT_EYE_CORNER_IDX = 263
RIGHT_EYE_CORNER_IDX = 33
LEFT_MOUTH_IDX = 61
RIGHT_MOUTH_IDX = 291

# ──────────────────────────────────────────────
# 더미 센서 데이터 (데스크탑 모드)
# ──────────────────────────────────────────────
DUMMY_CO2 = 600
DUMMY_TEMPERATURE = 22.0
DUMMY_HUMIDITY = 50.0

# ──────────────────────────────────────────────
# 로컬 LLM (Ollama) 설정 - 데스크탑 전용
# ──────────────────────────────────────────────
LLM_ENABLED = True                        # False로 끄면 정적 가이드만 사용
LLM_HOST = "http://127.0.0.1:11435"       # Ollama 호스트 (tq-ollama 인스턴스에 한국어 모델 보유)
LLM_MODEL = "exaone3.5:7.8b"              # LG AI연구원, 한국어 특화. 대안: gemma4:e4b
LLM_TIMEOUT = 30                          # 초
LLM_COOLDOWN = 300                        # 같은 코칭 반복 방지 (초)
LLM_MAX_TOKENS = 400                      # 응답 최대 토큰

# ──────────────────────────────────────────────
# 파일 경로
# ──────────────────────────────────────────────
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GUIDES_JSON_PATH = os.path.join(BASE_DIR, 'data', 'guides.json')

# ──────────────────────────────────────────────
# .env 파일에서 DB 자격증명 로드 (있으면 덮어쓰기)
# ──────────────────────────────────────────────
def _load_env():
    """프로젝트 루트의 .env 파일에서 환경변수를 읽어 설정을 덮어쓴다."""
    env_path = os.path.join(BASE_DIR, '.env')
    if not os.path.exists(env_path):
        return {}
    env_vars = {}
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    return env_vars

_env = _load_env()
if _env:
    DB_HOST = _env.get('DB_HOST', DB_HOST)
    DB_USER = _env.get('DB_USER', DB_USER)
    DB_PASSWORD = _env.get('DB_PASSWORD', DB_PASSWORD)
    DB_NAME = _env.get('DB_NAME', DB_NAME)
    if 'DB_PORT' in _env:
        DB_PORT = int(_env['DB_PORT'])

# 환경변수 직접 주입 (Docker Compose environment 섹션)이 .env보다 우선
DB_HOST = os.environ.get('DB_HOST', DB_HOST)
LLM_HOST = os.environ.get('LLM_HOST', LLM_HOST)
CAMERA_URL = os.environ.get('CAMERA_URL', CAMERA_URL)
