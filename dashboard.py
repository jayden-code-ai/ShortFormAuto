"""Streamlit 관리자 대시보드: 업로드 로그 조회 + LLM On/Off 토글.

실행: venv 활성화 후 `streamlit run dashboard.py`
"""

import pandas as pd
import streamlit as st

from config import settings
from core import database, runtime_config

st.set_page_config(page_title="Shortform Auto Uploader", page_icon="🎬", layout="wide")

database.init_db()

st.title("🎬 Shortform Auto Uploader")

# --- 사이드바: 제어 ---
with st.sidebar:
    st.header("⚙️ 제어")

    llm_on = st.toggle("LLM 메타데이터 자동 생성", value=runtime_config.get_llm_on())
    if llm_on != runtime_config.get_llm_on():
        runtime_config.set_llm_on(llm_on)
        st.success("LLM 설정이 저장되었습니다. 다음 업로드부터 적용됩니다.")

    st.caption(f"활성 플랫폼: {', '.join(settings.ENABLED_PLATFORMS)}")

    if st.button("🔄 새로고침"):
        st.rerun()

# --- 요약 지표 ---
logs = database.get_recent_logs(limit=500)
col1, col2, col3 = st.columns(3)
success_count = sum(1 for r in logs if r["status"] == "success")
failed_count = sum(1 for r in logs if r["status"] == "failed")
col1.metric("총 기록", len(logs))
col2.metric("성공", success_count)
col3.metric("실패", failed_count)

# --- 로그 테이블 ---
st.subheader("📋 업로드 로그")
if logs:
    df = pd.DataFrame(logs)[["created_at", "filename", "platform", "status", "detail"]]
    df.columns = ["시각", "파일", "플랫폼", "상태", "상세"]

    platforms = ["(전체)"] + sorted(df["플랫폼"].unique().tolist())
    selected = st.selectbox("플랫폼 필터", platforms)
    if selected != "(전체)":
        df = df[df["플랫폼"] == selected]

    def _highlight(row):
        color = "#e6ffed" if row["상태"] == "success" else "#ffe6e6"
        return [f"background-color: {color}"] * len(row)

    st.dataframe(df.style.apply(_highlight, axis=1), use_container_width=True, hide_index=True)
else:
    st.info("아직 업로드 기록이 없습니다. Upload_Queue에 mp4+json 쌍을 넣어보세요.")
