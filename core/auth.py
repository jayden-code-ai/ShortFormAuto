"""대시보드 접속 암호 확인.

암호는 `.streamlit/secrets.toml`의 `dashboard_password`에 두며 git에서 제외된다.
값이 설정되어 있지 않으면(로컬 전용으로 쓰는 경우) 잠금을 걸지 않는다.
"""

import hmac

import streamlit as st

PASSWORD_KEY = "dashboard_password"


def _configured_password() -> str:
    try:
        return str(st.secrets.get(PASSWORD_KEY, "") or "")
    except FileNotFoundError:
        # secrets.toml 자체가 없는 경우
        return ""


def require_password() -> None:
    """암호가 설정되어 있으면 인증될 때까지 페이지 렌더링을 중단한다."""
    expected = _configured_password()
    if not expected:
        return

    if st.session_state.get("_authenticated"):
        return

    st.title("🔒 Shortform Auto Uploader")
    st.caption("계속하려면 대시보드 암호를 입력하세요.")

    with st.form("login"):
        entered = st.text_input("암호", type="password")
        submitted = st.form_submit_button("접속")

    if submitted:
        # 타이밍 공격을 피하기 위해 상수 시간 비교를 쓴다.
        if hmac.compare_digest(entered, expected):
            st.session_state["_authenticated"] = True
            st.rerun()
        else:
            st.error("암호가 올바르지 않습니다.")

    st.stop()
