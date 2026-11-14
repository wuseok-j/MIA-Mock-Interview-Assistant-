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

from . import ai, safety

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"

MAX_TURNS_PER_STAGE = 3   # 한 단계에서 판단할 기회. 다 쓰면 서버가 '실패'로 기록하고 다음 단계로 넘긴다.
VERDICTS = {"correct", "wrong", "unclear"}
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
    status: str = "playing"                     # playing | cleared | failed
    stage_results: dict[int, str] = field(default_factory=dict)   # {단계번호: "correct" | "failed"}
    transcript: list[dict] = field(default_factory=list)          # {stage, role, name, text}
    blocked_count: int = 0                      # 안전 필터에 걸린 횟수 (리포트·로그용)
    report: dict | None = None                  # 한 번 만든 리포트는 저장해서 재사용 (AI 재호출 방지)


# TODO(장우석): SQLite 로 교체 (세션 이어하기·만료)
SESSIONS: dict[str, Session] = {}


# ---------- 조회 도우미 ----------

def current_stage(s: Session) -> dict:
    return s.scenario["stages"][s.stage_index]


def character(s: Session, char_id: str) -> dict:
    return next(c for c in s.scenario["characters"] if c["id"] == char_id)


def public_scenario(sc: dict) -> dict:
    """이용자 화면에 보내도 되는 정보만. 정답(correct_action·keywords)은 절대 내보내지 않는다."""
    return {
        "id": sc["id"], "title": sc["title"], "summary": sc["summary"],
        "category": sc["category"], "thumbnail": sc.get("thumbnail"),
        "estimated_minutes": sc.get("estimated_minutes"),
        "total_stages": len(sc["stages"]),
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

    # 2) AI 판정 제안
    history = [t for t in s.transcript if t["stage"] == st["stage"]]
    suggestion = ai.judge_action(s.scenario, st, ch, text, history)

    # 3) 서버 검증 — 형식이 이상하면 안전한 기본값으로
    verdict = suggestion.get("verdict")
    if verdict not in VERDICTS:
        verdict = "unclear"
    if verdict == "correct" and KEYWORD_GUARD and not _has_keyword(text, st["keywords"]):
        verdict = "unclear"
    reply = str(suggestion.get("reply") or "").strip()[:MAX_REPLY_CHARS] or st["reactions"][verdict]
    _say(s, out, "character", ch["name"], reply)

    # 4) 서버 규칙으로 진행 결정
    s.turns_in_stage += 1
    if verdict == "correct":
        s.stage_results[st["stage"]] = "correct"
        out += _go_next(s, st["next_if_correct"])
        return out

    if verdict == "wrong":
        s.risk += st["if_wrong"]["risk_delta"]
        _say(s, out, "narrator", "상황", st["if_wrong"]["narration"])

    if s.risk >= s.scenario["max_risk"]:
        s.stage_results[st["stage"]] = "failed"
        s.status = "failed"
        _say(s, out, "system", "결과",
             "위험도가 한계를 넘었습니다. 구조대에 의해 구조되었지만 대피에는 실패했어요. 리포트에서 어떤 판단이 필요했는지 확인해 보세요.")
    elif s.turns_in_stage >= MAX_TURNS_PER_STAGE:
        s.stage_results[st["stage"]] = "failed"
        _say(s, out, "narrator", "상황", "판단이 늦어지는 사이 상황이 다음으로 흘러갑니다.")
        out += _go_next(s, st["next_if_correct"])
    return out


def _go_next(s: Session, next_stage: int | None) -> list[dict]:
    if next_stage is None:
        s.status = "cleared"
        out: list[dict] = []
        _say(s, out, "system", "결과", "무사히 대피를 마쳤습니다! 리포트에서 단계별 판단을 확인해 보세요.")
        return out
    s.stage_index = next(i for i, x in enumerate(s.scenario["stages"]) if x["stage"] == next_stage)
    s.turns_in_stage = 0
    return _enter_stage(s)


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
        })

    s.report = {
        "session_id": s.id,
        "scenario_title": sc["title"],
        "status": s.status,
        "risk": s.risk,
        "max_risk": sc["max_risk"],
        "passed": sum(c["result"] == "correct" for c in checks),
        "total": len(checks),
        "summary": str(ai_text.get("summary", ""))[:600],
        "checks": checks,
        "sources": [{"name": x["name"], "url": x["url"]} for x in sc.get("sources", [])],
    }
    return s.report
