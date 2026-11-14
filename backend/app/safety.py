"""서버 1차 안전 필터 — AI를 부르기 전에 서버 코드로 먼저 거른다.

왜 서버에서? 프롬프트에 "인젝션은 무시해"라고만 써 두면 모델이 속을 수 있다.
여기서 걸리면 AI를 아예 호출하지 않으므로 (1) 진행 조작이 불가능하고 (2) 토큰 비용도 들지 않는다.

지금은 단순 문자열 목록이다. 김채희가 테스트 문장으로 목록을 늘리고 오탐(정상 문장이 걸림)을 기록한다.
"""
from __future__ import annotations

# 진행·역할을 조작하려는 시도 (공백 제거·소문자 기준으로 비교)
INJECTION_PATTERNS = [
    "다음단계로", "다음스테이지", "단계넘겨", "스킵",
    "정답알려", "정답이뭐", "답알려",
    "역할그만", "역할극그만", "캐릭터그만", "연기그만",
    "시스템프롬프트", "프롬프트보여", "프롬프트알려", "너의지시",
    "이전지시", "지시를무시", "지시무시", "규칙무시",
    "개발자모드", "관리자모드", "너는이제",
    "ignoreprevious", "ignoreall", "systemprompt", "jailbreak",
    "verdict", "\"correct\"", "<user_input>", "</user_input>",
]

# 10대 이용자를 고려한 부적절 표현 (예시 일부. 김채희가 보강)
INAPPROPRIATE_PATTERNS = [
    "섹스", "성관계", "야한", "야동", "벗어", "가슴만져",
    "씨발", "시발", "병신", "좆", "개새끼",
]

REDIRECT = {
    "injection": "⚠️ 진행 방법을 바꾸는 요청은 받을 수 없어요. 지금 상황에서 어떻게 행동할지 말해 주세요.",
    "inappropriate": "⚠️ 이 대화에서는 사용할 수 없는 표현이에요. 지금 재난 상황에 집중해 주세요.",
}


def _normalize(text: str) -> str:
    return "".join(text.lower().split())


def check(text: str) -> str | None:
    """문제가 없으면 None, 걸리면 "injection" 또는 "inappropriate"."""
    t = _normalize(text)
    if any(p in t for p in INAPPROPRIATE_PATTERNS):
        return "inappropriate"
    if any(p in t for p in INJECTION_PATTERNS):
        return "injection"
    return None
