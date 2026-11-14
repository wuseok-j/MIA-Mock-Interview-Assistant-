"""AI 호출 모음 (담당: 김채희).

서버(harness.py)는 이 파일의 함수 2개만 부른다.
함수 이름·입력·반환 형식은 팀 합의 사항이므로, 바꿀 때는 장우석과 먼저 이야기한다.

judge_action 은 실제 API 를 호출한다. (.env 에 LLM_API_KEY 가 없으면 키워드 기반 가짜 AI 로 동작)
evaluate 는 아직 가짜 응답이다. (4주차에 상위 모델로 교체)

실제 호출로 바꿀 때 지킬 것
- 진행(judge_action): 경량 모델 LLM_MODEL_FAST / 리포트(evaluate): 상위 모델 LLM_MODEL_SMART
- 프롬프트 문장은 prompts.py 에 따로 둔다.
- 시스템 프롬프트에 role_doc·캐릭터·현재 단계(correct_action 포함)를 넣고, 이 부분은 프롬프트 캐싱 대상.
- 이용자 입력은 <user_input> ... </user_input> 로 감싸 "판정할 데이터"로만 취급하라고 지시한다.
- 출력은 JSON 하나만. 파싱 실패 → 1회 재요청 → 그래도 실패하면 아래 fallback 반환.
- 매 호출의 res.usage (입력·출력 토큰)를 기록할 수 있게 남겨 둔다. (기록 위치는 장우석과 상의)
- 판정이 틀려도 서버가 형식·키워드로 한 번 더 검사하니, 여기서는 '자연스러운 대사'와 '정직한 판정'에 집중.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from . import prompts

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
log = logging.getLogger("mia.ai")
logging.basicConfig(level=logging.INFO, format="%(message)s")

MODEL_FAST = os.getenv("LLM_MODEL_FAST", "claude-haiku-5-5")
FALLBACK_JUDGE = {"verdict": "unclear", "reply": "", "reason": "fallback"}

_client: anthropic.Anthropic | None = None


def _api_key() -> str | None:
    key = os.getenv("LLM_API_KEY", "").strip()
    return key if key and not key.startswith("여기에") else None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # max_retries=1: 네트워크 오류·429·5xx 는 SDK 가 1회 자동 재시도한다. (팀 규칙: API 오류 1회 재시도)
        _client = anthropic.Anthropic(api_key=_api_key(), max_retries=1, timeout=30.0)
    return _client


def judge_action(scenario: dict, stage: dict, character: dict,
                 user_text: str, history: list[dict]) -> dict:
    """(아래 _mock_judge_action 과 같은 계약) 이용자 행동 판정 + 캐릭터 대사.

    API 키가 없으면 키워드 기반 가짜 AI 로 동작한다. (키 없는 팀원도 play_test 가 돌도록)
    """
    if not _api_key():
        return _mock_judge_action(scenario, stage, character, user_text, history)

    system = prompts.judge_system(scenario, stage, character)
    user = prompts.judge_user(history, user_text)

    # JSON 형식 오류·빈 응답이면 1회 재요청, 두 번 다 실패하면 fallback.
    for attempt in (1, 2):
        try:
            start = time.time()
            res = _get_client().messages.create(
                model=MODEL_FAST,
                max_tokens=2000,
                system=system,
                messages=[{"role": "user", "content": user}],
                # 대화형·빠른 응답이 중요하므로 생각(thinking) 깊이를 낮게.
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": prompts.JUDGE_SCHEMA},
                },
            )
            elapsed = time.time() - start
        except anthropic.APIError as e:
            # SDK 재시도까지 실패한 API 오류 (키 오류·잘못된 모델 이름 포함). 같은 요청을 또 보내도 소용없다.
            log.warning("[ai] judge_action API 오류: %s", e)
            return dict(FALLBACK_JUDGE)

        # 토큰 사용량 기록 (어디에 저장할지는 장우석·조민선과 상의 → 지금은 서버 로그에만)
        u = res.usage
        log.info("[ai] judge_action model=%s %.2fs in=%s out=%s stop=%s",
                 MODEL_FAST, elapsed, u.input_tokens, u.output_tokens, res.stop_reason)

        if res.stop_reason == "refusal":
            log.warning("[ai] 모델이 응답을 거절함 → fallback")
            return dict(FALLBACK_JUDGE)

        try:
            text = next(b.text for b in res.content if b.type == "text")
            data = json.loads(text)
            if data.get("verdict") in ("correct", "wrong", "unclear") and isinstance(data.get("reply"), str):
                return {"verdict": data["verdict"], "reply": data["reply"].strip(),
                        "reason": str(data.get("reason", ""))}
        except (StopIteration, json.JSONDecodeError):
            pass
        log.warning("[ai] 응답 형식 오류 (시도 %d/2)", attempt)

    return dict(FALLBACK_JUDGE)


def _mock_judge_action(scenario: dict, stage: dict, character: dict,
                       user_text: str, history: list[dict]) -> dict:
    """이용자의 행동(말)을 보고 판정을 '제안'하고, 캐릭터의 다음 대사를 만든다.

    scenario:  시나리오 전체 (role_doc 등)
    stage:     현재 단계 (situation, correct_action, keywords ...)
    character: 지금 말하는 캐릭터 (name, personality, speech_style)
    user_text: 이용자의 이번 입력
    history:   이번 단계에서 오간 대화 [{"role": "narrator"|"character"|"user"|"system", "name", "text"}]

    반환: {"verdict": "correct" | "wrong" | "unclear",
           "reply":   캐릭터 대사 (1~2문장, 캐릭터 말투),
           "reason":  판정 이유 한 줄 (로그·디버깅용, 화면에 안 나감)}
      - correct: correct_action 의 핵심을 실행하거나 제안함
      - wrong:   위험한 행동을 하거나 따라가려 함
      - unclear: 그 외 (질문, 애매함, 상황과 무관한 말)
    실패 시 {"verdict": "unclear", "reply": "", "reason": "fallback"}
      → reply 가 비어 있으면 서버가 stage["reactions"] 문장을 대신 쓴다.
    """
    # API 키가 없을 때 쓰는 키워드 기반 가짜 판정.
    text = "".join(user_text.split())
    if any("".join(k.split()) in text for k in stage["keywords"]):
        verdict = "correct"
    elif any("".join(k.split()) in text for k in stage.get("wrong_keywords", [])):
        verdict = "wrong"
    else:
        verdict = "unclear"
    return {"verdict": verdict, "reply": stage["reactions"][verdict], "reason": "mock: keyword match"}


def evaluate(scenario: dict, results: dict[int, str], transcript: list[dict]) -> dict:
    """플레이가 끝난 뒤 리포트용 코멘트와 총평을 쓴다.

    results:    {단계번호: "correct" | "failed" | "not_reached"}  ← 통과 여부는 서버가 이미 정했다.
    transcript: 전체 대화 [{"stage", "role", "name", "text"}]

    반환: {"summary": "총평 2~3문장",
           "comments": {"c1": "이 항목에 대한 피드백 1~2문장", ...}}   # scenario["evaluation"] 의 id 기준
    통과/실패를 바꾸는 권한은 없다. 이용자의 실제 발언을 근거로 칭찬·보완점을 쓴다.
    실패 시 {"summary": "", "comments": {}} (서버가 빈 칸으로 표시)
    """
    # TODO(김채희): 실제 API 호출로 교체. 아래는 가짜 응답.
    comments = {}
    for ev in scenario["evaluation"]:
        r = results.get(ev["stage"])
        if r == "correct":
            comments[ev["id"]] = "(가짜 데이터) 올바르게 판단했어요. 실제 상황에서도 이렇게 행동하면 됩니다."
        elif r == "failed":
            comments[ev["id"]] = "(가짜 데이터) 이 단계에서 판단이 늦거나 위험한 선택을 했어요. 아래 올바른 행동을 확인해 보세요."
        else:
            comments[ev["id"]] = "(가짜 데이터) 이 단계까지 도달하지 못했어요."
    passed = sum(r == "correct" for r in results.values())
    return {
        "summary": f"(가짜 데이터) {len(results)}단계 중 {passed}단계에서 올바르게 판단했습니다.",
        "comments": comments,
    }
