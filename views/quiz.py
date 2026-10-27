"""문제 풀이 화면: 연습 모드(한 문제씩 즉시 채점)와 모의고사 모드(제한 시간, 일괄 채점)."""

import random
import time

import plotly.graph_objects as go
import streamlit as st

from core import db, grader
from core import question_bank as qb
from core.config import DIFFICULTIES, PASS_SUBJECT_SCORE, SUBJECTS
from ui.components import choice_label, render_choices, render_feedback, render_question
from ui.session import (
    PENDING_KEY,
    QUIZ_KEY,
    capped_elapsed,
    end_quiz,
    finish_quiz,
    progress_count,
    save_state,
    start_quiz,
    submit_exam,
)
from ui.styles import color, esc

MODES = {"practice": "연습 모드", "exam": "모의고사 모드"}
MODE_CAPTIONS = ["한 문제씩 바로 채점하고 해설 확인", "제한 시간 안에 풀고 한 번에 채점"]
TIMER_WARN_SEC = 300
TIMER_DANGER_SEC = 60


# ---------------------------------------------------------------- 시작 화면

def pending_box() -> None:
    pending = st.session_state.get(PENDING_KEY)
    if not pending:
        return
    with st.container(border=True, key="accent_pending"):
        st.markdown(f"**:material/target: {pending['title']}**")
        count = len(pending["ids"])
        if count:
            st.caption(f"{count}문항이 준비되었습니다. 풀이 방식을 고르세요.")
        else:
            st.caption("이 세트에는 풀 수 있는 문제가 없습니다.")
        c1, c2, c3 = st.columns(3)
        for col, mode, label, icon, primary in (
            (c1, "practice", "연습 모드로 풀기", ":material/play_arrow:", True),
            (c2, "exam", "모의고사로 풀기", ":material/timer:", False),
        ):
            if col.button(label, type="primary" if primary else "secondary", width="stretch", icon=icon, disabled=not count):
                if start_quiz(pending["ids"], mode, shuffle_choices=False):
                    del st.session_state[PENDING_KEY]
                    st.rerun()
                st.warning("풀 수 있는 문제가 없습니다.", icon=":material/info:")
        if c3.button("취소", width="stretch"):
            del st.session_state[PENDING_KEY]
            st.rerun()


def setup_view() -> None:
    st.title(":material/edit_note: 문제 풀이")
    pending_box()

    with st.form("setup"):
        mode = st.radio("풀이 방식", list(MODES), format_func=MODES.get, captions=MODE_CAPTIONS, horizontal=True)
        subjects = st.multiselect("과목", SUBJECTS, placeholder="전체 과목")
        c1, c2 = st.columns(2)
        rounds = c1.multiselect("회차", qb.list_rounds(), placeholder="전체 회차")
        difficulties = c2.multiselect("난이도", DIFFICULTIES, placeholder="전체 난이도")
        c3, c4 = st.columns(2)
        count = c3.number_input("문항 수", min_value=1, max_value=120, value=10)
        order = c4.radio("출제 순서", ["과목 순서", "무작위"], horizontal=True)
        shuffle_choices = st.checkbox("보기 순서 섞기", help="보기 위치를 외워서 맞히는 것을 방지합니다.")
        submitted = st.form_submit_button("풀이 시작", type="primary", width="stretch", icon=":material/play_arrow:")

    if submitted:
        pool = qb.filter_questions(subjects, rounds, difficulties)
        if not pool:
            st.warning("조건에 맞는 문제가 없습니다. 조건을 넓혀 주세요.", icon=":material/filter_alt_off:")
            return
        if order == "무작위":
            pool = random.sample(pool, len(pool))
        selected = pool[: int(count)]
        if len(selected) < count:
            st.toast(f"조건에 맞는 문제가 {len(selected)}문항이라 모두 출제합니다.", icon=":material/info:")
        start_quiz([q["id"] for q in selected], mode, shuffle_choices)
        st.rerun()

    st.caption(
        f"문제은행 {len(qb.load_questions())}문항 · 실제 시험은 6과목 120문항, 150분 · "
        "합격 기준: 과목별 40점 이상, 평균 60점 이상"
    )


# ---------------------------------------------------------------- 연습 모드

def progress_header(done: int, total: int, current: int, correct: int) -> None:
    """스크롤해도 보이도록 상단에 고정되는 진행 표시."""
    with st.container(key="quiz_progress"):
        st.html(
            f'<div class="qb-progress-text"><span><b>{current}</b> / {total}문항</span>'
            f"<span>정답 <b>{correct}</b>개</span></div>"
        )
        st.progress(done / total)


def practice_view(quiz: dict) -> None:
    ids, idx = quiz["ids"], quiz["idx"]
    qid = ids[idx]
    question = qb.get_question(qid)
    perm = quiz["perm"][qid]
    graded = qid in quiz["answers"]

    correct_so_far = sum(grader.is_correct(qb.get_question(i), c) for i, c in quiz["answers"].items())
    progress_header(idx + graded, len(ids), idx + 1, correct_so_far)

    with st.container(border=True):
        render_question(question, idx + 1)
        if graded:
            render_choices(question, quiz["answers"][qid], perm)
        else:
            with st.container(key=f"answer_area_{qid}"):
                selected = st.radio(
                    "답 선택",
                    perm,
                    format_func=lambda orig: choice_label(question, orig, perm),
                    index=None,
                    key=f"p_{quiz['session_id']}_{qid}",
                    label_visibility="collapsed",
                )

    if not graded:
        if st.button("제출", type="primary", width="stretch", icon=":material/check:"):
            if selected is None:
                st.warning("답을 선택하세요.", icon=":material/touch_app:")
                return
            correct = grader.is_correct(question, selected)
            elapsed = capped_elapsed(time.time() - quiz["q_started"])
            db.record_attempt(quiz["session_id"], question, selected, correct, elapsed)
            quiz["answers"][qid] = selected
            save_state(quiz)
            st.rerun()
        return

    render_feedback(question, quiz["answers"][qid], perm, auto_ai=True, key=f"{quiz['session_id']}_{qid}")

    st.divider()
    if idx + 1 < len(ids):
        if st.button("다음 문제", type="primary", width="stretch", icon=":material/arrow_forward:"):
            quiz["idx"] += 1
            quiz["q_started"] = time.time()
            save_state(quiz)
            st.rerun()
    elif st.button("결과 보기", type="primary", width="stretch", icon=":material/assignment_turned_in:"):
        finish_quiz(quiz)
        st.rerun()


# ---------------------------------------------------------------- 모의고사 모드

def _exam_widget_key(quiz: dict, qid: str) -> str:
    return f"e_{quiz['session_id']}_{qid}"


@st.fragment(run_every=1)
def exam_timer(quiz: dict) -> None:
    remaining = max(0, int(quiz["deadline"] - time.time()))
    minutes, seconds = divmod(remaining, 60)
    state = "ok" if remaining > TIMER_WARN_SEC else "warn" if remaining > TIMER_DANGER_SEC else "danger"
    with st.container(key=f"timer_{state}"):
        st.metric(":material/timer: 남은 시간", f"{minutes:02d}:{seconds:02d}")
        if state == "warn":
            st.caption(":orange[5분 이하 남았습니다]")
        elif state == "danger":
            st.caption(":red[1분 이하 · 시간이 끝나면 자동 제출됩니다]")
    answered = progress_count(quiz)
    st.progress(answered / len(quiz["ids"]), text=f"응답 {answered} / {len(quiz['ids'])}")
    if remaining == 0 and not quiz["timeout"]:
        quiz["timeout"] = True
        st.rerun(scope="app")


def exam_view(quiz: dict) -> None:
    # 다른 화면에 있는 동안 시간이 끝났을 수도 있으므로 화면에 들어올 때마다 확인한다
    if quiz["timeout"] or time.time() >= quiz["deadline"]:
        submit_exam(quiz)
        st.toast("시간이 종료되어 자동 제출되었습니다.", icon=":material/alarm:")
        st.rerun()

    st.title(":material/timer: 모의고사")

    questions = [qb.get_question(qid) for qid in quiz["ids"]]
    subjects = [s for s in SUBJECTS if any(q["subject"] == s for q in questions)]
    tab_labels = [f"{SUBJECTS.index(s) + 1}과목" for s in subjects]
    tabs = st.tabs(tab_labels) if len(subjects) > 1 else [st.container()]

    number = 0
    for tab, subject in zip(tabs, subjects):
        with tab:
            st.subheader(subject)
            for q in questions:
                if q["subject"] != subject:
                    continue
                number += 1
                perm = quiz["perm"][q["id"]]
                saved = quiz["selections"].get(q["id"])
                with st.container(border=True):
                    render_question(q, number)
                    with st.container(key=f"answer_area_{q['id']}"):
                        # 고른 답은 quiz["selections"]에 보관하고, 위젯 상태가 지워져도 index로 복원한다
                        quiz["selections"][q["id"]] = st.radio(
                            "답 선택",
                            perm,
                            format_func=lambda orig, q=q, perm=perm: choice_label(q, orig, perm),
                            index=perm.index(saved) if saved is not None else None,
                            key=_exam_widget_key(quiz, q["id"]),
                            label_visibility="collapsed",
                        )

    # 타이머는 선택을 반영한 뒤에 그려야 응답 수가 맞는다
    with st.sidebar:
        exam_timer(quiz)

    unanswered = len(quiz["ids"]) - progress_count(quiz)
    if unanswered:
        st.caption(f"아직 답하지 않은 문항이 {unanswered}개 있습니다. 미응답 문항은 오답 처리됩니다.")
    if st.button("답안 제출", type="primary", width="stretch", icon=":material/send:"):
        submit_exam(quiz)
        st.rerun()


# ---------------------------------------------------------------- 결과 화면

def result_banner(result: grader.ExamResult) -> None:
    full_exam = len(result.subjects) == len(SUBJECTS)
    if full_exam:
        cls, title = ("is-pass", "합격입니다") if result.passed else ("is-fail", "불합격입니다")
        sub = f"평균 {result.average}점 · 정답 {result.correct} / {result.total}"
    else:
        cls = "is-info"
        title = "합격 기준 충족 (참고)" if result.passed else "합격 기준 미달 (참고)"
        sub = f"평균 {result.average}점 · 정답 {result.correct} / {result.total} · 6과목을 모두 풀었을 때만 실제 합격 판정과 같습니다"
    reasons = "".join(f"<li>{esc(r)}</li>" for r in result.fail_reasons)
    st.html(
        f'<div class="qb-banner {cls}"><div class="qb-banner-title">{title}</div>'
        f'<div class="qb-banner-sub">{esc(sub)}</div>'
        + (f'<ul class="qb-banner-sub">{reasons}</ul>' if reasons else "")
        + "</div>"
    )


def subject_score_chart(result: grader.ExamResult) -> None:
    """과목별 점수 막대와 과락선(40점). 막대 끝에 '과락' 글자를 함께 붙여 색에만 의존하지 않는다."""
    subjects = list(reversed(result.subjects))
    fig = go.Figure(
        go.Bar(
            x=[s.score for s in subjects],
            y=[f"{SUBJECTS.index(s.subject) + 1}. {s.subject}" for s in subjects],
            orientation="h",
            marker_color=[color("success") if s.passed else color("danger") for s in subjects],
            text=[f"{s.score:g}점" + ("" if s.passed else " · 과락") for s in subjects],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: %{x}점<extra></extra>",
        )
    )
    fig.add_vline(
        x=PASS_SUBJECT_SCORE, line_dash="dash", line_color=color("muted"),
        annotation_text="과락선 40점", annotation_position="top",
    )
    fig.update_layout(
        xaxis={"range": [0, 115], "title": None, "showgrid": False},
        yaxis={"title": None, "automargin": True},
        height=90 + 44 * len(subjects),
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def result_view(quiz: dict) -> None:
    questions = [qb.get_question(qid) for qid in quiz["ids"] if qid in quiz["answers"]]
    result = grader.summarize(questions, quiz["answers"])

    st.title(":material/assignment_turned_in: 채점 결과")
    result_banner(result)
    if result.subjects:
        subject_score_chart(result)

    wrong = [q for q in questions if not grader.is_correct(q, quiz["answers"][q["id"]])]
    st.subheader(f"틀린 문제 {len(wrong)}개")
    if not wrong:
        st.success("모두 맞혔습니다!", icon=":material/celebration:")
    numbers = {qid: i + 1 for i, qid in enumerate(quiz["ids"])}
    for subject in [s.subject for s in result.subjects]:
        group = [q for q in wrong if q["subject"] == subject]
        if not group:
            continue
        st.markdown(f"**{SUBJECTS.index(subject) + 1}과목 · {subject}** :red-badge[{len(group)}개]")
        for q in group:
            chosen = quiz["answers"][q["id"]]
            perm = quiz["perm"][q["id"]]
            mine = choice_label(q, chosen, perm).split()[0] if chosen else "미응답"
            with st.expander(f"Q{numbers[q['id']]}. [{q['unit']}] {q['question'][:38]}… · 내 답 {mine}"):
                render_question(q, numbers[q["id"]])
                render_choices(q, chosen, perm)
                render_feedback(q, chosen, perm, auto_ai=False, key=f"{quiz['session_id']}_{q['id']}")

    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("약점 분석 보기", type="primary", width="stretch", icon=":material/analytics:"):
        st.session_state[QUIZ_KEY] = None
        st.switch_page("views/analysis.py")
    if c2.button("새로 풀기", width="stretch", icon=":material/restart_alt:"):
        st.session_state[QUIZ_KEY] = None
        st.rerun()


# ---------------------------------------------------------------- 진입점

quiz = st.session_state.get(QUIZ_KEY)
if quiz is not None and not quiz["finished"] and not quiz["ids"]:
    # 문항이 없는 풀이는 진행할 수 없으므로 정리한다
    end_quiz(quiz)
    quiz = None

if quiz is None:
    setup_view()
elif quiz["finished"]:
    result_view(quiz)
else:
    with st.sidebar:
        if st.button("풀이 중단", icon=":material/close:"):
            end_quiz(quiz)
            st.rerun()
    if quiz["mode"] == "practice":
        practice_view(quiz)
    else:
        exam_view(quiz)
        save_state(quiz)
