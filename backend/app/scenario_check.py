"""시나리오 JSON 검사 — CMS가 저장·공개하기 전에 부른다.

하네스는 시나리오 JSON을 그대로 믿고 돌기 때문에, 칸이 빠지거나 연결이 틀리면 플레이 도중 서버가 멈춘다.
그래서 저장 전에 여기서 막는다.
  errors   : 있으면 저장 불가 (하네스가 깨지는 문제)
  warnings : 저장은 되지만 공개 전에 확인할 것 (출처 없음, 키워드 적음 등)
공개(published)는 errors 가 0개일 때만 가능하다.
"""
from __future__ import annotations

import re

ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,39}$")      # 파일 이름으로도 쓰이므로 엄격하게 (경로 조작 방지)
CHAR_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,29}$")
STATUSES = ("draft", "published")
MAX_TEXT = 2000


def _text(errors: list[str], where: str, value, required: bool = True) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            errors.append(f"{where}: 비어 있습니다.")
        return
    if not isinstance(value, str):
        errors.append(f"{where}: 글자여야 합니다.")
    elif len(value) > MAX_TEXT:
        errors.append(f"{where}: {MAX_TEXT}자 이하로 써 주세요.")


def _str_list(errors: list[str], where: str, value, required: bool = False) -> list[str]:
    if value is None:
        if required:
            errors.append(f"{where}: 하나 이상 필요합니다.")
        return []
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        errors.append(f"{where}: 글자 목록이어야 합니다.")
        return []
    if required and not [x for x in value if x.strip()]:
        errors.append(f"{where}: 하나 이상 필요합니다.")
    return value


def _regex(errors: list[str], where: str, pattern: str) -> None:
    try:
        re.compile(pattern)
    except re.error as e:
        errors.append(f"{where}: 표현 패턴 문법 오류 ({e.msg}) — '{pattern}'")
    if " " in pattern:
        errors.append(f"{where}: 패턴에 띄어쓰기를 넣지 마세요. 판정할 때 이용자 말의 띄어쓰기를 지우고 비교합니다 — '{pattern}'")


def check(sc: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(sc, dict):
        return {"errors": ["시나리오 형식이 올바르지 않습니다."], "warnings": []}

    if not isinstance(sc.get("id"), str) or not ID_RE.match(sc["id"]):
        errors.append("id: 영문 소문자로 시작하고 소문자·숫자·밑줄만 3~40자 (예: earthquake_school)")
    if sc.get("status", "published") not in STATUSES:
        errors.append("status: draft 또는 published 여야 합니다.")
    for key in ("title", "summary", "category"):
        _text(errors, key, sc.get(key))
    if not isinstance(sc.get("max_risk"), int) or not 1 <= sc["max_risk"] <= 20:
        errors.append("max_risk: 1~20 사이 정수여야 합니다.")

    role = sc.get("role_doc")
    if not isinstance(role, dict):
        errors.append("role_doc: 배경 정보가 없습니다.")
        role = {}
    _text(errors, "배경 > 장소", role.get("place"))
    _text(errors, "배경 > 상황", role.get("situation"))
    _str_list(errors, "배경 > 캐릭터 규칙", role.get("rules"), required=True)
    if not _str_list(errors, "배경 > 상황 정보", role.get("world_facts")):
        warnings.append("배경 > 상황 정보(world_facts)가 없으면 이용자 질문에 AI가 지어내서 답할 수 있습니다.")

    briefing = sc.get("briefing") or {}
    if not isinstance(briefing, dict) or not briefing.get("mission"):
        warnings.append("브리핑 > 임무가 비어 있습니다. 시작 화면에 표시됩니다.")

    chars = sc.get("characters")
    char_ids: set[str] = set()
    if not isinstance(chars, list) or not chars:
        errors.append("캐릭터: 한 명 이상 필요합니다.")
        chars = []
    for i, c in enumerate(chars, start=1):
        where = f"캐릭터 {i}"
        if not isinstance(c, dict):
            errors.append(f"{where}: 형식 오류")
            continue
        if not isinstance(c.get("id"), str) or not CHAR_ID_RE.match(c["id"]):
            errors.append(f"{where} > id: 영문 소문자·숫자·밑줄 (예: jihoon)")
        elif c["id"] in char_ids:
            errors.append(f"{where} > id: '{c['id']}' 가 중복됩니다.")
        else:
            char_ids.add(c["id"])
        for key, label in (("name", "이름"), ("role", "역할"), ("personality", "성격"), ("speech_style", "말투")):
            _text(errors, f"{where} > {label}", c.get(key))

    stages = sc.get("stages")
    if not isinstance(stages, list) or not stages:
        errors.append("단계: 하나 이상 필요합니다.")
        stages = []
    numbers = [st.get("stage") for st in stages if isinstance(st, dict)]
    if numbers != list(range(1, len(stages) + 1)):
        errors.append("단계 번호는 1부터 차례대로여야 합니다.")
    source_count = len(sc.get("sources") or [])

    for idx, st in enumerate(stages, start=1):
        where = f"{idx}단계"
        if not isinstance(st, dict):
            errors.append(f"{where}: 형식 오류")
            continue
        for key, label in (("title", "제목"), ("situation", "상황"), ("opening_line", "캐릭터 첫 대사"),
                           ("correct_action", "올바른 행동")):
            _text(errors, f"{where} > {label}", st.get(key))
        if st.get("character_id") not in char_ids:
            errors.append(f"{where} > 말하는 캐릭터: 캐릭터 목록에 없는 id 입니다 ('{st.get('character_id')}').")
        nxt = st.get("next_if_correct")
        expected = idx + 1 if idx < len(stages) else None
        if nxt != expected:
            errors.append(f"{where} > 다음 단계: {expected if expected else '없음(마지막 단계)'} 이어야 합니다.")
        wrong = st.get("if_wrong")
        if not isinstance(wrong, dict):
            errors.append(f"{where} > 틀렸을 때: 정보가 없습니다.")
        else:
            _text(errors, f"{where} > 틀렸을 때 전개", wrong.get("narration"))
            if not isinstance(wrong.get("risk_delta"), int) or not 0 <= wrong["risk_delta"] <= 10:
                errors.append(f"{where} > 틀렸을 때 위험도: 0~10 정수")
        reactions = st.get("reactions")
        if not isinstance(reactions, dict):
            errors.append(f"{where} > 예비 대사: 정보가 없습니다.")
        else:
            for key, label in (("correct", "맞았을 때"), ("wrong", "틀렸을 때"), ("unclear", "애매할 때")):
                _text(errors, f"{where} > 예비 대사({label})", reactions.get(key))
        _str_list(errors, f"{where} > 행동 키워드", st.get("keywords"), required=True)
        _str_list(errors, f"{where} > 위험 키워드", st.get("wrong_keywords"))
        _str_list(errors, f"{where} > 상황 정보", st.get("facts"))
        for j, p in enumerate(st.get("danger_patterns") or [], start=1):
            if isinstance(p, str):
                _regex(errors, f"{where} > 위험 행동 패턴 {j}", p)
            else:
                errors.append(f"{where} > 위험 행동 패턴 {j}: 글자여야 합니다.")

        rubric = st.get("rubric") or []
        if not isinstance(rubric, list):
            errors.append(f"{where} > 행동 기준: 목록이어야 합니다.")
            rubric = []
        if not rubric:
            warnings.append(f"{where}: 행동 기준이 없으면 AI 판정만으로 통과합니다. 서버 검증을 위해 하나 이상 넣어 주세요.")
        rubric_ids: set[str] = set()
        for k, item in enumerate(rubric, start=1):
            w = f"{where} > 행동 기준 {k}"
            if not isinstance(item, dict):
                errors.append(f"{w}: 형식 오류")
                continue
            if not isinstance(item.get("id"), str) or not CHAR_ID_RE.match(item["id"]) or item["id"] in rubric_ids:
                errors.append(f"{w} > id: 영문 소문자로, 단계 안에서 겹치지 않게")
            else:
                rubric_ids.add(item["id"])
            _text(errors, f"{w} > 이름", item.get("label"))
            groups = item.get("patterns")
            if not isinstance(groups, list) or not groups or not all(isinstance(g, list) and g for g in groups):
                errors.append(f"{w} > 인정할 표현: 표현 묶음이 하나 이상 필요합니다.")
            else:
                for g in groups:
                    for p in g:
                        if isinstance(p, str):
                            _regex(errors, f"{w} > 인정할 표현", p)
                        else:
                            errors.append(f"{w}: 표현은 글자여야 합니다.")
            for p in item.get("exclude") or []:
                _regex(errors, f"{w} > 제외할 표현", p)
            for s_idx in item.get("source_indices") or []:
                if not isinstance(s_idx, int) or not 0 <= s_idx < source_count:
                    errors.append(f"{w} > 근거 출처 번호 {s_idx}: 출처 목록에 없습니다.")
        effect = st.get("consequence")
        if effect is not None:
            if not isinstance(effect, dict) or not all(effect.get(k) for k in ("key", "success", "missed", "success_label", "missed_label")):
                errors.append(f"{where} > 선택의 결과: 키·성공/놓침 문장·표시 이름이 모두 필요합니다.")

    evaluation = sc.get("evaluation") or []
    if not evaluation:
        errors.append("평가 기준: 하나 이상 필요합니다. (리포트에 쓰임)")
    eval_ids = set()
    for i, ev in enumerate(evaluation, start=1):
        if not isinstance(ev, dict) or not isinstance(ev.get("id"), str) or ev["id"] in eval_ids:
            errors.append(f"평가 기준 {i}: id 가 없거나 겹칩니다.")
            continue
        eval_ids.add(ev["id"])
        if ev.get("stage") not in numbers:
            errors.append(f"평가 기준 {i}: 없는 단계 번호({ev.get('stage')})입니다.")
        _text(errors, f"평가 기준 {i} > 내용", ev.get("criterion"))

    sources = sc.get("sources") or []
    if not sources:
        warnings.append("출처가 없습니다. 올바른 행동은 공공기관 행동요령을 근거로 써야 합니다.")
    for i, src in enumerate(sources, start=1):
        if not isinstance(src, dict) or not src.get("name"):
            errors.append(f"출처 {i}: 이름이 필요합니다.")
        elif not str(src.get("url", "")).startswith(("https://", "http://")):
            errors.append(f"출처 {i}: 주소는 http(s):// 로 시작해야 합니다.")

    return {"errors": errors, "warnings": warnings}
