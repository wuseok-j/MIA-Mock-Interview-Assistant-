"""시나리오에 정의한 관찰 가능한 행동만 근거로 인정한다.

정규식은 의미 이해를 대체하지 않는다. 미등록 표현은 미확인으로 남기고,
AI의 correct 제안만으로 근거를 만들어 내지 않는다.
"""
import re


NOT_ACTION_WORDS = ("라고하면", "라고말하면", "안할", "안하겠", "하지않", "하지말")


def compact(text: str) -> str:
    return re.sub(r"[\s,.!?。！？]", "", text.lower())


def action_text(text: str) -> str:
    """실행 의사로 볼 수 있는 문장만 남긴다.

    질문(물음표로 끝나는 문장)·가정·부정 문장은 그 문장만 뺀다.
    예) "불 난 거 아냐? 사람들한테 빨리 알리자" → "사람들한테빨리알리자"
    메시지 전체를 버리면 실제 사람들이 쓰는 "질문 + 행동" 문장이 인정되지 않는다.
    남은 문장은 합쳐서 검사하므로 "7층이에요. 탕비실이요." 처럼 나뉜 행동도 인정된다.
    """
    kept = []
    for sentence in re.split(r"(?<=[?？!！.。\n])", text):
        if sentence.strip().endswith(("?", "？")):
            continue
        value = compact(sentence)
        if value and not any(word in value for word in NOT_ACTION_WORDS):
            kept.append(value)
    return "".join(kept)


def observe(stage: dict, text: str) -> list[str]:
    value = action_text(text)
    if not value:
        return []
    found = []
    for criterion in stage.get("rubric", []):
        if any(re.search(p, value) for p in criterion.get("exclude", [])):
            continue
        if all(any(re.search(p, value) for p in group) for group in criterion["patterns"]):
            found.append(criterion["id"])
    return found


def dangerous(stage: dict, text: str) -> bool:
    value = compact(text)
    for pattern in stage.get("danger_patterns", []):
        for match in re.finditer(pattern, value):
            suffix = value[match.end():]
            if re.match(r'(들어가지마|들어가면안|가지마|말자)', suffix):
                continue
            return True
    return False
