"""
졸음 감지 기준 시각화 (조정 전/후 비교)
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── 파라미터 ──────────────────────────────────────────────────
BEFORE = {
    "perclos": [(0,0),(5,0),(10,15),(20,40),(30,65),(45,85),(60,100)],
    "mar":     [(0,0),(1,15),(2,30),(3,50),(5,80),(7,100)],
    "ema":     0.30,
    "min_win": 10,
}
AFTER = {
    "perclos": [(0,0),(10,0),(20,20),(30,45),(45,70),(55,85),(65,100)],
    "mar":     [(0,0),(1,5),(2,20),(3,40),(5,70),(7,100)],
    "ema":     0.15,
    "min_win": 20,
}

ALERT_LEVEL_0_MAX = 40
ALERT_LEVEL_1_MAX = 70
ALERT_LEVEL_2_MAX = 85
W1_EAR, W2_MAR, W3_HEAD = 0.45, 0.30, 0.25

CLR_BEFORE = "#EF5350"
CLR_AFTER  = "#1565C0"
CLR_NORMAL  = "#4CAF50"
CLR_CAUTION = "#FFC107"
CLR_WARNING = "#FF7043"
CLR_DANGER  = "#D32F2F"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.facecolor": "#FAFAFA",
    "figure.facecolor": "white",
    "axes.grid": True,
    "grid.alpha": 0.4,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def lerp_score(value, bp):
    if value <= bp[0][0]:  return bp[0][1]
    if value >= bp[-1][0]: return bp[-1][1]
    for i in range(len(bp) - 1):
        x0, y0 = bp[i]; x1, y1 = bp[i+1]
        if value <= x1:
            return y0 + (value - x0) / (x1 - x0) * (y1 - y0)
    return bp[-1][1]


fig = plt.figure(figsize=(16, 13))
fig.suptitle("Drowsiness Detection Thresholds  —  Before vs After",
             fontsize=15, fontweight="bold", y=0.99)
gs = GridSpec(2, 2, figure=fig, hspace=0.50, wspace=0.35)

# ── 1. PERCLOS 비교 ───────────────────────────────────────────
ax1 = fig.add_subplot(gs[0, 0])
px = np.linspace(0, 70, 400)
ax1.fill_between(px, [lerp_score(v, AFTER["perclos"]) for v in px],
                 alpha=0.12, color=CLR_AFTER)
ax1.plot(px, [lerp_score(v, BEFORE["perclos"]) for v in px],
         color=CLR_BEFORE, linewidth=2.2, linestyle="--", label="Before")
ax1.plot(px, [lerp_score(v, AFTER["perclos"]) for v in px],
         color=CLR_AFTER, linewidth=2.5, label="After")

# 정상 깜빡임 범위
ax1.axvspan(0, 6,  alpha=0.15, color=CLR_NORMAL, label="Normal blink (~6%)")
ax1.axvline(10, color=CLR_AFTER, linestyle=":", linewidth=1.2, alpha=0.6)
ax1.text(10.5, 5, "New 0-point\nboundary (10%)", fontsize=8, color=CLR_AFTER)

# PERCLOS → alert 기준선 (PERCLOS만 있을 때 L0/L1 경계)
ax1.axhline(40, color="gray", linestyle=":", linewidth=1, alpha=0.6)
ax1.text(0.5, 41, "L0/L1 boundary (40pt)", fontsize=8, color="gray")

ax1.set_xlim(0, 70); ax1.set_ylim(-5, 105)
ax1.set_xlabel("PERCLOS (%) — Eye closed ratio in 60s", fontsize=10)
ax1.set_ylabel("Score (0–100)", fontsize=10)
ax1.set_title("① PERCLOS Score", fontsize=12, fontweight="bold")
ax1.legend(fontsize=9)

# 조정 전후 주요 포인트 표시
for bp, color in [(BEFORE["perclos"], CLR_BEFORE), (AFTER["perclos"], CLR_AFTER)]:
    ax1.scatter([p[0] for p in bp], [p[1] for p in bp],
                color=color, zorder=5, s=45, alpha=0.8)

# ── 2. MAR 비교 ───────────────────────────────────────────────
ax2 = fig.add_subplot(gs[0, 1])
mx = np.linspace(0, 8, 400)
ax2.fill_between(mx, [lerp_score(v, AFTER["mar"]) for v in mx],
                 alpha=0.12, color=CLR_AFTER)
ax2.plot(mx, [lerp_score(v, BEFORE["mar"]) for v in mx],
         color=CLR_BEFORE, linewidth=2.2, linestyle="--", label="Before")
ax2.plot(mx, [lerp_score(v, AFTER["mar"]) for v in mx],
         color=CLR_AFTER, linewidth=2.5, label="After")

ax2.axhline(40, color="gray", linestyle=":", linewidth=1, alpha=0.6)
ax2.text(0.1, 41, "L0/L1 boundary (40pt)", fontsize=8, color="gray")

# 하품 1회 기준 비교 표시
y_before_1 = lerp_score(1, BEFORE["mar"])
y_after_1  = lerp_score(1, AFTER["mar"])
ax2.annotate(f"1 yawn\nBefore: {y_before_1:.0f}pt\nAfter:  {y_after_1:.0f}pt",
             xy=(1, y_after_1), xytext=(2.5, 30),
             arrowprops=dict(arrowstyle="->", color="gray"),
             fontsize=9, color="gray",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

for bp, color in [(BEFORE["mar"], CLR_BEFORE), (AFTER["mar"], CLR_AFTER)]:
    ax2.scatter([p[0] for p in bp], [p[1] for p in bp],
                color=color, zorder=5, s=45, alpha=0.8)

ax2.set_xlim(0, 8); ax2.set_ylim(-5, 105)
ax2.set_xlabel("Yawn count (within 3 min)", fontsize=10)
ax2.set_ylabel("Score (0–100)", fontsize=10)
ax2.set_title("② MAR Score (Yawn)", fontsize=12, fontweight="bold")
ax2.set_xticks(range(0, 9))
ax2.legend(fontsize=9)

# ── 3. EMA 스무딩 비교 ───────────────────────────────────────
ax3 = fig.add_subplot(gs[1, 0])
t = np.arange(0, 60, 1)
# 시뮬레이션: 20초에 급격히 점수가 오르는 상황
raw = np.where(t < 20, 10, np.where(t < 35, 70, 15)).astype(float)

ema_before = [raw[0]]
for r in raw[1:]:
    ema_before.append(BEFORE["ema"] * r + (1 - BEFORE["ema"]) * ema_before[-1])

ema_after = [raw[0]]
for r in raw[1:]:
    ema_after.append(AFTER["ema"] * r + (1 - AFTER["ema"]) * ema_after[-1])

ax3.fill_between(t, 0, raw, alpha=0.08, color="gray", label="Raw score")
ax3.step(t, raw, color="gray", linewidth=1.2, linestyle=":", where="post")
ax3.plot(t, ema_before, color=CLR_BEFORE, linewidth=2.2, linestyle="--",
         label=f"Before (α={BEFORE['ema']})")
ax3.plot(t, ema_after, color=CLR_AFTER, linewidth=2.5,
         label=f"After  (α={AFTER['ema']})")

# 경보 기준선
for y, label, color in [(40, "L0/L1 (40)", CLR_CAUTION),
                         (70, "L1/L2 (70)", CLR_WARNING)]:
    ax3.axhline(y, color=color, linestyle="--", linewidth=1.2, alpha=0.7)
    ax3.text(1, y + 1.5, label, fontsize=8, color=color)

ax3.set_xlim(0, 60); ax3.set_ylim(0, 95)
ax3.set_xlabel("Time (seconds)", fontsize=10)
ax3.set_ylabel("Drowsiness Score", fontsize=10)
ax3.set_title(f"③ EMA Smoothing  (Before α={BEFORE['ema']} → After α={AFTER['ema']})",
              fontsize=12, fontweight="bold")
ax3.legend(fontsize=9)

# ── 4. 히트맵 비교 (After 기준) ──────────────────────────────
ax4 = fig.add_subplot(gs[1, 1])
ear_vals = np.linspace(0, 100, 60)
mar_vals = np.linspace(0, 100, 60)
HEAD_FIXED = 20

Z = np.zeros((60, 60))
for i, m in enumerate(mar_vals):
    for j, e in enumerate(ear_vals):
        raw = W1_EAR * e + W2_MAR * m + W3_HEAD * HEAD_FIXED
        Z[i, j] = min(max(raw, 0), 100)

im = ax4.contourf(ear_vals, mar_vals, Z,
                  levels=[0, 40, 70, 85, 100],
                  colors=[CLR_NORMAL, CLR_CAUTION, CLR_WARNING, CLR_DANGER],
                  alpha=0.75)
ax4.contour(ear_vals, mar_vals, Z,
            levels=[40, 70, 85], colors="white", linewidths=1.2, linestyles="--")

# After 기준 실제 PERCLOS→score 값으로 축 눈금 표시
perclos_ticks = [0, 10, 20, 30, 45, 55, 65]
perclos_scores = [lerp_score(v, AFTER["perclos"]) for v in perclos_ticks]
ax4.set_xticks(perclos_scores)
ax4.set_xticklabels([f"{s:.0f}\n({p}%)" for s, p in zip(perclos_scores, perclos_ticks)],
                    fontsize=8)

mar_ticks = [0, 1, 2, 3, 5, 7]
mar_scores = [lerp_score(v, AFTER["mar"]) for v in mar_ticks]
ax4.set_yticks(mar_scores)
ax4.set_yticklabels([f"{s:.0f}\n({v}회)" for s, v in zip(mar_scores, mar_ticks)],
                    fontsize=8)

patches = [
    mpatches.Patch(color=CLR_NORMAL,  alpha=0.75, label="L0 Normal"),
    mpatches.Patch(color=CLR_CAUTION, alpha=0.75, label="L1 Caution"),
    mpatches.Patch(color=CLR_WARNING, alpha=0.75, label="L2 Warning"),
    mpatches.Patch(color=CLR_DANGER,  alpha=0.75, label="L3 Danger"),
]
ax4.legend(handles=patches, fontsize=9, loc="upper left")
ax4.set_xlabel("EAR Score  (PERCLOS % in parentheses)", fontsize=10)
ax4.set_ylabel("MAR Score  (Yawn count in parentheses)", fontsize=10)
ax4.set_title(f"④ Combined Heatmap — After\n(Head={HEAD_FIXED}, W1={W1_EAR} W2={W2_MAR} W3={W3_HEAD})",
              fontsize=11, fontweight="bold")

out_path = os.path.join(os.path.dirname(__file__), "thresholds.png")
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"[saved] {out_path}")
plt.show()
