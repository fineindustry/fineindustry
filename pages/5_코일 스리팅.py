"""
Slitting Program Demo (Streamlit)

– 원자재(코일) 재고 입력/확인: LOT NO 입력 → 자동 파싱
– 주문 입력: 품명 입력 → 파싱(thickness, width, material) → 수량 입력
– 안전재고 설정: 품명 입력 → 파싱 → 안전재고/현재재고 입력
– 슬리팅 계산: DEMO 알고리즘

Usage:
    streamlit run slitting_program.py
"""

import re
from datetime import datetime

import streamlit as st
import pandas as pd

# -------------------------------------------------------------------
# 1) Data Editor Wrapper
# -------------------------------------------------------------------
def data_editor(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Streamlit Data Editor 래퍼 (호환성)"""
    if hasattr(st, "data_editor"):
        return st.data_editor(df, **kwargs)
    elif hasattr(st, "experimental_data_editor"):
        return st.experimental_data_editor(df, **kwargs)
    else:
        st.error("이 버전의 Streamlit에서는 Data Editor를 사용할 수 없습니다.")
        return df

# -------------------------------------------------------------------
# 2) 코일 LOT 파싱 함수
# -------------------------------------------------------------------
def parse_coil_lot(lot_code: str):
    """
    예: "CR060 1038C11200 250306-1"
     → material, thickness_mm, width_mm, production_date, sequence
    """
    pattern = re.compile(
        r"^([A-Z]+?)(\d{3})\s+"   # 재질+두께(3자리)
        r"(\d+)[A-Za-z]\d+\s+"    # 폭 앞 숫자만 캡처
        r"(\d{6})-(\d+)$"         # YYMMDD-SEQ
    )
    m = pattern.match(lot_code.strip())
    if not m:
        raise ValueError(f"LOT 형식 오류: {lot_code!r}")
    mat, thick, width_str, date_str, seq = m.groups()
    return {
        "material": mat,
        "thickness_mm": int(thick) / 100,
        "width_mm":    int(width_str),
        "production_date": datetime.strptime(date_str, "%y%m%d").date(),
        "sequence":    int(seq)
    }

# -------------------------------------------------------------------
# 3) 주문·안전재고 품명 파싱 함수
# -------------------------------------------------------------------
def parse_product_name(item_name: str):
    """
    예: "EL곤도라 선반 400 코일 0.75x437(CR)"
     → thickness_mm, width_mm, material, product(품명 앞부분)
    """
    name = item_name.strip()
    # (1) 괄호 안 재질
    m_mat = re.search(r"\((CR|HR|HGI)\)\s*$", name)
    if m_mat:
        material = m_mat.group(1)
        core = name[:m_mat.start()].strip()
    else:
        material = None
        core = name

    # (2) 두께×폭 (0.75x437, 0.8X563, 0.75TX617 등)
    m_dim = re.search(r"(\d+(?:\.\d+)?)[Tt]?x(\d+)", core)
    if m_dim:
        thickness_mm = float(m_dim.group(1))
        width_mm = int(m_dim.group(2))
    else:
        thickness_mm = None
        width_mm = None

    # (3) 재질 미입력 시 기본 할당
    if material is None and thickness_mm is not None:
        material = "CR" if thickness_mm < 1.2 else "HR"

    return {
        "raw_name":     item_name,
        "product":      core,
        "thickness_mm": thickness_mm,
        "width_mm":     width_mm,
        "material":     material
    }

# -------------------------------------------------------------------
# 4) Session State 초기화
# -------------------------------------------------------------------
def init_session_state():
    # 4-1) 코일 재고: LOT NO만
    if "df_coil_inventory" not in st.session_state:
        st.session_state.df_coil_inventory = pd.DataFrame({
            "coil_lot_no": [
                "CR060 1038C11200 250306-1",
                "CR075 1219C12700 250401-1"
            ]
        })
    # 4-2) 주문: 품명 + 수량
    if "df_orders" not in st.session_state:
        st.session_state.df_orders = pd.DataFrame({
            "product_name": pd.Series(dtype=str),
            "quantity":     pd.Series(dtype=int),
        })
    # 4-3) 안전재고: 품명 + 안전재고 + 현재재고
    if "df_safety_stock" not in st.session_state:
        st.session_state.df_safety_stock = pd.DataFrame({
            "product_name":   [
                "EL곤도라 선반 400 코일 0.75x437(CR)",
                "EL곤도라 선반 450 코일 0.75x487(CR)"
            ],
            "safety_stock":   [200, 150],
            "current_stock":  [120,  80],
        })
    # 4-4) 계산 결과
    if "slitting_result" not in st.session_state:
        st.session_state.slitting_result = None

# -------------------------------------------------------------------
# 5) Demo Slitting Solver
# -------------------------------------------------------------------
def solve_slitting(coils_df, safety_df, orders_df):
    results = []
    # 파싱된 주문 정보
    orders_parsed = orders_df["product_name"].apply(parse_product_name)
    orders_info = pd.json_normalize(orders_parsed).to_dict(orient="records")

    for _, row in coils_df.iterrows():
        lot = row["coil_lot_no"]
        try:
            info = parse_coil_lot(lot)
            cw = info["width_mm"]
        except Exception:
            cw = None
        scrap = 50
        used_sum = cw - scrap if cw is not None else None

        results.append({
            "coil_lot_no": lot,
            "parsed_coil": info if cw is not None else {},
            "used_width_sum": used_sum,
            "scrap": scrap,
            "orders": orders_info
        })
    return results

# -------------------------------------------------------------------
# 6) 페이지 정의
# -------------------------------------------------------------------
def page_inventory_input():
    st.title("현재 재고 입력/확인")
    st.write("▶ Streamlit version:", st.__version__)

    df = st.session_state.df_coil_inventory
    edited = data_editor(df, num_rows="dynamic", key="coil_inv_editor")
    st.session_state.df_coil_inventory = edited.fillna("")

    st.success("코일 LOT 리스트가 업데이트되었습니다.")

    parsed = []
    for lot in st.session_state.df_coil_inventory["coil_lot_no"]:
        if lot.strip():
            try:
                parsed.append(parse_coil_lot(lot))
            except:
                parsed.append({})
    if parsed:
        st.write("#### 파싱된 LOT 정보")
        st.dataframe(pd.DataFrame(parsed))

def page_orders_input():
    st.title("주문 입력")
    st.write("품명(product_name)과 수량(quantity)을 입력하세요.")
    df = st.session_state.df_orders
    edited = data_editor(df, num_rows="dynamic", key="orders_editor")
    # 수량 컬럼 정수 변환
    edited["quantity"] = pd.to_numeric(edited["quantity"], errors="coerce").fillna(0).astype(int)
    # 파싱 적용
    parsed = edited["product_name"].apply(parse_product_name)
    df_parsed = pd.json_normalize(parsed)
    st.session_state.df_orders = pd.concat([edited, df_parsed], axis=1)
    st.write("#### 파싱된 주문 정보")
    st.dataframe(df_parsed)
    st.success("주문 리스트가 업데이트되었습니다.")

def page_safety_stock():
    st.title("안전재고 설정")
    st.write("품명(product_name)과 안전재고, 현재재고를 입력하세요.")
    df = st.session_state.df_safety_stock
    edited = data_editor(df, num_rows="dynamic", key="safety_editor")
    # 파싱 적용
    parsed = edited["product_name"].apply(parse_product_name)
    df_parsed = pd.json_normalize(parsed)
    st.session_state.df_safety_stock = pd.concat([edited, df_parsed], axis=1)
    st.write("#### 파싱된 안전재고 품목 정보")
    st.dataframe(df_parsed)
    st.success("안전재고 설정이 업데이트되었습니다.")

def page_slitting_calc():
    st.title("슬리팅 계산 (데모)")
    st.write("#### 코일 LOT 리스트")
    st.dataframe(st.session_state.df_coil_inventory)
    st.write("#### 주문 리스트")
    st.dataframe(st.session_state.df_orders)
    st.write("#### 안전재고 현황")
    st.dataframe(st.session_state.df_safety_stock)

    if st.button("슬리팅 계산 실행"):
        st.session_state.slitting_result = solve_slitting(
            st.session_state.df_coil_inventory,
            st.session_state.df_safety_stock,
            st.session_state.df_orders
        )
        st.success("슬리팅 계산이 완료되었습니다.")

    if st.session_state.slitting_result:
        st.subheader("슬리팅 결과 상세")
        for r in st.session_state.slitting_result:
            st.write(f"- **LOT**: {r['coil_lot_no']}")
            st.write(f"    • 파싱된 코일 폭: {r['parsed_coil'].get('width_mm')} mm")
            st.write(f"    • 사용 폭 합계: {r['used_width_sum']} mm | 스크랩: {r['scrap']} mm")
            st.write("    • 주문 정보:")
            for o in r["orders"]:
                st.write(f"      - {o['product']}: {o['thickness_mm']}T × {o['width_mm']}mm | 재질:{o['material']} | 수량:{o['quantity']}")
            st.write("---")

# -------------------------------------------------------------------
# 7) Main
# -------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Slitting Program", layout="wide")
    init_session_state()

    menu = ["현재 재고 입력", "주문 입력", "안전재고 설정", "슬리팅 계산"]
    choice = st.sidebar.radio("메뉴 선택", menu)

    if choice == "현재 재고 입력":
        page_inventory_input()
    elif choice == "주문 입력":
        page_orders_input()
    elif choice == "안전재고 설정":
        page_safety_stock()
    else:
        page_slitting_calc()

if __name__ == "__main__":
    main()
