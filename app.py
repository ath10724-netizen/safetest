"""산업안전기사 필기 문제은행 — Streamlit 진입점.

실행: streamlit run app.py
"""

import streamlit as st

from core import config, db, explainer
from ui import session, styles

st.set_page_config(page_title="산업안전기사 필기 문제은행", page_icon=":material/health_and_safety:", layout="centered")
db.init_db()
styles.inject()
if session.restore_state():
    st.toast("풀던 문제를 불러왔습니다. 이어서 풀 수 있습니다.", icon=":material/history:")

pages = [
    st.Page("views/home.py", title="홈", icon=":material/home:", default=True),
    st.Page("views/quiz.py", title="문제 풀이", icon=":material/edit_note:"),
    st.Page("views/analysis.py", title="약점 분석", icon=":material/analytics:"),
    st.Page("views/wrong_notes.py", title="오답노트", icon=":material/menu_book:"),
]
page = st.navigation(pages)

with st.sidebar:
    # AI 해설은 선택 기능: API 키가 있을 때만 상태를 표시한다
    if explainer.is_configured():
        st.caption(f":material/auto_awesome: AI 해설 켜짐 · {config.CLAUDE_MODEL}")

page.run()
