# AIoT 기반 졸음 및 집중력 저하 방지 시스템

## 실행 방법

### 1. Python 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. MediaPipe 모델 다운로드
`models/` 폴더에 face_landmarker 모델이 필요합니다.
```bash
mkdir models
curl -L -o models/face_landmarker.task "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
```

### 3. MySQL 데이터베이스 설정 (선택사항)
```bash
mysql -u root -p < sql/schema.sql
```
> DB 없이도 실행 가능합니다 (경고 메시지 출력 후 정상 동작).

### 4. 실행
```bash
python main.py
```
종료: `q` 키 또는 `Ctrl+C`

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
- **원인**: MySQL/MariaDB 서버가 실행되지 않음
- **해결**:
  - MySQL 설치 및 시작: `net start mysql` (Windows) 또는 `sudo systemctl start mariadb` (Linux)
  - `sql/schema.sql` 실행하여 DB 및 테이블 생성
  - `config.py`에서 `DB_HOST`, `DB_USER`, `DB_PASSWORD` 확인
  - DB 없이도 AI 감지 기능은 정상 동작 (로그 저장만 건너뜀)

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
│   ├── recovery_guide.py   # 피로 해소 가이드
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
