"""오답 이력 분석: 취약 단원 진단과 문제 추천."""

import random

import pandas as pd

from core.config import SUBJECTS

RECENCY_DECAY = 0.8  # 같은 단원에서 한 번 이전 풀이일수록 가중치를 0.8배로 낮춘다
MIN_ATTEMPTS = 2  # 이보다 적게 푼 단원은 진단하지 않는다
FULL_CONFIDENCE_ATTEMPTS = 3  # 이 횟수 이상 풀어야 취약도를 그대로 반영한다
WEAK_THRESHOLD = 0.4


def usable_attempts(attempts: list[dict], questions: list[dict] | tuple[dict, ...]) -> list[dict]:
    """분석에 쓸 기록만 남긴다.

    - 모의고사 미응답(chosen 없음)은 채점에서는 오답이지만, 실력을 보여주지 않으므로 분석에서 뺀다.
    - 문제 데이터에서 지워진 문제의 기록도 뺀다.
    """
    valid_ids = {q["id"] for q in questions}
    return [a for a in attempts if a["chosen"] is not None and a["question_id"] in valid_ids]


def _diagnose(attempts: int, weakness: float, recent: list[int]) -> str:
    if attempts < MIN_ATTEMPTS:
        return "데이터 부족"
    if recent[-2:] == [0, 0]:
        return "최근 연속 오답 · 집중 보완 필요"
    if weakness >= 0.6:
        return "집중 보완 필요"
    if weakness >= WEAK_THRESHOLD:
        return "보완 필요"
    return "양호"


def unit_stats(attempts: list[dict]) -> pd.DataFrame:
    """단원별 정답률과 취약도(최근 풀이에 가중치를 둔 오답률)를 계산한다."""
    columns = ["subject", "unit", "attempts", "correct", "accuracy", "weakness", "is_weak", "diagnosis"]
    if not attempts:
        return pd.DataFrame(columns=columns)

    grouped: dict[tuple[str, str], list[int]] = {}
    for a in attempts:
        grouped.setdefault((a["subject"], a["unit"]), []).append(a["is_correct"])

    rows = []
    for (subject, unit), results in grouped.items():
        n = len(results)
        weights = [RECENCY_DECAY**k for k in range(n)][::-1]  # 최신 풀이 가중치 1
        weighted_error = sum(w * (1 - r) for w, r in zip(weights, results)) / sum(weights)
        weakness = weighted_error * min(1.0, n / FULL_CONFIDENCE_ATTEMPTS)
        rows.append(
            {
                "subject": subject,
                "unit": unit,
                "attempts": n,
                "correct": sum(results),
                "accuracy": round(sum(results) / n * 100, 1),
                "weakness": round(weakness * 100, 1),
                "is_weak": n >= MIN_ATTEMPTS and weakness >= WEAK_THRESHOLD,
                "diagnosis": _diagnose(n, weakness, results),
            }
        )
    df = pd.DataFrame(rows, columns=columns)
    return df.sort_values(["weakness", "attempts"], ascending=[False, False]).reset_index(drop=True)


def subject_stats(attempts: list[dict]) -> pd.DataFrame:
    rows = []
    for subject in SUBJECTS:
        results = [a["is_correct"] for a in attempts if a["subject"] == subject]
        n = len(results)
        rows.append(
            {
                "subject": subject,
                "attempts": n,
                "correct": sum(results),
                "accuracy": round(sum(results) / n * 100, 1) if n else None,
            }
        )
    return pd.DataFrame(rows)


def weak_units(attempts: list[dict]) -> pd.DataFrame:
    df = unit_stats(attempts)
    if df.empty:
        return df
    return df[df["is_weak"].astype(bool)].reset_index(drop=True)


def _similarity(a: dict, b: dict) -> float:
    ka, kb = set(a.get("keywords", [])), set(b.get("keywords", []))
    jaccard = len(ka & kb) / len(ka | kb) if ka | kb else 0.0
    return jaccard + (0.3 if a["unit"] == b["unit"] else 0.0)


def similar_questions(question: dict, questions: list[dict], k: int = 3, exclude: set[str] | None = None) -> list[dict]:
    """키워드와 단원이 겹치는 유사 문제를 반환한다."""
    exclude = (exclude or set()) | {question["id"]}
    scored = [
        (s, q) for q in questions if q["id"] not in exclude and (s := _similarity(question, q)) > 0
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [q for _, q in scored[:k]]


def recommend(attempts: list[dict], questions: list[dict], size: int = 10, seed: int | None = None) -> list[tuple[dict, str]]:
    """오답 이력을 바탕으로 (문제, 추천 이유) 목록을 만든다.

    우선순위: ① 아직 못 맞힌 오답 다시 풀기 → ② 취약 단원의 안 푼 문제
    → ③ 틀린 문제와 개념이 겹치는 유사 문제 → ④ 안 푼 문제로 채우기.
    """
    rng = random.Random(seed)
    by_id = {q["id"]: q for q in questions}
    latest: dict[str, int] = {}
    for a in attempts:
        latest[a["question_id"]] = a["is_correct"]
    solved = set(latest)
    still_wrong = [qid for qid, ok in latest.items() if not ok and qid in by_id]

    weak = weak_units(attempts)
    weakness_by_unit = dict(zip(weak["unit"], weak["weakness"]))

    picked: list[tuple[dict, str]] = []
    picked_ids: set[str] = set()

    def add(q: dict, reason: str) -> bool:
        if len(picked) >= size or q["id"] in picked_ids:
            return False
        picked.append((q, reason))
        picked_ids.add(q["id"])
        return True

    # ① 오답 재도전: 전체의 40%까지, 취약도가 높은 단원부터
    retry_quota = max(1, int(size * 0.4))
    still_wrong.sort(key=lambda qid: weakness_by_unit.get(by_id[qid]["unit"], 0), reverse=True)
    for qid in still_wrong[:retry_quota]:
        add(by_id[qid], "다시 풀기 · 최근에 틀린 문제")

    # ② 취약 단원 보강
    for unit in weak["unit"]:
        candidates = [q for q in questions if q["unit"] == unit and q["id"] not in solved]
        rng.shuffle(candidates)
        for q in candidates[:2]:
            add(q, f"취약 단원 보강 · {unit}")

    # ③ 틀린 문제와 개념이 겹치는 유사 문제
    for qid in still_wrong:
        wrong_q = by_id[qid]
        for q in similar_questions(wrong_q, questions, k=2, exclude=picked_ids):
            shared = set(q["keywords"]) & set(wrong_q["keywords"])
            label = f"'{sorted(shared)[0]}'" if shared else f"'{wrong_q['unit']}' 단원"
            add(q, f"유사 개념 · {label} 관련")

    # ④ 남은 자리는 안 푼 문제(없으면 전체)에서 무작위로 채운다
    unsolved = [q for q in questions if q["id"] not in solved]
    rng.shuffle(unsolved)
    for q in unsolved:
        add(q, "새 문제 · 아직 풀지 않은 문제")
    rest = list(questions)
    rng.shuffle(rest)
    for q in rest:
        add(q, "복습 · 이전에 맞힌 문제")
    return picked
