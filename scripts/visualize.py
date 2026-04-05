"""
Step 5~6: 시각화 + 상관관계 분석 + Lag 분석
Figure 1: LAI 시계열
Figure 2: RSSI 처리 방식별 4개 subplot (대표 링크: G<->GW, 9_to_3)
Figure 3: 환경보정 전/후 RSSI vs LAI 비교
Figure 4: 처리 방식별 LAI 산점도 + Pearson r
Figure 5: Lag 분석 (G<->GW, rssi_raw / rssi_ma7)
"""

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "figures"
OUT_DIR.mkdir(exist_ok=True)

lai = pd.read_csv(ROOT / "data" / "lai_daily.csv", parse_dates=["date"])
rssi = pd.read_csv(ROOT / "data" / "rssi_daily.csv", parse_dates=["date"])

# 생육 급증 구간
GROWTH_START = pd.Timestamp("2016-04-27")
GROWTH_END = pd.Timestamp("2016-05-20")

# 대표 링크
LINK_AGW = "9_to_1"  # A<->GW (3일치, 참고용)
LINK_GGW = "9_to_3"  # G<->GW (25일치, 주 분석)

feat_labels = {
    "rssi_raw": "Raw RSSI (daily mean)",
    "rssi_ma7": "7-day Moving Average",
    "rssi_delta": "Daily Delta",
    "rssi_std7": "7-day Rolling Std",
    "rssi_residual": "Env-corrected Residual",
}


def add_growth_shade(ax, alpha=0.12):
    ax.axvspan(
        GROWTH_START, GROWTH_END, color="green", alpha=alpha, label="Growth surge"
    )


def fmt_xaxis(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=0))


# ── Figure 1: LAI 시계열 ───────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 4))
ax.fill_between(
    lai["date"],
    lai["lai_median"] - lai["lai_std"],
    lai["lai_median"] + lai["lai_std"],
    alpha=0.25,
    color="steelblue",
    label="±1 std",
)
ax.plot(lai["date"], lai["lai_median"], color="steelblue", lw=1.8, label="LAI median")
add_growth_shade(ax)
ax.set_xlabel("Date")
ax.set_ylabel("LAI")
ax.set_title("Figure 1: Daily LAI Time Series (10–14h, 0 < LAI ≤ 8)")
ax.legend(fontsize=9)
fmt_xaxis(ax)
fig.tight_layout()
fig.savefig(OUT_DIR / "fig1_lai_timeseries.png", dpi=150)
plt.close(fig)
print("Figure 1 saved.")

# ── Figure 2: RSSI 처리 방식별 4개 subplot (대표: G<->GW) ─────────────────────
feats_fig2 = ["rssi_raw", "rssi_ma7", "rssi_delta", "rssi_std7"]
ggw = rssi[rssi["link"] == LINK_GGW].sort_values("date")

fig, axes = plt.subplots(4, 1, figsize=(10, 12), sharex=True)
for ax, feat in zip(axes, feats_fig2):
    sub = ggw.dropna(subset=[feat])
    ax2 = ax.twinx()
    ax2.plot(lai["date"], lai["lai_median"], color="gray", lw=1, alpha=0.4, label="LAI")
    ax2.set_ylabel("LAI", color="gray", fontsize=8)
    ax2.tick_params(axis="y", labelcolor="gray", labelsize=7)
    ax.plot(sub["date"], sub[feat], color="tomato", lw=1.5, label=feat_labels[feat])
    add_growth_shade(ax)
    ax.set_ylabel(feat_labels[feat], fontsize=8)
    ax.legend(loc="upper left", fontsize=8)
    fmt_xaxis(ax)

fig.suptitle(f"Figure 2: RSSI Feature Types - G<->GW link ({LINK_GGW})", fontsize=11)
axes[-1].set_xlabel("Date")
fig.tight_layout()
fig.savefig(OUT_DIR / "fig2_rssi_features.png", dpi=150)
plt.close(fig)
print("Figure 2 saved.")

# ── Figure 3: 환경보정 전/후 RSSI vs LAI ──────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
ggw_lai = ggw.dropna(subset=["rssi_raw", "rssi_residual", "lai_median"])

for ax, col, title in zip(
    axes,
    ["rssi_raw", "rssi_residual"],
    ["Before env-correction (rssi_raw)", "After env-correction (rssi_residual)"],
):
    x = ggw_lai["lai_median"]
    y = ggw_lai[col]
    r, p = stats.pearsonr(x, y)
    ax.scatter(x, y, color="steelblue", alpha=0.7, s=40)
    m, b = np.polyfit(x, y, 1)
    xr = np.linspace(x.min(), x.max(), 100)
    ax.plot(xr, m * xr + b, color="tomato", lw=1.5)
    ax.set_xlabel("LAI median")
    ax.set_ylabel(col)
    ax.set_title(f"{title}\nr = {r:.3f}, p = {p:.3f}", fontsize=9)

fig.suptitle(
    f"Figure 3: Env-correction Effect on RSSI vs LAI - {LINK_GGW}", fontsize=10
)
fig.tight_layout()
fig.savefig(OUT_DIR / "fig3_env_correction.png", dpi=150)
plt.close(fig)
print("Figure 3 saved.")

# ── Figure 4: 처리 방식별 산점도 + Pearson r ──────────────────────────────────
feats_fig4 = ["rssi_raw", "rssi_ma7", "rssi_delta", "rssi_std7", "rssi_residual"]
fig, axes = plt.subplots(1, 5, figsize=(16, 4))

for ax, feat in zip(axes, feats_fig4):
    sub = ggw.dropna(subset=[feat, "lai_median"])
    x = sub["lai_median"]
    y = sub[feat]
    if len(sub) >= 3:
        r, p = stats.pearsonr(x, y)
        ax.scatter(x, y, alpha=0.7, s=35, color="steelblue")
        m, b = np.polyfit(x, y, 1)
        xr = np.linspace(x.min(), x.max(), 100)
        ax.plot(xr, m * xr + b, color="tomato", lw=1.5)
        ax.set_title(f"{feat}\nr={r:.3f} (p={p:.2f})", fontsize=8)
    else:
        ax.set_title(f"{feat}\n(n<3)", fontsize=8)
    ax.set_xlabel("LAI median", fontsize=8)
    ax.set_ylabel(feat_labels[feat], fontsize=7)

fig.suptitle(f"Figure 4: RSSI Feature vs LAI Scatter - {LINK_GGW}", fontsize=10)
fig.tight_layout()
fig.savefig(OUT_DIR / "fig4_scatter.png", dpi=150)
plt.close(fig)
print("Figure 4 saved.")

# ── 상관관계 분석 ─────────────────────────────────────────────────────────────
print("\n[처리 방식별 상관관계 - G<->GW (9_to_3)]")
print(
    f"{'Feature':<22} {'Pearson r':>10} {'Pearson p':>10} {'Spearman r':>11} {'Spearman p':>11} {'n':>5}"
)
print("-" * 72)
for feat in feats_fig4:
    sub = ggw.dropna(subset=[feat, "lai_median"])
    n = len(sub)
    if n >= 3:
        pr, pp = stats.pearsonr(sub["lai_median"], sub[feat])
        sr, sp = stats.spearmanr(sub["lai_median"], sub[feat])
        print(f"{feat:<22} {pr:>10.3f} {pp:>10.3f} {sr:>11.3f} {sp:>11.3f} {n:>5}")
    else:
        print(f"{feat:<22} {'n<3':>10}")

print("\n[처리 방식별 상관관계 - A<->GW (9_to_1, 참고용)]")
agw = rssi[rssi["link"] == LINK_AGW].sort_values("date")
print(
    f"{'Feature':<22} {'Pearson r':>10} {'Pearson p':>10} {'Spearman r':>11} {'Spearman p':>11} {'n':>5}"
)
print("-" * 72)
for feat in feats_fig4:
    sub = agw.dropna(subset=[feat, "lai_median"])
    n = len(sub)
    if n >= 3:
        pr, pp = stats.pearsonr(sub["lai_median"], sub[feat])
        sr, sp = stats.spearmanr(sub["lai_median"], sub[feat])
        print(f"{feat:<22} {pr:>10.3f} {pp:>10.3f} {sr:>11.3f} {sp:>11.3f} {n:>5}")
    else:
        print(f"{feat:<22} {'n<3':>10}")

# ── Figure 5: Lag 분석 (G<->GW) ───────────────────────────────────────────────
LAG_FEATS = ["rssi_raw", "rssi_ma7"]
lags = range(-7, 8)

fig, axes = plt.subplots(1, 2, figsize=(12, 4))

for ax, feat in zip(axes, LAG_FEATS):
    rs, ps, ns = [], [], []
    base = ggw[["date", feat]].dropna().copy()
    for lag in lags:
        shifted = base.copy()
        shifted["date"] = shifted["date"] + pd.Timedelta(days=lag)
        merged = shifted.merge(lai[["date", "lai_median"]], on="date", how="inner")
        n = len(merged)
        ns.append(n)
        if n >= 3:
            r, p = stats.pearsonr(merged["lai_median"], merged[feat])
            rs.append(r)
            ps.append(p)
        else:
            rs.append(np.nan)
            ps.append(np.nan)

    rs = np.array(rs)
    ps = np.array(ps)
    best_idx = np.nanargmax(np.abs(rs))
    best_lag = list(lags)[best_idx]

    ax.bar(
        list(lags),
        rs,
        color=["tomato" if i == best_idx else "steelblue" for i in range(len(lags))],
        alpha=0.8,
    )
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(best_lag, color="tomato", lw=1.2, linestyle="--", alpha=0.6)
    ax.set_xlabel("Lag (days, positive = RSSI leads LAI)")
    ax.set_ylabel("Pearson r")
    ax.set_title(
        f"{feat_labels[feat]}\nbest lag = {best_lag}d (r={rs[best_idx]:.3f}, n={ns[best_idx]})",
        fontsize=9,
    )
    ax.set_xticks(list(lags))

    # 표 출력
    print(f"\n[Lag 분석 - {feat} / G<->GW (9_to_3)]")
    print(f"{'lag':>5} {'r':>8} {'p':>8} {'n':>5}")
    for lag, r, p, n in zip(lags, rs, ps, ns):
        marker = " <-- best" if lag == best_lag else ""
        r_str = f"{r:.3f}" if not np.isnan(r) else "  nan"
        p_str = f"{p:.3f}" if not np.isnan(p) else "  nan"
        print(f"{lag:>5} {r_str:>8} {p_str:>8} {n:>5}{marker}")

fig.suptitle(
    f"Figure 5: Lag Analysis - G<->GW ({LINK_GGW})\n"
    "[Note: n=25, ground-above link only - interpret with caution]",
    fontsize=10,
)
fig.tight_layout()
fig.savefig(OUT_DIR / "fig5_lag_analysis.png", dpi=150)
plt.close(fig)
print("\nFigure 5 saved.")
print(
    "\n[주의] Lag 분석은 G<->GW 25일치 기반. 표본 부족으로 결과 해석 시 한계 명시 필요."
)
