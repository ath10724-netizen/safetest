"""화면 스타일: 색 토큰과 사용자 정의 CSS를 한 곳에서 관리한다.

스타일은 st.container(key=...)가 붙이는 `st-key-<key>` 클래스와 직접 쓴 HTML 클래스(qb-*)에만 건다.
Streamlit 내부 클래스명(st-emotion-cache-*)에는 기대지 않는다.
"""

import html

import streamlit as st

TOKENS = {
    "light": {
        "bg": "#FFFFFF",
        "surface": "#F6F5F2",
        "border": "#E4E2DD",
        "muted": "#5F636B",
        "accent": "#C2410C",
        "accent-bg": "#FFF4EC",
        "success": "#15803D",
        "success-bg": "#EEF9F1",
        "danger": "#B91C1C",
        "danger-bg": "#FDF0F0",
        "warning": "#A15C07",
        "warning-bg": "#FEF7E6",
    },
    "dark": {
        "bg": "#15171C",
        "surface": "#1E222A",
        "border": "#2F3440",
        "muted": "#A3A7AF",
        "accent": "#FB923C",
        "accent-bg": "#2A1C12",
        "success": "#4ADE80",
        "success-bg": "#132619",
        "danger": "#F87171",
        "danger-bg": "#2B1618",
        "warning": "#FBBF24",
        "warning-bg": "#2A2210",
    },
}

CSS = """
/* 문제 본문 */
.qb-question { font-size: 1.12rem; font-weight: 600; line-height: 1.65; margin: .25rem 0 .5rem; word-break: keep-all; overflow-wrap: anywhere; }
.qb-question .qb-num { color: var(--qb-accent); margin-right: .35rem; }

/* 풀이 중 보기: 클릭 영역을 넓힌다 */
[class*="st-key-answer_area"] [data-testid="stRadioOption"] {
  width: 100%; padding: .55rem .8rem; margin: .2rem 0;
  border: 1px solid var(--qb-border); border-radius: .6rem;
}
[class*="st-key-answer_area"] [data-testid="stRadioOption"]:hover { border-color: var(--qb-accent); }

/* 채점 후 보기 */
.qb-choice { display: flex; gap: .6rem; align-items: flex-start; padding: .55rem .8rem; margin: .35rem 0;
  border: 1px solid var(--qb-border); border-radius: .6rem; line-height: 1.5; }
.qb-choice .qb-tag { margin-left: auto; font-size: .8rem; font-weight: 700; white-space: nowrap; }
.qb-choice.is-correct { border-color: var(--qb-success); background: var(--qb-success-bg); }
.qb-choice.is-correct .qb-tag { color: var(--qb-success); }
.qb-choice.is-wrong { border-color: var(--qb-danger); background: var(--qb-danger-bg); }
.qb-choice.is-wrong .qb-tag { color: var(--qb-danger); }

/* 상단 고정 진행률: Streamlit이 블록을 같은 높이의 래퍼로 감싸므로 그 부모(:has)를 고정한다 */
:has(> .st-key-quiz_progress) { position: sticky; top: 3.75rem; z-index: 20; }
.st-key-quiz_progress { position: relative; background: var(--qb-bg); padding: .5rem 0 .4rem; }
/* 고정된 진행률 위쪽(투명한 상단 헤더 영역)으로 스크롤된 내용이 비치지 않게 가린다 */
.st-key-quiz_progress::before { content: ""; position: absolute; left: 0; right: 0; bottom: 100%; height: 3.75rem; background: var(--qb-bg); }
.qb-progress-text { display: flex; justify-content: space-between; font-size: .9rem; color: var(--qb-muted); margin-bottom: .3rem; }
.qb-progress-text b { color: inherit; }

/* AI 해설 상자: 소제목이 페이지 제목보다 커지지 않게 한다 */
[class*="st-key-aibox"] { border-left: 4px solid var(--qb-accent) !important; }
[class*="st-key-aibox"] h4 { font-size: 1.02rem; margin: .9rem 0 .3rem; padding: 0; }

/* 결과 배너 */
.qb-banner { padding: 1.1rem 1.3rem; border-radius: .8rem; border: 1px solid; margin: .5rem 0 1rem; }
.qb-banner .qb-banner-title { font-size: 1.6rem; font-weight: 800; }
.qb-banner .qb-banner-sub { margin-top: .25rem; color: var(--qb-muted); }
.qb-banner.is-pass { border-color: var(--qb-success); background: var(--qb-success-bg); }
.qb-banner.is-pass .qb-banner-title { color: var(--qb-success); }
.qb-banner.is-fail { border-color: var(--qb-danger); background: var(--qb-danger-bg); }
.qb-banner.is-fail .qb-banner-title { color: var(--qb-danger); }
.qb-banner.is-info { border-color: var(--qb-border); background: var(--qb-surface); }

/* 모의고사 타이머 */
.st-key-timer_warn [data-testid="stMetricValue"] { color: var(--qb-warning); }
.st-key-timer_danger [data-testid="stMetricValue"] { color: var(--qb-danger); }

/* 진단 단계별 카드 */
[class*="st-key-level_danger"] { border-left: 4px solid var(--qb-danger) !important; }
[class*="st-key-level_warning"] { border-left: 4px solid var(--qb-warning) !important; }
[class*="st-key-level_ok"] { border-left: 4px solid var(--qb-success) !important; }
[class*="st-key-accent"] { border-left: 4px solid var(--qb-accent) !important; }

/* 보조 문구 */
.qb-muted { color: var(--qb-muted); font-size: .9rem; }
.qb-step { display: flex; gap: .75rem; align-items: flex-start; margin: .5rem 0; }
.qb-step .qb-step-num { flex: none; width: 1.7rem; height: 1.7rem; border-radius: 50%; display: grid; place-items: center;
  background: var(--qb-accent-bg); color: var(--qb-accent); font-weight: 700; }
"""


def theme_type() -> str:
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:
        return "light"


def color(name: str) -> str:
    return TOKENS[theme_type()][name]


def inject() -> None:
    variables = ";".join(f"--qb-{k}:{v}" for k, v in TOKENS[theme_type()].items())
    st.html(f"<style>:root{{{variables}}}{CSS}</style>")


def esc(text: str) -> str:
    return html.escape(str(text))


def md(text: str) -> str:
    """마크다운으로 표시할 본문을 안전하게 만든다. '10~15mA' 같은 범위 표기가 취소선(~)으로 바뀌지 않게 한다."""
    return str(text).replace("~", r"\~")
