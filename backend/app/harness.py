"""하네스: 시나리오 진행 상태는 모델이 아니라 서버가 쥔다.

모델(ai.py)이 하는 일은 딱 두 가지:
  ① 캐릭터가 할 말   ② 이용자 행동 판정 '제안' (correct / wrong / unclear)
서버(이 파일)가 하는 일:
  현재 단계, 위험도, 단계별 시도 횟수, 다음 단계 이동, 종료 여부 — 전부 시나리오 JSON 규칙으로 결정.
그래서 모델이 "다음 단계로 넘겨줘" 같은 말에 속아도 진행은 조작되지 않는다.

한 턴의 흐름 (handle_message):
  이용자 입력 → [safety 필터] → [ai.judge_action] → [서버 검증: 형식·키워드 가드]
  → [서버 규칙: 위험도/시도 횟수/단계 이동] → 화면에 보낼 메시지 목록
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import ai, safety, rules

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"

MAX_TURNS_PER_STAGE = 3   # 한 단계에서 판단할 기회. 다 쓰면 서버가 '실패'로 기록하고 다음 단계로 넘긴다.
# 질문·대화는 판단 기회를 쓰지 않는다 (롤플레잉 자유도). 대신 단계당 횟수에 상한을 둔다 (토큰 비용 보호).
# 상한을 넘으면 그 뒤의 말은 모두 판단 시도로 센다.
MAX_FREE_TURNS_PER_STAGE = 6
VERDICTS = {"correct", "wrong", "unclear"}
INTENTS = {"action", "question", "chat"}
MAX_REPLY_CHARS = 300     # 모델 대사가 너무 길면 자른다.

# 키워드 가드: 모델이 correct 라고 해도, 이용자 입력에 그 단계의 행동 키워드가 하나도 없으면 인정하지 않는다.
# → 모델이 속아서 correct 를 내도 진행이 조작되지 않는 2차 안전장치.
# 단점: 키워드에 없는 표현으로 맞게 말하면 인정이 안 될 수 있음 → 시나리오 keywords 를 넉넉히 적는다.
KEYWORD_GUARD = True


def load_scenarios() -> dict[str, dict]:
    scenarios = {}
    for path in sorted(SCENARIO_DIR.glob("*.json")):
        s = json.loads(path.read_text(encoding="utf-8"))
        scenarios[s["id"]] = s
    return scenarios


SCENARIOS: dict[str, dict] = load_scenarios()


@dataclass
class Session:
    id: str
    scenario: dict
    stage_index: int = 0
    risk: int = 0
    turns_in_stage: int = 0
    free_turns_in_stage: int = 0                # 이번 단계에서 판단 기회를 쓰지 않은 질문·대화 수
    status: str = "playing"                    # playing | cleared | failed
    stage_results: dict[int, str] = field(default_factory=dict)   # {단계번호: "correct" | "failed"}
    transcript: list[dict] = field(default_factory=list)          # {stage, role, name, text}
    blocked_count: int = 0                      # 안전 필터에 걸린 횟수 (리포트·로그용)
    actions: dict[int, list[str]] = field(default_factory=dict)
    evidence: dict[int, dict[str, str]] = field(default_factory=dict)
    conditions: dict[str, str] = field(default_factory=dict)
    timeline: list[dict] = field(default_factory=list)
    report: dict | None = None                  # 한 번 만든 리포트는 저장해서 재사용 (AI 재호출 방지)


# TODO(장우석): SQLite 로 교체 (세션 이어하기·만료)
SESSIONS: dict[str, Session] = {}


# ---------- 조회 도우미 ----------

def current_stage(s: Session) -> dict:
    base = s.scenario["stages"][s.stage_index]
    for variant in base.get("variants", []):
        when = variant["when"]
        if s.conditions.get(when["key"]) == when["value"]:
            return {**base, **{k: v for k, v in variant.items() if k != "when"}}
    return base


def character(s: Session, char_id: str) -> dict:
    return next(c for c in s.scenario["characters"] if c["id"] == char_id)


def public_scenario(sc: dict) -> dict:
    """이용자 화면에 보내도 되는 정보만. 정답(correct_action·keywords)은 절대 내보내지 않는다."""
    return {
        "id": sc["id"], "title": sc["title"], "summary": sc["summary"],
        "category": sc["category"], "thumbnail": sc.get("thumbnail"),
        "estimated_minutes": sc.get("estimated_minutes"),
        "total_stages": len(sc["stages"]),
        "briefing": sc.get("briefing", {}),
        "characters": [{"name": c["name"], "role": c["role"], "image": c.get("image")}
                       for c in sc["characters"]],
    }


# ---------- 진행 ----------

def create_session(scenario_id: str) -> tuple[Session, list[dict]]:
    sc = SCENARIOS[scenario_id]
    s = Session(id=uuid.uuid4().hex[:12], scenario=sc)
    SESSIONS[s.id] = s
    return s, _enter_stage(s)


def handle_message(s: Session, text: str) -> list[dict]:
    """이용자 한 마디를 처리하고, 화면에 보여줄 메시지 목록을 돌려준다."""
    if s.status != "playing":
        return []
    st = current_stage(s)
    ch = character(s, st["character_id"])
    out: list[dict] = []
    _say(s, out, "user", "나", text)

    # 1) 서버 안전 필터 — 걸리면 AI를 부르지 않는다. 단계·위험도·시도 횟수도 그대로.
    flag = safety.check(text)
    if flag:
        s.blocked_count += 1
        _say(s, out, "system", "안내", safety.REDIRECT[flag])
        return out

    s.actions.setdefault(st["stage"], []).append(text)

    # 2) AI 판정 제안
    history = [t for t in s.transcript if t["stage"] == st["stage"]
               and not (t["role"] == "user" and safety.check(t["text"]))]
    suggestion = ai.judge_action(s.scenario, _ai_context(s, st), ch, text, history)
    if (not isinstance(suggestion, dict) or suggestion.get("reason") == "fallback"
            or suggestion.get("verdict") not in VERDICTS or not isinstance(suggestion.get("reply"), str)):
        # API 장애를 이용자의 판단 실패로 계산하지 않는다.
        s.actions[st["stage"]].pop()
        _say(s, out, "system", "안내", "응답을 확인하지 못했습니다. 판단 기회와 위험도는 유지됩니다. 잠시 후 다시 말해 주세요.")
        return out

    # 3) 서버 검증 — 형식이 이상하면 안전한 기본값으로
    verdict = suggestion.get("verdict")
    if verdict not in VERDICTS:
        verdict = "unclear"
    if verdict == "correct" and KEYWORD_GUARD and not _has_keyword(text, st["keywords"]):
        verdict = "unclear"
    before_risk = s.risk
    observed = rules.observe(st, text)
    evidence = s.evidence.setdefault(st["stage"], {})
    if rules.dangerous(st, text):
        verdict = "wrong"
    if st.get("rubric"):
        if verdict == "wrong":
            evidence.clear()
        if verdict != "wrong":
            for item_id in observed:
                evidence[item_id] = text
        complete = all(item["id"] in evidence for item in st["rubric"])
        if verdict != "wrong":
            verdict = "correct" if complete else "unclear"
    reply = str(suggestion.get("reply") or "").strip()[:MAX_REPLY_CHARS] or st["reactions"][verdict]
    # AI가 통과를 제안했어도 서버 근거가 부족하면 성공 대사를 노출하지 않는다.
    if verdict != suggestion.get("verdict"):
        reply = st.get("partial_reply", st["reactions"][verdict]) if verdict == "unclear" else st["reactions"][verdict]
    _say(s, out, "character", ch["name"], reply)

    # 4) 판단 시도인지, 질문·대화인지 — 서버가 최종 결정
    #    AI의 intent 는 '기회를 덜 쓰게' 만들 수만 있다. 근거·위험 행동이 잡히면 AI 분류와 무관하게 시도로 센다.
    intent = suggestion.get("intent") if suggestion.get("intent") in INTENTS else "action"
    is_attempt = (verdict != "unclear" or bool(observed) or intent == "action"
                  or s.free_turns_in_stage >= MAX_FREE_TURNS_PER_STAGE)
    if not is_attempt:
        s.free_turns_in_stage += 1
        s.actions[st["stage"]].pop()   # 리포트의 '판단 기록'에는 넣지 않는다 (대화 기록에는 남음)
        return out

    # 5) 서버 규칙으로 진행 결정
    s.turns_in_stage += 1
    if verdict == "correct":
        s.stage_results[st["stage"]] = "correct"
        _record(s, st, text, verdict, before_risk, "단계 행동 확인")
        _consequence(s, st, True, out)
        out += _go_next(s, st["next_if_correct"])
        return out

    if verdict == "wrong":
        s.risk += st["if_wrong"]["risk_delta"]
        _say(s, out, "narrator", "상황", st["if_wrong"]["narration"])

    if s.risk >= s.scenario["max_risk"]:
        s.stage_results[st["stage"]] = "failed"
        s.status = "failed"
        _record(s, st, text, verdict, before_risk, "위험도 한도로 종료")
        _say(s, out, "system", "결과",
             "위험도가 한계를 넘었습니다. 구조대에 의해 구조되었지만 대피에는 실패했어요. 리포트에서 어떤 판단이 필요했는지 확인해 보세요.")
    elif s.turns_in_stage >= MAX_TURNS_PER_STAGE:
        s.stage_results[st["stage"]] = "failed"
        _record(s, st, text, verdict, before_risk, "판단 기회 소진 · 도움받아 이동")
        _consequence(s, st, False, out)
        out += _go_next(s, st["next_if_correct"])
    else:
        _record(s, st, text, verdict, before_risk, "위험 행동" if verdict == "wrong" else "행동 추가 확인 필요")
    return out


def _record(s: Session, st: dict, text: str, verdict: str, before: int, outcome: str) -> None:
    s.timeline.append({"stage": st["stage"], "title": st["title"], "action": text,
                       "verdict": verdict, "risk_before": before, "risk_after": s.risk,
                       "outcome": outcome})


def _consequence(s: Session, st: dict, success: bool, out: list[dict]) -> None:
    effect = st.get("consequence")
    if effect:
        s.conditions[effect["key"]] = "success" if success else "missed"
        _say(s, out, "narrator", "선택의 결과", effect["success" if success else "missed"])


def public_conditions(s: Session) -> list[str]:
    return [st["consequence"]["success_label" if s.conditions[st["consequence"]["key"]] == "success" else "missed_label"]
            for st in s.scenario["stages"] if st.get("consequence", {}).get("key") in s.conditions]


def _go_next(s: Session, next_stage: int | None) -> list[dict]:
    if next_stage is None:
        s.status = "cleared"
        out: list[dict] = []
        _say(s, out, "system", "결과", "건물 밖에서 플레이를 마쳤습니다. 대피 결과와 별개로, 리포트에서 확인된 행동과 도움받은 판단을 살펴보세요.")
        return out
    s.stage_index = next(i for i, x in enumerate(s.scenario["stages"]) if x["stage"] == next_stage)
    s.turns_in_stage = 0
    s.free_turns_in_stage = 0
    return _enter_stage(s)


def _ai_context(s: Session, st: dict) -> dict:
    """AI에게 넘길 현재 단계 정보. 진행 결정에는 쓰지 않고, 자연스러운 대사를 위한 재료만 준다.

    - world_facts: 질문에 일관되게 답하기 위한 상황 정보 (시나리오 공통 + 이 단계)
    - confirmed/missing_actions: 이번 단계에서 이미 확인된 행동과 아직 남은 행동
      → 일부만 맞았을 때 AI가 고정 문장 대신 자연스럽게 재촉한다. (정답을 직접 말하지는 않게 프롬프트로 제한)
    - story_so_far: 지난 단계에서 일어난 일 → 대화가 단계마다 끊기지 않게
    """
    done = s.evidence.get(st["stage"], {})
    rubric = st.get("rubric", [])
    story = []
    for prev in s.scenario["stages"][:s.stage_index]:
        result = s.stage_results.get(prev["stage"])
        story.append(f'{prev["stage"]}단계 「{prev["title"]}」: '
                     + ("이용자가 직접 해냄" if result == "correct" else "이용자가 놓쳐서 다른 사람의 도움을 받음"))
    return {
        **st,
        "world_state": dict(s.conditions),
        "world_facts": list(s.scenario.get("role_doc", {}).get("world_facts", [])) + list(st.get("facts", [])),
        "confirmed_actions": [item["label"] for item in rubric if item["id"] in done],
        "missing_actions": [item["label"] for item in rubric if item["id"] not in done],
        "story_so_far": story,
    }


def _enter_stage(s: Session) -> list[dict]:
    st = current_stage(s)
    ch = character(s, st["character_id"])
    out: list[dict] = []
    _say(s, out, "narrator", "상황", st["situation"])
    _say(s, out, "character", ch["name"], st["opening_line"])
    return out


def _has_keyword(text: str, keywords: list[str]) -> bool:
    t = "".join(text.split())
    return any("".join(k.split()) in t for k in keywords)


def _say(s: Session, out: list[dict], role: str, name: str, text: str) -> None:
    msg = {"role": role, "name": name, "text": text}
    out.append(msg)
    s.transcript.append({"stage": current_stage(s)["stage"], **msg})


# ---------- 리포트 ----------

def build_report(s: Session) -> dict:
    """통과/실패는 서버 기록(stage_results)으로 정한다. AI는 코멘트와 총평 문장만 쓴다."""
    if s.report:
        return s.report
    sc = s.scenario
    results = {st["stage"]: s.stage_results.get(st["stage"], "not_reached") for st in sc["stages"]}
    ai_text = ai.evaluate(sc, results, s.transcript)
    comments = ai_text.get("comments", {}) if isinstance(ai_text.get("comments"), dict) else {}

    checks = []
    for ev in sc["evaluation"]:
        st = next(x for x in sc["stages"] if x["stage"] == ev["stage"])
        checks.append({
            "id": ev["id"],
            "stage": ev["stage"],
            "stage_title": st["title"],
            "criterion": ev["criterion"],
            "result": results[ev["stage"]],          # correct | failed | not_reached
            "correct_action": st["correct_action"],  # 리포트에서는 정답 공개 (학습용)
            "comment": str(comments.get(ev["id"], ""))[:MAX_REPLY_CHARS],
            "user_actions": s.actions.get(ev["stage"], []),
            "attempts": len(s.actions.get(ev["stage"], [])),
            "evidence": [{"id": item["id"], "label": item["label"],
                          "met": item["id"] in s.evidence.get(st["stage"], {}),
                          "quote": s.evidence.get(st["stage"], {}).get(item["id"], ""),
                          "sources": [{"name": sc["sources"][i]["name"], "url": sc["sources"][i]["url"]}
                                      for i in item.get("source_indices", [])]}
                         for item in st.get("rubric", [])],
        })

    s.report = {
        "session_id": s.id,
        "scenario_title": sc["title"],
        "status": s.status,
        "risk": s.risk,
        "max_risk": sc["max_risk"],
        "passed": sum(c["result"] == "correct" for c in checks),
        "total": len(checks),
        "summary": "대피 결과와 행동 충족도는 별개입니다. 확인된 발언 근거를 바탕으로 놓친 행동을 복기하세요. 자동 판정은 표현을 놓칠 수 있으며 안전 역량 인증이 아닙니다.",
        "timeline": s.timeline,
        "conditions": public_conditions(s),
        "review_points": [c["stage_title"] for c in checks if c["result"] != "correct"],
        "checks": checks,
        "sources": [{"name": x["name"], "url": x["url"]} for x in sc.get("sources", [])],
    }
    return s.report
