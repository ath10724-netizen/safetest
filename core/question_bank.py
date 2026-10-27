"""문제 데이터 로드 및 필터링.

문제의 정답(answer)과 사용자가 고른 답은 모두 1부터 시작하는 보기 번호를 쓴다.
"""

import json
from functools import lru_cache

from core.config import QUESTIONS_PATH, SUBJECTS


@lru_cache(maxsize=1)
def load_questions() -> tuple[dict, ...]:
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        return tuple(json.load(f))


@lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    return {q["id"]: q for q in load_questions()}


def get_question(qid: str) -> dict | None:
    return _index().get(qid)


def list_rounds() -> list[str]:
    return sorted({q["round"] for q in load_questions()})


def list_units(subject: str | None = None) -> list[str]:
    units: dict[str, None] = {}
    for q in load_questions():
        if subject is None or q["subject"] == subject:
            units.setdefault(q["unit"])
    return list(units)


def filter_questions(
    subjects: list[str] | None = None,
    rounds: list[str] | None = None,
    difficulties: list[str] | None = None,
    units: list[str] | None = None,
) -> list[dict]:
    """조건에 맞는 문제를 과목 순서대로 반환한다. 빈 조건은 전체를 의미한다."""
    result = [
        q
        for q in load_questions()
        if (not subjects or q["subject"] in subjects)
        and (not rounds or q["round"] in rounds)
        and (not difficulties or q["difficulty"] in difficulties)
        and (not units or q["unit"] in units)
    ]
    return sorted(result, key=lambda q: SUBJECTS.index(q["subject"]))
