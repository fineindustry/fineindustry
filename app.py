import streamlit as st

# 비밀번호
CORRECT_PASSWORD = "your_password"

# 세션 상태로 로그인 여부 저장
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# 로그인 화면
if not st.session_state["authenticated"]:
    pw = st.text_input("비밀번호를 입력하세요", type="password")
    if pw == CORRECT_PASSWORD:
        st.session_state["authenticated"] = True
        st.success("✅ 로그인 성공")
        st.rerun()
    elif pw:
        st.error("❌ 비밀번호가 틀렸습니다.")
    st.stop()  # ⛔ 여기서 앱 전체 실행을 중단함

# 여기 아래부터는 비밀번호 입력 후에만 실행됨
st.title("🔐 비공개 앱에 오신 것을 환영합니다")
st.write("이제 자유롭게 앱 기능을 사용하실 수 있습니다.")
