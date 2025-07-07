import streamlit as st
import pandas as pd
import pulp
import re
from itertools import combinations

st.set_page_config(page_title="코일 품명 파서 및 슬리팅 최적화", layout="wide")
st.title("🧾 품명 자동 파싱 + 🔧 슬리팅 최적화")

# 🔧 파싱 함수 정의 (LOSS 제외)
def parse_name_final(name: str):
    name = name.strip().upper()
    if name.startswith("LOSS"):
        return None, None
    match = re.search(r'(\d+(?:\.\d+)?)[Tt]?[xX×](\d+(?:\.\d+)?)', name)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None, None

# 📋 주문 리스트 입력
st.subheader("1️⃣ 주문 리스트")
orders_raw = pd.DataFrame(columns=["name"])
orders_raw = st.data_editor(orders_raw, num_rows="dynamic", key="orders_raw")
orders = pd.DataFrame()
if not orders_raw.empty:
    orders_raw["name"] = orders_raw["name"].astype(str)
    parsed = orders_raw["name"].apply(parse_name_final)
    orders = pd.DataFrame(parsed.tolist(), columns=["thickness", "width"])
    orders = orders.dropna()
    orders["demand"] = 1
    orders["thk_id"] = (orders["thickness"] * 1000).round().astype(int)
    st.dataframe(orders, use_container_width=True)

# 📋 Filler 리스트 입력
st.subheader("2️⃣ Filler 리스트")
fillers_raw = pd.DataFrame(columns=["name"])
fillers_raw = st.data_editor(fillers_raw, num_rows="dynamic", key="fillers_raw")
fillers = pd.DataFrame()
if not fillers_raw.empty:
    fillers_raw["name"] = fillers_raw["name"].astype(str)
    parsed = fillers_raw["name"].apply(parse_name_final)
    fillers = pd.DataFrame(parsed.tolist(), columns=["thickness", "width"])
    fillers = fillers.dropna()
    fillers["thk_id"] = (fillers["thickness"] * 1000).round().astype(int)
    st.dataframe(fillers, use_container_width=True)

# 📋 LOT 리스트 입력
st.subheader("3️⃣ LOT 리스트")
lot_raw = pd.DataFrame(columns=["LOT_NO", "weight", "vendor"])
lot_raw = st.data_editor(lot_raw, num_rows="dynamic", key="lot_raw")
stock = pd.DataFrame()
if not lot_raw.empty:
    try:
        lot_raw["weight"] = lot_raw["weight"].astype(str).str.replace(",", "").astype(float)
        tok1 = lot_raw["LOT_NO"].str.split().str[0]
        tok2 = lot_raw["LOT_NO"].str.split().str[1]
        mt = tok1.str.extract(r"([A-Z]+)(\d+)")
        stock = pd.DataFrame({
            "coil_id": lot_raw["LOT_NO"],
            "vendor": lot_raw["vendor"],
            "thickness": (mt[1].astype(int) / 100).round(2),
            "width": tok2.str.extract(r"(\d{3,4})")[0].astype(int),
            "weight": lot_raw["weight"],
            "qty": 1
        })
        stock["thk_id"] = (stock["thickness"] * 1000).round().astype(int)
        st.dataframe(stock, use_container_width=True)
    except:
        st.warning("❗ LOT_NO 파싱 오류")
else:
    st.info("📝 위에 LOT_NO를 입력해주세요 (예: SPCC750 1250)")

# 최적화 관련 함수들
def match_thk(df, thk_id):
    if thk_id in (750, 800):
        return df[df["thk_id"].isin([750, 800])]
    return df[df["thk_id"] == thk_id]

def best_fill(remain, slots):
    combs = []
    for r in range(1, len(slots)+1):
        for c in combinations(slots, r):
            s = sum(c)
            if s <= remain:
                combs.append((c, remain - s))
    combs.append(((), remain))
    return sorted(combs, key=lambda x: x[1])

def gen_preview(w, ords, fills, N=5):
    pats = []
    L = len(ords)
    for w0 in ords:
        if w0 <= w:
            bf = best_fill(w - w0, fills)
            total = w0 + sum(bf[0][0])
            waste = w - total
            pats.append(([w0] + list(bf[0][0]), waste))
    for k in range(L, 1, -1):
        for cmb in combinations(ords, k):
            t = sum(cmb)
            if t <= w:
                bf = best_fill(w - t, fills)
                for c, _ in bf[:N]:
                    total = t + sum(c)
                    waste = w - total
                    pats.append((list(cmb) + list(c), waste))
    seen, uni = set(), []
    for s, l in pats:
        key = tuple(sorted(s))
        if key not in seen:
            seen.add(key)
            uni.append((s, l))
    uni.sort(key=lambda x: x[1])
    return uni[:N * 2]  # 다양한 옵션 확보

# 📊 최적화 실행
st.subheader("4️⃣ 최적화 실행")
if st.button("▶ 슬리팅 최적화 시작"):
    if orders.empty or stock.empty:
        st.error("❌ 주문 또는 재고 없음")
        st.stop()

    results_all = []
    for thk, grp in stock.groupby("thk_id"):
        df_o = match_thk(orders, thk)
        if df_o.empty:
            continue

        demands = df_o.groupby("width")["demand"].sum().to_dict()
        wids = sorted(demands)
        all_patterns = {}
        waste_dict = {}

        for _, row in grp.iterrows():
            coil_id = row["coil_id"]
            cw = int(row["width"])
            ord_ws = [wid for wid in wids if wid <= cw]
            fills = match_thk(fillers, thk)["width"].tolist()
            raw = gen_preview(cw, ord_ws, fills, N=5)
            vecs = []
            waste_vals = []
            for slots, _ in raw:
                count_dict = {w: 0 for w in wids}
                for s in slots:
                    if s in count_dict:
                        count_dict[s] += 1
                vec = [count_dict[w] for w in wids]
                vecs.append(vec)
                used_width = sum(slots)
                true_waste = cw - used_width
                waste_vals.append(true_waste)
            all_patterns[coil_id] = vecs
            waste_dict[coil_id] = waste_vals

        if not all_patterns:
            st.warning(f"🔸 두께 {thk/1000}t에 유효 패턴 없음")
            continue

        model = pulp.LpProblem(f"Cut_{thk}", pulp.LpMinimize)
        x = {}
        for coil_id, pats in all_patterns.items():
            for p_idx in range(len(pats)):
                x[(coil_id, p_idx)] = pulp.LpVariable(f"x_{coil_id}_{p_idx}", cat="Binary")

        model += pulp.lpSum(waste_dict[coil_id][p] * x[(coil_id, p)]
                            for coil_id in all_patterns
                            for p in range(len(all_patterns[coil_id])))

        for coil_id, pats in all_patterns.items():
            model += pulp.lpSum(x[(coil_id, p)] for p in range(len(pats))) <= 1

        for j, w in enumerate(wids):
            model += pulp.lpSum(
                all_patterns[coil_id][p][j] * x[(coil_id, p)]
                for coil_id in all_patterns
                for p in range(len(all_patterns[coil_id]))
            ) >= int(demands[w])

        status = model.solve(pulp.PULP_CBC_CMD(msg=False))
        if pulp.LpStatus[status] != "Optimal":
            st.warning(f"❌ 두께 {thk/1000}t 최적화 실패")
            continue

        for (coil_id, p_idx), var in x.items():
            if var.value() > 0.5:
                pat = all_patterns[coil_id][p_idx]
                waste = waste_dict[coil_id][p_idx]
                slot_desc = [f"{w}×{pat[i]}" for i, w in enumerate(wids) if pat[i] > 0]
                results_all.append({
                    "thickness": thk / 1000,
                    "coil": coil_id,
                    "pattern": "+".join(slot_desc),
                    "waste": round(waste, 1)
                })

    if not results_all:
        st.warning("최적화 결과 없음")
    else:
        df_res = pd.DataFrame(results_all)
        st.success("✅ 최적화 완료")
        st.dataframe(df_res, use_container_width=True)
        st.download_button(
            "📥 다운로드 (CSV)",
            df_res.to_csv(index=False).encode("utf-8-sig"),
            "cutting_plan.csv",
            "text/csv"
        )
