# AI 개인 맞춤형 포모도로 타이머

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | AI 개인 맞춤형 포모도로 타이머 |
| 전공 | 임베디드 소프트웨어 |
| 핵심 기술 | MediaPipe, OpenCV, Ollama(로컬 LLM), MeloTTS, Django, Docker, WSL2 |

USB 웹캠으로 얼굴을 실시간 분석하여 사용자의 피로도·졸음 상태를 측정하고, 이를 기반으로 **작업 인터벌과 휴식 시간을 동적으로 조정**하는 AI 포모도로 타이머. 고정된 25/5분 방식이 아닌, 지금 내 상태에 맞는 인터벌을 로컬 LLM이 판단한다. 세션 초반 30초 캘리브레이션으로 개인별 EAR/MAR 기준을 자동 설정하고, TTS 음성 코칭으로 자연스럽게 안내한다.

---

## 2. 시스템 아키텍처

```mermaid
flowchart TD
    CAM["📷 USB 웹캠\n/dev/video0"]
    FFMPEG["ffmpeg subprocess\nBGR 프레임"]
    MP["MediaPipe FaceMesh\nLandmarks (신뢰도 0.3)"]

    subgraph CALIB["개인 캘리브레이션 (30초)"]
        EC["EARCalibrator\nEAR × 0.75 → 임계값\nMAR × 3.0 → 임계값"]
    end

    subgraph BIOMETRIC["생체 신호 분석"]
        DT["DrowsinessTracker\nPERCLOS(60s) / MAR(0.8s 지속)"]
        HP["HeadPoseEstimator\nPitch / Roll (Yaw 제외)"]
    end

    subgraph SCORING["졸음 점수 산출"]
        DJ["DrowsinessJudge\nEMA α=0.25 / x^1.5/10\nW1=0.50 / W2=0.25 / W3=0.25\n지속 고개 떨굼 보너스(5초~)"]
        AJ["AIJudge\ngemma4:e4b\n5초 비동기 (캘리브레이션 후 시작)"]
    end

    subgraph NOFACE["얼굴 미검출 처리"]
        NF["2초 초과 시 졸음 점수 상승\near_score 0→100 (2~7초)\nhead_score=100 고정"]
    end

    subgraph FATIGUE["피로도 관리"]
        FM["FatigueManager\n연속작업 + 졸음빈도"]
    end

    subgraph POMODORO["🍅 AI 포모도로 타이머 ★"]
        PT["PomodoroTimer\n동적 작업 10~40분\n수동 리셋: 40분 초기화\n휴식 중 경고 억제"]
    end

    subgraph OUTPUT["출력"]
        AC["AlertController\n히스테리시스 적용\nTTS 경보 MeloTTS"]
        LC["LLMCoach\ngemma4:26b\n개인화 음성 코칭"]
        DB["DBWriter\nMySQL 8.0\nDocker :3307"]
        WEB["Django 대시보드\nDocker :8000"]
    end

    CAM --> FFMPEG --> MP
    MP -->|첫 30초| EC
    EC -->|개인 임계값| DT
    MP --> DT & HP
    MP -->|미검출| NF
    DT -->|ear_score, mar_score| DJ
    HP -->|head_score| DJ
    NF -->|가상 ear/head score| DJ
    DJ -->|캘리브레이션 후| AJ
    AJ -->|편차 30 초과 시 중간값| DJ
    DJ --> FM
    FM -->|fatigue_score| PT
    DJ -->|drowsiness_score| PT
    PT -->|휴식 시작| LC
    PT -->|위험 경보 (WORKING 중만)| AC
    FM --> DB
    DJ --> DB
    DB --> WEB
```

### 실행 환경

| 구성 요소 | 실행 위치 | 접속 |
|----------|-----------|------|
| `main.py` (AI 엔진) | WSL2 호스트 직접 실행 | — |
| MySQL 8.0 | Docker (`mysql`) | `localhost:3307` |
| Django 대시보드 | Docker (`web`) | `http://localhost:8000` |
| Ollama LLM 서버 | WSL2 호스트 직접 실행 | `http://127.0.0.1:11434` |

### 실행 방법

```bash
# 한 번에 실행 (usbipd attach → Docker → Ollama → main.py)
~/capstone/run.sh

# Windows에서 더블클릭
\\wsl$\Ubuntu\home\parkjiho\capstone\run_windows.bat
```

---

## 3. 핵심 알고리즘

### 3.1 개인 캘리브레이션 (세션 초반 30초)

```
목적: 사람마다 다른 눈/입 크기 기준을 자동 측정

측정: 30초간 EAR·MAR 평균값 수집
  EAR 임계값 = avg_ear × 0.75  (클램프: 0.10 ~ 0.25)
  MAR 임계값 = avg_mar × 3.0   (클램프: 0.65 ~ 0.90)

효과: 눈이 작은 사람 / 입이 큰 사람도 오탐 없이 측정
캘리브레이션 완료 전: AI 판정(AIJudge) 비활성화
```

### 3.2 EAR → PERCLOS (눈 감김 비율)

```
EAR = (|P2-P6| + |P3-P5|) / (2 × |P1-P4|)

임계값: EAR < 개인 임계값(기본 0.20) → 눈 감김
워밍업: 20초 미만 데이터 → 0점 (오탐 방지)

PERCLOS (최근 60초 윈도우):
  PERCLOS(%) = 눈 감김 시간 / 전체 관측 시간 × 100

PERCLOS 점수 (선형 보간):
   0~10%  →   0점  (정상 깜빡임 데드존)
  10~20%  →   0~20점
  20~30%  →  20~45점
  30~45%  →  45~70점
  45~55%  →  70~85점
  55~65%  →  85~100점
```

### 3.3 MAR (Mouth Aspect Ratio) — 하품 감지

```
MAR = (세로 거리 합) / (2 × 가로 거리)

임계값: MAR > 개인 임계값(기본 0.75)
지속시간 요건: 0.8초 이상 초과 유지 시만 카운트 (순간 오탐 방지)

MAR 점수 (3분 슬라이딩 윈도우):
  1회 →  5점 / 2회 → 20점 / 3회 → 40점
  5회 → 70점 / 7회 → 100점
```

### 3.4 Head Pose 점수 — 고개 떨굼 감지

```
solvePnP로 Pitch(상하), Roll(기울기) 추정.
Yaw(좌우 돌림)는 졸음 징후 아님 → 제외.
FaceLandmarker 신뢰도 임계값: 0.3 (고개 떨굼 시 검출 유지)

Pitch 점수 (데드존 15°):
  0~15° → 0점 / 20° → 10점 / 28° → 30점
  38° → 60점 / 50° → 80점 / 65° → 100점

Roll 점수 (데드존 12°):
  0~12° → 0점 / 22° → 10점 / 32° → 25점 / 48° → 40점

head_score = pitch_score + roll_score  (최대 100)

지속 고개 떨굼 보너스 (judge.py):
  head_score ≥ 60 이 5초 이상 지속 → 초당 +2.5 raw 점수 추가
  보너스 상한: +45점 (약 23초 후 상한 도달)
```

### 3.5 얼굴 미검출 → 졸음 판단

```
얼굴이 프레임에서 사라지더라도 사용자가 자리에 있다고 가정.

0~2초:  이전 점수 유지 (순간 얼굴 손실 무시)
2~7초:  ear_score 0→100 선형 증가 + head_score=100 고정
         → 고개를 완전히 떨군 상태로 간주해 점수 상승
7초 이상: ear_score=100 고정 → 졸음 점수 최고치 유지
얼굴 재검출: 즉시 실제 측정값으로 복귀 (EMA로 부드럽게)
```

### 3.6 종합 졸음 점수

```
raw = W1×EAR + W2×MAR + W3×Head
  W1 = 0.50 (눈 감김)
  W2 = 0.25 (하품)
  W3 = 0.25 (고개 기울기)

지속 고개 떨굼 보너스 적용 후:
1.5승 변환 (제곱보다 이른 감지, 선형보다 오경보 억제):
  score_curved = raw^1.5 / 10

EMA 스무딩 (α = 0.25):
  drowsiness_score = α × score_curved + (1-α) × prev

경고 단계:
   0 ~ 20 → 정상 (L0)
  21 ~ 45 → 주의 (L1)  ← TTS "주의하세요."
  46 ~ 65 → 경고 (L2)  ← TTS "경고! 졸음 수준이 높습니다."
  66 ~100 → 위험 (L3)  ← TTS "위험! 즉시 작업을 멈추세요."

히스테리시스 (레벨 하강 시, 진동 방지):
  L1→L0: 점수 < 13 / L2→L1: 점수 < 33 / L3→L2: 점수 < 53

휴식(BREAK) 중: 모든 경고 억제
```

> AI 판정(gemma4:e4b, 5초 주기, 캘리브레이션 완료 후): 규칙 기반 점수와 편차 30 초과 시 중간값 적용

---

## 4. 피로도 관리

### 4.1 누적 피로도 점수

```
피로도 = F1×연속작업 점수 + F2×졸음빈도 점수
  F1 = 0.40 / F2 = 0.60

연속작업 점수: 30분→0점, 60분→20점, 90분→50점, 120분→80점
졸음빈도 점수(30분 윈도우, alert_level≥2 시 30초마다):
  3회→10점, 10회→40점, 20회→65점, 40회→100점

피로 단계: 0~50 양호 / 51~75 주의 / 76~88 경고 / 89~100 위험
```

### 4.2 원인 기반 맞춤 가이드

피로의 주된 원인(연속작업 / 졸음빈도)을 분석하여 단계별 가이드 추천.

| 피로 단계 | 기본 가이드 | + 연속작업 | + 졸음 빈도 |
|-----------|------------|-----------|------------|
| 주의 | 눈 피로 해소 | 자세 교정, 수분 보충 | 냉수 세안, 호흡법 |
| 경고 | 스트레칭, 눈 피로 해소 | 산책, 수분 보충, 자세 교정 | 냉수 세안, 호흡법, 카페인 |
| 위험 | 즉시 휴식, 스트레칭 | 산책, 수분 보충 | 냉수 세안, 카페인, 호흡법 |

### 4.3 시간대별 피로 패턴 학습

DB `fatigue_logs`에서 시간대별 평균 피로도를 집계해 포모도로 인터벌에 선제 반영.
- 과거 피로 평균 ≥ 75 → 작업 인터벌 -5분
- 과거 피로 평균 ≥ 50 → 작업 인터벌 -3분
- 각 시간대 최소 3샘플 이상 쌓여야 활성화

### 4.4 개인 최적 작업 인터벌 학습

과거 경고/위험 단계 진입 시점의 평균 연속 작업 시간을 역산.
- 공식: 개인 기준 = 피로 임계 도달 평균 시간 × 0.85
- DB 5회 이상 기록 후 활성화

---

## 5. AI 포모도로 타이머

### 5.1 동적 인터벌 계산

```
기준: 개인 학습 인터벌 (없으면 POMODORO_BASE_WORK_MIN=25분)

피로도 보정:
  ≤30 → +10분 / ≤50 → +5분 / ≤75 → 0 / ≤88 → -8분 / >88 → -15분

졸음 보정:
  ≤20 → +5분 / ≤40 → 0 / ≤70 → -5분 / >70 → -10분

시간대 보정: 과거 피로 패턴 반영 (최대 -5분)

범위: 10분 ~ 40분
```

### 5.2 수동 리셋

- 대시보드 "리셋" 버튼 → 항상 **최대 40분**으로 초기화
- `cmd.json` 파일을 통해 Django(Docker) → main.py로 명령 전달

### 5.3 휴식 시간

```
4사이클마다 긴 휴식 (15분)
피로 단계별:
  양호 → 5분 / 주의 → 8분 / 경고 → 15분 / 위험 → 30분
```

---

## 6. LLM 코칭 (LLMCoach)

```
모델: gemma4:26b (Ollama, 로컬)  쿨다운: 5분  타임아웃: 180초
입력: 피로 단계/점수, 원인, 연속 작업 시간, 30분 졸음 횟수, 추천 가이드
출력: 3~4문장 자연스러운 한국어 대화체 + MeloTTS 발화
```

---

## 7. AI 졸음 판정 (AIJudge)

```
모델: gemma4:e4b (Ollama, 로컬)  주기: 5초 비동기
캘리브레이션(30초) 완료 후에만 시작
출력: {"drowsiness": 0~100, "level": 0~3}
규칙 기반 점수를 앵커로 전달 (±25 이내 판정 유도)
편차 30 초과 시: 최종값 = (규칙 기반 + AI 판정) / 2
```

---

## 8. 웹 서버 (Django + Docker)

### 8.1 페이지 구성

| URL | 설명 |
|-----|------|
| `/` | 메인 대시보드 (날짜 선택, 이력 조회) |
| `/realtime/` | 실시간 대시보드 (1초 폴링, 졸음 게이지, 포모도로) |
| `/settings/` | 감지 설정 + 사용자 이름 설정 |

### 8.2 주요 API

| 엔드포인트 | 설명 |
|------------|------|
| `/api/realtime/` | main.py 실시간 상태 (1초 갱신) |
| `/api/logs/` | 감지 이력 (날짜 필터, 페이지네이션) |
| `/api/fatigue/` | 피로도 이력 |
| `/api/settings/` | EAR/MAR 임계값·가중치 조회/변경 |
| `/api/command/` | 포모도로 리셋 등 main.py 제어 |
| `/api/profile/` | 사용자 이름 조회/저장 |
| `/api/daily_report/` | 일간 요약 |

### 8.3 DB 스키마

```
detection_logs : ear, mar, pitch, yaw, drowsiness_score, alert_level
fatigue_logs   : fatigue_score, continuous_work_min, drowsy_count, fatigue_level
settings       : 설정 키-값
daily_summary  : 일간 집계 통계
```

---

## 9. 파일 구조

```
capstone/
├── main.py                  # 메인 실행 파일 (얼굴 미검출 처리, 프로필 로드)
├── config.py                # 전체 설정값
├── run.sh                   # 한 번에 실행
├── run_windows.bat          # Windows 더블클릭 실행
│
├── modules/
│   ├── camera.py            # ffmpeg subprocess 카메라 캡처 (종료 시 kill 보장)
│   ├── face_detector.py     # MediaPipe FaceLandmarker (신뢰도 0.3)
│   ├── drowsiness.py        # EAR/MAR/PERCLOS (개인 임계값, 하품 0.8s 지속 요건)
│   ├── calibration.py       # 세션 초반 30초 EAR/MAR 캘리브레이션
│   ├── head_pose.py         # Pitch/Roll 고개 기울기 추정
│   ├── judge.py             # EMA + 1.5승 + 지속 고개 떨굼 보너스
│   ├── ai_judge.py          # gemma4:e4b 비동기 판정
│   ├── fatigue_manager.py   # 피로도 추적 + 가이드 추천
│   ├── recovery_guide.py    # 가이드 데이터 출력
│   ├── llm_coach.py         # gemma4:26b 개인화 코칭
│   ├── alert.py             # 경고 단계 + 히스테리시스 + TTS
│   ├── voice.py             # MeloTTS + WSL2 PowerShell 오디오 브릿지
│   ├── pomodoro.py          # AI 동적 포모도로 (수동 리셋=40분)
│   └── db_writer.py         # MySQL 저장 / 시간대별 패턴 / 최적 인터벌 조회
│
├── data/
│   ├── guides.json          # 피로 해소 가이드 데이터
│   ├── realtime_status.json # main.py → Django 실시간 상태 공유
│   ├── cmd.json             # Django → main.py 제어 명령
│   └── user_profile.json    # 사용자 이름 저장
│
├── web/                     # Django (Docker :8000)
├── sql/
│   └── schema.sql           # DB 테이블 생성 스크립트
└── tests/                   # 단위 테스트
```

---

## 10. 기술 스택

| 분류 | 기술 |
|------|------|
| 얼굴 분석 | MediaPipe FaceLandmarker, OpenCV |
| AI 판정 | Ollama + gemma4:e4b |
| LLM 코칭 | Ollama + gemma4:26b |
| TTS | MeloTTS (로컬 AI, KR 모델) + WSL2 PowerShell 브릿지 |
| 웹 | Django 4.x, MySQL 8.0, Chart.js |
| 인프라 | Docker Compose, WSL2 Ubuntu 24.04 |
| 카메라 | USB 2.0 (usbipd-win → /dev/video0, ffmpeg MJPEG) |
