"""시나리오에 정의한 관찰 가능한 행동만 근거로 인정한다.

정규식은 의미 이해를 대체하지 않는다. 미등록 표현은 미확인으로 남기고,
AI의 correct 제안만으로 근거를 만들어 내지 않는다.
"""
import re


def compact(text: str) -> str:
    return re.sub(r"[\s,.!?。！？]", "", text.lower())


def observe(stage: dict, text: str) -> list[str]:
    value = compact(text)
    # 질문·가정·인용은 실행 의사로 확정하지 않는다.
    if "?" in text or any(word in value for word in ("라고하면", "라고말하면", "안할", "안하겠", "하지않", "하지말")):
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
