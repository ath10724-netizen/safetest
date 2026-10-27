"""풀이 세션 관리: 시작·종료, 진행 상태 저장과 복원, 새 세트로 바꾸기 확인.

진행 중인 풀이는 st.session_state["quiz"]에 두고, 바뀔 때마다 DB(sessions.state)에도 저장한다.
모의고사에서 고른 답은 위젯 상태가 아니라 quiz["selections"]에 보관한다.
Streamlit은 화면에 그려지지 않은 위젯의 상태를 지우기 때문이다.
"""

import json
import random
import time

import streamlit as st

from core import db, grader
from core import question_bank as qb
from core.config import EXAM_SECONDS_PER_QUESTION

QUIZ_KEY = "quiz"
PENDING_KEY = "pending_set"
MAX_ELAPSED_SEC = 600  # 문항당 소요 시간 상한: 자리를 비운 시간이 기록을 왜곡하지 않게 한다
MODE_NAMES = {"practice": "연습", "exam": "모의고사"}


def active_quiz() -> dict | None:
    quiz = st.session_state.get(QUIZ_KEY)
    return quiz if quiz and not quiz["finished"] else None


def progress_count(quiz: dict) -> int:
    """지금까지 답한 문항 수. 모의고사는 고른 답, 연습은 제출한 답을 센다."""
    if quiz["mode"] == "exam":
        return sum(v is not None for v in quiz["selections"].values())
    return len(quiz["answers"])


def capped_elapsed(seconds: float) -> float:
    return min(max(seconds, 0.0), MAX_ELAPSED_SEC)


# ---------------------------------------------------------------- 시작·종료

def start_quiz(question_ids: list[str], mode: str, shuffle_choices: bool) -> bool:
    """풀이를 시작한다. 문항이 없으면 시작하지 않고 False를 반환한다."""
    question_ids = [qid for qid in question_ids if qb.get_question(qid)]
    if not question_ids:
        return False
    close_unfinished_sessions()
    perms = {}
    for qid in question_ids:
        order = list(range(1, len(qb.get_question(qid)["choices"]) + 1))
        if shuffle_choices:
            random.shuffle(order)
        perms[qid] = order
    now = time.time()
    quiz = {
        "mode": mode,
        "ids": question_ids,
        "perm": perms,
        "idx": 0,
        "answers": {},
        "selections": {},
        "session_id": db.create_session(mode),
        "started": now,
        "q_started": now,
        "deadline": now + EXAM_SECONDS_PER_QUESTION * len(question_ids),
        "finished": False,
        "timeout": False,
    }
    st.session_state[QUIZ_KEY] = quiz
    save_state(quiz)
    return True


def finish_quiz(quiz: dict) -> None:
    questions = [qb.get_question(qid) for qid in quiz["ids"]]
    answered = [q for q in questions if q["id"] in quiz["answers"]]
    result = grader.summarize(answered, quiz["answers"])
    db.finish_session(quiz["session_id"], result.total, result.correct, result.average, result.passed)
    quiz["finished"] = True


def _exam_elapsed_per_question(quiz: dict) -> float:
    """모의고사 소요 시간은 제출·중단 모두 '경과 시간 ÷ 출제 문항 수'로 계산한다."""
    elapsed = min(time.time(), quiz["deadline"]) - quiz["started"]
    return elapsed / len(quiz["ids"])


def submit_exam(quiz: dict) -> None:
    per_question = _exam_elapsed_per_question(quiz)
    for qid in quiz["ids"]:
        question = qb.get_question(qid)
        chosen = quiz["selections"].get(qid)
        quiz["answers"][qid] = chosen
        db.record_attempt(quiz["session_id"], question, chosen, grader.is_correct(question, chosen), per_question)
    finish_quiz(quiz)


def record_exam_selections(quiz: dict) -> None:
    """모의고사를 중단할 때 답을 고른 문항만 기록한다. 미응답 문항은 풀지 않은 것으로 본다."""
    per_question = _exam_elapsed_per_question(quiz)
    for qid, chosen in quiz["selections"].items():
        if chosen is None or qid in quiz["answers"]:
            continue
        question = qb.get_question(qid)
        db.record_attempt(quiz["session_id"], question, chosen, grader.is_correct(question, chosen), per_question)
        quiz["answers"][qid] = chosen


def end_quiz(quiz: dict) -> None:
    """진행 중인 풀이를 끝낸다. 푼 문항은 기록하고, 기록이 없으면 세션을 지운다."""
    if quiz["mode"] == "exam":
        record_exam_selections(quiz)
    if quiz["answers"]:
        finish_quiz(quiz)
    else:
        db.delete_session(quiz["session_id"])
    st.session_state[QUIZ_KEY] = None


def close_unfinished_sessions() -> None:
    """이전에 끝내지 못한 세션을 정리한다. 기록이 있으면 그 기록으로 종료하고, 없으면 지운다."""
    for session_id in db.unfinished_session_ids():
        attempts = db.session_attempts(session_id)
        if not attempts:
            db.delete_session(session_id)
            continue
        answers = {a["question_id"]: a["chosen"] for a in attempts}
        questions = [q for qid in answers if (q := qb.get_question(qid))]
        result = grader.summarize(questions, answers)
        db.finish_session(session_id, result.total, result.correct, result.average, result.passed)


# ---------------------------------------------------------------- 상태 저장·복원

def save_state(quiz: dict) -> None:
    if not quiz["finished"]:
        db.save_session_state(quiz["session_id"], json.dumps(quiz, ensure_ascii=False))


def restore_state() -> bool:
    """새로고침 등으로 세션 상태가 비었을 때, DB에 저장된 미완료 풀이를 불러온다."""
    if st.session_state.get(QUIZ_KEY) is not None:
        return False
    saved = db.load_unfinished_state()
    if not saved:
        return False
    session_id, state = saved
    try:
        quiz = json.loads(state)
    except json.JSONDecodeError:
        return False
    quiz["ids"] = [qid for qid in quiz["ids"] if qb.get_question(qid)]
    if not quiz["ids"] or quiz.get("session_id") != session_id:
        return False
    quiz["idx"] = min(quiz["idx"], len(quiz["ids"]) - 1)
    st.session_state[QUIZ_KEY] = quiz
    return True


# ---------------------------------------------------------------- 새 세트로 바꾸기

def _go_pending(title: str, ids: list[str]) -> None:
    st.session_state[PENDING_KEY] = {"title": title, "ids": ids}
    st.switch_page("views/quiz.py")


@st.dialog("진행 중인 풀이가 있습니다")
def _confirm_replace(title: str, ids: list[str]) -> None:
    quiz = active_quiz()
    if quiz is None:
        _go_pending(title, ids)
        return
    st.markdown(
        f"{MODE_NAMES[quiz['mode']]} {progress_count(quiz)} / {len(quiz['ids'])}문항을 풀고 있습니다.  \n"
        f"지금까지 푼 문항은 기록에 남기고 종료한 뒤 **{title}**을(를) 시작할까요?"
    )
    c1, c2 = st.columns(2)
    if c1.button("종료하고 새로 시작", type="primary", width="stretch"):
        end_quiz(quiz)
        _go_pending(title, ids)
    if c2.button("이어 풀기", width="stretch"):
        st.switch_page("views/quiz.py")


def request_set(title: str, ids: list[str]) -> None:
    """문제 세트 풀기를 요청한다. 진행 중인 풀이가 있으면 먼저 확인을 받는다."""
    ids = [qid for qid in ids if qb.get_question(qid)]
    if not ids:
        st.toast("풀 수 있는 문제가 없습니다.", icon=":material/info:")
        return
    if active_quiz():
        _confirm_replace(title, ids)
    else:
        _go_pending(title, ids)
