"""홈 화면: 오늘 할 일, 학습 현황 요약, 시험 안내."""

import streamlit as st

from core import analyzer, db, explainer
from core import question_bank as qb
from core.config import PASS_AVERAGE_SCORE, PASS_SUBJECT_SCORE, SUBJECTS
from ui.session import active_quiz, progress_count, request_set

st.title(":material/health_and_safety: 산업안전기사 필기 문제은행")
# 조사(로/으로)까지 포함한다: 받침에 따라 달라지기 때문
EXPLANATION = "법령 근거와 AI 해설로" if explainer.is_configured() else "해설과 관련 법령으로"
st.markdown(f":gray[짧은 시간에 많이 풀고, 틀린 문제는 {EXPLANATION} 확실히 이해하세요.]")

questions = list(qb.load_questions())
attempts = analyzer.usable_attempts(db.fetch_attempts(), questions)

quiz = active_quiz()
if quiz:
    with st.container(border=True, key="accent_resume"):
        mode = "연습이" if quiz["mode"] == "practice" else "모의고사가"
        st.markdown(f"**풀던 {mode} 있습니다** :gray[· {progress_count(quiz)} / {len(quiz['ids'])}문항 진행]")
        if st.button("이어 풀기", type="primary", icon=":material/play_arrow:"):
            st.switch_page("views/quiz.py")

if not attempts:
    # 처음 쓰는 사용자: 사용 순서를 안내한다
    with st.container(border=True, key="accent_welcome"):
        st.markdown("**처음 오셨나요? 이렇게 공부하세요**")
        steps = [
            ("과목과 문항 수를 고르고 <b>연습 모드</b>로 풀어 보세요.", "한 문제씩 바로 채점됩니다."),
            (f"틀린 문제는 <b>{EXPLANATION}</b> 이유를 확인하세요.", "같은 실수를 반복하지 않게 핵심만 짚어 드립니다."),
            ("<b>약점 분석</b>에서 취약 단원과 추천 문제를 확인하세요.", "풀수록 진단이 정확해집니다."),
        ]
        st.html(
            "".join(
                f'<div class="qb-step"><div class="qb-step-num">{i}</div><div>{main}<div class="qb-muted">{sub}</div></div></div>'
                for i, (main, sub) in enumerate(steps, 1)
            )
        )
        if st.button("첫 문제 풀기", type="primary", icon=":material/play_arrow:"):
            st.switch_page("views/quiz.py")
else:
    c1, c2, c3 = st.columns(3)
    c1.metric("누적 풀이", f"{len(attempts)}회", border=True)
    c2.metric("전체 정답률", f"{sum(a['is_correct'] for a in attempts) / len(attempts) * 100:.1f}%", border=True)
    c3.metric("푼 문제", f"{len({a['question_id'] for a in attempts})} / {len(questions)}", border=True)

    st.subheader("오늘 할 일")
    left, right = st.columns(2)
    with left, st.container(border=True, height="stretch"):
        st.markdown("**:material/target: 맞춤 추천 10문항**")
        st.caption("최근 오답, 취약 단원, 비슷한 개념을 섞어 골랐습니다.")
        if st.button("추천 세트 풀기", type="primary", width="stretch", icon=":material/play_arrow:"):
            recs = analyzer.recommend(attempts, questions, size=10)
            request_set("맞춤 추천 문제 세트", [q["id"] for q, _ in recs])
    with right, st.container(border=True, height="stretch"):
        st.markdown("**:material/stethoscope: 집중 보완 단원**")
        weak = analyzer.weak_units(attempts).head(3)
        if weak.empty:
            st.caption("아직 뚜렷한 취약 단원이 없습니다. 더 풀면 진단이 정확해집니다.")
        else:
            st.markdown(" ".join(f":orange-badge[{u}]" for u in weak["unit"]))
        if st.button("약점 분석 보기", width="stretch", icon=":material/analytics:"):
            st.switch_page("views/analysis.py")

with st.expander("시험 안내", icon=":material/info:", expanded=not attempts):
    st.markdown(
        f"- **구성**: {len(SUBJECTS)}과목 × 20문항 = 120문항, 시험시간 150분\n"
        f"- **합격 기준**: 과목당 {PASS_SUBJECT_SCORE}점 이상 + 전 과목 평균 {PASS_AVERAGE_SCORE}점 이상"
    )
    for i, subject in enumerate(SUBJECTS, 1):
        st.markdown(f"**{i}과목. {subject}**  \n:gray[{', '.join(qb.list_units(subject))}]")
    st.caption("수록 문제는 학습용 예시 문제이며 실제 기출 원문이 아닙니다. 법령 수치는 최신 법령에서 다시 확인하세요.")
