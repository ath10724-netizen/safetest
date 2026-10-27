"""오답노트 화면: 틀린 문제와 저장된 AI 해설 다시 보기."""

import streamlit as st

from core import analyzer, db, explainer
from core import question_bank as qb
from core.config import SUBJECTS
from ui.components import empty_state, render_choices, render_feedback, render_question
from ui.session import request_set

st.title(":material/menu_book: 오답노트")

# 모의고사 미응답과 지워진 문제의 기록은 오답노트에 넣지 않는다
attempts = analyzer.usable_attempts(db.fetch_attempts(), qb.load_questions())
notes: dict[str, dict] = {}
for a in attempts:
    note = notes.setdefault(a["question_id"], {"wrong": 0, "last_wrong": None, "resolved": False})
    if a["is_correct"]:
        note["resolved"] = True
    else:
        note.update(wrong=note["wrong"] + 1, last_wrong=a["chosen"], resolved=False)
notes = {qid: n for qid, n in notes.items() if n["wrong"]}

if not notes:
    empty_state(
        "아직 틀린 문제가 없습니다. 문제를 풀다 틀린 문제는 이곳에 모여 해설과 함께 다시 볼 수 있습니다.",
        "문제 풀러 가기", "views/quiz.py", ":material/edit_note:",
    )
    st.stop()

c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
subject = c1.selectbox("과목", ["전체", *SUBJECTS])
only_open = c2.toggle("아직 못 맞힌 문제만", value=True)

items = [
    (qb.get_question(qid), n)
    for qid, n in notes.items()
    if (subject == "전체" or qb.get_question(qid)["subject"] == subject) and not (only_open and n["resolved"])
]
items.sort(key=lambda pair: (-pair[1]["wrong"], SUBJECTS.index(pair[0]["subject"])))

resolved_count = sum(n["resolved"] for n in notes.values())
open_ids = [qid for qid, n in notes.items() if not n["resolved"]]
st.caption(f"오답 {len(notes)}문항 중 {resolved_count}문항 극복 · 표시 {len(items)}문항")
if open_ids and st.button(f"못 맞힌 {len(open_ids)}문항 다시 풀기", type="primary", icon=":material/replay:"):
    request_set("오답 다시 풀기", open_ids)
if not items:
    st.success(
        "조건에 맞는 오답이 없습니다. 틀렸던 문제를 모두 다시 맞혔어요!" if only_open else "조건에 맞는 오답이 없습니다.",
        icon=":material/celebration:",
    )

for q, note in items:
    status = ":green[:material/check_circle: 극복]" if note["resolved"] else f":red[:material/cancel: {note['wrong']}회 오답]"
    with st.expander(f"{status} · [{q['unit']}] {q['question'][:45]}…"):
        render_question(q)
        render_choices(q, note["last_wrong"])
        render_feedback(q, note["last_wrong"], auto_ai=False, key=f"note_{q['id']}")

st.divider()
with st.expander("풀이 기록 초기화", icon=":material/delete:"):
    st.caption("풀이 이력과 오답 기록을 모두 삭제합니다." + (" 생성된 AI 해설은 유지됩니다." if explainer.is_configured() else ""))
    confirm = st.checkbox("초기화에 동의합니다")
    if st.button("초기화", type="primary", disabled=not confirm):
        db.reset_history()
        st.rerun()
