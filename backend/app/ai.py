"""Gemini action adapter; deterministic report comments.

No key (or LLM_PROVIDER=mock) keeps offline playback available.
The harness owns progression, risk, evidence and results.
"""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv
from . import gemini

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _api_key():
    return gemini.api_key() if os.getenv("LLM_PROVIDER", "gemini").strip().lower() == "gemini" else None


def judge_action(scenario, stage, character, user_text, history):
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if provider not in ("gemini", "mock"):
        return dict(gemini.FALLBACK)
    if not _api_key():
        return _mock_judge_action(scenario, stage, character, user_text, history)
    return gemini.judge(scenario, stage, character, user_text, history)


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
            comments[ev["id"]] = "서버의 행동 기준이 충족되었습니다. 항목별 발언 근거를 확인해 보세요."
        elif r == "failed":
            comments[ev["id"]] = "시도 횟수 또는 위험도 한도에 도달했습니다. 행동 기준을 확인하고 다시 연습해 보세요."
        else:
            comments[ev["id"]] = "플레이가 먼저 종료되어 이 단계는 평가하지 않았습니다."
    passed = sum(r == "correct" for r in results.values())
    return {
        "summary": f"{len(results)}단계 중 {passed}단계가 규칙 기반 판정을 통과했습니다. 키워드 일치에 따른 연습 기록이며 실제 안전 역량을 인증하지 않습니다.",
        "comments": comments,
    }
