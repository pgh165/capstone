@echo off
chcp 65001 > nul

:: Docker Desktop 실행
tasklist /FI "IMAGENAME eq Docker Desktop.exe" 2>nul | find /I "Docker Desktop.exe" >nul
if errorlevel 1 (
    echo [run] Docker Desktop 시작 중...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
) else (
    echo [run] Docker Desktop 이미 실행 중
)

:: Docker daemon 준비 대기 (최대 60초)
echo [run] Docker daemon 준비 대기 중...
set /a count=0
:wait_docker
wsl -e bash -c "docker info" > nul 2>&1
if %errorlevel% == 0 goto docker_ready
set /a count+=1
if %count% geq 30 (
    echo [run] Docker daemon 응답 없음. 계속 진행합니다...
    goto docker_ready
)
timeout /t 2 /nobreak > nul
goto wait_docker

:docker_ready
echo [run] Docker daemon 준비 완료

:: 실시간 대시보드 브라우저에서 열기 (15초 대기 후 오픈)
echo [run] 실시간 대시보드 브라우저 열기 대기 중...
start "" cmd /c "cd /d %USERPROFILE% && ping -n 16 127.0.0.1 > nul & start http://localhost:8000/realtime/"

wsl -e bash /home/parkjiho/capstone/run.sh
pause
