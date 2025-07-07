
import streamlit as st
import pandas as pd
import re, json, os
from datetime import datetime, timedelta
import streamlit.components.v1 as components

st.set_page_config(page_title="인보이스 품명 번역기 + 협조전", page_icon="📄", layout="wide")
st.title("📄 인보이스 품명 자동 생성기 + 협조전")

CFG_FILE = "config.json"
DEFAULT_CFG = {
    "beneficiary": "Feihong Dayuan (Tianjin) Trading Co., Ltd",
    "account_number": "02040014040007406",
    "bank": "Tianjin Beichen Branch of Agricultural Bank of China Co., Ltd.",
    "swift": "ABOCCNBJ020",
    "container": "40'피트 1대",
    "bank_address": (
        "27H, West Zone, Tianjin Ruijing International Shoes City,\n"
        "No. 778 Longquan Road, Chenchang Road,\n"
        "Ruijing Subdistrict, Beichen District, Tianjin, China"
    )
}
if os.path.exists(CFG_FILE):
    cfg = json.load(open(CFG_FILE, encoding="utf-8"))
    cfg = {**DEFAULT_CFG, **cfg}
else:
    cfg = DEFAULT_CFG.copy()

def save_cfg():
    json.dump(cfg, open(CFG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

SIZE_RE = re.compile(r"(\d{2,4})\s*[＊*×xX]\s*(\d{2,4})")
DATE_RE = re.compile(r"([A-Z][a-z]{2})\.?(\d{1,2})th,?\s*(\d{4})")

def safe_int(v):
    try:
        return int(float(str(v).replace(",", "").strip()))
    except Exception:
        return None

def eval_int(v):
    try:
        return int(eval(str(v).replace("=", "").strip()))
    except Exception:
        return safe_int(v)

def extract_size(s):
    m = SIZE_RE.search(s)
    return f"{m.group(1)}x{m.group(2)}" if m else ""

def make_kor(cn, size, ratio):
    base = "FM슬림곤도라" if ratio == 8 else "FM곤도라"
    color = "무도장" if "本色" in cn else ("다크그레이" if ratio == 8 else "딥그레이")
    sub = re.search(r"[（(](.+?)[）)]", cn)
    sub = sub.group(1) if sub else ""
    mids = {
        "中层板": "중선반", "底层板": "밑선반", "END·中": "END라운드중선반",
        "END·底": "END라운드밑선반", "下连杆": "하연결대", "前罩": "앞장", "安全销": "안전핀",
    }
    mid = next((mids[k] for k in mids if k in sub), "기타")
    return f"{base} {mid}{(' ' + size) if size else ''} {color}".replace("*", "x").strip()

def infer_cols(df: pd.DataFrame) -> pd.DataFrame:
    cmap = {}
    for c in df.columns:
        s = df[c].astype(str).head(10)
        if any(SIZE_RE.search(v) for v in s):
            cmap[c] = "규격"
        elif any("SHELF" in v.upper() for v in s):
            cmap[c] = "품명"
        elif s.str.fullmatch(r"\d{1,6}").all():
            if "Package" not in cmap.values():
                cmap[c] = "Package"
            elif "Pieces" not in cmap.values():
                cmap[c] = "Pieces"
    df.rename(columns=cmap, inplace=True)
    if "규격" not in df.columns:
        df["규격"] = df.apply(
            lambda r: next((extract_size(str(v)) for v in r.values if isinstance(v, str) and SIZE_RE.search(v)), ""),
            axis=1,
        )
    return df

def run(df: pd.DataFrame):
    df = infer_cols(df.applymap(lambda x: x.strip() if isinstance(x, str) else x))
    kor_list, qty, usd, ship_date = [], 0, 0.0, None

    for _, row in df.iterrows():
        row_join = " ".join(str(v) for v in row.values if isinstance(v, str))
        if "Sailing on" in row_join:
            m = DATE_RE.search(row_join)
            if m:
                mon, day, yr = m.groups()
                ship_date = datetime.strptime(f"{yr}-{mon}-{day}", "%Y-%b-%d").date()
            continue

        if str(row.get("Item", "")).upper().startswith(("TOTAL", "소계", "합계")):
            try:
                usd = float(str(row.dropna().iloc[-1]).replace(",", ""))
            except Exception:
                pass
            continue

        desc = str(row.get("품명", "")).strip()
        if not desc:
            continue

        size = str(row.get("규격", "")).strip()
        if size.startswith("="):
            try:
                size = str(eval(size.lstrip("=")))
            except Exception:
                size = ""
        if not SIZE_RE.search(size):
            size = extract_size(desc)

        pkg = eval_int(row.get("Package", ""))
        pcs = safe_int(row.get("Pieces", ""))

        ratio = round(pcs / pkg) if pkg and pcs else 8
        kor_list.append(make_kor(desc, size, ratio))

    # ✅ Pieces 열의 모든 숫자 추출 후 합산
    try:
        qty = (
            df["Pieces"]
            .dropna()
            .astype(str)
            .apply(lambda x: sum(map(float, re.findall(r"\d+(?:\.\d+)?", x))))
            .sum()
        )
        qty = int(qty) if qty == int(qty) else round(qty, 2)
    except Exception as e:
        st.error(f"❌ 수량 계산 오류: {e}")
        qty = 0

    st.markdown("### ✅ 생성된 한국품명 리스트")
    st.text_area("미리보기", "\n".join(kor_list[1:]), height=200)

    col1, col2, col3 = st.columns(3)
    cheosu = col1.text_input("수입 차수")
    load_dt = ship_date if ship_date else datetime.today().date()
    load_dt = col2.date_input("상차일", value=load_dt)
    in_dt = col3.date_input("입고일", value=load_dt + timedelta(days=6))
    cfg["container"] = st.text_input("컨테이너", value=cfg["container"])

    with st.expander("⚙️ 지급·은행 정보"):
        cfg["beneficiary"] = st.text_input("beneficiary", value=cfg["beneficiary"])
        cfg["account_number"] = st.text_input("account_number", value=cfg["account_number"])
        cfg["bank"] = st.text_input("bank", value=cfg["bank"])
        cfg["swift"] = st.text_input("swift", value=cfg["swift"])
        cfg["bank_address"] = st.text_area("bank_address", value=cfg["bank_address"], height=100)
    save_cfg()

    main_item = kor_list[1] if len(kor_list) > 1 else "FM곤도라 중선반 800×300 다크그레이"
    others = max(len(set(kor_list[1:])) - 1, 0)
    krw, cny = 1400.39, 7.2405

    letter = f"""중국 2025-{cheosu}차 수입 물품({load_dt.month}/{load_dt.day} 상차, {in_dt.month}/{in_dt.day} 입고 예정분) 대금 지급을 요청합니다.

* 지급 업체 :
    {cfg['beneficiary']}

* 은행정보 :
    ACCOUNT NUMBER : {cfg['account_number']}
    BENEFICIARY BANK : {cfg['bank']}
    SWIFT CODE : {cfg['swift']}

* BANK ADDRESS :
    {cfg['bank_address']}

* 지급 요청 금액 :
    ${usd:,.2f}

* 운송컨테이너 :
    {cfg['container']}

* 수입품 내역 :
    {main_item} 외 {others}품목   {qty} EA

* 수입품 금액 :
    ${usd:,.2f} = ₩{int(usd*krw):,} = ￥{int(usd*cny):,}

※ 환율({datetime.today().date()}) : ₩{krw}/$, ￥{cny}/$

※ 지급 사유 :
    24차 12/3 입고분 대금 지급 보류(담보성)
    {cheosu}차 {in_dt.month}/{in_dt.day} 입고 예정
    제조업체 자금 부족
"""

    hl = [cfg["beneficiary"], cfg["account_number"], cfg["bank"], cfg["swift"]] + cfg["bank_address"].splitlines()
    html = "<br>".join("&nbsp;" * (len(l) - len(l.lstrip())) + l.lstrip() for l in letter.split("\n"))

    def mark(html_src: str, target: str):
        pattern = re.compile(r"\s+".join(map(re.escape, target.split())), flags=re.IGNORECASE)
        return pattern.sub(lambda m: f'<b><font color="red">{m.group()}</font></b>', html_src)

    for t in hl:
        html = mark(html, t)

    components.html(
        f"""
        <style>
            #d {{
                font-family:굴림; font-size:9pt; white-space:pre-wrap;
                max-height:550px; overflow-y:auto; padding:8px; border:1px solid #ddd
            }}
            #b {{ margin:12px 0; padding:6px 14px; font-size:14px }}
        </style>
        <button id="b">📋 협조전 복사</button>
        <div id="d">{html}</div>
        <script>
        const b = document.getElementById("b");
        b.onclick = async () => {{
            const d = document.getElementById("d");
            try {{
                await navigator.clipboard.writeText(d.innerText);
            }} catch (e) {{
                document.execCommand("copy");
            }}
            b.textContent = "복사 완료";
        }};
        </script>
        """,
        height=620,
        scrolling=True,
    )

st.markdown("#### 📋 엑셀 표를 복사 → 첫 셀에 Ctrl+V")
cols = ["Item", "Description", "규격", "Package", "NO of PACK", "Pieces", "Unit Price", "Amount"]
grid = st.data_editor(pd.DataFrame(columns=cols), num_rows="dynamic", key="invoice", use_container_width=True, hide_index=True)

if not grid.dropna(how="all").empty:
    run(grid.dropna(how="all").copy())
else:
    st.info("그리드 첫 셀 클릭 후 Ctrl+V 하세요.")
