# AIoT 기반 졸음 및 집중력 저하 방지 시스템

## 실행 방법 (WSL2 + Docker Desktop, 하이브리드 구성)

웹캠/GUI가 필요한 `main.py`는 **WSL 호스트에서 직접 실행**하고, **MySQL + Ollama만 Docker 컨테이너**로 띄우는 방식입니다.

### 0. 사전 준비 (Windows → WSL 이전 시)
1. Windows 11 + Docker Desktop 설치 후 **Settings → Resources → WSL Integration**에서 사용할 배포판(Ubuntu 등) 활성화
2. Windows에서 WSL로 프로젝트 복사:
   ```powershell
   # PowerShell 에서 (예: Windows 경로 → WSL 홈)
   wsl cp -r /mnt/c/Users/<USER>/Desktop/capstone ~/capstone
   ```
   > ⚠️ 성능상 반드시 `/home/<user>/` 아래(ext4)로 옮기세요. `/mnt/c` 아래서 실행하면 파일 I/O가 매우 느립니다.
3. 웹캠 사용이 필요하면 [usbipd-win](https://github.com/dorssel/usbipd-win)으로 USB 패스스루 설정 (`usbipd list` → `usbipd bind` → `usbipd attach --wsl`).

### 1. Python 가상환경 + 패키지 설치 (WSL)
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip libgl1 libglib2.0-0
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. MediaPipe 모델 다운로드
```bash
mkdir -p models
curl -L -o models/face_landmarker.task "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
```

### 3. `.env` 파일 생성
```bash
cp .env.example .env
# 필요 시 값 수정 (DB_PASSWORD 등)
```

### 4. Docker로 MySQL + Ollama 실행
```bash
docker compose up -d
docker compose ps           # 상태 확인
docker compose logs -f mysql  # 초기화 로그 (schema.sql 자동 실행)
```
- MySQL: `localhost:3306` (schema.sql은 최초 실행 시 자동 적용됨)
- Ollama: `localhost:11434`

### 5. Ollama 모델 pull (최초 1회)
```bash
docker exec -it capstone-ollama ollama pull qwen2.5:14b
# 경량 대안: docker exec -it capstone-ollama ollama pull gemma3:4b
```
> `config.py`의 `LLM_MODEL` 값과 일치해야 합니다. LLM을 끄려면 `LLM_ENABLED = False`.

### 6. 메인 실행 (WSL 호스트)
```bash
source venv/bin/activate
python main.py
```
종료: `q` 키 또는 `Ctrl+C`

### 컨테이너 관리
```bash
docker compose stop          # 중지 (데이터 유지)
docker compose down          # 컨테이너 제거 (볼륨은 유지)
docker compose down -v       # 볼륨까지 삭제 (DB/모델 초기화)
```

---

## 실행 시 발생할 수 있는 에러 및 해결 방법

### 에러 1: `ModuleNotFoundError: No module named 'cv2'`
- **원인**: Python 패키지 미설치
- **해결**: `pip install -r requirements.txt`

### 에러 2: `AttributeError: module 'mediapipe' has no attribute 'solutions'`
- **원인**: mediapipe 0.10.21+ 버전에서 `mp.solutions` 레거시 API 제거됨
- **해결**: 본 프로젝트는 새로운 Tasks API (`mp.tasks.vision.FaceLandmarker`)를 사용하도록 구현됨. `models/face_landmarker.task` 모델 파일 필요

### 에러 3: `RuntimeError: Unable to open file at .../face_landmarker.task`
- **원인**: 프로젝트 경로에 한글이 포함된 경우 mediapipe C 라이브러리가 파일을 열지 못함
- **해결**: `model_asset_buffer`로 바이트 데이터를 직접 전달하는 방식으로 우회 (현재 적용됨)

### 에러 4: `Camera ret=False, frame=None`
- **원인**: 웹캠이 연결되지 않았거나 다른 프로그램이 사용 중
- **해결**:
  - 웹캠이 연결되어 있는지 확인
  - `config.py`의 `CAMERA_INDEX`를 변경 (0, 1, 2 등)
  - 다른 프로그램(Zoom, Teams 등)이 카메라를 사용 중이면 종료

### 에러 5: `MySQL 연결 실패: Can't connect to MySQL server on 'localhost'`
- **원인**: MySQL 컨테이너 미실행 또는 `.env` 설정 불일치
- **해결**:
  - `docker compose ps` 로 `capstone-mysql` 이 `healthy` 인지 확인
  - `docker compose logs mysql` 로 초기화 오류 확인
  - `.env` 의 `DB_USER` / `DB_PASSWORD` / `DB_NAME` 이 컴포즈 기동 시 값과 같은지 확인 (비밀번호를 바꿨다면 `docker compose down -v` 로 볼륨을 지우고 재기동)
  - DB 없이도 AI 감지 기능은 정상 동작 (로그 저장만 건너뜀)

### 에러 6: `Ollama 연결 실패` / LLM 코칭 미동작
- **원인**: Ollama 컨테이너 미실행 또는 모델 미 pull
- **해결**:
  - `docker compose ps` 로 `capstone-ollama` 상태 확인
  - `docker exec -it capstone-ollama ollama list` 로 설치된 모델 확인
  - 모델이 없으면 `docker exec -it capstone-ollama ollama pull qwen2.5:14b`

### 에러 7: WSL에서 웹캠이 잡히지 않음 (`Camera ret=False`)
- **원인**: WSL2는 기본적으로 Windows USB 장치에 접근 불가
- **해결**:
  - [usbipd-win](https://github.com/dorssel/usbipd-win) 설치 후 관리자 PowerShell에서:
    ```powershell
    usbipd list                           # BUSID 확인
    usbipd bind --busid <BUSID>
    usbipd attach --wsl --busid <BUSID>
    ```
  - WSL 쪽에서 `ls /dev/video*` 로 장치 인식 확인

---

## 설정 변경

`config.py`에서 주요 설정을 변경할 수 있습니다:

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `IS_DESKTOP` | `True` | `True`: 웹캠+더미센서, `False`: Pi Camera+실제센서 |
| `CAMERA_INDEX` | `0` | 웹캠 인덱스 |
| `EAR_THRESHOLD` | `0.2` | 눈 감김 판정 임계값 |
| `MAR_THRESHOLD` | `0.6` | 하품 판정 임계값 |
| `DB_HOST` | `localhost` | MySQL 호스트 |
| `DB_PASSWORD` | `password` | MySQL 비밀번호 |

---

## 프로젝트 구조

```
capstone_project/
├── main.py                 # 메인 실행 파일
├── config.py               # 설정값
├── requirements.txt        # Python 패키지
├── models/                 # MediaPipe 모델 파일
├── modules/                # Python 모듈
│   ├── camera.py           # 카메라 캡처
│   ├── face_detector.py    # 얼굴 랜드마크 검출
│   ├── drowsiness.py       # EAR/MAR 졸음 감지
│   ├── head_pose.py        # 고개 기울기 추정
│   ├── env_sensor.py       # 환경 센서 (CO2/온습도)
│   ├── judge.py            # 종합 졸음 판단
│   ├── fatigue_manager.py  # 피로도 관리
│   ├── recovery_guide.py   # 피로 해소 가이드 (정적)
│   ├── llm_coach.py        # 로컬 LLM 개인화 코칭 (Ollama)
│   ├── alert.py            # GPIO 경고 출력
│   └── db_writer.py        # MySQL 저장
├── data/guides.json        # 피로 해소 가이드 데이터
├── sql/schema.sql          # DB 스키마
├── web/                    # LAMP 웹 대시보드
├── tests/                  # 단위 테스트
└── docs/                   # 문서
```

## 테스트 실행
```bash
python -m pytest tests/ -v
```
