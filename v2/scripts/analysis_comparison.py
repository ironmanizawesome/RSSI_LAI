"""
세션 4: 환경변수 보정 방식 A/B/C 비교 분석
방식 A: 보정 없음 (raw RSSI vs LAI, Pearson r)
방식 B: OLS 잔차 (rssi_residual vs LAI, Pearson r)
방식 C: 다중회귀 공변량 (LAI ~ RSSI + T + AH, statsmodels OLS)
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

V2_ROOT = Path(__file__).parent.parent
DATA_DIR = V2_ROOT / "data"

df = pd.read_csv(DATA_DIR / "features_merged.csv", parse_dates=["date"])

# 분석 가능 행: 모든 컬럼 non-null
analysis_cols = [
    "lai_median", "rssi_raw", "rssi_ma7", "rssi_delta",
    "rssi_std7", "rssi_residual", "temp_mean", "ah_mean",
]
df_clean = df.dropna(subset=analysis_cols).copy()
n = len(df_clean)
print(f"분석 가능 행: {n}행")
print(f"기간: {df_clean['date'].min().date()} ~ {df_clean['date'].max().date()}\n")

results = []

# ── 방식 A: 보정 없음 ─────────────────────────────────────────────────────────
print("=" * 60)
print("방식 A: 보정 없음 (Pearson r)")
print("=" * 60)
for feat in ["rssi_raw", "rssi_ma7", "rssi_delta", "rssi_std7"]:
    sub = df_clean[["lai_median", feat]].dropna()
    n_sub = len(sub)
    r, p = stats.pearsonr(sub[feat], sub["lai_median"])
    sig = "유의" if p <= 0.05 else "비유의"
    print(f"  {feat:20s}  r={r:+.3f}  p={p:.4f}  n={n_sub}  [{sig}]")
    results.append({"방식": "A", "RSSI입력": feat, "지표": "Pearson r",
                    "값": round(r, 4), "p_value": round(p, 4), "n": n_sub})

# ── 방식 B: OLS 잔차 ──────────────────────────────────────────────────────────
print()
print("=" * 60)
print("방식 B: 야간 OLS 잔차 (Pearson r)")
print("=" * 60)
sub = df_clean[["lai_median", "rssi_residual"]].dropna()
n_sub = len(sub)
r, p = stats.pearsonr(sub["rssi_residual"], sub["lai_median"])
sig = "유의" if p <= 0.05 else "비유의"
print(f"  {'rssi_residual':20s}  r={r:+.3f}  p={p:.4f}  n={n_sub}  [{sig}]")
results.append({"방식": "B", "RSSI입력": "rssi_residual", "지표": "Pearson r",
                "값": round(r, 4), "p_value": round(p, 4), "n": n_sub})

# ── 방식 C: 다중회귀 공변량 ───────────────────────────────────────────────────
print()
print("=" * 60)
print("방식 C: 다중회귀 (LAI ~ RSSI + T + AH)")
print("=" * 60)

for feat in ["rssi_raw", "rssi_ma7"]:
    sub = df_clean[["lai_median", feat, "temp_mean", "ah_mean"]].dropna()
    n_sub = len(sub)

    X = sm.add_constant(sub[[feat, "temp_mean", "ah_mean"]])
    y = sub["lai_median"]
    model = sm.OLS(y, X).fit()

    r2 = model.rsquared
    adj_r2 = model.rsquared_adj
    f_p = model.f_pvalue
    coef_p = model.pvalues[feat]
    sig = "유의" if f_p <= 0.05 else "비유의"

    print(f"\n  [{feat}]  n={n_sub}")
    print(f"  R²={r2:.4f}  adj R²={adj_r2:.4f}  F-test p={f_p:.4f}  [{sig}]")
    print(f"  계수:")
    for var in model.params.index:
        print(f"    {var:20s}  β={model.params[var]:+.4f}  p={model.pvalues[var]:.4f}")

    # VIF 계산
    X_vif = sub[[feat, "temp_mean", "ah_mean"]].copy()
    vif_vals = {}
    for i, col in enumerate(X_vif.columns):
        X_arr = sm.add_constant(X_vif.values)
        vif = variance_inflation_factor(X_arr, i + 1)
        vif_vals[col] = vif
    print(f"  VIF: " + ", ".join([f"{k}={v:.1f}" for k, v in vif_vals.items()]))
    vif_warn = [k for k, v in vif_vals.items() if v > 10]
    if vif_warn:
        print(f"  ⚠️  VIF > 10: {vif_warn} → 다중공선성 주의, RSSI 계수 해석 신중히")

    results.append({"방식": "C", "RSSI입력": feat, "지표": "R²",
                    "값": round(r2, 4), "p_value": round(f_p, 4), "n": n_sub})
    results.append({"방식": "C", "RSSI입력": feat, "지표": "adj_R²",
                    "값": round(adj_r2, 4), "p_value": round(coef_p, 4), "n": n_sub})

# ── 비교표 출력 및 저장 ───────────────────────────────────────────────────────
print()
print("=" * 60)
print("비교표")
print("=" * 60)
result_df = pd.DataFrame(results)
print(result_df.to_string(index=False))
result_df.to_csv(DATA_DIR / "comparison_results.csv", index=False)
print(f"\ncomparison_results.csv 저장 완료")

# ── 해석 ─────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("해석 (CLAUDE_v2.md 가이드 기준)")
print("=" * 60)

# 방식별 대표 값 추출
r_A_raw = next(r["값"] for r in results if r["방식"] == "A" and r["RSSI입력"] == "rssi_raw")
p_A_raw = next(r["p_value"] for r in results if r["방식"] == "A" and r["RSSI입력"] == "rssi_raw")
r_A_ma7 = next(r["값"] for r in results if r["방식"] == "A" and r["RSSI입력"] == "rssi_ma7")
p_A_ma7 = next(r["p_value"] for r in results if r["방식"] == "A" and r["RSSI입력"] == "rssi_ma7")
r_B = next(r["값"] for r in results if r["방식"] == "B")
p_B = next(r["p_value"] for r in results if r["방식"] == "B")
r2_C_raw = next(r["값"] for r in results if r["방식"] == "C" and r["RSSI입력"] == "rssi_raw" and r["지표"] == "R²")
p_C_raw = next(r["p_value"] for r in results if r["방식"] == "C" and r["RSSI입력"] == "rssi_raw" and r["지표"] == "R²")
r2_C_ma7 = next(r["값"] for r in results if r["방식"] == "C" and r["RSSI입력"] == "rssi_ma7" and r["지표"] == "R²")
p_C_ma7 = next(r["p_value"] for r in results if r["방식"] == "C" and r["RSSI입력"] == "rssi_ma7" and r["지표"] == "R²")
n_main = next(r["n"] for r in results if r["방식"] == "A" and r["RSSI입력"] == "rssi_raw")

def sig_str(p):
    return "유의(p≤0.05)" if p <= 0.05 else "비유의(p>0.05)"

print(f"""
방식 A (보정 없음):
  rssi_raw vs LAI: r={r_A_raw:+.3f}, {sig_str(p_A_raw)}, n={n_main}
  rssi_ma7 vs LAI: r={r_A_ma7:+.3f}, {sig_str(p_A_ma7)}, n={n_main}

방식 B (야간 OLS 잔차):
  rssi_residual vs LAI: r={r_B:+.3f}, {sig_str(p_B)}, n={n_main}

방식 C (다중회귀 공변량):
  rssi_raw 모델: R²={r2_C_raw:.4f}, {sig_str(p_C_raw)}, n={n_main}
  rssi_ma7 모델: R²={r2_C_ma7:.4f}, {sig_str(p_C_ma7)}, n={n_main}
""")
