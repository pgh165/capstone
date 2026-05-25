#!/usr/bin/env bash
# AI 기반 학습 피로 관리 시스템 한 번에 실행
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 0. 카메라 usbipd attach (WSL에서 PowerShell 호출) ─────────
_attach_camera() {
    local CAMERA_NAME="USB 2.0 Camera"

    echo "[run] 카메라 usbipd 상태 확인..."

    # usbipd list에서 카메라 BUSID 추출
    local busid
    busid=$(powershell.exe -NoProfile -Command "
        usbipd list | Select-String '$CAMERA_NAME' | ForEach-Object {
            (\$_ -split '\s+')[0]
        }
    " 2>/dev/null | tr -d '\r\n ')

    if [ -z "$busid" ]; then
        echo "[run] 경고: '$CAMERA_NAME' 장치를 찾을 수 없습니다. USB 연결을 확인하세요."
        return
    fi

    # 이미 Attached 상태인지 확인
    local state
    state=$(powershell.exe -NoProfile -Command "
        usbipd list | Select-String '$CAMERA_NAME' | ForEach-Object { \$_.Line }
    " 2>/dev/null | tr -d '\r')

    if echo "$state" | grep -q "Attached"; then
        echo "[run] 카메라 이미 WSL에 연결됨 (busid=$busid)"
        return
    fi

    # Shared 상태가 아니면 bind 필요 (관리자 권한)
    if ! echo "$state" | grep -q "Shared"; then
        echo "[run] 카메라 bind 중... (관리자 권한 필요 — UAC 창이 뜰 수 있습니다)"
        powershell.exe -NoProfile -Command "
            Start-Process powershell -Verb RunAs -Wait -ArgumentList \`
                '-NoProfile -Command \"usbipd bind --busid $busid\"'
        " 2>/dev/null || true
    fi

    echo "[run] 카메라 attach 중 (busid=$busid)..."
    powershell.exe -NoProfile -Command "usbipd attach --wsl --busid $busid" 2>/dev/null || {
        echo "[run] 경고: attach 실패. 아래 명령을 Windows PowerShell(관리자)에서 직접 실행하세요:"
        echo "       usbipd bind --busid $busid"
        echo "       usbipd attach --wsl --busid $busid"
        return
    }

    # /dev/video0 생성 대기 (최대 5초)
    for i in $(seq 1 5); do
        sleep 1
        if [ -e /dev/video0 ]; then
            echo "[run] 카메라 연결 완료 (/dev/video0)"
            return
        fi
    done
    echo "[run] 경고: /dev/video0 확인 안 됨 — 카메라 없이 진행합니다"
}

if [ ! -e /dev/video0 ]; then
    _attach_camera
else
    echo "[run] 카메라 이미 사용 가능 (/dev/video0)"
fi

# ── 1. Docker (MySQL + Django) ─────────────────────────────────
echo "[run] Docker 컨테이너 빌드 및 시작..."
docker compose up -d --build
echo "[run] Docker 준비 완료"

# ── 2. Ollama ─────────────────────────────────────────────────
if ! curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "[run] Ollama 시작..."
    ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!
    for i in $(seq 1 10); do
        sleep 1
        if curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
            echo "[run] Ollama 준비 완료 (PID=$OLLAMA_PID)"
            break
        fi
        if [ "$i" -eq 10 ]; then
            echo "[run] 경고: Ollama 응답 없음 — AI 판정 없이 실행됩니다"
        fi
    done
else
    echo "[run] Ollama 이미 실행 중"
fi

# ── 3. main.py ────────────────────────────────────────────────
echo "[run] main.py 실행"
echo ""
source "$SCRIPT_DIR/.venv/bin/activate"
python3 "$SCRIPT_DIR/main.py"
