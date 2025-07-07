import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter
import json, os, uuid

# ─────────────────────────────────────────────
# 0. 파라미터 저장/불러오기
# ─────────────────────────────────────────────
SETTING_FILE = "pipe_cutter_settings.json"

def load_settings():
    if os.path.exists(SETTING_FILE):
        with open(SETTING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"stock_len": 6000, "chuck_len": 300}

def save_settings(cfg):
    with open(SETTING_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

cfg = load_settings()

st.set_page_config(page_title="Pipe Cutter Optimizer", layout="wide")
st.title("Pipe Cutting Optimization (First‑Fit‑Decreasing)")

# ─────────────────────────────────────────────
# 1. 사이드바 – 파라미터 입력 & 저장
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("Base Parameters")
    stock_len = st.number_input("Stock Length (mm)", min_value=1, value=int(cfg["stock_len"]), step=10)
    chuck_len = st.number_input("Chuck Length (mm)", min_value=0, value=int(cfg["chuck_len"]), step=10)
    st.markdown(f"**Effective Length** = {stock_len - chuck_len} mm")

if (stock_len != cfg["stock_len"]) or (chuck_len != cfg["chuck_len"]):
    cfg["stock_len"], cfg["chuck_len"] = stock_len, chuck_len
    save_settings(cfg)

# ─────────────────────────────────────────────
# 2. 절단 리스트 입력 – 입력 에디터
# ─────────────────────────────────────────────
st.subheader("Cutting List Input")

if "cut_df" not in st.session_state:
    st.session_state.cut_df = pd.DataFrame(columns=["Length(mm)", "Qty"]).astype("object")

left, _ = st.columns([1, 8])
with left:
    if st.button("Reset List"):
        st.session_state.cut_df = pd.DataFrame(columns=["Length(mm)", "Qty"]).astype("object")
        st.session_state.tbl_key = str(uuid.uuid4())

tbl_key = st.session_state.get("tbl_key", "cut_editor")

editor_df = st.session_state.cut_df.reset_index(drop=True)
editor_df.index.name = None
edited_df = st.data_editor(
    editor_df,
    hide_index=True,
    num_rows="dynamic",
    column_config={
        "Length(mm)": st.column_config.NumberColumn(format="%d"),
        "Qty":        st.column_config.NumberColumn(format="%d"),
    },
    key=tbl_key,
    use_container_width=True,
)

# ─────────────────────────────────────────────
# 3. 계산 실행
# ─────────────────────────────────────────────
if st.button("Run Optimization", use_container_width=True):
    st.session_state.cut_df = edited_df.copy()

    df = st.session_state.cut_df.copy()
    df["Length(mm)"] = pd.to_numeric(df["Length(mm)"], errors="coerce")
    df["Qty"]        = pd.to_numeric(df["Qty"],        errors="coerce")
    df = df.dropna().astype(int)
    df = df[df["Qty"] > 0]

    if df.empty:
        st.warning("Please enter valid lengths and quantities.")
        st.stop()
    if stock_len <= chuck_len:
        st.error("Chuck length cannot be equal to or greater than stock length.")
        st.stop()

    # ── FFD 알고리즘
    pieces = [l for l, q in zip(df["Length(mm)"], df["Qty"]) for _ in range(q)]
    pieces.sort(reverse=True)
    eff_len = stock_len - chuck_len
    bars = []
    for p in pieces:
        for bar in bars:
            if bar["remain"] >= p:
                bar["cuts"].append(p)
                bar["remain"] -= p
                break
        else:
            bars.append({"cuts": [p], "remain": eff_len - p})

    # ── 패턴 묶기
    def pat_key(bar): return tuple(sorted(bar["cuts"], reverse=True))
    pattern_dict = Counter(pat_key(b) for b in bars)

    # ── 시각화
    st.subheader("Cutting Pattern Chart (by Pattern)")
    fig_height = 1 + 0.8 * len(pattern_dict)
    fig, ax = plt.subplots(figsize=(12, fig_height))

    ax.set_xlim(0, stock_len)
    ax.set_xlabel("mm")
    ax.invert_yaxis()
    ax.set_yticks([])
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    for idx, (pat, qty) in enumerate(pattern_dict.items()):
        cuts = list(pat)
        y = idx + 0.4
        cursor = 0
        color = colors[idx % len(colors)]
        for cut in cuts:
            ax.barh(y, cut, left=cursor, height=0.6, color=color)
            ax.text(cursor + cut / 2, y, str(cut), va="center", ha="center", color="white", fontsize=8)
            cursor += cut

        remain = eff_len - sum(cuts)
        if remain > 0:
            ax.barh(y, remain, left=cursor, height=0.6, color="dimgray")
            ax.text(cursor + remain / 2, y, str(remain), va="center", ha="center", color="white", fontsize=8)

        ax.barh(y, chuck_len, left=stock_len - chuck_len, height=0.6, color="lightgray")
        ax.text(-200, y, f"Pattern {idx + 1} × {qty}", va="center", ha="right", fontsize=10)

    ax.set_title("Cutting Pattern Summary (Quantities by Pattern)", fontsize=14)
    ax.axis("off")

    # ▶ 총 막대 수량 표시
    total_bars = sum(pattern_dict.values())
    ax.text(stock_len / 2, len(pattern_dict) + 0.8, f"TOTAL: {total_bars} bars",
            ha="center", va="center", fontsize=14, fontweight="bold", color="black")

    st.pyplot(fig)

    # ── 결과 테이블
    rows = []
    for i, (pat, qty) in enumerate(pattern_dict.items(), 1):
        used = sum(pat)
        remain = eff_len - used
        rows.append({
            "#": i,
            "Quantity": qty,
            "Cuts": ", ".join(map(str, pat)),
            "Used(mm)": used,
            "Remain(mm)": remain,
            "Waste(mm)": remain + chuck_len
        })
    result_df = pd.DataFrame(rows)

    st.subheader("Pattern Summary Table")
    st.dataframe(result_df, use_container_width=True)

    total_waste = sum(b["remain"] for b in bars) + chuck_len * len(bars)
    st.info(f"Total Bars: {len(bars)} | Total Waste: {total_waste} mm")

    # ── CSV 다운로드
    csv = result_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Download as CSV", csv, "cutting_patterns.csv", "text/csv")
