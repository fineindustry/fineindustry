import streamlit as st
import pandas as pd
import re
import math
from collections import defaultdict

# ─────────────────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────────────────
st.set_page_config(page_title="견적 요청 자동 생성기", page_icon="📄")
st.title("📄 시트판 + 파이프 + C형강/ㄷ형강 견적 요청 자동 생성")
st.markdown("품명, 수량, 단위(EA 또는 kg)만 입력하면 자동으로 견적 요청 문장이 생성됩니다.")

# ─────────────────────────────────────────────────────────
# 1) C형강 / ㄷ형강 무게표 (10m 기준, kg)
# ─────────────────────────────────────────────────────────
weights = {
    "C형강": {
        "60×30×10×1.6": 16.3,
        "60×30×10×2.0": 19.9,
        "60×30×10×2.3": 22.5,
        "75×45×15×1.6": 23.2,
        "75×45×15×2.0": 28.6,
        "75×45×15×2.3": 32.5,
        "75×45×20×2.0": 35.6,
        "75×45×20×2.3": 40.6,
        "100×50×20×1.6": 28.8,
        "100×50×20×2.0": 35.6,
        "100×50×20×2.3": 40.6,
        "100×50×20×2.6": 45.5,
        "100×50×20×3.2": 55.0,
        "125×50×20×2.0": 39.5,
        "125×50×20×2.3": 45.1,
        "125×50×20×3.2": 61.3,
        "150×50×20×3.2": 67.6,
        "150×65×20×3.2": 75.1,
        "150×65×20×4.0": 92.2,
        "150×65×20×4.5": 103.0,
        "150×75×20×3.2": 82.7,
        "200×75×20×3.2": 92.7,
        "200×75×20×4.0": 127.0,
        "200×75×20×4.5": 140.0,
        "200×75×25×3.2": 95.2,
        "200×75×25×4.0": 117.0,
        "200×75×25×4.5": 131.0,
        "200×80×20×4.0": 133.0,
        "200×80×20×4.5": 149.0
    },
    "ㄷ형강": {
        "75×40 (5.0/7.0)": 69.2,
        "100×50 (5.0/7.5)": 93.6,
        "125×65 (6.0/8.0)": 134.0,
        "150×75 (6.5/10.0)": 186.0,
        "150×75 (9.0/12.5)": 240.0,
        "200×80 (7.5/11.0)": 246.0,
        "200×90 (8.0/13.5)": 303.0,
        "250×90 (9.0/13.0)": 346.0,
        "250×90 (11.0/14.5)": 402.0,
        "300×90 (9.0/13.0)": 381.0,
        "300×90 (10.0/15.5)": 438.0,
        "300×90 (12.0/16.0)": 486.0,
        "380×100 (10.5/16.0)": 545.0,
        "380×100 (13.0/16.5)": 620.0,
        "380×100 (13.0/20.0)": 673.0
    }
}

# ─────────────────────────────────────────────────────────
# 2) 스펙 추출 함수
# ─────────────────────────────────────────────────────────
def extract_spec(name: str, form: str) -> str:
    # 공백 제거 · 대문자 통일 · ascii x, X, * → 유니코드 × 로 치환
    nm = name.upper().replace(" ", "")
    nm = nm.replace("X", "×").replace("x", "×").replace("*", "×")

    if form == "C형강":
        m = re.search(
            r"(\d+(?:\.\d+)?)[×](\d+(?:\.\d+)?)[×](\d+(?:\.\d+)?)[×](\d+(?:\.\d+)?)[tT]?",
            nm
        )
        if m:
            return f"{m.group(1)}×{m.group(2)}×{m.group(3)}×{m.group(4)}"

    elif form == "ㄷ형강":
        # ── ① 괄호 없는 네 숫자 (예: 100×50×5×7.5t) ──
        tmp = re.sub(r"[tT]", "", nm)
        m1 = re.search(
            r"(\d+(?:\.\d+)?)[×](\d+(?:\.\d+)?)[×](\d+(?:\.\d+)?)[×](\d+(?:\.\d+)?)",
            tmp
        )
        if m1:
            d1, d2, v1, v2 = m1.groups()
            return f"{d1}×{d2} ({float(v1):.1f}/{float(v2):.1f})"

        # ── ② 기존 괄호+슬래시 패턴 ──
        m2 = re.search(
            r"(\d+(?:\.\d+)?)[×](\d+(?:\.\d+)?)[(](\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)[)]",
            nm
        )
        if m2:
            return f"{m2.group(1)}×{m2.group(2)} ({float(m2.group(3)):.1f}/{float(m2.group(4)):.1f})"

    elif form == "원형파이프":
        m = re.search(
            r"Ø?(\d+(?:\.\d+)?)[×](\d+(?:\.\d+)?)[tT]?",
            nm
        )
        if m:
            return f"Ø{m.group(1)}×{m.group(2)}"

    elif form == "각파이프":
        m = re.search(
            r"(\d+(?:\.\d+)?)[×](\d+(?:\.\d+)?)(?:[×](\d+(?:\.\d+)?))?",
            nm
        )
        if m:
            parts = [m.group(1), m.group(2)]
            if m.group(3):
                parts.append(m.group(3))
            return "×".join(parts)

    # 시트판 패턴은 기존 코드 그대로 처리
    return None

# ─────────────────────────────────────────────────────────
# 3) 중량 계산 보조 함수
# ─────────────────────────────────────────────────────────
def calc_round_pipe_weight(d_mm: float, t_mm: float, length_mm: float) -> float:
    density = 7.85e-6
    id_mm = d_mm - 2 * t_mm
    if id_mm <= 0:
        return 0.0
    cross = math.pi/4 * (d_mm**2 - id_mm**2)
    return round(cross * length_mm * density, 2)

def calc_rect_pipe_weight(w_mm: float, h_mm: float, t_mm: float, length_mm: float) -> float:
    density = 7.85e-6
    inner_w = w_mm - 2 * t_mm
    inner_h = h_mm - 2 * t_mm
    if inner_w <= 0 or inner_h <= 0:
        return 0.0
    cross = (w_mm * h_mm) - (inner_w * inner_h)
    return round(cross * length_mm * density, 2)

def extract_dimensions(name: str):
    # ① 공백 제거 · 대문자 통일
    nm = name.upper().replace(" ", "")
    # ② ascii x/X/* 문자를 유니코드 × 로 통일
    nm = nm.replace("X", "×").replace("x", "×").replace("*", "×")

    # ③ 'T×폭×길이' 패턴 매칭
    m = re.search(r"(\d+(?:\.\d+)?)T×(\d+(?:\.\d+)?)[×](\d+(?:\.\d+)?)", nm)
    if m:
        return float(m.group(1)), float(m.group(2)), float(m.group(3))
    return None, None, None


def calc_sheet_weight(t: float, w: float, l: float) -> float:
    return round(t * w * l * 7.85 / 1_000_000, 2)

def calculate_weight(form: str, spec: str) -> float:
    # ① 테이블 우선
    if form in weights and spec in weights[form]:
        return weights[form][spec]
    # ② 원형파이프 (6m)
    if form == "원형파이프" and spec:
        d, t = map(float, spec.replace("Ø", "").split("×"))
        return calc_round_pipe_weight(d, t, 6000)
    # ③ 각파이프 (6m)
    if form == "각파이프" and spec:
        parts = list(map(float, spec.split("×")))
        return calc_rect_pipe_weight(parts[0], parts[1], parts[2] if len(parts) > 2 else 0, 6000)
    return None

# ─────────────────────────────────────────────────────────
# 4) 분류 & 공급처
# ─────────────────────────────────────────────────────────
def classify_form(name: str) -> str:
    nm = name.upper()
    if "C형강" in nm:
        return "C형강"
    if "ㄷ형강" in nm:
        return "ㄷ형강"
    if any(k in nm for k in ["각파이프", "각관"]):
        return "각파이프"
    if any(k in nm for k in ["원형파이프", "Ø"]):
        return "원형파이프"
    if "시트판" in nm:
        return "시트판"
    return "기타"

def classify_type(name: str) -> str:
    nm = name.upper()
    if "HR" in nm or "HGI" in nm:
        return "HR"
    if "CR" in nm or "EGI" in nm:
        return "CR"
    return "기타"

def get_vendors(form: str, mat: str, name: str) -> list:
    s = name.replace("x", "×").upper()
    if form in ["각파이프", "원형파이프"] and any(x in s for x in ["27×70", "70×27"]):
        return ["경안파이프"]
    if form in ["C형강", "ㄷ형강"]:
        v = ["백산철강", "태강스틸"]
        if mat == "HR":
            v.append("유민철강")
        return v
    if form in ["각파이프", "원형파이프"]:
        v = ["백산철강", "태강스틸"]
        if mat == "HR":
            v.append("유민철강")
        return v
    if form == "시트판":
        return (["문배철강", "태창철강", "지오스틸", "경북코일센터", "신영스틸", "성주에스티"]
                if mat == "HR"
                else ["금강철강", "창화철강", "기보스틸", "영진철강", "애니스틸"])
    return []

# ─────────────────────────────────────────────────────────
# 5) DataEditor 설정
# ─────────────────────────────────────────────────────────
sample = pd.DataFrame({
    "품명": [
        "150×75×20×3.2 C형강", "Ø25.4×2.3 원형파이프",
        "시트판 1.0T×1220×2440 CR", "CR 1.2T 코일",
        "100x50x5x7.5t ㄷ형강"
    ],
    "수량": [10, 300, 10, 500, 4],
    "단위": ["ea", "kg", "ea", "kg", "ea"]
})

edited = st.data_editor(
    sample,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "단위": st.column_config.SelectboxColumn(
            label="단위",
            options=["ea", "kg"]
        )
    }
)


# ─────────────────────────────────────────────────────────
# 6) 계산 & 그룹핑
# ─────────────────────────────────────────────────────────
vendor_to_items = defaultdict(list)
item_to_text = {}

for _, row in edited.iterrows():
    name = str(row["품명"]).strip()
    if not name:
        continue

    qty_raw, unit_raw = row["수량"], row["단위"]
    if pd.isna(qty_raw) or pd.isna(unit_raw):
        continue
    unit = str(unit_raw).lower()
    if unit not in ("ea", "kg"):
        continue
    try:
        qty = float(qty_raw)
    except:
        continue

    form = classify_form(name)
    mat  = classify_type(name)
    spec = extract_spec(name, form)
    wt   = 0.0

    if form == "시트판":
        t, w, l = extract_dimensions(name)
        if t and w and l:
            wt = calc_sheet_weight(t, w, l)
            if unit == "kg":
                total = qty
                pcs = int(round(total / wt)) if wt else 0
            else:
                pcs = int(qty)
                total = round(pcs * wt, 2)
        else:
            pcs, total = 0, 0.0
    else:
        w_calc = calculate_weight(form, spec)
        if w_calc is not None:
            wt = w_calc
            if unit == "kg":
                total = qty
                pcs = int(round(total / wt)) if wt else 0
            else:
                pcs = int(qty)
                total = round(pcs * wt, 2)
        else:
            st.warning(f"'{name}'의 중량을 찾을 수 없습니다.")
            pcs, total = 0, 0.0

    item_to_text[name] = f"{name} {pcs}EA (총 {total}kg)"
    for v in get_vendors(form, mat, name):
        vendor_to_items[v].append(name)

# ─────────────────────────────────────────────────────────
# 7) 출력
# ─────────────────────────────────────────────────────────
grouped = defaultdict(list)
for v, items in vendor_to_items.items():
    key = tuple(sorted(set(items)))
    grouped[key].append(v)

for i, (item_grp, vend_list) in enumerate(grouped.items()):
    st.subheader(f"📨 견적 요청 - {', '.join(vend_list)}")
    lines = [item_to_text[x] for x in item_grp]
    msg   = "안녕하세요.\n" + "\n".join(lines) + "\n재고 및 견적 요청드립니다."
    st.text_area("견적 요청 내용", msg, height=200, key=f"msg_{i}")
