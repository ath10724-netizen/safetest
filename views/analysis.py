"""약점 분석 화면: 과목·단원별 정답률, 취약 단원 진단, 추천 문제 세트."""

import plotly.graph_objects as go
import streamlit as st

from core import analyzer, db, law_search
from core import question_bank as qb
from core.config import PASS_SUBJECT_SCORE, SUBJECTS
from ui.components import empty_state
from ui.session import request_set
from ui.styles import color, md

REASON_COLOR = {"다시 풀기": "red", "취약 단원 보강": "orange", "유사 개념": "blue", "새 문제": "green", "복습": "gray"}


def _rgba(hex_color: str, alpha: float) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def _level(diagnosis: str, weakness: float) -> str:
    return "danger" if "연속" in diagnosis or weakness >= 60 else "warning"


st.title(":material/analytics: 약점 분석")

questions = list(qb.load_questions())
attempts = analyzer.usable_attempts(db.fetch_attempts(), questions)
if not attempts:
    empty_state(
        "아직 풀이 기록이 없습니다. 문제를 풀면 과목별 정답률과 취약 단원을 분석해 드립니다.",
        "문제 풀러 가기", "views/quiz.py", ":material/edit_note:",
    )
    st.stop()

subject_df = analyzer.subject_stats(attempts)
unit_df = analyzer.unit_stats(attempts)
weak_df = unit_df[unit_df["is_weak"].astype(bool)].reset_index(drop=True)

# ---------------------------------------------------------------- 요약 지표
total = len(attempts)
correct = sum(a["is_correct"] for a in attempts)
solved_ids = {a["question_id"] for a in attempts}
c1, c2, c3, c4 = st.columns(4)
c1.metric("누적 풀이", f"{total}회", border=True)
c2.metric("전체 정답률", f"{correct / total * 100:.1f}%", border=True)
c3.metric("푼 문제", f"{len(solved_ids)} / {len(questions)}", border=True)
c4.metric("취약 단원", f"{len(weak_df)}개", border=True)

# ---------------------------------------------------------------- 과목별 현황
st.subheader("과목별 정답률")
with st.container():
    values = subject_df["accuracy"].fillna(0).tolist()
    labels = [f"{i + 1}과목" for i in range(len(SUBJECTS))]
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values + values[:1], theta=labels + labels[:1], name="내 정답률",
            fill="toself", fillcolor=_rgba(color("accent"), 0.25), line={"color": color("accent"), "width": 2},
            hovertext=SUBJECTS + SUBJECTS[:1], hovertemplate="%{hovertext}: %{r}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=[PASS_SUBJECT_SCORE] * (len(labels) + 1), theta=labels + labels[:1], name="과락선 40점",
            line={"color": color("danger"), "dash": "dash", "width": 1.5}, hoverinfo="skip",
        )
    )
    fig.update_layout(
        polar={
            "bgcolor": "rgba(0,0,0,0)",
            "radialaxis": {"range": [0, 100], "tickvals": [0, 40, 60, 100], "gridcolor": color("border"), "linecolor": color("border")},
            "angularaxis": {"gridcolor": color("border"), "linecolor": color("border")},
        },
        margin={"l": 40, "r": 40, "t": 20, "b": 20}, height=330,
        legend={"orientation": "h", "y": -0.1},
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
with st.container():
    table = subject_df.assign(과목=[f"{i + 1}. {s}" for i, s in enumerate(SUBJECTS)])
    st.dataframe(
        table[["과목", "attempts", "accuracy"]],
        hide_index=True,
        width="stretch",
        column_config={
            "과목": st.column_config.TextColumn("과목", width="large"),
            "attempts": st.column_config.NumberColumn("풀이", width="small"),
            "accuracy": st.column_config.ProgressColumn("정답률", min_value=0, max_value=100, format="%.0f%%", width="medium"),
        },
    )
    risk = subject_df[subject_df["accuracy"] < PASS_SUBJECT_SCORE]["subject"].tolist()
    if risk:
        st.error("**과락 위험 과목**  \n" + "  \n".join(risk), icon=":material/warning:")

# ---------------------------------------------------------------- 취약 단원 리포트
st.subheader("취약 단원 리포트")
if weak_df.empty:
    st.success("뚜렷한 취약 단원이 없습니다. 단원별로 2회 이상 풀면 더 정확하게 진단할 수 있습니다.", icon=":material/verified:")
for i, row in weak_df.iterrows():
    level = _level(row["diagnosis"], row["weakness"])
    badge = "red" if level == "danger" else "orange"
    with st.container(border=True, key=f"level_{level}_{i}"):
        top, action = st.columns([4, 1], vertical_alignment="center")
        with top:
            st.markdown(f"**{row['unit']}** :gray-badge[{row['subject']}] :{badge}-badge[{row['diagnosis']}]")
            st.progress(row["accuracy"] / 100, text=f"정답률 {row['accuracy']:g}% · 취약도 {row['weakness']:g} · {row['attempts']}회 풀이")
        unit_ids = [q["id"] for q in questions if q["unit"] == row["unit"]]
        if unit_ids and action.button("이 단원 풀기", key=f"unit_{i}", width="stretch", icon=":material/play_arrow:"):
            request_set(f"{row['unit']} 단원 집중 풀이", unit_ids)
        laws = law_search.search_by_unit(row["unit"])
        if laws:
            st.caption(md("복습할 법령·개념: " + " / ".join(f"{law['title']} ({law['source']})" for law in laws)))

with st.expander("전체 단원 통계", icon=":material/table_chart:"):
    st.dataframe(
        unit_df.drop(columns=["is_weak"]),
        hide_index=True,
        width="stretch",
        column_config={
            "subject": "과목",
            "unit": "단원",
            "attempts": "풀이 수",
            "correct": "정답 수",
            "accuracy": st.column_config.ProgressColumn("정답률", min_value=0, max_value=100, format="%.1f%%"),
            "weakness": st.column_config.NumberColumn("취약도", help="최근 풀이에 가중치를 둔 오답률(0~100)"),
            "diagnosis": "진단",
        },
    )
    st.caption("취약도 = 최근 풀이일수록 큰 가중치를 둔 오답률 × 표본 신뢰도(3회 미만이면 낮춤). 40 이상이면 취약 단원으로 분류합니다. 모의고사 미응답 문항은 분석에서 제외합니다.")

# ---------------------------------------------------------------- 추천 문제 세트
st.subheader("맞춤 추천 문제 세트")
size = st.slider("추천 문항 수", 5, 20, 10)
if "rec_seed" not in st.session_state:
    st.session_state["rec_seed"] = 0
recommendations = analyzer.recommend(attempts, questions, size=size, seed=st.session_state["rec_seed"])
with st.container(border=True):
    for n, (q, reason) in enumerate(recommendations, 1):
        kind, _, detail = reason.partition(" · ")
        st.markdown(
            f"{n}. :{REASON_COLOR.get(kind, 'gray')}-badge[{kind}] {md(q['question'])}  \n"
            f":gray[{q['unit']} · {detail}]"
        )
c1, c2 = st.columns(2)
if c1.button("추천 세트 풀기", type="primary", width="stretch", icon=":material/play_arrow:"):
    request_set("맞춤 추천 문제 세트", [q["id"] for q, _ in recommendations])
if c2.button("다른 조합 추천", width="stretch", icon=":material/shuffle:"):
    st.session_state["rec_seed"] += 1
    st.rerun()

# ---------------------------------------------------------------- 학습 추이
sessions = db.fetch_sessions()
if len(sessions) >= 2:
    st.subheader("학습 추이")
    rates = [round(s["correct"] / s["total"] * 100, 1) if s["total"] else 0 for s in sessions]
    rounds = list(range(1, len(sessions) + 1))
    trend = go.Figure(
        go.Scatter(
            x=rounds, y=rates, mode="lines+markers", name="정답률",
            line={"color": color("accent"), "width": 2}, hovertemplate="%{x}회차: %{y}%<extra></extra>",
        )
    )
    trend.add_hline(y=60, line_dash="dot", line_color=color("muted"), annotation_text="평균 합격선 60%")
    trend.update_layout(
        xaxis={"title": "풀이 회차", "dtick": 1}, yaxis={"title": "정답률(%)", "range": [0, 105]},
        height=280, margin={"l": 10, "r": 10, "t": 20, "b": 10}, showlegend=False,
    )
    st.plotly_chart(trend, width="stretch", config={"displayModeBar": False})
