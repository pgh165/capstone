FROM python:3.11-slim

WORKDIR /app

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# OpenCV GUI + MediaPipe 에 필요한 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libsm6 \
    libxrandr2 \
    libxfixes3 \
    libxcursor1 \
    libxi6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY . .

CMD ["python", "main.py"]
