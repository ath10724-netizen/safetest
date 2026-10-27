"""문제와 관련된 법령·개념 조항을 로컬 데이터에서 검색한다."""

import json
from functools import lru_cache

from core.config import LAWS_PATH


@lru_cache(maxsize=1)
def load_laws() -> tuple[dict, ...]:
    with open(LAWS_PATH, encoding="utf-8") as f:
        return tuple(json.load(f))


def _score(law: dict, question: dict) -> int:
    text = " ".join([question["question"], *question["choices"]])
    q_keywords = set(question.get("keywords", []))
    score = 0
    if law["id"] in question.get("law_refs", []):
        score += 10
    if question["unit"] in law.get("units", []):
        score += 3
    score += 2 * len(q_keywords & set(law["keywords"]))
    score += sum(1 for kw in law["keywords"] if kw in text)
    return score


def search(question: dict, top_k: int = 3) -> list[dict]:
    """문제에 직접 연결된 조항, 같은 단원, 키워드 일치 순으로 점수를 매겨 반환한다."""
    scored = [(s, law) for law in load_laws() if (s := _score(law, question)) > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [law for _, law in scored[:top_k]]


def search_by_unit(unit: str) -> list[dict]:
    return [law for law in load_laws() if unit in law.get("units", [])]
