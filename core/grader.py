"""채점과 합격 판정."""

from dataclasses import dataclass, field

from core.config import PASS_AVERAGE_SCORE, PASS_SUBJECT_SCORE, SUBJECTS


def is_correct(question: dict, chosen: int | None) -> bool:
    return chosen is not None and chosen == question["answer"]


@dataclass
class SubjectScore:
    subject: str
    total: int = 0
    correct: int = 0

    @property
    def score(self) -> float:
        return round(self.correct / self.total * 100, 1) if self.total else 0.0

    @property
    def passed(self) -> bool:
        return self.score >= PASS_SUBJECT_SCORE


@dataclass
class ExamResult:
    subjects: list[SubjectScore] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(s.total for s in self.subjects)

    @property
    def correct(self) -> int:
        return sum(s.correct for s in self.subjects)

    @property
    def average(self) -> float:
        """실제 시험처럼 과목별 점수의 평균으로 계산한다."""
        if not self.subjects:
            return 0.0
        return round(sum(s.score for s in self.subjects) / len(self.subjects), 1)

    @property
    def fail_reasons(self) -> list[str]:
        reasons = [
            f"{s.subject} 과락 ({s.score}점 < {PASS_SUBJECT_SCORE}점)"
            for s in self.subjects
            if not s.passed
        ]
        if self.average < PASS_AVERAGE_SCORE:
            reasons.append(f"평균 미달 ({self.average}점 < {PASS_AVERAGE_SCORE}점)")
        return reasons

    @property
    def passed(self) -> bool:
        return bool(self.subjects) and not self.fail_reasons


def summarize(questions: list[dict], answers: dict[str, int | None]) -> ExamResult:
    """문제 목록과 {문제ID: 선택한 보기 번호}로 과목별 점수를 계산한다."""
    by_subject: dict[str, SubjectScore] = {}
    for q in questions:
        score = by_subject.setdefault(q["subject"], SubjectScore(q["subject"]))
        score.total += 1
        score.correct += is_correct(q, answers.get(q["id"]))
    ordered = sorted(by_subject.values(), key=lambda s: SUBJECTS.index(s.subject))
    return ExamResult(subjects=ordered)
