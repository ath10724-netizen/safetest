# 🦺 산업안전기사 필기 문제은행

직장인 수험생을 위한 문제 풀이 중심 학습 플랫폼입니다.
과목·회차·난이도별로 문제를 풀고 바로 채점받습니다. 틀린 문제는 관련 법령을 근거로 한 Claude AI 해설로 이해하고, 누적된 오답 이력으로 취약 단원과 추천 문제를 확인할 수 있습니다.

## 주요 기능

| 화면 | 기능 |
|---|---|
| 문제 풀이 | **연습 모드**: 한 문제씩 제출 즉시 채점하고, 오답이면 AI 해설을 자동 생성<br>**모의고사 모드**: 문항당 75초 제한 타이머, 시간 종료 시 자동 제출, 과목별 과락·평균 판정 |
| 약점 분석 | 과목별 정답률 레이더 차트, 최근 풀이에 가중치를 둔 취약 단원 진단, 맞춤 추천 문제 세트(오답 재도전 → 취약 단원 → 유사 개념 순) |
| 오답노트 | 틀린 문제 모아보기, 극복 여부 표시, 저장된 AI 해설 다시 보기 |

## 설치 및 실행

```bash
pip install -r requirements.txt
cp .env.example .env          # ANTHROPIC_API_KEY 입력
streamlit run app.py
```

API 키가 없어도 앱은 동작하며, 이 경우 기본 해설과 관련 법령만 표시됩니다.

## AI 해설 동작

1. 오답이 나오면 `core/law_search.py`가 `data/laws.json`에서 관련 조항을 찾습니다. 문제에 직접 연결된 조항, 같은 단원, 키워드 일치 순으로 점수를 매깁니다.
2. 찾은 조항, 문제, 수험생이 고른 답을 Claude(`claude-opus-5-5`)에 보내고 해설을 스트리밍으로 받습니다. 해설은 다음 순서로 구성됩니다.
   - 틀린 이유
   - 정답 근거
   - 암기 포인트
   - 출제 함정
3. 생성된 해설은 SQLite에 `(문제ID, 고른 답)` 단위로 캐시되어 같은 오답에 API를 다시 호출하지 않습니다.
4. 안전 분류기가 요청을 거절하면 서버 측 fallback(`fallbacks="default"`)이 권장 모델로 재시도합니다.

모델과 effort는 `.env`의 `CLAUDE_MODEL`, `CLAUDE_EFFORT`로 바꿀 수 있습니다.

## 폴더 구조

```
app.py               진입점 (페이지 내비게이션)
views/               화면: home, quiz, analysis, wrong_notes
ui/components.py     문제·해설·법령 표시 공용 컴포넌트
core/
  config.py          과목, 합격 기준, 모델 설정
  question_bank.py   문제 로드·필터링
  grader.py          채점, 과락·평균 판정
  db.py              SQLite (sessions, attempts, explanations)
  law_search.py      법령·개념 검색
  explainer.py       Claude API 해설 생성
  analyzer.py        취약 단원 진단, 유사 문제·추천 세트
data/
  questions.json     문제 (answer는 1부터 시작하는 보기 번호)
  laws.json          법령·개념 요약
tests/test_core.py   단위 테스트 (pytest)
```

## 문제 추가하기

`data/questions.json`에 아래 형식으로 문제를 추가합니다. `law_refs`에는 `laws.json`의 조항 ID를 적습니다.

```json
{
  "id": "S1-R3-01", "subject": "산업재해 예방 및 안전보건교육", "unit": "재해조사 및 분석",
  "round": "모의 3회", "difficulty": "중",
  "question": "...", "choices": ["...", "...", "...", "..."], "answer": 2,
  "explanation": "...", "keywords": ["도수율"], "law_refs": ["L03"]
}
```

`subject`는 `core/config.py`의 `SUBJECTS`에 있는 6과목 중 하나여야 합니다. 추가한 뒤 `pytest`로 데이터 무결성을 확인하세요.

> 수록 문제는 학습용 예시이며 실제 기출 원문이 아닙니다. 법령 요약은 학습용이므로 최신 내용은 국가법령정보센터(law.go.kr)에서 확인하세요.
