"""화면 로직 테스트 (streamlit.testing.v1.AppTest)."""

import pytest
from streamlit.testing.v1 import AppTest

from core import db

QUIZ_PAGE = "../views/quiz.py"  # 이 테스트 파일 기준 경로


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "ui.db")
    db.init_db()


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def _start_exam(count=3):
    at = AppTest.from_file(QUIZ_PAGE, default_timeout=20)
    at.run()
    at.radio[0].set_value("exam")
    at.number_input[0].set_value(count)
    _button(at, "풀이 시작").click().run()
    assert not at.exception
    return at


def test_exam_selection_survives_widget_state_loss():
    """B1: 다른 화면에 다녀와 위젯 상태가 지워져도 고른 답이 유지된다."""
    at = _start_exam()
    quiz = at.session_state["quiz"]
    qid = quiz["ids"][0]
    key = f"e_{quiz['session_id']}_{qid}"
    at.radio(key=key).set_value(2).run()
    assert at.session_state["quiz"]["selections"][qid] == 2
    # 다른 화면에 다녀오는 상황: 라디오가 그려지지 않는 실행을 한 번 거치면 Streamlit이 위젯 상태를 지운다
    at.session_state["quiz"] = None
    at.run()
    assert key not in at.session_state
    at.session_state["quiz"] = quiz
    at.run()
    assert at.radio(key=key).value == 2


def test_exam_stop_records_only_selected():
    """B1·B5: 중단하면 고른 답만 기록하고, 아무것도 고르지 않았으면 세션을 지운다."""
    at = _start_exam()
    quiz = at.session_state["quiz"]
    qid = quiz["ids"][0]
    at.radio(key=f"e_{quiz['session_id']}_{qid}").set_value(1).run()
    _button(at, "풀이 중단").click().run()
    attempts = db.fetch_attempts()
    assert [(a["question_id"], a["chosen"]) for a in attempts] == [(qid, 1)]
    assert db.unfinished_session_ids() == []

    at2 = _start_exam()
    _button(at2, "풀이 중단").click().run()
    assert len(db.fetch_sessions()) == 1  # 빈 세션은 남지 않는다


def test_empty_pending_set_cannot_start():
    """B2: 0문항 세트는 시작 버튼이 비활성화되고 오류가 나지 않는다."""
    at = AppTest.from_file(QUIZ_PAGE, default_timeout=20)
    at.session_state["pending_set"] = {"title": "빈 세트", "ids": []}
    at.run()
    assert not at.exception
    assert _button(at, "연습 모드로 풀기").disabled


def test_restore_after_refresh():
    """B4: 새 세션(새로고침)에서도 저장된 미완료 풀이와 고른 답을 불러온다."""
    at = _start_exam()
    quiz = at.session_state["quiz"]
    qid = quiz["ids"][1]
    at.radio(key=f"e_{quiz['session_id']}_{qid}").set_value(3).run()

    fresh = AppTest.from_string(
        "from ui import session\nimport streamlit as st\nst.write(session.restore_state())\n", default_timeout=20
    )
    fresh.run()
    assert not fresh.exception
    restored = fresh.session_state["quiz"]
    assert restored["session_id"] == quiz["session_id"]
    assert restored["selections"][qid] == 3
