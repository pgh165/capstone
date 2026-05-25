"""
AI 기반 학습 피로 관리 시스템 - 설정 파일
"""

# ──────────────────────────────────────────────
# 카메라 설정
# ──────────────────────────────────────────────
CAMERA_INDEX = 0          # 웹캠 인덱스
CAMERA_URL = ""           # URL 스트림 사용 시 지정 (예: http://127.0.0.1:8554/stream)
CAMERA_FORMAT = "mjpeg"   # v4l2 캡처 포맷 (mjpeg / yuyv422)
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
MAR_THRESHOLD = 0.75      # 이 값 이상이면 하품 판정
YAWN_COUNT_THRESHOLD = 3  # 3분 내 이 횟수 이상이면 졸음 전조
YAWN_WINDOW_SECONDS = 180 # 하품 카운트 윈도우 (초)

# ──────────────────────────────────────────────
# 졸음 점수 가중치
# ──────────────────────────────────────────────
W1_EAR = 0.55   # 눈 감김 (가장 직접적)
W2_MAR = 0.30   # 하품 빈도
W3_HEAD = 0.15  # 고개 기울기

# ──────────────────────────────────────────────
# 피로도 가중치
# ──────────────────────────────────────────────
F1_WORK = 0.40    # 연속 작업 시간
F2_DROWSY = 0.60  # 졸음 감지 빈도 (가장 직접적)

# ──────────────────────────────────────────────
# 경고 단계 (졸음 점수 기준)
# ──────────────────────────────────────────────
ALERT_LEVEL_0_MAX = 20   # 정상 (0~20)
ALERT_LEVEL_1_MAX = 45   # 주의 (21~45)
ALERT_LEVEL_2_MAX = 65   # 경고 (46~65)
# 66~100                 # 위험

# ──────────────────────────────────────────────
# 피로 단계
# ──────────────────────────────────────────────
FATIGUE_GOOD_MAX = 50       # 양호
FATIGUE_CAUTION_MAX = 75    # 주의
FATIGUE_WARNING_MAX = 88    # 경고
# 86~100                    # 위험

# ──────────────────────────────────────────────
# 얼굴 미검출 설정
# ──────────────────────────────────────────────
NO_FACE_ALERT_SECONDS = 5  # 얼굴 미검출 시 경고까지 시간 (초)

# ──────────────────────────────────────────────
# 데이터베이스 설정
# ──────────────────────────────────────────────
DB_HOST = 'localhost'
DB_USER = 'jiho'
DB_PASSWORD = ''        # .env 파일에서 DB_PASSWORD=... 로 설정
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

RECOVERY_EVAL_DURATION = 30   # 회복 후 평가 시간 (초)
RECOVERY_EVAL_MIN_SAMPLES = 10  # 최소 평가 샘플 수
RECOVERY_EFFECTIVE_DROWSY_MAX = 30  # 이 점수 이하면 회복 성공 (졸음 점수)
RECOVERY_EFFECTIVE_FATIGUE_DROP = 10  # 이 점수 이상 하락하면 회복 성공 (피로도)

# ──────────────────────────────────────────────
# MediaPipe Face Mesh 랜드마크 인덱스
# ──────────────────────────────────────────────
LEFT_EYE_IDX = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_IDX = [33, 160, 158, 133, 153, 144]
MOUTH_IDX = [61, 37, 0, 267, 270, 291, 405, 314, 17, 84, 181, 78]
NOSE_TIP_IDX = 1
CHIN_IDX = 152
LEFT_EYE_CORNER_IDX = 263
RIGHT_EYE_CORNER_IDX = 33
LEFT_MOUTH_IDX = 61
RIGHT_MOUTH_IDX = 291

# ──────────────────────────────────────────────
# 포모도로 타이머 설정
# ──────────────────────────────────────────────
POMODORO_BASE_WORK_MIN = 25    # 기본 작업 인터벌 (분)
POMODORO_MIN_WORK_MIN  = 10    # 최소 작업 인터벌
POMODORO_MAX_WORK_MIN  = 40    # 최대 작업 인터벌
POMODORO_BASE_BREAK_MIN = 5    # 기본 휴식 시간
POMODORO_LONG_BREAK_MIN = 15   # 긴 휴식 시간 (N사이클마다)
POMODORO_LONG_BREAK_CYCLE = 4  # 긴 휴식 주기 (완료 사이클 수)

# ──────────────────────────────────────────────
# 로컬 LLM (Ollama) 설정
# ──────────────────────────────────────────────
LLM_ENABLED = True
LLM_HOST = "http://127.0.0.1:11434"
LLM_MODEL = "gemma4:e4b"       # ai_judge 판정용 (단순 분류, 빠른 응답 우선)
LLM_COACH_MODEL = "gemma4:26b" # llm_coach 코칭 메시지용 (언어 품질 우선)
LLM_TIMEOUT = 180
LLM_COOLDOWN = 300
LLM_MAX_TOKENS = 1500          # gemma4 thinking 모델: 추론+응답 합산 토큰

# ──────────────────────────────────────────────
# TTS (음성 출력) 설정
# ──────────────────────────────────────────────
TTS_ENABLED = True
TTS_ENGINE = "melo-tts"        # "espeak-ng"(오프라인) | "edge-tts"(온라인) | "melo-tts"(로컬 AI)

# espeak-ng 설정
TTS_VOICE = "ko"
TTS_RATE  = 150
TTS_PITCH = 50

# edge-tts 설정
TTS_EDGE_VOICE = "ko-KR-InJoonNeural"
TTS_EDGE_RATE  = "+0%"

# melo-tts 설정
TTS_MELO_SPEED  = 1.1    # 말하기 속도 (1.0=기본, 높을수록 빠름)
TTS_MELO_DEVICE = "cpu"  # "cpu" | "cuda"

# 경보 단계별 발화 문구 (0=정상 → 발화 없음)
ALERT_PHRASES = {
    1: "주의하세요. 졸음이 감지되고 있습니다.",
    2: "경고! 졸음 수준이 높습니다. 잠시 쉬어가세요.",
    3: "위험! 즉시 작업을 멈추고 눈을 감아 쉬세요.",
}

# ──────────────────────────────────────────────
# 파일 경로
# ──────────────────────────────────────────────
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GUIDES_JSON_PATH = os.path.join(BASE_DIR, 'data', 'guides.json')

# ──────────────────────────────────────────────
# .env 파일에서 설정 로드 (있으면 덮어쓰기)
# ──────────────────────────────────────────────
def _load_env():
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

# 환경변수 직접 주입이 .env보다 우선
DB_HOST = os.environ.get('DB_HOST', DB_HOST)
LLM_HOST = os.environ.get('LLM_HOST', LLM_HOST)
CAMERA_INDEX = int(os.environ.get('CAMERA_INDEX', CAMERA_INDEX))
CAMERA_URL = os.environ.get('CAMERA_URL', CAMERA_URL)
