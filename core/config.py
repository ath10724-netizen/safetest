"""앱 전역 설정."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
QUESTIONS_PATH = DATA_DIR / "questions.json"
LAWS_PATH = DATA_DIR / "laws.json"
DB_PATH = Path(os.getenv("HISTORY_DB_PATH", BASE_DIR / "db" / "history.db"))

# 산업안전기사 필기 과목 (2020년 개편 기준, 과목당 20문항)
SUBJECTS = [
    "산업재해 예방 및 안전보건교육",
    "인간공학 및 위험성 평가·관리",
    "기계·기구 및 설비 안전관리",
    "전기설비 안전관리",
    "화학설비 안전관리",
    "건설공사 안전관리",
]
DIFFICULTIES = ["하", "중", "상"]

# 합격 기준: 과목당 40점 이상, 전 과목 평균 60점 이상
PASS_SUBJECT_SCORE = 40
PASS_AVERAGE_SCORE = 60
# 실제 시험은 120문항 150분 → 문항당 75초
EXAM_SECONDS_PER_QUESTION = 75

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
CLAUDE_EFFORT = os.getenv("CLAUDE_EFFORT", "medium")
CLAUDE_MAX_TOKENS = 16000
