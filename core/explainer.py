"""Claude API로 오답 맞춤 해설을 생성한다."""

import os
from collections.abc import Iterator

import anthropic

from core import config

SYSTEM_PROMPT = """당신은 산업안전기사 필기시험을 가르치는 강사입니다.
수험생은 퇴근 후 짧은 시간에 공부하는 직장인이며, 방금 문제를 틀렸습니다.
수험생이 왜 그 보기를 골랐을지 짐작하고, 오해를 바로잡아 다음에는 맞힐 수 있게 설명하세요.

원칙:
- 함께 제공되는 [관련 법령·개념] 자료를 1차 근거로 삼고, 인용할 때는 법령명과 조문(예: 안전보건규칙 제13조)을 밝힙니다.
- 자료에 없는 수치나 조문을 쓸 때는 일반적으로 알려진 기준임을 밝히고 "최신 법령 확인 권장"이라고 덧붙입니다.
- 계산 문제는 공식과 대입 과정을 한 줄씩 보여 줍니다.
- 2분 안에 읽을 수 있는 분량으로 간결하게 씁니다.

다음 마크다운 형식으로 답하세요:
#### ❌ 고른 답이 틀린 이유
#### ✅ 정답 근거
#### 📌 핵심 암기 포인트
(3개 이내 글머리표, 비슷한 수치·용어와 구별하는 요령 포함)
#### ⚠️ 출제 함정
(이 단원에서 자주 나오는 오답 유도 방식 한두 줄)"""

CIRCLED = "①②③④⑤"


class ExplainerError(Exception):
    """해설 생성 실패를 사용자에게 보여줄 메시지와 함께 전달한다."""


def is_configured() -> bool:
    return any(
        os.getenv(key) for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE")
    )


def build_prompt(question: dict, chosen: int, laws: list[dict]) -> str:
    choices = "\n".join(f"{CIRCLED[i]} {c}" for i, c in enumerate(question["choices"]))
    law_text = "\n\n".join(
        f"- {law['title']} ({law['source']})\n  {law['content']}" for law in laws
    ) or "- (검색된 자료 없음)"
    return f"""[과목] {question['subject']}
[단원] {question['unit']}

[문제]
{question['question']}

[보기]
{choices}

[정답] {CIRCLED[question['answer'] - 1]} {question['choices'][question['answer'] - 1]}
[수험생이 고른 답] {CIRCLED[chosen - 1]} {question['choices'][chosen - 1]}

[교재 기본 해설]
{question.get('explanation', '')}

[관련 법령·개념]
{law_text}"""


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def stream_explanation(question: dict, chosen: int, laws: list[dict]) -> Iterator[str]:
    """해설 텍스트를 스트리밍으로 내보낸다. 실패하면 ExplainerError를 던진다."""
    try:
        with _get_client().beta.messages.stream(
            model=config.CLAUDE_MODEL,
            max_tokens=config.CLAUDE_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(question, chosen, laws)}],
            output_config={"effort": config.CLAUDE_EFFORT},
            # 안전 분류기가 요청을 거절하면 서버가 권장 대체 모델로 재시도한다.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            yield from stream.text_stream
            final = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise ExplainerError("API 키 인증에 실패했습니다. .env의 ANTHROPIC_API_KEY를 확인하세요.") from e
    except anthropic.RateLimitError as e:
        raise ExplainerError("요청이 많아 잠시 제한되었습니다. 잠시 후 다시 시도하세요.") from e
    except anthropic.APIStatusError as e:
        raise ExplainerError(f"Claude API 오류가 발생했습니다 (HTTP {e.status_code}).") from e
    except anthropic.APIConnectionError as e:
        raise ExplainerError("Claude API에 연결할 수 없습니다. 네트워크를 확인하세요.") from e
    except anthropic.AnthropicError as e:
        raise ExplainerError(f"AI 해설을 사용할 수 없습니다: {e}") from e

    if final.stop_reason == "refusal":
        raise ExplainerError("이 문제에 대한 AI 해설을 생성하지 못했습니다. 기본 해설을 참고하세요.")
