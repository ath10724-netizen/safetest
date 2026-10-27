"""여러 화면에서 함께 쓰는 Streamlit 컴포넌트."""

import streamlit as st

from core import analyzer, config, db, explainer, law_search
from core import question_bank as qb
from ui.styles import esc, md

CIRCLED = "①②③④⑤"
DIFFICULTY_COLOR = {"하": "green", "중": "blue", "상": "violet"}


def choice_label(question: dict, original: int, perm: list[int] | None = None) -> str:
    """보기 번호(1부터)를 화면에 보이는 순서의 원문자와 함께 표시한다."""
    pos = perm.index(original) if perm else original - 1
    return f"{CIRCLED[pos]} {question['choices'][original - 1]}"


def question_badges(question: dict) -> str:
    level = question["difficulty"]
    return (
        f":gray-badge[{question['subject']}] :gray-badge[{question['unit']}] "
        f":{DIFFICULTY_COLOR[level]}-badge[난이도 {level}] :gray-badge[{question['round']}]"
    )


def render_question(question: dict, number: int | None = None) -> None:
    st.markdown(question_badges(question))
    num = f'<span class="qb-num">Q{number}.</span>' if number else ""
    st.html(f'<div class="qb-question">{num}{esc(question["question"])}</div>')


def render_choices(question: dict, chosen: int | None, perm: list[int] | None = None) -> None:
    """채점 후 보기 목록. 색만으로 구분하지 않도록 '정답', '내 답' 라벨을 함께 붙인다."""
    order = perm or list(range(1, len(question["choices"]) + 1))
    rows = []
    for orig in order:
        cls, tag = "", ""
        if orig == question["answer"]:
            cls, tag = "is-correct", "✓ 정답" + (" · 내 답" if orig == chosen else "")
        elif orig == chosen:
            cls, tag = "is-wrong", "✗ 내 답"
        rows.append(
            f'<div class="qb-choice {cls}"><span>{esc(choice_label(question, orig, perm))}</span>'
            f'<span class="qb-tag">{tag}</span></div>'
        )
    st.html("".join(rows))


def render_laws(question: dict) -> None:
    laws = law_search.search(question)
    if not laws:
        return
    with st.expander("관련 법령·개념", icon=":material/gavel:"):
        for law in laws:
            st.markdown(f"**{law['title']}**  \n:gray[{law['source']}]")
            st.caption(md(law["content"]))
        st.caption("학습용 요약입니다. 최신 법령은 국가법령정보센터(law.go.kr)에서 확인하세요.")


def render_ai_explanation(question: dict, chosen: int, auto: bool, key: str) -> None:
    """저장된 해설이 있으면 보여주고, 없으면 Claude로 생성해 저장한다.

    API 키가 없으면 AI 해설 영역을 아예 그리지 않는다(기본 해설만으로 학습하는 경우).
    """
    cached = db.get_explanation(question["id"], chosen)
    if not cached and not explainer.is_configured():
        return
    with st.container(border=True, key=f"aibox_{key}"):
        st.markdown("**:material/auto_awesome: AI 맞춤 해설**")
        if cached:
            st.markdown(md(cached))
            return

        failed: set[str] = st.session_state.setdefault("ai_failed", set())
        retry: set[str] = st.session_state.setdefault("ai_retry", set())
        if key in retry:
            retry.discard(key)
        elif not auto or key in failed:
            st.caption("틀린 이유와 법령 근거를 AI가 정리해 드립니다.")
            if not st.button("AI 해설 생성", key=f"ai_{key}", icon=":material/auto_awesome:"):
                return

        laws = law_search.search(question)
        try:
            with st.spinner("법령 근거를 찾아 해설을 작성하는 중…"):
                text = st.write_stream(md(chunk) for chunk in explainer.stream_explanation(question, chosen, laws))
        except explainer.ExplainerError as e:
            failed.add(key)
            st.warning(str(e), icon=":material/error:")
            # 실패한 화면에서 바로 재시도할 수 있게 한다. 자동 재호출은 하지 않는다.
            st.button("다시 시도", key=f"ai_retry_{key}", icon=":material/refresh:", on_click=retry.add, args=(key,))
            return
        failed.discard(key)
        if isinstance(text, str) and text.strip():
            db.save_explanation(question["id"], chosen, text, config.CLAUDE_MODEL)


def render_similar(question: dict) -> None:
    similar = analyzer.similar_questions(question, list(qb.load_questions()), k=3)
    if not similar:
        return
    with st.expander("함께 풀어볼 유사 문제", icon=":material/repeat:"):
        for q in similar:
            st.markdown(f":gray-badge[{q['unit']}] {md(q['question'])}")
        st.caption("유사 문제는 '약점 분석' 화면의 추천 세트에 자동으로 포함됩니다.")


def render_feedback(question: dict, chosen: int | None, perm: list[int] | None = None, auto_ai: bool = False, key: str = "") -> None:
    """채점 결과와 해설을 표시한다. 오답이면 법령 근거, AI 해설, 유사 문제까지 보여준다.

    순서: 결과 → 기본 해설 → 관련 법령(접기) → AI 해설 → 유사 문제(접기)
    """
    answer_text = choice_label(question, question["answer"], perm)
    if chosen == question["answer"]:
        st.success(f"**정답입니다!** {answer_text}", icon=":material/check_circle:")
    elif chosen is None:
        st.error(f"**답을 고르지 않았습니다.** 정답: {answer_text}", icon=":material/timer_off:")
    else:
        st.error(
            f"**오답입니다.** 고른 답 {choice_label(question, chosen, perm)} → 정답 {answer_text}",
            icon=":material/cancel:",
        )

    st.markdown("**:material/menu_book: 기본 해설**")
    st.markdown(md(question["explanation"]))
    render_laws(question)

    if chosen is not None and chosen != question["answer"]:
        render_ai_explanation(question, chosen, auto=auto_ai, key=key or question["id"])
        render_similar(question)


def empty_state(message: str, button_label: str, page: str, icon: str) -> None:
    """빈 화면에서 다음 행동을 안내한다."""
    with st.container(border=True):
        st.markdown(message)
        if st.button(button_label, type="primary", icon=icon):
            st.switch_page(page)
