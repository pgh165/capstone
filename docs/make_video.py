#!/usr/bin/env python3
"""
HTML 프레젠테이션 → 영상 변환 스크립트
- HTML 파일 원본을 수정하지 않음
- 네비게이션 바를 JS 주입으로 숨김
- 자막을 브라우저 내 오버레이로 렌더링 (한국어 폰트 그대로)
사용: python3 docs/make_video.py
출력: docs/project_demo_final.mp4
"""

import asyncio
import subprocess
import sys
import re
import json
from pathlib import Path

BASE   = Path(__file__).parent
HTML   = BASE / "project_overview.html"
SRT    = BASE / "subtitles.srt"
OUTPUT = BASE / "project_demo_final.mp4"

WIDTH, HEIGHT = 1280, 720
FPS = 12

# 슬라이드별 표시 시간 (초) — 총 232초(3분52초)
SLIDE_DURATIONS = [15, 25, 25, 30, 30, 25, 45, 37]


# ── SRT 파서 ──────────────────────────────────────────────
def parse_srt(path: Path) -> list[dict]:
    entries = []
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        times = lines[1]
        m = re.match(
            r"(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)", times
        )
        if not m:
            continue
        g = m.groups()
        start = int(g[0])*3600 + int(g[1])*60 + int(g[2]) + int(g[3])/1000
        end   = int(g[4])*3600 + int(g[5])*60 + int(g[6]) + int(g[7])/1000
        body  = "\n".join(lines[2:]).strip()
        entries.append({"start": start, "end": end, "text": body})
    return entries


def subtitle_at(srt: list[dict], t: float) -> str:
    for e in srt:
        if e["start"] <= t < e["end"]:
            return e["text"]
    return ""


# ── 자막 오버레이 JS ──────────────────────────────────────
SUBTITLE_INIT_JS = """
() => {
    const d = document.createElement('div');
    d.id = '__sub__';
    d.style.cssText = [
        'position:fixed',
        'bottom:36px',
        'left:50%',
        'transform:translateX(-50%)',
        'background:rgba(0,0,0,0.75)',
        'color:#fff',
        'font-family:"Noto Sans KR","Segoe UI",sans-serif',
        'font-size:14px',
        'font-weight:500',
        'line-height:1.7',
        'padding:10px 28px',
        'border-radius:8px',
        'text-align:center',
        'max-width:90%',
        'white-space:pre-line',
        'z-index:99999',
        'display:none',
        'pointer-events:none',
    ].join(';');
    document.body.appendChild(d);
}
"""


async def set_subtitle(page, text: str):
    escaped = json.dumps(text)
    await page.evaluate(f"""
    () => {{
        const d = document.getElementById('__sub__');
        if (!d) return;
        if ({escaped}) {{
            d.textContent = {escaped};
            d.style.display = 'block';
        }} else {{
            d.style.display = 'none';
        }}
    }}
    """)


# ── 메인 ──────────────────────────────────────────────────
def check_deps():
    if not HTML.exists():
        sys.exit(f"[오류] HTML 파일을 찾을 수 없습니다: {HTML}")
    r = subprocess.run(["which", "ffmpeg"], capture_output=True)
    if r.returncode != 0:
        sys.exit("[오류] ffmpeg 미설치: sudo apt install ffmpeg")
    try:
        from playwright.sync_api import sync_playwright  # noqa
    except ImportError:
        sys.exit("[오류] playwright 미설치: pip install playwright && python3 -m playwright install chromium")


async def main():
    check_deps()
    from playwright.async_api import async_playwright

    srt = parse_srt(SRT) if SRT.exists() else []
    print(f"자막 항목: {len(srt)}개")

    total_sec = sum(SLIDE_DURATIONS)
    total_frames = sum(int(d * FPS) for d in SLIDE_DURATIONS)
    m, s = divmod(total_sec, 60)

    print("=" * 52)
    print("  HTML 프레젠테이션 → 영상 변환")
    print(f"  {WIDTH}×{HEIGHT}  {FPS}fps  {m}분 {s}초  ({total_frames}프레임)")
    print("=" * 52)

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "image2pipe", "-vcodec", "png", "-r", str(FPS), "-i", "-",
        "-vcodec", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "22", "-preset", "fast", "-movflags", "+faststart",
        str(OUTPUT),
    ]
    ffmpeg_proc = subprocess.Popen(
        ffmpeg_cmd, stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    print("\n[1/2] 슬라이드 캡처 + 자막 렌더링 중...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", "--disable-gpu",
                "--force-color-profile=srgb",
                "--font-render-hinting=none",
            ],
        )
        page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        await page.goto(f"file://{HTML.absolute()}")
        await page.wait_for_load_state("networkidle")
        await page.evaluate("() => document.fonts.ready")
        await page.wait_for_timeout(3000)

        # 네비게이션 바·힌트 숨기기 (HTML 원본 수정 없음)
        await page.evaluate("""
        () => {
            ['#nav', '#hint', '#slide-num'].forEach(sel => {
                const el = document.querySelector(sel);
                if (el) el.style.display = 'none';
            });
        }
        """)
        # 자막 오버레이 삽입
        await page.evaluate(SUBTITLE_INIT_JS)

        elapsed = 0.0
        done = 0
        interval_ms = int(1000 / FPS)

        for idx, duration in enumerate(SLIDE_DURATIONS):
            if idx > 0:
                await page.keyboard.press("ArrowRight")
                await page.wait_for_timeout(700)

            frames = int(duration * FPS)
            print(f"  슬라이드 {idx+1}/{len(SLIDE_DURATIONS)} ({duration}초) ", end="", flush=True)

            for _ in range(frames):
                sub_text = subtitle_at(srt, elapsed)
                await set_subtitle(page, sub_text)

                png = await page.screenshot(type="png")
                ffmpeg_proc.stdin.write(png)

                elapsed += 1.0 / FPS
                done += 1
                if done % (FPS * 5) == 0:
                    print(".", end="", flush=True)
                await page.wait_for_timeout(interval_ms)

            print(" ✓")

        await browser.close()

    ffmpeg_proc.stdin.close()
    ffmpeg_proc.wait()

    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"\n[2/2] 인코딩 완료")
    print(f"\n✅ 완료!")
    print(f"   출력: {OUTPUT}")
    print(f"   크기: {size_mb:.1f} MB")


if __name__ == "__main__":
    asyncio.run(main())
