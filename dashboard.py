"""Streamlit 관리자 대시보드.

실행: venv 활성화 후 `streamlit run dashboard.py`

구성:
  상단 상태 바(데몬/대기열/토큰) + 탭 4개(대시보드 / 업로드 내역 / 성과 / 실패 재시도)
"""

from datetime import date, datetime

import pandas as pd
import streamlit as st

from config import settings
from core import database, metrics, runtime_config, status
from core.pipeline import retry_failed

st.set_page_config(page_title="Shortform Auto Uploader", page_icon="🎬", layout="wide")

database.init_db()

PLATFORM_LABEL = {"youtube": "YouTube", "instagram": "Instagram", "tiktok": "TikTok"}


# --- 사이드바: 제어 ---
with st.sidebar:
    st.header("⚙️ 제어")

    llm_on = st.toggle("LLM 메타데이터 자동 생성", value=runtime_config.get_llm_on())
    if llm_on != runtime_config.get_llm_on():
        runtime_config.set_llm_on(llm_on)
        st.success("저장됨. 다음 업로드부터 적용됩니다.")

    st.divider()
    auto_refresh = st.toggle("자동 갱신", value=True, help="상태 바를 주기적으로 다시 읽습니다.")
    interval = st.select_slider("갱신 주기", options=[5, 10, 30, 60], value=10, disabled=not auto_refresh)
    if st.button("🔄 전체 새로고침", width="stretch"):
        st.rerun()

    st.divider()
    st.caption(f"활성 플랫폼: {', '.join(settings.ENABLED_PLATFORMS) or '(없음)'}")
    st.caption(f"감시 폴더: `{settings.QUEUE_DIR.name}`")


# --- 상단 상태 바 (자동 갱신 대상) ---
@st.fragment(run_every=interval if auto_refresh else None)
def render_status_bar():
    daemon = status.get_daemon_status()
    queue = status.get_queue_status()
    tokens = status.get_token_status()

    col1, col2, col3 = st.columns([1.1, 1.1, 2.3])

    with col1:
        if daemon["running"]:
            st.success(f"● 데몬 가동 중 · {daemon['detail']}")
        else:
            st.error(f"● 데몬 정지 · {daemon['detail']}")

    with col2:
        if queue["orphans"]:
            st.warning(f"대기열 {queue['pairs']}쌍 · 짝 없는 파일 {len(queue['orphans'])}개")
        else:
            st.info(f"대기열 {queue['pairs']}쌍 대기 중")

    with col3:
        parts = []
        for key in ("youtube", "instagram", "tiktok"):
            info = tokens.get(key, {})
            parts.append(f"{'✅' if info.get('ok') else '❌'} {PLATFORM_LABEL[key]} {info.get('detail', '')}")
        st.caption("토큰 상태 · " + "  |  ".join(parts))

    if queue["orphans"]:
        st.caption(f"⚠️ 짝이 없어 대기 중: {', '.join(queue['orphans'][:10])}")

    st.caption(f"마지막 확인: {datetime.now().strftime('%H:%M:%S')}")


st.title("🎬 Shortform Auto Uploader")
render_status_bar()
st.divider()


# --- 공통 헬퍼 ---
def _logs_dataframe(logs: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(logs)
    if df.empty:
        return df
    df["플랫폼"] = df["platform"].map(lambda p: PLATFORM_LABEL.get(p, p))
    df["상태"] = df["status"].map({"success": "✅ 성공", "failed": "❌ 실패"})
    # detail이 URL인 경우에만 링크 컬럼으로 노출한다(유튜브는 URL, 나머지는 ID/에러 문자열).
    df["링크"] = df["detail"].map(lambda d: d if isinstance(d, str) and d.startswith("http") else None)
    df["시각"] = df["created_at"]
    df["파일"] = df["filename"]
    return df


def _render_log_table(df: pd.DataFrame) -> None:
    view = df[["시각", "파일", "플랫폼", "상태", "링크"]]
    st.dataframe(
        view,
        width="stretch",
        hide_index=True,
        column_config={
            "링크": st.column_config.LinkColumn("링크", display_text="열기", width="small"),
            "시각": st.column_config.TextColumn("시각", width="medium"),
        },
    )


def _render_failures(df: pd.DataFrame) -> None:
    failures = df[df["status"] == "failed"]
    if failures.empty:
        return
    st.markdown("##### ❌ 실패 상세")
    for _, row in failures.iterrows():
        with st.expander(f"{row['시각']} · {row['파일']} · {row['플랫폼']}"):
            st.code(row["detail"] or "(에러 메시지 없음)", language=None)


logs = database.get_recent_logs(limit=1000)
log_df = _logs_dataframe(logs)

tab_home, tab_history, tab_perf, tab_retry = st.tabs(
    ["📊 대시보드", "📅 업로드 내역", "📈 성과", "🔁 실패 재시도"]
)


# --- 탭 1: 대시보드 ---
with tab_home:
    if log_df.empty:
        st.info("아직 업로드 기록이 없습니다. `Upload_Queue`에 mp4 + 같은 이름의 json을 넣어보세요.")
    else:
        success_count = int((log_df["status"] == "success").sum())
        failed_count = int((log_df["status"] == "failed").sum())
        total = len(log_df)
        rate = f"{success_count / total * 100:.0f}%" if total else "-"

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 기록", total)
        c2.metric("성공", success_count)
        c3.metric("실패", failed_count)
        c4.metric("성공률", rate)

        st.subheader("최근 업로드 로그")
        platforms = ["(전체)"] + sorted(log_df["플랫폼"].unique().tolist())
        selected = st.selectbox("플랫폼 필터", platforms, key="home_filter")
        shown = log_df if selected == "(전체)" else log_df[log_df["플랫폼"] == selected]

        _render_log_table(shown.head(100))
        _render_failures(shown.head(100))


# --- 탭 2: 업로드 내역 (날짜별) ---
with tab_history:
    if log_df.empty:
        st.info("표시할 업로드 내역이 없습니다.")
    else:
        log_df["날짜"] = pd.to_datetime(log_df["created_at"]).dt.date
        min_date, max_date = log_df["날짜"].min(), log_df["날짜"].max()

        col1, col2 = st.columns([2, 1])
        with col1:
            date_range = st.date_input(
                "기간",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
            )
        with col2:
            only_success = st.checkbox("성공만 보기", value=False)

        # date_input은 범위 선택 중 값을 1개만 반환하는 순간이 있어 방어한다.
        if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
            start, end = date_range
        else:
            start = end = date_range if isinstance(date_range, date) else min_date

        filtered = log_df[(log_df["날짜"] >= start) & (log_df["날짜"] <= end)]
        if only_success:
            filtered = filtered[filtered["status"] == "success"]

        if filtered.empty:
            st.warning("선택한 조건에 해당하는 기록이 없습니다.")
        else:
            st.caption(f"{start} ~ {end} · 총 {len(filtered)}건")
            daily = (
                filtered.assign(성공=(filtered["status"] == "success").astype(int))
                .groupby("날짜")
                .agg(건수=("id", "count"), 성공=("성공", "sum"))
            )
            daily["실패"] = daily["건수"] - daily["성공"]
            st.bar_chart(daily[["성공", "실패"]])

            for day in sorted(filtered["날짜"].unique(), reverse=True):
                day_df = filtered[filtered["날짜"] == day]
                files = day_df["파일"].nunique()
                ok = int((day_df["status"] == "success").sum())
                with st.expander(f"📅 {day} · 영상 {files}개 · 업로드 {len(day_df)}건 (성공 {ok})", expanded=False):
                    _render_log_table(day_df)


# --- 탭 3: 성과 ---
with tab_perf:
    st.caption(
        "업로드한 영상의 조회수·좋아요·댓글수입니다. "
        "인스타그램 조회수는 insights 권한이 없어 표시되지 않고, "
        "틱톡은 `video.list` 스코프(앱 심사 중)가 없어 아직 지원하지 않습니다."
    )

    if st.button("🔄 지표 갱신 (플랫폼 API 호출)"):
        with st.spinner("플랫폼에서 지표를 가져오는 중..."):
            try:
                summary = metrics.refresh_all_metrics()
                st.success(f"갱신 {summary['updated']}건 · 건너뜀 {summary['skipped']}건")
                for err in summary["errors"]:
                    st.warning(err)
            except Exception as exc:  # 대시보드가 통째로 죽지 않도록 방어
                st.error(f"지표 갱신 실패: {exc}")

    metric_rows = database.get_metrics()
    if not metric_rows:
        st.info("아직 수집된 지표가 없습니다. 위 버튼으로 갱신해보세요.")
    else:
        mdf = pd.DataFrame(metric_rows)
        mdf["플랫폼"] = mdf["platform"].map(lambda p: PLATFORM_LABEL.get(p, p))

        c1, c2, c3 = st.columns(3)
        c1.metric("총 조회수", f"{int(mdf['views'].fillna(0).sum()):,}")
        c2.metric("총 좋아요", f"{int(mdf['likes'].fillna(0).sum()):,}")
        c3.metric("총 댓글", f"{int(mdf['comments'].fillna(0).sum()):,}")

        view = mdf[["플랫폼", "title", "views", "likes", "comments", "fetched_at"]]
        view.columns = ["플랫폼", "제목", "조회수", "좋아요", "댓글", "수집시각"]
        st.dataframe(view, width="stretch", hide_index=True)


# --- 탭 4: 실패 재시도 ---
with tab_retry:
    failed_items = status.get_failed_items()
    if not failed_items:
        st.success("재시도할 실패 항목이 없습니다.")
    else:
        st.warning(
            f"{len(failed_items)}건이 `Failed_Uploads`에 있습니다. "
            "재시도하면 **이미 성공한 플랫폼은 건너뛰고** 실패한 플랫폼에만 다시 게시합니다."
        )
        confirm = st.checkbox("실제 계정에 게시된다는 점을 이해했습니다", key="retry_confirm")

        for item in failed_items:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{item['stem']}**")
                    st.caption(f"{item['size_mb']}MB · 최종 수정 {item['modified']}")
                    done = database.get_succeeded_platforms(f"{item['stem']}.mp4")
                    remaining = [p for p in settings.ENABLED_PLATFORMS if p not in done]
                    st.caption(
                        f"성공: {', '.join(PLATFORM_LABEL.get(p, p) for p in done) or '없음'}"
                        f" · 재시도 대상: {', '.join(PLATFORM_LABEL.get(p, p) for p in remaining) or '없음'}"
                    )
                with c2:
                    if st.button(
                        "재시도",
                        key=f"retry_{item['stem']}",
                        disabled=not confirm or not remaining,
                        width="stretch",
                    ):
                        with st.spinner(f"{item['stem']} 재업로드 중..."):
                            try:
                                retry_failed(item["stem"])
                                st.success("재시도 완료")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"재시도 실패: {exc}")
