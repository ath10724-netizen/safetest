# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Streamlit study app for the Korean 산업안전기사 (Industrial Safety Engineer) written exam: question bank with practice/mock-exam modes, Claude-generated explanations for wrong answers grounded in a local law/concept dataset, and weakness analysis with recommendations. Single-user, local SQLite. UI text, code comments, and docs are in Korean — keep it that way.

Key docs: `PRD.md` (requirements with IDs like F1-4, scoring/weakness formulas), `REVIEW.md` (bug review B1–B9, fixes, law verification), `PROMPTS.md` (staged build prompts).

## Commands

```bash
pip install -r requirements.txt
streamlit run app.py                         # needs .env with ANTHROPIC_API_KEY for AI explanations (app works without it)
python -m pytest -q                          # all tests (pytest.ini sets pythonpath=.)
python -m pytest tests/test_ui.py::test_restore_after_refresh -q   # single test
```

Run the app against a throwaway DB so real history isn't polluted: `HISTORY_DB_PATH=/tmp/x.db streamlit run app.py --server.headless true --server.port 8599`.

There is no linter/formatter configured.

`/quiz-add <과목 1~6> <회차 숫자> <하|중|상> <문항수>` (`.claude/commands/quiz-add.md`) adds questions to `data/questions.json` following the content rules below; e.g. `/quiz-add 5 3 상 2`. In command files, parse `$ARGUMENTS` in order — positional `$1`…`$4` arrived shifted by one in this environment.

## Architecture

- `app.py` — entry: `db.init_db()` (also migrates old schemas), `styles.inject()`, `session.restore_state()`, then `st.navigation` over `views/*.py`.
- `core/` — pure logic, no Streamlit: `config` (subjects, pass rules 40/60, 75 s per question, model `claude-opus-5-5`), `question_bank`, `grader`, `db`, `law_search`, `explainer` (Anthropic SDK streaming, `fallbacks="default"`, maps SDK errors to `ExplainerError`), `analyzer` (weakness score, recommendations).
- `ui/session.py` — quiz lifecycle shared by all pages: `start_quiz`, `finish_quiz`, `submit_exam`, `end_quiz`, `request_set` (confirm dialog when a quiz is in progress), `save_state`/`restore_state`.
- `ui/components.py` — question/choices/feedback/AI-explanation widgets; `ui/styles.py` — color tokens and the only custom CSS.
- `data/questions.json`, `data/laws.json` — content. `answer` and all stored choices are **1-based original choice numbers**; `law_refs` point to `laws.json` ids. `tests/test_core.py` enforces data integrity and balanced answer positions.

### Invariants that span files

- **Quiz state lives in `st.session_state["quiz"]` and is mirrored to `sessions.state` (JSON)** after every change so a refresh/new tab resumes it. Finishing a session clears `state`. Because restore picks the latest unfinished session, two tabs share one quiz (documented limitation).
- **Mock-exam answers are stored in `quiz["selections"]`, not read from widget state.** Streamlit deletes widget state when the widget isn't rendered (e.g. user visits another page), so radios are re-seeded via `index=` from `selections`. Don't reintroduce reads of `st.session_state[widget_key]` for answers.
- **Choice shuffling**: `quiz["perm"][qid]` maps display order → original numbers. Grade and persist original numbers; use `choice_label(..., perm)` for display.
- **Analysis inputs go through `analyzer.usable_attempts()`**, which drops unanswered exam items (`chosen is None`) and attempts for questions no longer in the data. Grading still counts unanswered as wrong; analysis/recommendations/wrong-notes must not.
- **Starting a different question set from any page must use `request_set()`**, never set `st.session_state["quiz"] = None` directly (that silently discards progress and leaves unfinished sessions).
- **AI explanations are optional.** Without an API key (`explainer.is_configured()` false) every AI-related UI element and hint is hidden, not just disabled — the user studies with the built-in explanations only. Keep new AI UI behind the same check.
- **AI explanations are cached per `(question_id, chosen)`** in `explanations`; `db.reset_history()` keeps this cache on purpose (API cost). Failed auto-generation is not retried automatically (`ai_failed` set) — only via the "다시 시도" button.
- **Markdown text from data/AI must pass through `styles.md()`** (escapes `~`, otherwise ranges like `7~8mA … 10~15mA` render as strikethrough). HTML built for `st.html` must use `styles.esc()`.
- **Styling hooks**: CSS targets `st-key-<key>` classes from `st.container(key=...)` (and `[class*="st-key-prefix"]` for per-item keys), not `st-emotion-cache-*`. Sticky elements must style the parent via `:has(> .st-key-...)` because Streamlit wraps keyed blocks in a same-height layout wrapper. Theme colors are in `.streamlit/config.toml` (`[theme.light]`/`[theme.dark]`); plotly charts need colors from `styles.color()` explicitly (e.g. polar `bgcolor` doesn't follow the theme).

## Testing notes

- `tests/test_ui.py` uses `streamlit.testing.v1.AppTest`; `from_file` paths are relative to the test file (`../views/quiz.py`). Tests monkeypatch `core.db.DB_PATH` to a temp file. To simulate a page visit that drops widget state, run once with `session_state["quiz"] = None`, then restore it.
- For end-to-end checks with Playwright: `page.goto()` starts a new Streamlit session (which will auto-restore any unfinished quiz from the DB); navigate within a session by clicking sidebar links. Edits to `core/` or `ui/` modules need a server restart to take effect; `views/` pages reload on rerun.

## Content rules (questions.json / laws.json)

- Law figures in `data/laws.json` were verified against current statutes on 2026-10-27 (see `REVIEW.md` §9). Use post-amendment values, cite article numbers only when verified, and label textbook-only values as such. For calculation questions, prefer giving the needed constants in the question so the item doesn't depend on unverified figures; recompute answers and distractors in Python.
- Question IDs are `S{subject}-R{round}-{nn}`, where `nn` continues per subject across rounds (max + 1). Rounds are named `"모의 N회"`. Reuse existing unit names verbatim; a new unit needs a matching `laws.json` entry.
- Append new questions; never reorder or edit existing ones (stored attempts and cached explanations reference ids and original choice numbers). Write with `json.dump(..., ensure_ascii=False, indent=2)` plus a trailing newline.
- Keep answer positions balanced (max − min ≤ 4 across ①~④, enforced by `test_answer_positions_are_balanced`); check the current distribution before choosing where the answer goes. Numeric choices are ascending.
- Explanations must not refer to choice numbers (shuffling changes them) and must not contain `$` (rendered as math). They should say why the main distractors are wrong.
