import streamlit as st

# ✅ 로그인 함수
def check_password():
    st.title("🔐 사내 전용 수입선반 인보이스")
    password = st.text_input("비밀번호를 입력하세요", type="password")
    if password == "fine123":
        return True
    elif password:
        st.error("❌ 비밀번호가 올바르지 않습니다.")
        return False
    return False

# ✅ 인증 실패 시 앱 실행 중단
if not check_password():
    st.stop()

# ✅ 로그인 성공 시 아래 내용 표시
st.set_page_config(page_title="수입선반 인보이스")
st.title("📄 수입선반 인보이스 자동 생성기")
st.write("왼쪽 메뉴에서 기능을 선택하세요.")
